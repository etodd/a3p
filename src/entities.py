from direct.showbase.DirectObject import DirectObject
from pandac.PandaModules import *
from random import random, uniform
import math
import engine
import components
import controllers
import audio
import net
import net2
import particles

class EntityGroup(DirectObject):
	"""An entity group handles all the logistics of Entities and Impostors.
	The entity group actually steps the ODE world and space in the AI world, and it updates all the controllers as well."""
	def __init__(self, netManager):
		self.entities = dict()
		self.graphicsObjects = []
		self.deletedEntities = []
		self.cameraShakeX = 0
		self.cameraShakeY = 0
		self.cameraShakeVelX = 0
		self.cameraShakeVelY = 0
		self.lastCameraShake = 0
		self.cameraShakeTime = 0.9
		self.manager = netManager
		self.teams = []

	def update(self):
		"Updates all graphics objects, clears deleted entities, shakes the camera."
		time = engine.clock.time - self.lastCameraShake
		decay = max(1 - (time / self.cameraShakeTime), 0)
		self.cameraShakeX = self.cameraShakeVelX * decay * math.sin(time * 7)
		self.cameraShakeY = self.cameraShakeVelY * decay * math.sin(time * 12)
		
		for obj in self.graphicsObjects:
			obj.update(self)

		self.clearDeletedEntities()

	def getEntity(self, id):
		"Gets the ObjectEntity associated with the given NodePath (which has a unique 8-bit identifier). Returns None if no ObjectEntity has the given NodePath."
		try:
			i = int(id)
		except ValueError:
			return None
		if i in self.entities:
			return self.entities[i]
		else:
			return None

	def getEntityFromEntry(self, entry):
		"Gets the ObjectEntity specified by the given collision entry, if one exists."
		if entry != None:
			entity = self.getEntity(entry.getIntoNodePath().getParent().getName())
			if entity == None:
				return self.getEntity(entry.getIntoNodePath().getName())
			else:
				return entity
		else:
			return None
	
	def spawnEntity(self, entity):
		"Spawning an ObjectEntity involves sending off a network packet so everyone else has the ObjectEntity too."
		self.generateEntityId(entity)
		self.manager.spawnEntity(entity)
		self.addEntity(entity)
	
	def addTeam(self, team):
		self.teams.append(team)

	def addEntity(self, entity):
		"Sets the ObjectEntity active and adds it to the list."
		entity.active = True
		if isinstance(entity, ObjectEntity):
			entity.node.reparentTo(engine.renderObjects)
		self.entities[entity.getId()] = entity
	
	def removeEntity(self, entity):
		"Removes the ObjectEntity from the entity list. Also schedules the ObjectEntity's resources to be cleared, as soon as possible."
		entity.active = False
		if entity.getId() in self.entities:
			self.deletedEntities.append(entity)
	
	# offset is used to ensure Fragments and other local-only entities don't interfere
	# with IDs from server-client synched entities.
	def generateEntityId(self, entity, offset = 0):
		id = offset + int(round(random() * 255))
		while id in self.entities:
			id = offset + int(round(random() * 255))
		entity.setId(id)
	
	def clearDeletedEntities(self):
		for entity in self.deletedEntities:
			if entity.getId() in self.entities:
				del self.entities[entity.getId()]
			entity.clear(self)
		del self.deletedEntities[:]
	
	def addGraphicsObject(self, obj):
		if not obj in self.graphicsObjects:
			self.graphicsObjects.append(obj)
	
	def removeGraphicsObject(self, obj):
		obj.delete(self)
		if obj in self.graphicsObjects:
			self.graphicsObjects.remove(obj)
	
	def getNearestPhysicsEntity(self, pos):
		closest = None
		closestDist = 1000000
		for entity in (x for x in self.entities.values() if isinstance(x, PhysicsEntity)):
			dist = (entity.getPosition() - pos).length()
			if dist < closestDist:
				closest = entity
				closestDist = dist
		return closest

	def resetMatch(self):
		for entity in (x for x in self.entities.values() if isinstance(x, Actor) or isinstance(x, Fragment)):
			entity.delete(self, killed = False, localDelete = False)
		self.clearDeletedEntities()
		for entity in self.entities.values():
			entity.controller.clearCriticalPackets()
		for object in self.graphicsObjects:
			object.delete(self)
		
	def deleteEntity(self, entity, killed = False):
		"Deleting an ObjectEntity involves sending off a network packet so everyone else also deletes the ObjectEntity."
		self.manager.deleteEntity(entity, killed)
		self.removeEntity(entity)
	
	def shakeCamera(self, amount = 6):
		if random() > 0.5:
			self.cameraShakeVelX = amount
		else:
			self.cameraShakeVelX = -amount
		if random() > 0.5:
			self.cameraShakeVelY = amount
		else:
			self.cameraShakeVelY = -amount
		self.lastCameraShake = engine.clock.time

	# The damagingEntity gets credit for any kills resulting from the explosion.
	# However instead of being invulnerable to the explosion, it receives 50% of the damage a normal entity would receive.
	def explode(self, position, force, damage, damageRadius, sourceEntity = None, damagingEntity = None):
		"""Triggers an explosion animation, which involves applying force to surrounding Entities, and damaging Entities where applicable.
		sourceEntity is excluded from damage and force, and damagingEntity gets the credit for any damage done.
		If damagingEntity is None, sourceEntity gets the credit. If both are None, no damage is done.
		"""
		
		particles.add(particles.SparkParticleGroup(position, numParticles = 500, speed = damageRadius * 2.5, lifeTime = 1.0, size = 6.0))
		particles.add(particles.ExplosionParticleGroup(position))
		
		for entity in (entity for entity in self.entities.values() if entity != sourceEntity and isinstance(entity, ObjectEntity)):
			vector = entity.getPosition() - position
			distance = vector.length()
			if distance >= damageRadius or distance == 0:
				continue
			force2 = force * max(1 - (distance / damageRadius), 0) * entity.radius * 0.5
			damage2 = damage * max(1 - (distance / damageRadius), 0)
			pos = entity.getPosition()
			vector = pos - position
			distance = vector.length()
			vector.normalize()

			if entity.active:
				vector = engine.impulseToForce(vector.getX() * force2, vector.getY() * force2, vector.getZ() * force2)
				pos = entity.getPosition()
				radius = entity.radius * 0.4
				pos += Vec3(uniform(-radius, radius), uniform(-radius, radius), uniform(-radius, radius))
				entity.addForceAtPosition(vector, pos)
				if damage2 > 0:
					if damagingEntity != None:
						entity.damage(damagingEntity, damage2, False) # Grenades don't count as ranged damage.
					elif sourceEntity != None:
						entity.damage(sourceEntity, damage2, False)

	def delete(self):
		"Deletes all entities and particles in this group. IMPORTANT: you must delete the entity group BEFORE deleting the AI world."
		for obj in self.graphicsObjects:
			obj.delete(self)
		del self.graphicsObjects[:]
		for entity in self.entities.values():
			entity.delete(self)
		self.clearDeletedEntities()

