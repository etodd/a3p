from direct.showbase.DirectObject import DirectObject
from pandac.PandaModules import *
from random import random, uniform
import math
import engine
import entities
import audio
import net
import net2
import particles
import controllers

class Component(DirectObject):
	"A component is an object (weapon, etc) of an actor. Components can take damage and be repaired."
	def __init__(self, actor, id):
		self.criticalPackets = []
		self.actor = actor
		self.active = True
		self.id = id
		self.criticalUpdate = False
	
	def needsToSendUpdate(self):
		return self.criticalUpdate
	
	def addCriticalPacket(self, p, packetUpdate):
		# If we have a critical packet on an update frame, and we add it to the critical packet queue,
		# it will get sent again on the next update frame.
		# So, we don't want that to happen.
		if packetUpdate:
			self.criticalUpdate = True
		elif not p in self.criticalPackets:
			self.criticalPackets.append(p)
		
	def serverUpdate(self, aiWorld, entityGroup, packetUpdate):
		p = net.Packet()
		if packetUpdate:
			self.criticalUpdate = len(self.criticalPackets) > 0
			for packet in self.criticalPackets:
				p.add(packet)
			del self.criticalPackets[:]
		else:
			self.criticalUpdate = False
		p.add(net.Uint8(self.id))
		return p

	def clientUpdate(self, aiWorld, entityGroup, iterator = None):
		pass
	
	def delete(self):
		self.active = False
	
	def hide(self):
		pass
	
	def show(self):
		pass

class Weapon(Component):
	def __init__(self, actor, id):
		Component.__init__(self, actor, id)
		self.zoomedFov = 50
		self.zoomedCameraOffset = Vec3(-1.25, -3, 1.25)
		self.zoomedMouseSpeed = 0.3
		self.defaultCrosshair = 1 # Wide crosshairs
		self.zoomedCrosshair = 2 # Narrow crosshairs
		# If we're zoomed, we need to be more accurate. Or at least, do something different.
		# AI bots are always zoomed in by default, to make them more challenging.
		# PlayerControllers will update this flag.
		self.zoomed = True 
		self.selected = False
		self.fireTime = 0
		self.lastFire = -10000
		self.firing = False
		self.triggerReleased = True
		self.node = None
		self.isAutomatic = False
		self.reloadActive = False
		self.lastTrigger = 0
		
		# Parameters for AI controllers
		self.burstTimer = -1
		self.burstDelayTimer = -1
		self.burstDelay = 0
		self.burstTime = 0
		self.shotDelay = 0
		self.burstTimeBase = 0.6
		self.burstDelayBase = 0.1
		self.shotDelayBase = 0
		self.accuracy = 0.4
		self.range = 40

	def fire(self):
		if self.isReady() and self.selected and (self.isAutomatic or engine.clock.getLastFrameTime() > self.lastTrigger):
			self.lastFire = engine.clock.getTime()
			self.firing = True
			result = True
		else:
			result = False
		self.lastTrigger = engine.clock.getTime()
		return result
	
	def isReady(self):
		return engine.clock.getTime() - self.lastFire > self.fireTime

	def serverUpdate(self, aiWorld, entityGroup, packetUpdate):
		return Component.serverUpdate(self, aiWorld, entityGroup, packetUpdate)

	def clientUpdate(self, aiWorld, entityGroup, iterator = None):
		Component.clientUpdate(self, aiWorld, entityGroup, iterator)

	def show(self):
		Component.show(self)
		if self.active:
			self.selected = True
			if self.node != None:
				self.node.show()
	
	def hide(self):
		Component.hide(self)
		if self.active:
			self.selected = False
			if self.node != None:
				self.node.hide()
	
	def delete(self):
		Component.delete(self)
		
