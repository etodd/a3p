import engine
from pandac.PandaModules import *
from random import random, uniform

particleGroups = []

def init():
	ParticleGroup.init()

def update():
	deletedParticleGroups = []
	for particleGroup in particleGroups:
		particleGroup.update()
		if not particleGroup.active:
			deletedParticleGroups.append(particleGroup)
	for particleGroup in deletedParticleGroups:
		particleGroups.remove(particleGroup)

def add(group):
	particleGroups.append(group)

def delete():
	global particleGroups
	for particleGroup in particleGroups:
		particleGroup.delete()
	del particleGroups[:]
	ParticleGroup.clear()
	ParticleGroup.end()

class ParticleGroup:
	# Plate IDs:
	# 0 - src-smoke.png
	# 1 - src-highlight.png
	# 2 - src-damage.png
	# 3 - empty
	# 4 - src-enemy-selector.png
	# 5 - src-fire.png
	# 6 - src-fire2.png
	# 7 - 
	# 8 - 
	frames = []
	generator = None
	generatorNode = None
	begun = False
	def __init__(self):
		self.active = True
		self.position = None
		self.lastPositionUpdate = engine.clock.getTime()
		self.lastPosition = None
	
	@staticmethod
	def init():
		if not engine.isDaemon:
			ParticleGroup.frames.append(Vec4(0, 0.6666, 0.3333, 0.3333)) # Smoke
			ParticleGroup.frames.append(Vec4(0.3333, 0.6666, 0.3333, 0.3333)) # Highlight
			ParticleGroup.frames.append(Vec4(0.6666, 0.6666, 0.3333, 0.3333)) # Damage
			ParticleGroup.frames.append(Vec4(0, 0.3333, 0.3333, 0.3333)) # Empty
			ParticleGroup.frames.append(Vec4(0.3333, 0.3333, 0.3333, 0.3333)) # Enemy selector
			ParticleGroup.frames.append(Vec4(0.6666, 0.3333, 0.3333, 0.3333)) # Flames frame 1
			ParticleGroup.frames.append(Vec4(0, 0.6666, 0.3333, 0.3333)) # Flames frame 2
			ParticleGroup.frames.append(Vec4(0.3333, 0.6666, 0.3333, 0.3333)) # Drop pod locator
			ParticleGroup.generator = MeshDrawer()
			ParticleGroup.generator.setBudget(10000)
			ParticleGroup.generatorNode = ParticleGroup.generator.getRoot()
			ParticleGroup.generatorNode.reparentTo(render)
			ParticleGroup.generatorNode.setDepthWrite(False)
			ParticleGroup.generatorNode.setTransparency(True)
			ParticleGroup.generatorNode.setTwoSided(False)
			ParticleGroup.generatorNode.setTexture(loader.loadTexture("images/plate.png"))
			ParticleGroup.generatorNode.setBin("fixed", 100)
			ParticleGroup.generatorNode.setLightOff(True)
			ParticleGroup.generatorNode.setShaderOff()
			ParticleGroup.generatorNode.node().setBounds(BoundingSphere((0, 0, 0), 1000)) 
			ParticleGroup.generatorNode.node().setFinal(True)
			
	@staticmethod
	def begin():
		if not engine.isDaemon:
			if ParticleGroup.generator == None:
				ParticleGroup.init()
			if not ParticleGroup.begun:
				ParticleGroup.generator.begin(base.cam, render)
				ParticleGroup.begun = True
		
	@staticmethod
	def end():
		if ParticleGroup.begun:
			ParticleGroup.generator.end()
			ParticleGroup.begun = False
	
	@staticmethod
	def clear():
		ParticleGroup.generator = None
		if ParticleGroup.generatorNode != None:
			ParticleGroup.generatorNode.removeNode()
		ParticleGroup.begun = False
	
	def setPosition(self, pos):
		if self.position != None:
			self.lastPosition = Vec3(self.position)
		self.position = Vec3(pos)
		self.lastPositionUpdate = engine.clock.getTime()
		
	def update(self):
		pass
		
	def delete(self):
		self.active = False