class Entity(DirectObject):
	"""Entity is a generic data object that has a controller."""
	def __init__(self, controller, local = net.netMode == net.MODE_SERVER):
		self.active = True
		self.id = -1
		self.isLocal = local
		self.controller = controller
		self.controller.setEntity(self)
		self.killed = False
		self.spawnTime = engine.clock.time

	def getId(self):
		return self.id

	def setId(self, id):
		self.id = id
	
	def damage(self, entity, damage, ranged = True):
		"Useful for Entities that have health."
		pass

	def kill(self, aiWorld, entityGroup, localDelete = True):
		"Killing an ObjectEntity triggers a death animation. Deleting an entity just silently removes it."
		if self.active:
			self.delete(entityGroup, True, localDelete)
	
	def delete(self, entityGroup, killed = False, localDelete = True):
		"""Schedules this ObjectEntity to be cleared and removed from the given EntityGroup."""
		if self.active:
			self.active = False
			self.killed = killed
			if localDelete:
				entityGroup.deleteEntity(self, killed)
			else:
				entityGroup.removeEntity(self)
	
	def clear(self, entityGroup):
		"""Clears all resources associated with this Entity."""
		self.controller.delete(self.killed)
		self.active = False
	
	def setLocal(self, local):
		self.isLocal = local

class ObjectEntity(Entity):
	"""An ObjectEntity is an object with an ODE body and geometry, and a single NodePath for visual representation.
	Anything that has mass and moves is an ObjectEntity, including physics objects, game characters, and shards of debris.
	ObjectEntities can't do much by themselves. They're manipulated by Controllers."""
	def __init__(self, filename, controller, local = net.netMode == net.MODE_SERVER):
		Entity.__init__(self, controller, local)
		self.node = None
		self.filename = ""
		self.radius = 0
		if filename != None:
			self.loadModel(filename)
	
	def loadModel(self, filename):
		self.filename = filename
		self.node = engine.loadModel(filename)
		self.node.setName(str(int(self.id)))
		self.radius = self.node.getBounds().getRadius()
	
	def setId(self, id):
		Entity.setId(self, id)
		if self.node != None:
			self.node.setName(str(int(id)))
	
	def getPosition(self):
		return self.body.getPosition()
	
	def setPosition(self, pos):
		self.node.setPos(pos)
		self.body.setPosition(pos)
	
	def setRotation(self, hpr):
		self.node.setHpr(hpr)
		self.body.setQuaternion(self.node.getQuat(render))
	
	def getRotation(self):
		return self.node.getHpr()
	
	def setLinearVelocity(self, vel):
		self.body.setLinearVel(vel)
	
	def getLinearVelocity(self):
		return self.body.getLinearVel()
	
	def setAngularVelocity(self, vel):
		self.body.setAngularVel(vel)
	
	def getAngularVelocity(self):
		return self.body.getAngularVel()
	
	def setQuaternion(self, quat):
		self.body.setQuaternion(quat)
		self.node.setQuat(quat)
	
	def getQuaternion(self):
		return self.body.getQuaternion()
	
	def addTorque(self, torque):
		self.body.addTorque(torque.getX(), torque.getY(), torque.getZ())
	
	def addForce(self, force):
		self.body.addForce(force)
	
	def addForceAtPosition(self, direction, position):
		self.body.addForceAtPos(direction.getX(), direction.getY(), direction.getZ(), position.getX(), position.getY(), position.getZ())

	def commitChanges(self):
		"Updates the visual orientation and position of this ObjectEntity to reflect that of the ODE body."
		self.node.setPosQuat(engine.renderObjects, self.getPosition(), Quat(self.body.getQuaternion()))
	
	def damage(self, entity, damage, ranged = True):
		"Useful for Entities that have health."
		Entity.damage(self, entity, damage, ranged)
	
	def kill(self, aiWorld, entityGroup, localDelete = True):
		Entity.kill(self, aiWorld, entityGroup, localDelete)
	
	def delete(self, entityGroup, killed = False, localDelete = True):
		Entity.delete(self, entityGroup, killed, localDelete)
	
	def clear(self, entityGroup):
		"""Clears all resources associated with this ObjectEntity."""
		Entity.clear(self, entityGroup)
		self.geometry.destroy()
		self.body.destroy()
		engine.deleteModel(self.node, self.filename)