class Gun(Weapon):
	"Guns don't kill people, but they sure help."
	def __init__(self, actor, damage, modelFile, id):
		Weapon.__init__(self, actor, id)
		self.clipSize = 10
		self.ammo = self.clipSize
		self.ammoAdditions = 0 # So that if fire() is called between serverUpdate and clientUpdate, ammo is still depleted
		self.reloadTime = 2.0
		self.newReloadActive = False
		self.reloadStarted = False # Server side; only true one frame
		self.damage = damage
		self.lastReload = -1
		self.ricochetSound = audio.SoundPlayer("ricochet")
		self.reloadSound = audio.SoundPlayer("reload")
		self.reloadBeepSound = audio.SoundPlayer("reload-beep")
		self.showSound = audio.SoundPlayer("change-weapon")
		self.node = engine.loadModel(modelFile)
		self.modelFile = modelFile
		self.node.reparentTo(engine.renderLit)
		self.activeSound = 0 # Client side
		self.showTime = -1 # For the showing animation
		self.totalShowTime = 0.3
		Gun.hide(self)
	
	def getPosition(self):
		return self.node.getPos()
	
	def setPosition(self, pos):
		self.node.setPos(pos)
	
	def getRotation(self):
		return self.node.getHpr()
	
	def setRotation(self, hpr):
		self.node.setHpr(hpr)
	
	def show(self):
		Weapon.show(self)
		self.showTime = engine.clock.getTime()
		self.showSound.play(entity = self.actor)
	
	def hide(self):
		Weapon.hide(self)
		self.newReloadActive = False
		self.reloadActive = False
		self.reloadStarted = False
		self.lastReload = -1
		if self.reloadBeepSound.isPlaying():
			self.reloadBeepSound.stop()
	
	def reload(self):
		if not self.reloadActive and self.selected and self.ammo < self.clipSize:
			self.lastReload = engine.clock.getTime()
			self.newReloadActive = True
			self.reloadActive = True
			self.reloadStarted = True
		
	def fire(self):
		if self.ammo > 0 and not self.reloadActive and self.showTime == -1: # We can't be switching weapons
			result = Weapon.fire(self)
			if result:
				self.ammoAdditions -= 1
			return result
		elif self.showTime == -1 and self.isReady():
			self.reload()
		return False
	
	def bulletTest(self, aiWorld, entityGroup, origin, direction):
		"""Low-level bullet ray test used by most guns.
		Returns the position of the bullet hit, and the ObjectEntity damaged, if any."""
		queue = aiWorld.getCollisionQueue(origin, direction)
		for i in range(queue.getNumEntries()):
			entry = queue.getEntry(i)
			pos = entry.getSurfacePoint(render)
			normal = entry.getSurfaceNormal(render)
			entity = entityGroup.getEntityFromEntry(entry)
			if entity == self.actor:
				continue
			return (entity, pos, normal, queue)
		return (None, None, None, None)

	def serverUpdate(self, aiWorld, entityGroup, packetUpdate):
		p = Weapon.serverUpdate(self, aiWorld, entityGroup, packetUpdate)

		if self.reloadStarted:
			self.addCriticalPacket(p, packetUpdate)
			self.reloadStarted = False
		
		self.reloadActive = self.newReloadActive
		self.activeSound = 0 # No sound
		if self.reloadActive:
			if engine.clock.getTime() - self.lastReload < self.reloadTime:
				self.activeSound = 1 # Reload beep sound
			else:
				self.ammo = self.clipSize
				self.reloadActive = False
				self.newReloadActive = False
				self.activeSound = 2 # Reload ready sound
				self.addCriticalPacket(p, packetUpdate)
		p.add(net.Uint8(self.activeSound))
		p.add(net.Boolean(self.selected))
		self.ammo += self.ammoAdditions
		self.ammoAdditions = 0
		if self.selected:
			p.add(net.Uint8(self.ammo))
		return p

	def clientUpdate(self, aiWorld, entityGroup, iterator = None):
		Weapon.clientUpdate(self, aiWorld, entityGroup, iterator)
		if iterator != None:
			self.activeSound = net.Uint8.getFrom(iterator)
			if net.Boolean.getFrom(iterator):
				self.ammo = net.Uint8.getFrom(iterator)
		if self.actor.active:
			offset = 0
			angleOffset = 0
			if self.showTime != -1:
				blend = min(1.0, (engine.clock.getTime() - self.showTime) / self.totalShowTime)
				if self.selected and blend < 1.0:
					offset = 1.0 - blend
					angleOffset = 90 - (blend * 90)
				else:
					self.showTime = -1
			if self.selected:
				vector = self.actor.controller.targetPos - self.actor.getPosition()
				pos = vector.cross(Vec3(0, 0, 1))
				pos.normalize()
				self.setPosition(self.actor.getPosition() + (pos * (self.actor.radius + 0.1)) + Vec3(0, 0, offset))
				self.node.lookAt(Point3(self.actor.controller.targetPos))
				self.node.setP(self.node.getP() + angleOffset)
			if self.activeSound == 1: # Reload beep sound
				self.reloadActive = True # So clients also have an accurate reloadActive value
				if not self.reloadBeepSound.isPlaying():
					self.reloadBeepSound.play(entity = self.actor)
			elif self.activeSound == 2: # Reload ready sound
				self.reloadActive = False # So clients also have an accurate reloadActive value
				if self.reloadBeepSound.isPlaying():
					self.reloadBeepSound.stop()
				self.reloadSound.play(entity = self.actor)
				self.activeSound = 0 # Only play once
	
	def delete(self):
		self.ricochetSound.delete()
		self.reloadBeepSound.delete()
		self.reloadSound.delete()
		self.node.removeNode()
		Weapon.delete(self)