class SmokeParticleGroup(ParticleGroup):
	generator = None
	generatorNode = None
	def __init__(self, position):
		ParticleGroup.__init__(self)
		self.lifeTime = 5.0
		self.positions = []
		self.spawnTimes = []
		self.initialAngles = []
		self.lastSpawn = engine.clock.getTime()
		self.interval = 2.0
	
	def spawnParticle(self, pos):
		self.positions.append(pos)
		self.spawnTimes.append(engine.clock.getTime())
		self.initialAngles.append(random() * 360)
		self.lastSpawn = engine.clock.getTime()
		
	def update(self):
		ParticleGroup.update(self)
		if engine.clock.getTime() - self.lastSpawn >= self.lifeTime:
			self.delete()
		if self.active and ParticleGroup.begun:
			if engine.clock.getTime() - self.lastPositionUpdate < 0.1:
				if self.lastPosition != None:
					vector = self.position - self.lastPosition
					distance = vector.length()
					if distance > 0:
						vector /= distance
						for f in engine.frange(0.0, distance, self.interval):
							self.spawnParticle(self.position + (vector * f))
					else:
						self.spawnParticle(self.position)

			for i in range(len(self.positions)):
				blend = (engine.clock.getTime() - self.spawnTimes[i]) / self.lifeTime
				if blend <= 1.0:
					ParticleGroup.generator.particle(self.positions[i], ParticleGroup.frames[0], 1.0 + (blend * 4.0), Vec4(1, 1, 1, max(0, 0.8 - (blend * 0.8))), self.initialAngles[i] + (blend * 45))

class FireParticleGroup(ParticleGroup):
	generator = None
	generatorNode = None
	def __init__(self, position):
		ParticleGroup.__init__(self)
		self.lifeTime = 0.75
		self.positions = []
		self.spawnTimes = []
		self.initialAngles = []
		self.finalAngles = []
		self.initialSizes = []
		self.finalHeights = []
		self.lastSpawn = engine.clock.getTime()
		self.interval = 0.5
		self.isIndependent = False
	
	def spawnParticle(self, pos):
		self.positions.append(pos)
		self.spawnTimes.append(engine.clock.getTime())
		self.lastSpawn = engine.clock.getTime()
		angle = random() * 360
		self.initialAngles.append(angle)
		self.initialSizes.append(0.5 + (random() * 0.8))
		self.finalAngles.append(angle + ((random() - 0.5) * 180))
		self.finalHeights.append(2.0 + (random() * 1.5))
		
	def update(self):
		ParticleGroup.update(self)
		if self.isIndependent and engine.clock.getTime() - self.lastSpawn >= self.lifeTime:
			self.delete()
		if self.active and ParticleGroup.begun:
			if engine.clock.getTime() - self.lastPositionUpdate < 0.1 and engine.clock.getTime() - self.lastSpawn > 0.01:
				if self.lastPosition != None:
					vector = self.position - self.lastPosition
					distance = vector.length()
					if distance > 0 and distance < 4.0:
						vector /= distance
						points = engine.frange(0.0, distance, self.interval)
						for f in points:
							self.spawnParticle(self.position + (vector * f) + (Vec3(uniform(-1.0, 1.0), uniform(-1.0, 1.0), uniform(-1.0, 1.0)) * 0.5))
					else:
						self.spawnParticle(self.position + Vec3(uniform(-1.0, 1.0), uniform(-1.0, 1.0), 0) * 0.5)
			for i in range(len(self.positions)):
				blend = (engine.clock.getTime() - self.spawnTimes[i]) / self.lifeTime
				if blend <= 1.0:
					ParticleGroup.generator.blendedParticle(self.positions[i] + Vec3(0, 0, blend * self.finalHeights[i]), ParticleGroup.frames[5], ParticleGroup.frames[6], blend, self.initialSizes[i] - (blend * 0.5), Vec4(1, 1, 1, (1.0 - blend) * 0.75), ((1.0 - blend) * self.initialAngles[i]) + (blend * self.finalAngles[i]))

class WaypointParticleGroup(ParticleGroup):
	def __init__(self):
		ParticleGroup.__init__(self)
		self.size = 0.5
		self.color = Vec4(1, 1, 1, 1)
		
	def draw(self, pos):
		if self.active and ParticleGroup.begun:
			ParticleGroup.generator.billboard(pos, ParticleGroup.frames[1], self.size, self.color)
	
	def drawLink(self, a, b):
		if self.active and ParticleGroup.begun:
			ParticleGroup.generator.segment(a, b, ParticleGroup.frames[1], .1, self.color)

class BulletTracerParticleGroup(ParticleGroup):
	def __init__(self):
		ParticleGroup.__init__(self)
		self.color = Vec4(1, 0.8, 0.6, 1)
	
	def draw(self, position1, position2):
		if ParticleGroup.begun:
			ParticleGroup.generator.segment(Vec3(position1), Vec3(position2), ParticleGroup.frames[1], .06, self.color)
			