class DropPod(Entity):
	def __init__(self, space, controller, local = net.netMode == net.MODE_SERVER):
		Entity.__init__(self, controller, local)
		self.node = loader.loadModel("models/pod/pod")
		self.node.reparentTo(engine.renderLit)
		self.collisionNode = CollisionNode("cnode")
		self.collisionNodePath = self.node.attachNewNode(self.collisionNode)
		sizex = 3
		sizey = 3
		sizez = 7
		point1 = Point3(-sizex / 2.0, -sizey / 2.0, -sizez / 2.0)
		point2 = Point3(sizex / 2.0, sizey / 2.0, sizez / 2.0)
		self.radius = max(sizez, max(sizex, sizey)) / 2.0
		self.vradius = sizez / 2.0
		self.collisionNode.addSolid(CollisionBox(point1, point2))
		self.geometry = OdeBoxGeom(space, sizex, sizey, sizez)
		self.geometry.setCollideBits(BitMask32(0x00000001))
		self.geometry.setCategoryBits(BitMask32(0x00000001))
		space.setSurfaceType(self.geometry, 1)
		visitorFont = loader.loadFont("menu/visitor2.ttf")
		self.amountIndicator = TextNode("dropPodAmountIndicator")
		self.amountIndicator.setText("")
		self.amountIndicator.setFont(visitorFont)
		self.amountIndicator.setTextColor(1, 1, 1, 1)
		self.amountIndicator.setAlign(TextNode.ACenter)
		self.amountIndicator.setCardColor(0, 0, 0, 0.7)
		self.amountIndicator.setCardAsMargin(0.02, 0.02, 0.02, 0.02)
		self.amountIndicator.setCardDecal(True)
		self.amountIndicatorNode = self.node.attachNewNode(self.amountIndicator)
		self.amountIndicatorNode.setShaderOff()
		self.amountIndicatorNode.setLightOff(True)
		self.amountIndicatorNode.setTwoSided(True)
		self.amountIndicatorNode.setDepthTest(False)
		self.amountIndicatorNode.setDepthWrite(False)
		self.amountIndicatorNode.setBin("fixed", 102) # 102 so it's in front of all the MeshDrawer particles.
		self.amountIndicatorNode.hide(BitMask32.bit(4)) # Don't cast shadows
		self.amountIndicatorNode.setBillboardPointEye()
	
	def getPosition(self):
		return self.node.getPos()
	
	def setPosition(self, pos):
		self.node.setPos(pos)
		self.geometry.setPosition(pos)
	
	def setRotation(self, hpr):
		self.node.setHpr(hpr)
		self.geometry.setQuat(self.node.getQuat(render))
	
	def getRotation(self):
		return self.node.getHpr()
		
	def delete(self, entityGroup, killed = False, localDelete = True):
		Entity.delete(self, entityGroup, killed, localDelete)
	
	def kill(self, aiWorld, entityGroup, localDelete = True):
		if self.active:
			position = self.getPosition()
			entityGroup.explode(position, force = 4000, damage = 67, damageRadius = 20, sourceEntity = self, damagingEntity = None) # Give damage credit to our parent actor
			explosionSound = audio.SoundPlayer("large-explosion")
			explosionSound.play(position = position)
		Entity.kill(self, aiWorld, entityGroup, localDelete)
	
	def clear(self, entityGroup):
		Entity.clear(self, entityGroup)
		self.node.removeNode()
		self.geometry.destroy()

class Fragment(ObjectEntity):
	def __init__(self, world, space, pos, velocity):
		ObjectEntity.__init__(self, "models/fragment/Fragment", controllers.FragmentController(velocity), True)
		self.radius = 0.7
		size = self.radius * 2
		self.body = OdeBody(world)
		M = OdeMass()
		M.setBox(3, size, size, 0.4)
		self.body.setMass(M)
		self.geometry = OdeBoxGeom(space, size, size, 0.4)
		self.geometry.setCollideBits(BitMask32(0x00000001))
		self.geometry.setCategoryBits(BitMask32(0x00000001))
		self.geometry.setBody(self.body)
		self.setPosition(pos)
		self.node.setHpr(uniform(0, 360), uniform(0, 360), uniform(0, 360))
		self.body.setQuaternion(self.node.getQuat())
		vel = 5
		self.setAngularVelocity(Vec3(uniform(-vel, vel), uniform(-vel, vel), uniform(-vel, vel)))
		space.setSurfaceType(self.geometry, 2)