CHAINGUN = 254
class ChainGun(Gun):
	def __init__(self, actor, id):
		Gun.__init__(self, actor, 10, "models/basicdroid/chaingun", id)
		self.clipSize = 50
		self.ammo = self.clipSize
		self.light = engine.Light(color = Vec4(1.0, 0.7, 0.4, 1), attenuation = Vec3(0, 0, 0.003))
		self.tracer = particles.BulletTracerParticleGroup()
		self.force = 150
		self.chainGunSound = audio.SoundPlayer("chaingun")
		self.fireTime = 0.05
		self.isAutomatic = True

	def serverUpdate(self, aiWorld, entityGroup, packetUpdate):
		p = Gun.serverUpdate(self, aiWorld, entityGroup, packetUpdate)
		
		if self.active and self.firing:
			self.addCriticalPacket(p, packetUpdate)
			p.add(net.Boolean(True))
			
			vector = self.actor.controller.targetPos - self.actor.getPosition()
			pos = vector.cross(Vec3(0, 0, 1))
			pos.normalize()
			origin = self.actor.getPosition() + (pos * (self.actor.radius + 0.1))
			direction = self.actor.controller.targetPos - origin
			direction.normalize()
			
			#self.actor.body.addForce(engine.impulseToForce(direction.getX() * -self.force, direction.getY() * -self.force, direction.getZ() * -self.force))
		
			if self.zoomed:
				angleX = uniform(-0.5, 0.5)
				angleY = uniform(-0.5, 0.5)
			else:
				angleX = uniform(-2, 2)
				angleY = uniform(-2, 2)
				
			mat = Mat3()
			mat.setRotateMatNormaxis(angleX, render.getRelativeVector(self.node, Vec3(0, 0, 1)))
			direction = mat.xformVec(direction)
			mat = Mat3()
			mat.setRotateMatNormaxis(angleY, render.getRelativeVector(self.node, Vec3(1, 0, 0)))
			direction = mat.xformVec(direction)
			
			p.add(net2.StandardVec3(direction))
			
			entity = None
			hitPos = None
			if direction.length() > 0:
				entity, hitPos, normal, queue = self.bulletTest(aiWorld, entityGroup, origin, direction)
			if hitPos == None:
				p.add(net.Boolean(False)) # Bullet didn't hit anything
			else:
				p.add(net.Boolean(True)) # Bullet hit something
				p.add(net2.StandardVec3(hitPos))
			
				if entity != None:
					p.add(net.Boolean(True))
					p.add(net.Uint8(entity.getId()))
					p.add(net.Uint16(self.damage * max(0, 1 - (vector.length() / 70)) * max(0, normal.dot(-direction) + 0.1)))
				else:
					p.add(net.Boolean(False))
		else:
			p.add(net.Boolean(False))
		self.firing = False
		return p

	def clientUpdate(self, aiWorld, entityGroup, iterator = None):
		Gun.clientUpdate(self, aiWorld, entityGroup, iterator)

		if iterator != None:
			if net.Boolean.getFrom(iterator): # We're firing
				self.lastFire = engine.clock.getTime()
				
				if self.active:
					self.chainGunSound.play(entity = self.actor)
					self.light.add()
				
				direction = net2.StandardVec3.getFrom(iterator)
				
				if net.Boolean.getFrom(iterator): # Bullet hit something
					hitPos = net2.StandardVec3.getFrom(iterator)
					if self.active:
						origin = self.getPosition() + (direction * random() * 4)
						pos = hitPos - (direction * random() * 4)
						self.tracer.draw(origin, pos)
					
					if net.Boolean.getFrom(iterator):
						entityId = net.Uint8.getFrom(iterator)
						entity = entityGroup.getEntity(entityId)
						damage = net.Uint16.getFrom(iterator)
						if entity != None:
							entity.damage(self.actor, damage)
							if isinstance(entity, entities.Actor):
								particles.add(particles.HitRegisterParticleGroup(hitPos - direction, entity.team.color, damage * 2 / self.damage))
							else:
								particles.add(particles.SparkParticleGroup(hitPos))
					else:
						particles.add(particles.SparkParticleGroup(hitPos))
						self.ricochetSound.play(position = hitPos)
		if engine.clock.getTime() - self.lastFire > 0.1:
			self.light.remove()
		elif self.active:
			self.light.setPos(self.getPosition())
			self.light.setAttenuation((0, 0, 0.005 + math.pow((engine.clock.getTime() - self.lastFire), 2) * 8))
	
	def delete(self):
		self.chainGunSound.delete()
		self.tracer.delete()
		self.light.remove()
		Gun.delete(self)