class SparkParticleGroup(ParticleGroup):
	def __init__(self, position, numParticles = 50, speed = 15.0, lifeTime = 0.2, size = 4.0):
		ParticleGroup.__init__(self)
		self.numParticles = numParticles
		
		self.position = Vec3(position)
		self.spawnTime = engine.clock.getTime()
		self.lifeTime = lifeTime + uniform(lifeTime * -0.3, lifeTime * 0.3)
		self.positions = []
		self.velocities = []
		self.color = Vec4(1, 0.8, 0.6, 1)
		for _ in range(self.numParticles):
			self.positions.append(Vec3(self.position))
		for _ in range(self.numParticles):
			self.velocities.append(Vec3(uniform(-speed, speed), uniform(-speed, speed), uniform(-speed, speed)))

	def update(self):
		ParticleGroup.update(self)
		if engine.clock.getTime() - self.spawnTime >= self.lifeTime:
			self.delete()
		if self.active and ParticleGroup.begun:
			self.color.setW(1 - ((engine.clock.getTime() - self.spawnTime) / self.lifeTime))
			for i in range(self.numParticles):
				self.velocities[i].setZ(self.velocities[i].getZ() - (engine.clock.timeStep * 40.0))
				self.positions[i] += self.velocities[i] * engine.clock.timeStep
				ParticleGroup.generator.segment(self.positions[i], self.positions[i] + (self.velocities[i] * 0.03), ParticleGroup.frames[1], .02, self.color)

class UnitHighlightParticleGroup(ParticleGroup):
	@staticmethod
	def draw(pos, color, size):
		if ParticleGroup.begun:
			ParticleGroup.generator.billboard(Vec3(pos), ParticleGroup.frames[1], size, color)

class EnemySelectorParticleGroup(ParticleGroup):
	color = Vec4(1, 1, 1, 0.3)
	@staticmethod
	def draw(pos):
		if ParticleGroup.begun:
			ParticleGroup.generator.billboard(Vec3(pos), ParticleGroup.frames[4], 2.5, EnemySelectorParticleGroup.color)

class HitRegisterParticleGroup(ParticleGroup):
	def __init__(self, position, color, size = 0.5):
		ParticleGroup.__init__(self)
		self.size = size
		self.position = Vec3(position)
		self.spawnTime = engine.clock.getTime()
		self.lifeTime = 0.25 * size
		self.color = color
		self.angle = random() * 360

	def update(self):
		ParticleGroup.update(self)
		if engine.clock.getTime() - self.spawnTime >= self.lifeTime:
			self.delete()
		if self.active and ParticleGroup.begun:
			blend = (engine.clock.getTime() - self.spawnTime) / self.lifeTime
			ParticleGroup.generator.particle(self.position, ParticleGroup.frames[2], (self.size * 0.25) + (blend * self.size), Vec4(self.color.getX(), self.color.getY(), self.color.getZ(), 1.25 - blend), self.angle)
	
class ExplosionParticleGroup(ParticleGroup):
	def __init__(self, position, numParticles = 50, lifeTime = 3, size = 4.0):
		ParticleGroup.__init__(self)
		self.numParticles = numParticles
		
		self.position = Vec3(position)
		
		self.light = engine.Light(color = Vec4(1.0, 0.7, 0.4, 1), attenuation = Vec3(0, 0, 0.0007))
		self.light.add()
		self.light.setPos(self.position)
		
		self.spawnTime = engine.clock.getTime()
		self.lifeTime = lifeTime + uniform(lifeTime * -0.3, lifeTime * 0.3)
		self.lightLifeTime = 1.5
		self.positions = []
		self.initialAngles = []
		radius = 5
		for _ in range(self.numParticles):
			self.positions.append(Vec3(self.position) + Vec3(uniform(-radius, radius), uniform(-radius, radius), uniform(-radius, radius)))
			self.initialAngles.append(random() * 360)

	def update(self):
		ParticleGroup.update(self)
		if engine.clock.getTime() - self.spawnTime >= self.lifeTime:
			self.delete()
		if engine.clock.getTime() - self.spawnTime >= self.lightLifeTime:
			self.light.remove()
		if self.active and ParticleGroup.begun:
			blend = (engine.clock.getTime() - self.spawnTime) / self.lifeTime
			blend2 = (engine.clock.getTime() - self.spawnTime) / self.lightLifeTime
			self.light.setColor(Vec4(1.0 * (1.0 - blend2), 0.7 * (1.0 - blend2), 0.4 * (1.0 - blend2), 1))
			for i in range(self.numParticles):
				ParticleGroup.generator.particle(self.positions[i], ParticleGroup.frames[0], 1.5 + (blend * 5.0), Vec4(1, 1, 1, max(0, 0.5 - (blend * 0.5))), self.initialAngles[i] + (blend * 45))

	def delete(self):
		ParticleGroup.delete(self)
		self.light.remove()