class GlassFragment(Fragment):
	def __init__(self, world, space, pos, velocity):
		ObjectEntity.__init__(self, "models/fragment/GlassFragment", controllers.FragmentController(velocity), True)
		self.node.setTransparency(TransparencyAttrib.MAlpha)
		self.node.hide(BitMask32.bit(4)) # Don't cast shadows
		self.radius = 0.3
		size = self.radius * 2
		self.body = OdeBody(world)
		M = OdeMass()
		M.setBox(3, size, size, 0.05)
		self.body.setMass(M)
		self.geometry = OdeBoxGeom(space, size, size, 0.05)
		self.geometry.setCollideBits(BitMask32(0x00000001))
		self.geometry.setCategoryBits(BitMask32(0x00000001))
		self.geometry.setBody(self.body)
		self.setPosition(pos)
		self.setRotation(Vec3(uniform(0, 360), uniform(0, 360), uniform(0, 360)))
		vel = 5
		self.setAngularVelocity(Vec3(uniform(-vel, vel), uniform(-vel, vel), uniform(-vel, vel)))
		space.setSurfaceType(self.geometry, 2)

class Springboard(ObjectEntity):
	"A springboard applies an upward force to any entity that touches it."
	def __init__(self, world, space):
		ObjectEntity.__init__(self, "models/springboard/springboard", controllers.SpringboardController(Vec3(0, 0, 1)))
		self.node.setTransparency(TransparencyAttrib.MAlpha)
		self.radius = 1.5
		self.vradius = 0.1
		size = self.radius
		vsize = self.vradius
		self.collisionNode = CollisionNode("cnode")
		self.collisionNodePath = self.node.attachNewNode(self.collisionNode)
		self.collisionNode.addSolid(CollisionSphere(0, 0, 0, size))
		self.body = OdeBody(world)
		M = OdeMass()
		M.setBox(50, size, size, vsize)
		self.body.setMass(M)
		self.geometry = OdeBoxGeom(space, size, size, size)
		self.geometry.setCollideBits(BitMask32(0x00000001))
		self.geometry.setCategoryBits(BitMask32(0x00000001))
		self.geometry.setBody(self.body)
		space.setSurfaceType(self.geometry, 1)

class Glass(ObjectEntity):
	def __init__(self, world, space):
		ObjectEntity.__init__(self, "models/fragment/GlassFragment", controllers.GlassController())
		self.body = OdeBody(world)
		
	def initGlass(self, world, space, width, height):
		engine.deleteModel(self.node, "models/fragment/GlassFragment")
		maker = CardMaker("glassNode")
		maker.setFrame(-width / 2.0, width / 2.0, -height / 2.0, height / 2.0)
		maker.setUvRange(Point2(0.0, 0.0), Point2(width, height) * 0.04)
		self.node = hidden.attachNewNode(maker.generate())
		self.node.setTexture(loader.loadTexture("models/fragment/glass.png"))
		self.node.setTwoSided(True)
		self.node.setTransparency(TransparencyAttrib.MAlpha)
		self.node.setName(str(int(self.id)))
		self.node.hide(BitMask32.bit(4)) # Don't cast shadows
		self.radius = width / 2.0
		self.vradius = height / 2.0
		self.collisionNode = CollisionNode("cnode")
		point1 = Point3(-width / 2.0, 0, -height / 2.0)
		point2 = Point3(-width / 2.0, 0, height / 2.0)
		point3 = Point3(width / 2.0, 0, height / 2.0)
		point4 = Point3(width / 2.0, 0, -height / 2.0)
		self.collisionNode.addSolid(CollisionPolygon(point4, point3, point2, point1))
		self.collisionNode.addSolid(CollisionPolygon(point1, point2, point3, point4))
		self.collisionNodePath = self.node.attachNewNode(self.collisionNode)
		self.geometry = OdeBoxGeom(space, width, 0.5, height)
		self.geometry.setCollideBits(BitMask32(0x00000001))
		self.geometry.setCategoryBits(BitMask32(0x00000001))
		space.setSurfaceType(self.geometry, 1)
		self.shattered = False
		self.glassWidth = width
		self.glassHeight = height
	
	def getPosition(self):
		return self.geometry.getPosition()
	
	def setPosition(self, pos):
		self.node.setPos(pos)
		self.geometry.setPosition(pos)
	
	def setRotation(self, hpr):
		self.node.setHpr(hpr)
		self.geometry.setQuaternion(self.node.getQuat(render))
	
	def getRotation(self):
		return self.node.getHpr()
	
	def damage(self, entity, damage, ranged = True):
		self.shattered = True

	def kill(self, aiWorld, entityGroup, localDelete = True):
		# Add fragments
		pos = self.getPosition()
		shatterSound = audio.SoundPlayer("glass-shatter")
		shatterSound.play(position = pos)
		for _ in range(40):
			offset = Vec3(uniform(-self.glassWidth / 2.0, self.glassWidth / 2.0), 0, uniform(-self.glassHeight / 2.0, self.glassHeight / 2.0))
			fragment = GlassFragment(aiWorld.world, aiWorld.space, render.getRelativePoint(self.node, offset), Vec3())
			entityGroup.generateEntityId(fragment, 1024)
			entityGroup.addEntity(fragment)
		ObjectEntity.kill(self, aiWorld, entityGroup, localDelete)