SHOTGUN = 253
class Shotgun(Gun):
	def __init__(self, actor, id):
		Gun.__init__(self, actor, 100, "models/basicdroid/shotgun", id)
		self.clipSize = 8
		self.ammo = self.clipSize
		self.light = engine.Light(color = Vec4(1.0, 0.7, 0.4, 1), attenuation = Vec3(0, 0, 0.003))
		self.tracer = particles.BulletTracerParticleGroup()
		self.force = 900
		self.shotGunSound = audio.SoundPlayer("shotgun")
		self.fireTime = 1.0
		self.range = 15
		self.accuracy = 1.0
		self.burstTimeBase = 0.3

	def serverUpdate(self, aiWorld, entityGroup, packetUpdate):
		p = Gun.serverUpdate(self, aiWorld, entityGroup, packetUpdate)
		
		if self.active and self.firing:
			self.addCriticalPacket(p, packetUpdate)
			p.add(net.Boolean(True))
			
			vector = self.actor.controller.targetPos - self.actor.getPosition()
			pos = vector.cross(Vec3(0, 0, 1))
			pos.normalize()
			origin = self.actor.getPosition() + (pos * (self.actor.radius + 0.1))
			direction = self.actor.controller.targetPos - origin
			direction.normalize()
			
			#self.actor.body.addForce(engine.impulseToForce(direction.getX() * -self.force, direction.getY() * -self.force, direction.getZ() * -self.force))
			
			p.add(net2.StandardVec3(direction))
			
			entity = None
			hitPos = None
			if direction.length() > 0:
				entity, hitPos, normal, queue = self.bulletTest(aiWorld, entityGroup, origin, direction)
			if hitPos == None:
				p.add(net.Boolean(False)) # Bullet didn't hit anything
			else:
				p.add(net.Boolean(True)) # Bullet hit something
				p.add(net2.StandardVec3(hitPos))
			
				if entity != None:
					p.add(net.Boolean(True))
					p.add(net.Uint8(entity.getId()))
					vector = entity.getPosition() - self.getPosition()
					range = self.range
					if self.zoomed:
						range *= 1.5
					p.add(net.Uint16(self.damage * max(0, 1 - (vector.length() / range) * max(0, normal.dot(-direction) * 1.25))))
				else:
					p.add(net.Boolean(False))
		else:
			p.add(net.Boolean(False))
		self.firing = False
		return p

	def clientUpdate(self, aiWorld, entityGroup, iterator = None):
		Gun.clientUpdate(self, aiWorld, entityGroup, iterator)

		if iterator != None:
			if net.Boolean.getFrom(iterator): # We're firing
				self.lastFire = engine.clock.getTime()
				
				if self.active:
					self.shotGunSound.play(entity = self.actor)
					self.light.add()
				
				direction = net2.StandardVec3.getFrom(iterator)
				
				if net.Boolean.getFrom(iterator): # Bullet hit something
					hitPos = net2.StandardVec3.getFrom(iterator)
					if self.active:
						radius = (hitPos - self.getPosition()).length() / 5
						for _ in range(5):
							particles.add(particles.SparkParticleGroup(hitPos + Vec3(uniform(-radius, radius), uniform(-radius, radius), uniform(-radius, radius))))
						origin = self.getPosition() + (direction * random() * 4)
						pos = hitPos - (direction * random() * 4)
						self.tracer.draw(origin, pos)
					
					if net.Boolean.getFrom(iterator):
						entityId = net.Uint8.getFrom(iterator)
						entity = entityGroup.getEntity(entityId)
						damage = net.Uint16.getFrom(iterator)
						if entity != None:
							entity.damage(self.actor, damage)
							if isinstance(entity, entities.Actor):
								particles.add(particles.HitRegisterParticleGroup(hitPos - direction, entity.team.color, (damage * 3) / self.damage))
					else:
						self.ricochetSound.play(position = hitPos)
		if engine.clock.getTime() - self.lastFire > 0.1:
			self.light.remove()
		elif self.active:
			self.light.setPos(self.getPosition())
			self.light.setAttenuation((0, 0, 0.005 + math.pow((engine.clock.getTime() - self.lastFire), 2) * 8))
	
	def delete(self):
		self.shotGunSound.delete()
		self.tracer.delete()
		self.light.remove()
		Gun.delete(self)

