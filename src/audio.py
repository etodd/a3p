from direct.showbase.DirectObject import DirectObject
from pandac.PandaModules import *
from random import randint, random, uniform
import math
import engine

from random import choice

from PatchedAudio3DManager import Audio3DManager

class SoundPlayer:
	"The client interface for playing sounds."
	def __init__(self, name):
		self.name = name
		self.soundGroup = soundGroups[self.name]
		self.activeSound = None
		self.entity = None
		self.position = None
		self.active = True
	def setEntity(self, entity):
		self.entity = entity
	def play(self, entity = None, position = None):
		"Plays a sound at the given position. If an ObjectEntity is given, attaches the sound to that ObjectEntity."
		if not enabled or not self.active:
			return
		self.position = position
		self.entity = entity
		self.activeSound = self.soundGroup.get()
		if self.entity != None and self.entity.active:
			manager.attachSoundToObject(self.activeSound, self.entity.node)
		elif self.position != None:
			self.activeSound.set3dAttributes(self.position.getX(), self.position.getY(), self.position.getZ(), 0, 0, 0)
		self.activeSound.play()
	def isPlaying(self):
		if self.activeSound != None:
			return self.activeSound.status() == 2
		return False
	def stop(self):
		if self.activeSound != None:
			self.activeSound.stop()
	def delete(self):
		"Only needs to be called if this sound was attached to an entity."
		if self.activeSound != None:
			self.active = False
			self.activeSound.stop()
			manager.detachSound(self.activeSound)

soundGroups = dict()
manager = None
enabled = True

def init(dropOffFactor, distanceFactor, dopplerFactor):
	"Loads all common sounds and initializes the Panda3D Audio3DManager."
	global manager
	# Setup audio
	manager = Audio3DManager(base.sfxManagerList[0], camera)
	manager.setDropOffFactor(dropOffFactor)
	manager.setDistanceFactor(distanceFactor)
	addSoundGroup(SoundGroup("chaingun", ["sounds/chaingun.ogg"], volume = 0.5))
	addSoundGroup(SoundGroup("shotgun", ["sounds/shotgun.ogg"], volume = 1.0))
	addSoundGroup(SoundGroup("large-explosion", ["sounds/large-explosion.ogg", "sounds/large-explosion2.ogg", "sounds/large-explosion3.ogg", "sounds/large-explosion4.ogg", "sounds/large-explosion5.ogg"], volume = 1.0))
	addSoundGroup(SoundGroup("sniper-rifle", ["sounds/sniper-rifle.ogg"], volume = 1.0))
	addSoundGroup(SoundGroup("grenade", ["sounds/grenade.ogg", "sounds/grenade2.ogg", "sounds/grenade3.ogg"], volume = 1.0))
	addSoundGroup(SoundGroup("grenade-launch", ["sounds/grenade-launch.ogg"], volume = 0.3))
	addSoundGroup(SoundGroup("ricochet", ["sounds/ricochet1.ogg", "sounds/ricochet2.ogg", "sounds/ricochet3.ogg", "sounds/ricochet4.ogg", "sounds/ricochet5.ogg"], volume = 0.15))
	addSoundGroup(SoundGroup("grenade-bounce", ["sounds/grenade-bounce.ogg"], volume = 0.2))
	addSoundGroup(SoundGroup("claw", ["sounds/claw.ogg"], volume = 1.0))
	addSoundGroup(SoundGroup("claw-fail", ["sounds/claw-fail.ogg"], volume = 1.0))
	addSoundGroup(SoundGroup("claw-retract", ["sounds/claw-retract.ogg"], volume = 1.0))
	addSoundGroup(SoundGroup("spawn", ["sounds/spawn.ogg"], volume = 1.0))
	addSoundGroup(SoundGroup("shield", ["sounds/shield.ogg"], volume = 1.0))
	addSoundGroup(SoundGroup("kamikaze-special", ["sounds/kamikaze-special.ogg"], volume = 1.0))
	addSoundGroup(SoundGroup("rocket", ["sounds/rocket.ogg"], volume = 1.0))
	addSoundGroup(SoundGroup("reload", ["sounds/reload.ogg"], volume = 0.3))
	addSoundGroup(SoundGroup("reload-beep", ["sounds/reload-beep.ogg"], volume = 0.3))
	addSoundGroup(SoundGroup("alarm", ["sounds/alarm.ogg"], volume = 0.25))
	addSoundGroup(SoundGroup("glass-shatter", ["sounds/glass-shatter1.ogg", "sounds/glass-shatter2.ogg", "sounds/glass-shatter3.ogg"], volume = 1.0))
	addSoundGroup(SoundGroup("pistol", ["sounds/pistol.ogg"], volume = 1.0))
	addSoundGroup(SoundGroup("pod-landing", ["sounds/pod-landing.ogg"], volume = 1.0))
	addSoundGroup(SoundGroup("change-weapon", ["sounds/change-weapon.ogg"], volume = 0.1))

def enable():
	global enabled
	enabled = True

def disable():
	global enabled
	enabled = False

def addSoundGroup(soundGroup):
	"Adds a sound group to the global list."
	global soundGroups
	soundGroups[soundGroup.name] = soundGroup

class SoundGroup(DirectObject):
	"""A SoundGroup is a collection of similar sounds. When the SoundGroup is played, one of the sounds is selected at random."""
	def __init__(self, name, soundFiles, volume = 1.0):
		self.name = name
		self.soundFiles = soundFiles
		self.volume = volume
		self.sounds = dict()
		for file in self.soundFiles:
			self.sounds[file] = []
			for _ in range(4):
				sound = manager.loadSfx(file)
				sound.setVolume(self.volume)
				self.sounds[file].append(sound)

	def get(self):
		sounds = self.sounds[choice(self.soundFiles)]
		for sound in sounds:
			if sound.status() != 2:
				return sound
		sound.stop()
		return sound

class FlatSound(DirectObject):
	def __init__(self, file, volume = 1.0):
		self.sound = loader.loadSfx(file)
		self.filename = file
		self.setVolume(volume)
	
	def setVolume(self, volume):
		self.sound.setVolume(volume)
	
	def getVolume(self):
		return self.sound.getVolume()
	
	def isPlaying(self):
		return self.sound.status() == 2
	
	def play(self):
		if enabled:
			self.sound.play()
	
	def setLoop(self, loop):
		self.sound.setLoop(loop)
	
	def stop(self):
		self.sound.stop()