class PhysicsEntity(ObjectEntity):
	"A PhysicsEntity is a large non-character physics object that is included in AI path calculations."
	def __init__(self, world, space, data = None, directory = None, file = None):
		ObjectEntity.__init__(self, None, controllers.PhysicsEntityController())
		self.geometries = []
		self.geometry = None
		self.vradius = 0
		if data != None:
			self.loadDataFile(world, space, data, directory, file)

	def loadDataFile(self, world, space, data, directory, file):
		self.directory = directory
		self.dataFile = file
		lines = data.split("\n")
		i = 0
		self.body = OdeBody(world)
		while i < len(lines):
			tokens = lines[i].split()
			if tokens[0] == "model" and self.node == None:
				self.loadModel(directory + "/" + tokens[1])
				self.collisionNode = CollisionNode("cnode")
				self.collisionNodePath = self.node.attachNewNode(self.collisionNode)
			elif tokens[0] == "geometry":
				offsetx = 0
				offsety = 0
				offsetz = 0
				geom = None
				if tokens[1] == "box":
					sizex = float(tokens[2])
					sizey = float(tokens[3])
					sizez = float(tokens[4])
					if len(tokens) == 8:
						offsetx = float(tokens[5])
						offsety = float(tokens[6])
						offsetz = float(tokens[7])
					point1 = Point3(-sizex / 2.0 + offsetx, -sizey / 2.0 + offsety, -sizez / 2.0 + offsetz)
					point2 = Point3(sizex / 2.0 + offsetx, sizey / 2.0 + offsety, sizez / 2.0 + offsetz)
					self.radius = max(self.radius, math.fabs(point1.getX()), math.fabs(point1.getY()), math.fabs(point2.getX()), math.fabs(point2.getY()))
					self.vradius = max(self.vradius, math.fabs(point1.getZ()), math.fabs(point2.getZ()))
					self.collisionNode.addSolid(CollisionBox(point1, point2))
					geom = OdeBoxGeom(space, sizex, sizey, sizez)
				elif tokens[1] == "sphere":
					radius = float(tokens[2])
					if len(tokens) == 6:
						offsetx = float(tokens[3])
						offsety = float(tokens[4])
						offsetz = float(tokens[5])
					self.collisionNode.addSolid(CollisionSphere(offsetx, offsety, offsetz, radius * 2.0))
					geom = OdeSphereGeom(space, radius)
					self.radius = max(self.radius, radius + max(math.fabs(offsetx), math.fabs(offsety)))
					self.vradius = max(self.radius, radius + math.fabs(offsetz))
				elif tokens[1] == "cylinder":
					radius = float(tokens[2])
					length = float(tokens[3])
					if len(tokens) == 7:
						offsetx = float(tokens[4])
						offsety = float(tokens[5])
						offsetz = float(tokens[6])
					point1 = Point3(-radius / 2.0 + offsetx, -radius / 2.0 + offsety, -length  / 2.0 + offsetz)
					point2 = Point3(radius / 2.0 + offsetx, radius / 2.0 + offsety, length  / 2.0 + offsetz)
					self.radius = max(self.radius, radius + max(math.fabs(offsetx), math.fabs(offsety)))
					self.vradius = max(self.vradius, length / 2.0 + math.fabs(offsetz))
					self.collisionNode.addSolid(CollisionBox(point1, point2))
					geom = OdeCylinderGeom(space, radius, length)
				geom.setCollideBits(BitMask32(0x00000001))
				geom.setCategoryBits(BitMask32(0x00000001))
				geom.setBody(self.body)
				geom.setOffsetPosition(offsetx, offsety, offsetz)
				space.setSurfaceType(geom, 1)
				if self.geometry == None:
					self.geometry = geom
				else:
					self.geometries.append(geom)
			elif tokens[0] == "mass":
				# Process the mass
				m = OdeMass()
				density = float(tokens[1])
				if tokens[2] == "box":
					m.setBox(density, float(tokens[3]), float(tokens[4]), float(tokens[5]))
				elif tokens[2] == "sphere":
					m.setSphere(density, float(tokens[3]))
				elif tokens[2] == "cylinder":
					m.setCylinder(density, 3, float(tokens[3]), float(tokens[4])) # 1 = X axis, 2 = Y axis, 3 = Z axis
				self.body.setMass(m)
			i += 1
	
	def clear(self, entityGroup):
		ObjectEntity.clear(self, entityGroup)
		for geom in self.geometries:
			geom.destroy()
		del self.geometries[:]