SNIPER = 252
class SniperRifle(Gun):
	def __init__(self, actor, id):
		Gun.__init__(self, actor, 50, "models/basicdroid/sniper", id)
		self.defaultCrosshair = 0 # No crosshair
		self.zoomedCrosshair = 3 # Sniper scope
		self.zoomedFov = 25
		self.zoomedMouseSpeed = 0.15
		self.clipSize = 4
		self.ammo = self.clipSize
		self.light = engine.Light(color = Vec4(1.0, 0.7, 0.4, 1), attenuation = Vec3(0, 0, 0.003))
		self.tracer = particles.BulletTracerParticleGroup()
		self.force = 800
		self.sniperSound = audio.SoundPlayer("sniper-rifle")
		self.zoomed = False
		self.fireTime = 0.8
		self.reloadTime = 3.0
		self.range = 300
		self.accuracy = 0.7
	
	def serverUpdate(self, aiWorld, entityGroup, packetUpdate):
		p = Gun.serverUpdate(self, aiWorld, entityGroup, packetUpdate)
		
		if self.active and self.firing:
			self.addCriticalPacket(p, packetUpdate)
			p.add(net.Boolean(True))

			vector = self.actor.controller.targetPos - self.actor.getPosition()
			pos = vector.cross(Vec3(0, 0, 1))
			pos.normalize()
			origin = self.actor.getPosition() + (pos * (self.actor.radius + 0.1))
			direction = self.actor.controller.targetPos - origin
			direction.normalize()
			
			#self.actor.body.addForce(engine.impulseToForce(direction.getX() * -self.force, direction.getY() * -self.force, direction.getZ() * -self.force))
			
			p.add(net2.StandardVec3(direction))
			
			entity, hitPos, normal, queue = self.bulletTest(aiWorld, entityGroup, origin, direction)
			if hitPos == None:
				p.add(net.Boolean(False)) # Bullet didn't hit anything
			else:
				p.add(net.Boolean(True)) # Bullet hit something
				p.add(net2.StandardVec3(hitPos))
			
				if entity != None:
					p.add(net.Boolean(True))
					p.add(net.Uint8(entity.getId()))
					dot = normal.dot(-direction)
					if dot > 0.95:
						p.add(net.Uint16(self.damage * 4))
					else:
						p.add(net.Uint16(self.damage * max(0, dot * 1.5)))
				else:
					p.add(net.Boolean(False))
		else:
			p.add(net.Boolean(False))
		self.firing = False
		return p

	def clientUpdate(self, aiWorld, entityGroup, iterator = None):
		Gun.clientUpdate(self, aiWorld, entityGroup, iterator)
			
		if iterator != None:
			if net.Boolean.getFrom(iterator): # We're firing
				if self.active:
					self.sniperSound.play(entity = self.actor)
					self.light.add()
				
				direction = net2.StandardVec3.getFrom(iterator)
				
				if net.Boolean.getFrom(iterator): # Bullet hit something
					hitPos = net2.StandardVec3.getFrom(iterator)
					if self.active:
						origin = self.getPosition() + (direction * random() * 4)
						pos = hitPos - (direction * random() * 4)
						self.tracer.draw(origin, pos)
					if net.Boolean.getFrom(iterator):
						entityId = net.Uint8.getFrom(iterator)
						entity = entityGroup.getEntity(entityId)
						damage = net.Uint16.getFrom(iterator)
						if entity != None:
							entity.damage(self.actor, damage)
							if isinstance(entity, entities.Actor):
								particles.add(particles.HitRegisterParticleGroup(hitPos - direction, entity.team.color, damage / self.damage))
							else:
								particles.add(particles.SparkParticleGroup(hitPos))
					else:
						self.ricochetSound.play(position = hitPos)
						particles.add(particles.SparkParticleGroup(hitPos))
		if engine.clock.getTime() - self.lastFire > 0.1:
			self.light.remove()
		elif self.active:
			self.light.setPos(self.getPosition())
			self.light.setAttenuation((0, 0, 0.005 + math.pow((engine.clock.getTime() - self.lastFire), 2) * 8))
	
	def hide(self):
		self.zoomed = False
		self.fov = 70
		self.desiredFov = 70
		Gun.hide(self)
	
	def delete(self):
		self.sniperSound.delete()
		self.tracer.delete()
		self.light.remove()
		Gun.delete(self)

MELEE_CLAW = 251
class MeleeClaw(Weapon):
	def __init__(self, actor, id):
		Weapon.__init__(self, actor, id)
		self.impaleStart = -1
		self.impaleTarget = None
		self.node = engine.loadAnimation("models/basicdroid/claw", {"Impale":"models/basicdroid/claw-Impale", "Retract":"models/basicdroid/claw-Retract"})
		self.node.reparentTo(engine.renderLit)
		self.clawSound = audio.SoundPlayer("claw")
		self.clawFailSound = audio.SoundPlayer("claw-fail")
		self.clawRetractSound = audio.SoundPlayer("claw-retract")
		self.impulseVector = None
		self.damage = 75
		self.fireTime = 1.25
		self.hide()
	
	def getPosition(self):
		return self.node.getPos()
	
	def setPosition(self, pos):
		self.node.setPos(pos)
	
	def getRotation(self):
		return self.node.getHpr()
	
	def setRotation(self, hpr):
		self.node.setHpr(hpr)
	
	def serverUpdate(self, aiWorld, entityGroup, packetUpdate):
		p = Weapon.serverUpdate(self, aiWorld, entityGroup, packetUpdate)
		if self.firing and self.active:
			self.addCriticalPacket(p, packetUpdate)
			p.add(net.Uint8(1)) # 1 = We're starting to impale an entity
			enemy = aiWorld.getNearestEnemy(entityGroup, self.actor.getPosition(), self.actor.team, includeCloakedUnits = True)
			if enemy != None:
				vector = self.actor.controller.targetPos - base.camera.getPos()
				vector2 = enemy.getPosition() - base.camera.getPos()
				vector3 = enemy.getPosition() - self.actor.getPosition()
				vector.normalize()
				vector2.normalize()
				if math.acos(vector.getX() * vector2.getX() + vector.getY() * vector2.getY() + vector.getZ() * vector2.getZ()) < math.pi / 5 and vector3.length() < 8:
					p.add(net.Boolean(True))
					vector3.normalize()
					self.actor.addForce(engine.impulseToForce(vector3 * 1000))
					self.impulseVector = vector3
					self.impaleTarget = enemy
				else:
					p.add(net.Boolean(False))
			else:
				p.add(net.Boolean(False))
			self.firing = False
		elif self.active and self.impaleStart != -1 and self.impaleTarget != None and self.impaleTarget.active and (self.actor.getPosition() - self.impaleTarget.getPosition()).length() < self.actor.radius + self.impaleTarget.radius + 0.5:
			self.addCriticalPacket(p, packetUpdate)
			# At this point, the blade is actually in the target.
			p.add(net.Uint8(2)) # 2 = We're now actually damaging the entity
			p.add(net.Uint8(self.impaleTarget.getId()))
			
			# Stop the player from flying past the target.
			if self.impaleTarget.health > self.damage: # Only add force if we don't kill the target. If the target dies, the explosion will already push us away.
				self.actor.addForce(engine.impulseToForce(self.impulseVector * -800))
			
			self.impaleTarget = None
		else:
			p.add(net.Uint8(0)) # 0 = Nothing's happening
		return p
	
	def clientUpdate(self, aiWorld, entityGroup, iterator = None):
		Weapon.clientUpdate(self, aiWorld, entityGroup, iterator)
		if iterator != None:
			state = net.Uint8.getFrom(iterator)
			if state == 1: # We're impaling
				self.impaleStart = engine.clock.getTime()
				# Show the claw and animate it.
				self.show()
				self.node.play("Impale")
				if net.Boolean.getFrom(iterator): # Impale was a success
					self.clawSound.play(entity = self.actor)
				else: # Fail!
					self.clawFailSound.play(entity = self.actor)
			elif state == 2: # We're damaging an entity
				enemy = entityGroup.getEntity(net.Uint8.getFrom(iterator))
				if enemy != None and enemy.active:
					pos = (enemy.getPosition() + self.actor.getPosition()) * 0.5
					particles.add(particles.HitRegisterParticleGroup(pos, enemy.team.color, 2))
					enemy.damage(self.actor, self.damage, False)
		
		# Animation code
		if self.selected and self.active:
			self.setPosition(self.actor.getPosition())
			self.node.lookAt(Point3(self.actor.controller.targetPos))
			if self.impaleStart != -1 and engine.clock.getTime() - self.impaleStart > self.node.getDuration("Impale") and engine.clock.getTime() - self.impaleStart < 0.75:
				self.node.pose("Impale", self.node.getNumFrames("Impale") - 1)
			elif self.impaleStart != -1 and engine.clock.getTime() - self.impaleStart > 0.75 and engine.clock.getTime() - self.impaleStart < 0.75 + self.node.getDuration("Retract"):
				if self.node.getCurrentAnim() != "Retract":
					self.node.play("Retract")
					self.clawRetractSound.play(entity = self.actor)
			elif engine.clock.getTime() - self.impaleStart > 0.75 + self.node.getDuration("Retract"):
				self.impaleStart = -1
				self.hide()
	
	def delete(self):
		self.clawSound.delete()
		self.clawFailSound.delete()
		self.clawRetractSound.delete()
		self.node.cleanup()
		self.node.removeNode()
		Weapon.delete(self)
	
	def show(self):
		if self.active:
			self.node.show()
		Weapon.show(self)
	
	def hide(self):
		if self.active:
			self.node.hide()
		Weapon.hide(self)