SPECIAL_DELAY = 18
class TeamEntity(Entity):
	"""A team is used to purchase new units. Each team has a controller and a color associated with it.
	The team also tracks which actors are on the team."""
	costs = {None:0, components.SHOTGUN:250, components.CHAINGUN:150, components.SNIPER:400, components.GRENADE_LAUNCHER:500, components.PISTOL:300, components.MOLOTOV_THROWER:550, controllers.CLOAK_SPECIAL:450, controllers.SHIELD_SPECIAL:300, controllers.AWESOME_SPECIAL:400, controllers.KAMIKAZE_SPECIAL:250, controllers.ROCKET_SPECIAL:600}
	def __init__(self):
		Entity.__init__(self, controllers.TeamEntityController(), local = False)
		self.actors = []
		self.color = Vec4()
		self.money = 600
		self.score = 0
		self.playerScore = 0
		self.player = None
		self.matchScore = 0
		self.purchasedTypes = []
		self.lastSpecialActivated = -SPECIAL_DELAY
		self.allies = []
		self.primaryWeapon = 6
		self.secondaryWeapon = 1
		self.special = 6
		self.dock = None
		self.isZombies = False
		self.isSurvivors = False
		self.username = "[empty]"
		self.lastMatchPosition = -1
	def isAlly(self, team):
		return team.getId() == self.getId() or team.getId() in self.allies
	def addAlly(self, teamId):
		if not teamId in self.allies:
			self.allies.append(teamId)
	def getAllies(self):
		return self.allies
	def setLocal(self, local):
		Entity.setLocal(self, local)
		if self.player != None:
			self.player.setLocal(self.isLocal)
	def resetScore(self):
		if self.isZombies:
			self.money += 800
		if self.isSurvivors:
			self.money += 250
		del self.purchasedTypes[:]
		self.lastSpecialActivated = -SPECIAL_DELAY
		self.score = 0
		self.player = None
		del self.actors[:]
	def purchaseItem(self, item):
		if self.money - TeamEntity.costs[item] >= 0:
			self.money -= TeamEntity.costs[item]
			return True
		return False
	def purchaseUnit(self, weapon, special):
		if weapon == None:
			return
		self.purchasedTypes.append((weapon, special))
	def setUsername(self, username):
		self.controller.oldUsername = "[empty]"
		self.username = username
	def getUsername(self):
		return self.username
	def specialAvailable(self):
		return engine.clock.time - self.lastSpecialActivated >= SPECIAL_DELAY
	def enableSpecial(self):
		self.lastSpecialActivated = engine.clock.time
	def setPrimaryWeapon(self, weapon):
		self.primaryWeapon = weapon
	def setSecondaryWeapon(self, weapon):
		self.secondaryWeapon = weapon
	def setSpecial(self, special):
		self.special = special
	def getPrimaryWeapon(self):
		return self.primaryWeapon
	def getSecondaryWeapon(self):
		return self.secondaryWeapon
	def getSpecial(self):
		return self.special
	def respawn(self, weapon, special, index = 0):
		if self.controller != None and (weapon, special) in self.purchasedTypes:
			self.controller.respawn(weapon, special, index)
	def respawnPlayer(self):
		if self.controller != None:
			self.controller.respawnPlayer(self.primaryWeapon, self.secondaryWeapon, self.special)
	def platformSpawnPlayer(self, pos):
		if self.controller != None:
			self.controller.platformSpawnPlayer(self.primaryWeapon, self.secondaryWeapon, None, pos)
	def respawnUnits(self):
		activeIndices = []
		for actor in (x for x in self.actors if x.active):
			activeIndices.append(actor.teamIndex)
		index = 0
		for unit in self.purchasedTypes:
			if not index in activeIndices:
				self.respawn(unit[0], unit[1], index)
			index += 1
	def setPlayer(self, player):
		self.player = player
		if player != None:
			self.player.setLocal(self.isLocal)
	def getPlayer(self):
		return self.player
	def setDock(self, dock):
		self.dock = dock
	def removeActor(self, actor):
		if actor in self.actors:
			self.actors.remove(actor)
	def clear(self, entityGroup):
		Entity.clear(self, entityGroup)
		if self in entityGroup.teams:
			entityGroup.teams.remove(self)

class Actor(ObjectEntity):
	"""An Actor is an ObjectEntity controlled by either a player or an AI controller.
	Actors can contain components, such as guns, engines, shields, etc."""
	def __init__(self, world, space, filename, controller, local = net.netMode == net.MODE_SERVER):
		self.team = None
		self.health = 100
		self.maxHealth = 100
		self.rangedDamageRatio = 1.0
		self.components = []
		self.killer = None
		self.teamIndex = 0
		self.scoreMultiplier = 1.0
		self.pinned = False
		self.pinPosition = None
		self.pinRotation = None
		self.pinTime = 0
		ObjectEntity.__init__(self, filename, controller, local)
	
	def setTeam(self, team):
		self.team = team
		if self.team.isSurvivors:
			ratio = float(self.health) / 100.0
			self.maxHealth = 300
			self.health = int(ratio * 300.0)
		elif self.team.isZombies:
			ratio = float(self.health) / 100.0
			self.maxHealth = 150
			self.health = int(ratio * 150.0)
	
	def setRangedDamageRatio(self, ratio):
		self.rangedDamageRatio = ratio
	
	def pin(self, pos):
		self.pinned = True
		self.pinPosition = pos
		self.pinRotation = self.getRotation()
		self.pinTime = engine.clock.time

	def damage(self, entity, damage, ranged = True):
		if self.health > 0 and (not isinstance(entity, Actor) or entity == self or (not entity.team.isAlly(self.team) and self.active)):
			if ranged:
				actualDamage = int(math.ceil(damage * self.rangedDamageRatio))
			else:
				actualDamage = int(math.ceil(damage))
			if entity == self:
				actualDamage = int(actualDamage / 2) # 50% damage if we're damaging ourself
			self.killer = entity
			self.controller.actorDamaged(entity, actualDamage, ranged)

	def kill(self, aiWorld, entityGroup, localDelete = True):
		if self.killer != None:
			score = self.maxHealth * self.scoreMultiplier
			if self.killer == self:
				score *= -1
			if isinstance(self.killer, Actor):
				self.killer.team.controller.addScore(score)
				if isinstance(self.killer, PlayerDroid) and self.killer.isLocal:
					entityGroup.shakeCamera()
		ObjectEntity.kill(self, aiWorld, entityGroup, localDelete)
	
	def delete(self, entityGroup, killed = False, localDelete = True):
		for component in self.components:
			component.delete()
		self.team.removeActor(self)
		ObjectEntity.delete(self, entityGroup, killed, localDelete)
	
	def clear(self, entityGroup):
		ObjectEntity.clear(self, entityGroup)