GRENADE_LAUNCHER = 249
class GrenadeLauncher(Weapon):
	def __init__(self, actor, id):
		Weapon.__init__(self, actor, id)
		self.force = 400
		self.grenadeLaunchSound = audio.SoundPlayer("grenade-launch")
		self.fireTime = 2.25
		self.grenadeId = -1

	def serverUpdate(self, aiWorld, entityGroup, packetUpdate):
		p = Weapon.serverUpdate(self, aiWorld, entityGroup, packetUpdate)
		p.add(net.Boolean(self.firing))
		if self.firing:
			self.addCriticalPacket(p, packetUpdate)
			direction = self.actor.controller.targetPos - self.actor.getPosition()
			direction.normalize()
			direction.setZ(direction.getZ() + 0.5)
			direction.normalize()
			
			origin = self.actor.getPosition() + (direction * (self.actor.radius + 0.1))
			#self.actor.body.addForce(engine.impulseToForce(direction.getX() * -self.force, direction.getY() * -self.force, direction.getZ() * -self.force))
			grenade = entities.Grenade(aiWorld.world, aiWorld.space)
			grenade.setTeam(self.actor.team)
			grenade.setActor(self.actor)
			grenade.setPosition(origin)
			grenade.setLinearVelocity(direction * 40)
			entityGroup.spawnEntity(grenade)
			p.add(net.Uint8(grenade.getId()))
		self.firing = False
		return p
	
	def clientUpdate(self, aiWorld, entityGroup, iterator = None):
		Component.clientUpdate(self, aiWorld, entityGroup, iterator)
		if iterator != None:
			if net.Boolean.getFrom(iterator):
				# We're firing, play the launch sound. Everything else is taken care of by the Grenade being spawned.
				self.grenadeLaunchSound.play(entity = self.actor)
				self.grenadeId = net.Uint8.getFrom(iterator)
		grenade = entityGroup.getEntity(self.grenadeId)
		if grenade != None and isinstance(grenade, entities.Grenade):
			grenade.setActor(self.actor)
	
	def delete(self):
		self.grenadeLaunchSound.delete()
		Component.delete(self)

MOLOTOV_THROWER = 247
class MolotovThrower(Weapon):
	def __init__(self, actor, id):
		Weapon.__init__(self, actor, id)
		self.force = 400
		self.grenadeLaunchSound = audio.SoundPlayer("grenade-launch")
		self.fireTime = 3.0
		self.grenadeId = -1

	def serverUpdate(self, aiWorld, entityGroup, packetUpdate):
		p = Weapon.serverUpdate(self, aiWorld, entityGroup, packetUpdate)
		p.add(net.Boolean(self.firing))
		if self.firing:
			self.addCriticalPacket(p, packetUpdate)
			direction = self.actor.controller.targetPos - self.actor.getPosition()
			direction.normalize()
			direction.setZ(direction.getZ() + 0.5)
			direction.normalize()
			
			origin = self.actor.getPosition() + (direction * (self.actor.radius + 0.1))
			#self.actor.body.addForce(engine.impulseToForce(direction.getX() * -self.force, direction.getY() * -self.force, direction.getZ() * -self.force))
			grenade = entities.Molotov(aiWorld.world, aiWorld.space)
			grenade.setTeam(self.actor.team)
			grenade.setActor(self.actor)
			grenade.setPosition(origin)
			grenade.setLinearVelocity(direction * 40)
			entityGroup.spawnEntity(grenade)
			p.add(net.Uint8(grenade.getId()))
		self.firing = False
		return p
	
	def clientUpdate(self, aiWorld, entityGroup, iterator = None):
		Component.clientUpdate(self, aiWorld, entityGroup, iterator)
		if iterator != None:
			if net.Boolean.getFrom(iterator):
				# We're firing, play the launch sound. Everything else is taken care of by the Grenade being spawned.
				self.grenadeLaunchSound.play(entity = self.actor)
				self.grenadeId = net.Uint8.getFrom(iterator)
		grenade = entityGroup.getEntity(self.grenadeId)
		if grenade != None and isinstance(grenade, entities.Grenade):
			grenade.setActor(self.actor)
	
	def delete(self):
		self.grenadeLaunchSound.delete()
		Component.delete(self)

PISTOL = 248
class Pistol(Gun):
	def __init__(self, actor, id):
		Gun.__init__(self, actor, 27, "models/basicdroid/pistol", id)
		self.clipSize = 12
		self.ammo = self.clipSize
		self.light = engine.Light(color = Vec4(1.0, 0.7, 0.4, 1), attenuation = Vec3(0, 0, 0.003))
		self.tracer = particles.BulletTracerParticleGroup()
		self.force = 700
		self.pistolSound = audio.SoundPlayer("pistol")
		self.pinSound = audio.SoundPlayer("claw")
		self.fireTime = 0.05
		self.burstTimeBase = 0.5
		self.burstDelayBase = 1.25
		self.shotDelayBase = 0.15

	def serverUpdate(self, aiWorld, entityGroup, packetUpdate):
		p = Gun.serverUpdate(self, aiWorld, entityGroup, packetUpdate)
		
		if self.active and self.firing:
			self.addCriticalPacket(p, packetUpdate)
			p.add(net.Boolean(True))
			
			vector = self.actor.controller.targetPos - self.actor.getPosition()
			pos = vector.cross(Vec3(0, 0, 1))
			pos.normalize()
			origin = self.actor.getPosition() + (pos * (self.actor.radius + 0.1))
			direction = self.actor.controller.targetPos - origin
			direction.normalize()
			
			if not self.zoomed:
				angleX = uniform(-1, 1)
				angleY = uniform(-1, 1)
				mat = Mat3()
				mat.setRotateMatNormaxis(angleX, render.getRelativeVector(self.node, Vec3(0, 0, 1)))
				direction = mat.xformVec(direction)
				mat = Mat3()
				mat.setRotateMatNormaxis(angleY, render.getRelativeVector(self.node, Vec3(1, 0, 0)))
				direction = mat.xformVec(direction)
			
			#self.actor.body.addForce(engine.impulseToForce(direction.getX() * -self.force, direction.getY() * -self.force, direction.getZ() * -self.force))
			
			p.add(net2.StandardVec3(direction))
			
			entity = None
			hitPos = None
			if direction.length() > 0:
				entity, hitPos, normal, queue = self.bulletTest(aiWorld, entityGroup, origin, direction)
			if hitPos == None:
				p.add(net.Boolean(False)) # Bullet didn't hit anything
			else:
				p.add(net.Boolean(True)) # Bullet hit something
				p.add(net2.StandardVec3(hitPos))
				if entity != None:
					p.add(net.Boolean(True))
					p.add(net.Uint8(entity.getId()))
					totalDamage = self.damage * max(0, 1 - (vector.length() / 200)) * max(0, normal.dot(-direction) + 0.1)
					p.add(net.Uint16(totalDamage))
				
					pinned = False
					if isinstance(entity, entities.BasicDroid):
						for i in range(queue.getNumEntries()):
							entry = queue.getEntry(i)
							pos = entry.getSurfacePoint(render)
							testEntity = entityGroup.getEntityFromEntry(entry)
							if testEntity == None and (pos - hitPos).length() < 5:
								p.add(net.Boolean(True))
								p.add(net2.HighResVec3(pos))
								pinned = True
								break
					if not pinned:
						p.add(net.Boolean(False))
						p.add(net2.HighResVec3(hitPos))
				else:
					p.add(net.Boolean(False))
		else:
			p.add(net.Boolean(False))
		self.firing = False
		return p

	def clientUpdate(self, aiWorld, entityGroup, iterator = None):
		Gun.clientUpdate(self, aiWorld, entityGroup, iterator)

		if iterator != None:
			if net.Boolean.getFrom(iterator): # We're firing
				self.lastFire = engine.clock.getTime()
				
				if self.active:
					self.pistolSound.play(entity = self.actor)
					self.light.add()
				
				direction = net2.StandardVec3.getFrom(iterator)
				
				if net.Boolean.getFrom(iterator): # Bullet hit something
					hitPos = net2.StandardVec3.getFrom(iterator)
					if self.active:
						origin = self.getPosition() + (direction * random() * 4)
						pos = hitPos - (direction * random() * 4)
						self.tracer.draw(origin, pos)
					
					if net.Boolean.getFrom(iterator):
						entityId = net.Uint8.getFrom(iterator)
						entity = entityGroup.getEntity(entityId)
						damage = net.Uint16.getFrom(iterator)
						pin = False
						pin = net.Boolean.getFrom(iterator) # Whether we're pinning the entity against the wall
						pinPos = net2.HighResVec3.getFrom(iterator)
						if entity != None:
							if pin:
								self.pinSound.play(position = hitPos)
								if not entity.pinned:
									entity.pin(hitPos - (direction * entity.radius))
								
							spike = entities.Spike(pinPos, direction)
							spike.attachTo(entity)
							entityGroup.addGraphicsObject(spike)
								
							entity.damage(self.actor, damage)
							if isinstance(entity, entities.Actor):
								particles.add(particles.HitRegisterParticleGroup(hitPos - direction, entity.team.color, damage * 2 / self.damage))
							else:
								particles.add(particles.SparkParticleGroup(hitPos))
					else:
						particles.add(particles.SparkParticleGroup(hitPos))
						entityGroup.addGraphicsObject(entities.Spike(hitPos, direction))
						self.ricochetSound.play(position = hitPos)
		if engine.clock.getTime() - self.lastFire > 0.1:
			self.light.remove()
		elif self.active:
			self.light.setPos(self.getPosition())
			self.light.setAttenuation((0, 0, 0.005 + math.pow((engine.clock.getTime() - self.lastFire), 2) * 8))
	
	def delete(self):
		self.pistolSound.delete()
		self.tracer.delete()
		self.light.remove()
		Gun.delete(self)

types = {CHAINGUN:ChainGun, PISTOL:Pistol, SHOTGUN:Shotgun, SNIPER:SniperRifle, MELEE_CLAW:MeleeClaw, GRENADE_LAUNCHER:GrenadeLauncher, MOLOTOV_THROWER:MolotovThrower}