class BasicDroid(Actor):
	"BasicDroid is the base for basically all the units in the game. Basically."
	def __init__(self, world, space, controller, local = net.netMode == net.MODE_SERVER):
		Actor.__init__(self, world, space, "models/basicdroid/BasicDroid", controller, local)
		self.radius = 1
		self.collisionNode = CollisionNode("cnode")
		self.collisionNodePath = self.node.attachNewNode(self.collisionNode)
		self.collisionNode.addSolid(CollisionSphere(0, 0, 0, self.radius + 0.05))
		self.node.hide(BitMask32.bit(4)) # Don't cast shadows
		self.node.setTransparency(TransparencyAttrib.MAlpha) # For when we're cloaked
		self.lowResNode = engine.loadModel("models/basicdroid/BasicDroid-lowres")
		self.lowResNode.reparentTo(self.node)
		self.lowResNode.hide(BitMask32.bit(1))
		self.lowResNode.showThrough(BitMask32.bit(4)) # Low-res shadow caster
		self.body = OdeBody(world)
		M = OdeMass()
		M.setSphere(15, self.radius)
		self.body.setMass(M)
		self.geometry = OdeSphereGeom(space, self.radius)
		self.geometry.setCollideBits(BitMask32(0x00000001))
		self.geometry.setCategoryBits(BitMask32(0x00000001))
		self.geometry.setBody(self.body)
		space.setSurfaceType(self.geometry, 2)
		self.cloaked = False
		self.shielded = False
		self.crosshairNode = engine.loadModel("models/crosshair/crosshair")
		self.crosshairNode.setBillboardPointEye()
		self.crosshairNode.reparentTo(self.node)
		self.crosshairNode.setShaderOff()
		self.crosshairNode.setLightOff(True)
		self.crosshairNode.hide()
		self.crosshairNode.setScale(1.5)
		self.shieldNode = engine.loadModel("models/shield/shield")
		self.shieldNode.reparentTo(self.node)
		self.shieldNode.setTwoSided(True)
		self.shieldNode.setColor(1.0, 0.9, 0.8, 0.6)
		self.shieldNode.setShaderOff(True)
		self.shieldNode.setTransparency(TransparencyAttrib.MAlpha)
		self.shieldNode.hide()
		self.shieldNode.hide(BitMask32.bit(4)) # Don't cast shadows
		self.initialSpawnShieldEnabled = True
		self.weaponIds = []
		self.specialId = None
		self.special = None
	
	def setTeam(self, team):
		Actor.setTeam(self, team)
	
	def setWeapons(self, weapons):
		self.weaponIds = weapons
		for id in self.weaponIds:
			if id in components.types:
				self.components.append(components.types[id](self, len(self.components)))
		
	def getWeapons(self):
		return [x for x in self.components if isinstance(x, components.Weapon)]
	
	def setSpecial(self, special):
		self.specialId = special
		if self.special != None:
			self.special.delete()
		if self.specialId in controllers.specialTypes:
			self.special = controllers.specialTypes[self.specialId](self)

	def setCloaked(self, cloaked):
		self.cloaked = cloaked
		if self.active:
			alpha = 1.0
			if cloaked:
				alpha = 0.1
			self.node.setColor(1, 1, 1, alpha)
	
	def setShielded(self, shielded):
		self.shielded = shielded
		if self.active:
			if self.shielded:
				self.setRangedDamageRatio(0.4)
				self.shieldNode.show()
			else:
				self.setRangedDamageRatio(1.0)
				self.shieldNode.hide()

	def kill(self, aiWorld, entityGroup, localDelete = True):
		if self.active:
			position = self.getPosition()
			
			entityGroup.explode(position, force = 2000, damage = 0, damageRadius = 25, sourceEntity = self)

			# Add fragments
			for _ in range(6):
				offset = Vec3(uniform(-1, 1), uniform(-1, 1), uniform(0, 1))
				offset.normalize()
				fragment = Fragment(aiWorld.world, aiWorld.space, position + (offset * 1.5), offset * 30)
				entityGroup.generateEntityId(fragment, 1024)
				entityGroup.addEntity(fragment)
			
			explosionSound = audio.SoundPlayer("large-explosion")
			explosionSound.play(position = position)
		Actor.kill(self, aiWorld, entityGroup, localDelete)

	def delete(self, entityGroup, killed = False, localDelete = True):
		Actor.delete(self, entityGroup, killed, localDelete)
	
	def clear(self, entityGroup):
		Actor.clear(self, entityGroup)
		engine.deleteModel(self.shieldNode, "models/shield/shield")

class PlayerDroid(BasicDroid):
	def __init__(self, world, space, controller, local = net.netMode == net.MODE_SERVER):
		BasicDroid.__init__(self, world, space, controller, local)
		self.username = "Unnamed"
		self.scoreMultiplier = 2.0
	
	def setTeam(self, team):
		BasicDroid.setTeam(self, team)
		self.team.setPlayer(self)
	
	def setWeapons(self, weapons):
		self.components.append(components.MeleeClaw(self, 0))
		BasicDroid.setWeapons(self, weapons)
	
	def setUsername(self, name):
		self.username = name

class Grenade(ObjectEntity):
	"Grenades trigger an explosion animation when damaged. Most of the action happens in the GrenadeController."
	def __init__(self, world, space):
		self.team = None
		ObjectEntity.__init__(self, "models/grenade/Grenade", controllers.GrenadeController())
		self.collisionNode = CollisionNode("cnode")
		self.collisionNodePath = self.node.attachNewNode(self.collisionNode)
		self.collisionNode.addSolid(CollisionSphere(0, 0, 0, 0.4))
		self.body = OdeBody(world)
		M = OdeMass()
		self.radius = 0.2
		M.setSphere(500, 0.2)
		self.body.setMass(M)
		self.geometry = OdeSphereGeom(space, 0.2)
		self.geometry.setCollideBits(BitMask32(0x00000001))
		self.geometry.setCategoryBits(BitMask32(0x00000001))
		self.geometry.setBody(self.body)
		space.setSurfaceType(self.geometry, 2)
		self.commitChanges()
		self.grenadeAlive = True
		self.actor = None
	
	def setActor(self, actor):
		self.actor = actor
	
	def setTeam(self, team):
		self.team = team
	
	def damage(self, entity, damage, ranged = True):
		"Immediately trigger an explosion."
		self.grenadeAlive = False
	
	def kill(self, aiWorld, entityGroup, localDelete = True):
		"Immediately trigger an explosion."
		if self.active:
			pos = self.getPosition()
			grenadeSound = audio.SoundPlayer("grenade")
			grenadeSound.play(position = self.getPosition())
			ObjectEntity.kill(self, aiWorld, entityGroup, localDelete)
			entityGroup.explode(pos, force = 4000, damage = 67, damageRadius = 20, sourceEntity = self, damagingEntity = self.actor) # Give damage credit to our parent actor

class Molotov(ObjectEntity):
	"Molotovs are basically flaming grenades. Most of the action happens in the MolotovController."
	def __init__(self, world, space):
		self.team = None
		ObjectEntity.__init__(self, "models/grenade/Grenade", controllers.MolotovController())
		self.collisionNode = CollisionNode("cnode")
		self.collisionNodePath = self.node.attachNewNode(self.collisionNode)
		self.collisionNode.addSolid(CollisionSphere(0, 0, 0, 0.4))
		self.body = OdeBody(world)
		M = OdeMass()
		self.radius = 0.2
		M.setSphere(500, 0.2)
		self.body.setMass(M)
		self.geometry = OdeSphereGeom(space, 0.2)
		self.geometry.setCollideBits(BitMask32(0x00000001))
		self.geometry.setCategoryBits(BitMask32(0x00000001))
		self.geometry.setBody(self.body)
		space.setSurfaceType(self.geometry, 2)
		self.commitChanges()
		self.grenadeAlive = True
		self.actor = None
	
	def setActor(self, actor):
		self.actor = actor
	
	def setTeam(self, team):
		self.team = team

class GraphicsObject(DirectObject):
	def __init__(self):
		self.active = True
	def delete(self):
		self.active = False
	def update(self):
		pass

class Spike(GraphicsObject):
	def __init__(self, pos, direction):
		GraphicsObject.__init__(self)
		self.node = engine.loadModel("models/spike/spike")
		self.node.reparentTo(engine.renderLit)
		self.node.setPos(pos)
		self.node.lookAt(Point3(pos + direction))
		self.spawnTime = engine.clock.time
		self.entity = None
		self.lifetime = 5.0
		
	def delete(self, entityGroup):
		GraphicsObject.delete(self)
		self.node.removeNode()
	
	def attachTo(self, entity):
		if (self.node.getPos() - entity.getPosition()).length() > entity.radius + 0.5:
			vector = self.node.getPos() - entity.getPosition()
			vector.normalize()
			vector *= entity.radius
			self.node.setPos(entity.getPosition() + vector)
		self.node.wrtReparentTo(entity.node)
		self.entity = entity
		self.lifetime = 15.0
		
	def update(self, entityGroup):
		GraphicsObject.update(self)
		if not self.active:
			return
		if engine.clock.time - self.spawnTime > self.lifetime or (self.entity != None and not self.entity.active):
			self.delete(entityGroup)