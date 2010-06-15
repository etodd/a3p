from pandac.PandaModules import *
from direct.showbase.DirectObject import DirectObject
from direct.gui.OnscreenText import OnscreenText
from direct.distributed.PyDatagram import PyDatagram
from direct.distributed.PyDatagramIterator import PyDatagramIterator
from direct.gui.OnscreenImage import OnscreenImage

import ai
import entities
import ui
import net
import controllers
import components
import engine
import sys
import audio
import online
import net2
import particles

import gc
from random import uniform, choice

# Game type constants
DEATHMATCH = 0
SURVIVAL = 1

deathmatchMaps = ["impact", "verdict", "orbit", "arena", "complex", "grid"]
survivalMaps = ["matrix"]

firstBoot = True

class GameInfo(DirectObject): # Data structure containing game setup information
	def __init__(self):
		self.mapFile = ""
		self.teamId = 0
		self.scoreLimit = 0
		self.enableRespawn = True
		self.type = DEATHMATCH
	
class Backend(DirectObject):
	def __init__(self, username):
		engine.log.info("Initializing game.")
		self.type = DEATHMATCH
		self.active = True
		self.map = engine.Map()
		self.aiWorld = ai.World()
		self.netManager = net2.NetManager()
		self.entityGroup = entities.EntityGroup(self.netManager)
		self.game = None
		self.lastGc = engine.clock.time
		self.scoreLimit = 3000
		self.username = username
		self.enableRespawn = True
		self.startTime = engine.clock.time
		self.gameOver = False
		self.matchLimit = 1
		self.matchNumber = 0
		self.connected = True # All backends are connected by default. Clients can be disconnected though.

	def setGame(self, game):
		self.game = game

	def update(self):
		if self.active:
			if engine.clock.time - self.lastGc > 10:
				gc.collect()
				self.lastGc = engine.clock.time
			self.aiWorld.update()
			self.netManager.update(self)
			self.entityGroup.update()
			if self.map != None:
				self.map.update()

	def loadMap(self, mapFile):
		self.reset()
		if self.game != None:
			self.game.reset()
		engine.log.info("Loading map: " + mapFile)
		self.map.load(mapFile, self.aiWorld, self.entityGroup)
		engine.log.info("Map loaded: " + self.map.filename)

	def reset(self):
		self.gameOver = False
		self.entityGroup.delete()
		del self.entityGroup
		self.map.delete()
		self.aiWorld.delete()
		del self.aiWorld
		del self.map
		engine.clearLights()
		self.entityGroup = entities.EntityGroup(self.netManager)
		self.aiWorld = ai.World()
		self.map = engine.Map()
		self.matchNumber = 0
	
	def delete(self):
		self.entityGroup.delete()
		self.aiWorld.delete()
		self.map.delete()
		engine.clearLights()
		particles.clear()
		self.netManager.delete()
		del self.entityGroup
		del self.aiWorld
		del self.map
		del self.netManager
		self.active = False
		self.ignoreAll()

class ServerBackend(Backend):
	def __init__(self, registerHost = True, username = "Unnamed"):
		Backend.__init__(self, username)
		self.type = DEATHMATCH
		net.context.listen()
		engine.log.info("Listening on port " + str(net.context.port))
		self.lastRegister = -60
		self.registerHost = registerHost
		self.clients = []
		self.accept("server-new-connection", self.newConnectionCallback)
		self.accept("disconnect", self.clientDisconnectedCallback)
		net.context.disconnectCallback = self.clientDisconnectedCallback
		self.accept("change-map", self.loadMap)
		self.numClients = 0
		self.endOnReachingScoreLimit = True
		self.accept("lobby-confirm-register", self.lobbyServerRegistrationCallback)
		self.accept("client-ready", self.clientReadyCallback)
		self.registrationConfirmed = False
	
	def getPlayerCounts(self):
		livePlayers = 0
		deadPlayers = 0
		for team in self.entityGroup.teams:
			player = team.getPlayer()
			if player != None:
				if player.active:
					dist = -1
					pos = player.getPosition()
					for platform in self.map.platforms:
						d = (pos - platform.getPosition()).length()
						if dist == -1 or d < dist:
							dist = d
					if dist > 3: # Players still on the winner platform don't count
						livePlayers += 1
				else:
					deadPlayers += 1
		return livePlayers, deadPlayers
	
	def loadMap(self, mapFile):
		Backend.loadMap(self, mapFile)
		net.context.resetConnectionStatuses()
		if self.game != None:
			self.game.setLocalTeamID(self.entityGroup.teams[0].getId())
			self.entityGroup.teams[0].setUsername(self.username)
		for client in net.context.activeConnections:
			net.context.activeConnections[client].ready = False
			self.sendSetupPackets(client)
	
	def setGame(self, game):
		Backend.setGame(self, game)
		self.numClients += 1 # Count ourselves as a client since we have a Game attached
		self.clients.append(("127.0.0.1", 0)) # Reserve a spot here; we are our own client.
	
	def lobbyServerRegistrationCallback(self):
		self.registrationConfirmed = True
	
	def update(self):
		Backend.update(self)
		if self.active:
			if self.gameOver and engine.clock.time - self.gameOverTime > 10:
				self.loadMap(choice(self.maps)) # self.maps is defined by our descendants
			if self.registerHost:
				registerDelay = 15.0 if self.registrationConfirmed else 2.0
				if engine.clock.time - self.lastRegister > registerDelay:
					self.registrationConfirmed = False
					online.registerHost(self.username, self.map.name, self.numClients, len(self.entityGroup.teams))
					self.lastRegister = engine.clock.time
			if self.endOnReachingScoreLimit:
				for team in self.entityGroup.teams:
					if team.score + sum([self.entityGroup.getEntity(x).score for x in team.getAllies()]) >= self.scoreLimit:
						self.endMatch(winningTeam = team)
						break
	
	def endMatch(self, winningTeam):
		self.entityGroup.resetMatch()
		self.matchNumber += 1
		winningTeam.matchScore += 1
		if winningTeam.matchScore > self.matchLimit / 2:
			self.gameOver = True
			self.gameOverTime = engine.clock.time
		p = net.Packet()
		p.add(net.Uint8(net.PACKET_ENDMATCH))
		p.add(net.Boolean(self.gameOver))
		engine.log.info("Broadcasted match end packet.")
		for team in self.entityGroup.teams:
			team.lastMatchPosition = len([x for x in self.entityGroup.teams if x.score > team.score])
			p.add(net.Uint8(team.getId()))
			p.add(net.Uint8(team.lastMatchPosition))
		net.context.broadcast(p)
		for team in self.entityGroup.teams:
			team.resetScore() # Just in case some packets came in late after the match ended.
		if self.game != None:
			self.game.endMatchCallback(winningTeam)

	def clientDisconnectedCallback(self, address):
		if address in self.clients:
			teamId = self.clients.index(address)
			team = self.entityGroup.teams[teamId]
			if team.getPlayer() != None and team.getPlayer().active:
				team.getPlayer().delete(self.entityGroup)
			engine.log.info("Client " + team.getUsername() + " (" + net.addressToString(address) + ") disconnected.")
			messenger.send("chat-outgoing", ["Console", team.getUsername() + " disconnected."])
			team.setLocal(True)
			team.setUsername("[empty]")
			team.resetScore()
			for actor in team.actors:
				actor.delete(self.entityGroup)
			self.clients[self.clients.index(address)] = None
			self.numClients -= 1
		else:
			engine.log.info("Client " + net.addressToString(address) + " disconnected.")
	
	def newConnectionCallback(self, client, username):
		if not client in self.clients: # We may receive multiple "new client" packets. We need to ignore all but the first.
			if self.numClients < len(self.entityGroup.teams):
				engine.log.info("New connection from " + username + " (" + net.addressToString(client) + ")")
				messenger.send("chat-outgoing", ["Console", username + " connected."])
				self.numClients += 1
				if None in self.clients:
					self.clients[self.clients.index(None)] = client
				else:
					self.clients.append(client)
				team = self.entityGroup.teams[self.clients.index(client)]
				team.setLocal(False)
				team.setUsername(username)
				self.sendSetupPackets(client)
				net.context.addClient(client)
			else:
				engine.log.info("Connection from " + username + " (" + net.addressToString(client) + ") refused. Server full.")
				p = net.Packet()
				p.add(net.Uint8(net.PACKET_SERVERFULL))
				net.context.send(p, client)
	
	def sendSetupPackets(self, client):
		engine.log.info("Constructing initialization packet for client " + net.addressToString(client))
		net.context.send(self.makeSetupPacket(client), client)
	
	def makeSetupPacket(self, client):
		p = net.Packet()
		p.add(net.Uint8(net.PACKET_SETUP))
		p.add(net.Uint8(self.entityGroup.teams[self.clients.index(client)].getId()))
		p.add(net.String(self.map.name))
		p.add(net.Uint16(self.scoreLimit))
		p.add(net.Boolean(self.enableRespawn))
		p.add(net.Uint8(self.type))
		# Teams have to be spawned first, so other entities can link to them.
		for entity in (x for x in self.entityGroup.entities.values() if isinstance(x, entities.TeamEntity)):
			p.add(entity.controller.buildSpawnPacket())
		return p
	
	def clientReadyCallback(self, client):
		engine.log.info("Client " + net.addressToString(client) + " completed loading. Sending spawn packets...")
		net.context.send(self.makeUberSpawnPacket(), client)
	
	def makeUberSpawnPacket(self):
		p = net.Packet()
		for entity in (x for x in self.entityGroup.entities.values() if not isinstance(x, entities.TeamEntity)):
			p.add(entity.controller.buildSpawnPacket())
		return p
	
	def delete(self):
		engine.log.info("Sending disconnect notifications...")
		p = net.Packet()
		p.add(net.Uint8(net.PACKET_DISCONNECT))
		net.context.broadcast(p)
		Backend.delete(self)

class PointControlBackend(ServerBackend):
	def __init__(self, registerHost = True, username = "Unnamed"):
		ServerBackend.__init__(self, registerHost, username)
		self.lastPodSpawnCheck = 0
		self.maps = deathmatchMaps # List of all valid maps for this gametype
	
	def update(self):
		ServerBackend.update(self)
		if engine.clock.time - self.lastPodSpawnCheck > 0.5:
			numPods = 1 if self.numClients <= 2 else 2
			self.lastPodSpawnCheck = engine.clock.time
			if len([1 for x in self.entityGroup.entities.values() if isinstance(x, entities.DropPod)]) < numPods\
			and len([1 for team in self.entityGroup.teams if team.getPlayer() != None and team.getPlayer().active]) > 0:
				self.spawnPod()
	
	def spawnPod(self):
		size = self.map.worldSize * 0.8
		queue = None
		while queue == None or queue.getNumEntries() == 0:
			queue = self.aiWorld.getCollisionQueue(Vec3(uniform(-size, size), uniform(-size, size), 100), Vec3(0, 0, -1))
			pos = None
			for i in range(queue.getNumEntries()):
				entry = queue.getEntry(i)
				if entry.getSurfaceNormal(render).getZ() >= 0:
					pos = entry.getSurfacePoint(render)
					break
			if pos == None or self.aiWorld.navMesh.getNode(pos) == None:
				queue = None
		pod = entities.DropPod(self.aiWorld.world, self.aiWorld.space)
		pod.controller.setFinalPosition(pos)
		self.entityGroup.spawnEntity(pod)
		self.lastPodSpawn = engine.clock.time

class SurvivalBackend(ServerBackend):
	def __init__(self, registerHost = True, username = "Unnamed"):
		ServerBackend.__init__(self, registerHost, username)
		self.maps = survivalMaps # List of all valid maps for this gametype
		self.type = SURVIVAL
		self.enableRespawn = False
		self.zombiesSpawned = False
		self.roundNumber = 0
		self.zombieLoadouts = [(components.SHOTGUN, None), (components.SNIPER, None), (components.GRENADE_LAUNCHER, None), (components.CHAINGUN, controllers.SHIELD_SPECIAL), (components.PISTOL, None), (components.GRENADE_LAUNCHER, controllers.SHIELD_SPECIAL)]
		self.zombieCounts = [4, 5, 5, 5, 9, 9]
		self.matchLimit = 100000
		self.zombieSpawnTime = 0
		self.scoreLimit = self.zombieCounts[0] * 150
		self.endOnReachingScoreLimit = False
		self.zombieTeam = None

	def loadMap(self, mapFile):
		ServerBackend.loadMap(self, mapFile)
		self.scoreLimit = self.zombieCounts[0] * 150
		self.zombieTeam = entities.TeamEntity()
		self.zombieTeam.color = Vec4(0, 0, 0, 1)
		self.zombieTeam.username = "Zombies"
		self.zombieTeam.isZombies = True
		self.zombieTeam.setLocal(True)
		self.zombieTeam.resetScore()
		self.zombieTeam.purchaseUnit(self.zombieLoadouts[self.matchNumber][0], self.zombieLoadouts[self.matchNumber][1])
		self.entityGroup.spawnEntity(self.zombieTeam)
		self.zombiesSpawned = False
		# Zombie team doesn't appear in entityGroup.teams or anywhere else.

	def endMatch(self, winningTeam):
		if self.matchNumber >= len(self.zombieLoadouts) or winningTeam.isAlly(self.zombieTeam):
			self.gameOver = True
			self.gameOverTime = engine.clock.time
		ServerBackend.endMatch(self, winningTeam)
		self.zombiesSpawned = False
		self.zombieTeam.resetScore()
		self.zombieTeam.purchaseUnit(self.zombieLoadouts[self.matchNumber][0], self.zombieLoadouts[self.matchNumber][1])
		self.scoreLimit = self.zombieCounts[self.matchNumber] * 150
	
	def update(self):
		ServerBackend.update(self)
		if self.numClients > 0:
			livePlayers, deadPlayers = self.getPlayerCounts()
			if not self.zombiesSpawned and livePlayers == self.numClients:
				for i in range(self.zombieCounts[self.matchNumber]):
					self.zombieTeam.respawn(self.zombieLoadouts[self.matchNumber][0], self.zombieLoadouts[self.matchNumber][1])
				self.zombiesSpawned = True
				self.zombieSpawnTime = engine.clock.time
			else:
				if deadPlayers == self.numClients:
					self.endMatch(self.zombieTeam)
				elif self.zombiesSpawned and engine.clock.time - self.zombieSpawnTime > self.zombieTeam.controller.spawnDelay + 1.0 and len([x for x in self.entityGroup.entities.values() if isinstance(x, entities.Actor) and x.team.isAlly(self.zombieTeam)]) == 0:
					highestScore = -1
					winningTeam = None
					for team in self.entityGroup.teams:
						if team.score > highestScore:
							highestScore = team.score
							winningTeam = team
					self.endMatch(winningTeam)

class ClientBackend(Backend):
	def __init__(self, serverAddress, username = "Unnamed"):
		Backend.__init__(self, username)
		self.type = DEATHMATCH
		engine.log.info("Connecting to " + serverAddress)
		net.context.connectToServer(serverAddress, username)
		self.connected = True
		self.accept("end-match", self.endMatchCallback)
		self.accept("disconnect", self.disconnectCallback)
		net.context.disconnectCallback = self.disconnectCallback
		self.accept("server-full", engine.exit)
		self.accept("client-connection-failed", engine.exit)
	
	def disconnectCallback(self, address):
		if net.compareAddresses(address, net.context.hostConnection.address): # We only care if the server disconnected
			engine.log.info("Server disconnected.")
			self.connected = False
		else:
			engine.log.info("Client " + address.getIpString() + " disconnected.")
		
	def loadMap(self, mapFile):
		Backend.loadMap(self, mapFile)
		p = net.Packet()
		p.add(net.Uint8(net.PACKET_CLIENTREADY))
		net.context.broadcast(p)
	
	def endMatchCallback(self, iterator):
		self.entityGroup.resetMatch()
		self.matchNumber += 1
		try:
			self.gameOver = net.Boolean.getFrom(iterator)
			winningTeam = None
			for i in range(len(self.entityGroup.teams)):
				id = net.Uint8.getFrom(iterator)
				team = self.entityGroup.getEntity(id)
				pos = net.Uint8.getFrom(iterator)
				if team != None:
					team.lastMatchPosition = pos
					if winningTeam == None and team.lastMatchPosition == 0: # Winning team
						winningTeam = team
				self.entityGroup.teams[i].resetScore() # Just in case some packets came in late after the match ended.
			if winningTeam != None:
				winningTeam.matchScore += 1
			self.game.endMatchCallback(winningTeam)
		except AssertionError:
			pass
	
	def delete(self):
		if self.connected:
			engine.log.info("Disconnecting...")
			p = net.Packet()
			p.add(net.Uint8(net.PACKET_DISCONNECT))
			net.context.broadcast(p)
			self.connected = False
		Backend.delete(self)
	
class Game(DirectObject):
	def __init__(self, backend):
		self.backend = backend
		
		self.matchInProgress = False
		
		self.unitSelector = None
		self.gameui = None
		visitorFont = loader.loadFont("menu/visitor2.ttf")
		self.promptText = OnscreenText(pos = (0, 0.85), scale = 0.1, fg = (0.7, 0.7, 0.7, 1), shadow = (0, 0, 0, 0.5), font = visitorFont, mayChange = True)
		self.scoreText = OnscreenText(pos = (0, 0.92), scale = 0.06, fg = (1, 1, 1, 1), shadow = (0, 0, 0, 0.5), font = visitorFont, mayChange = True)			
		self.winSound = audio.FlatSound("sounds/win.ogg")
		self.loseSound = audio.FlatSound("sounds/lose.ogg")
		self.errorSound = audio.FlatSound("sounds/error.ogg")
		
		self.playerLastActive = -1 # -1 means the player is currently active
		
		self.localTeam = None
		self.localTeamID = 0

		self.unitSelector = ui.UnitSelectorScreen(self.startMatch)
		if isinstance(self.backend, SurvivalBackend):
			self.unitSelector.disableUnits()
		if isinstance(self.backend, ClientBackend):
			self.accept("client-setup", self.gameInfoCallback)
			self.unitSelector.hide()
			self.promptText.setText("Connecting...")
			self.scoreText.hide()
		self.gameui = ui.GameUI()
		self.gameui.hide()
		self.accept("space", self.handleSpacebar)
		self.backend.setGame(self)
		self.spawnedOnce = False
		self.spectatorController = controllers.SpectatorController()
		self.buyScreenDisplayed = False

	def startMatch(self):
		# Must buy at least one weapon
		# Can't buy two of the same weapon
		if self.unitSelector.getPrimaryWeapon() == None or self.unitSelector.getPrimaryWeapon() == self.unitSelector.getSecondaryWeapon():
			self.errorSound.play()
			return
		
		if not self.matchInProgress:
			self.backend.map.hidePlatforms()
			self.spawnedOnce = False
			self.matchInProgress = True
			self.winSound.stop()
			self.loseSound.stop()
			
		self.gameui.show()
		self.unitSelector.hide()
		self.promptText.hide()
		self.scoreText.hide()

		weaponSelections = self.unitSelector.getUnitWeapons()
		specialSelections = self.unitSelector.getUnitSpecials()
		self.localTeam.clearUnits()
		for i in range(len(weaponSelections)):
			self.localTeam.purchaseUnit(weaponSelections[i], specialSelections[i])
		
		self.localTeam.setPrimaryWeapon(self.unitSelector.getPrimaryWeapon())
		self.localTeam.setSecondaryWeapon(self.unitSelector.getSecondaryWeapon())
		self.localTeam.setSpecial(self.unitSelector.getSpecial())
	
	def gameInfoCallback(self, iterator):
		engine.log.info("Processing game setup information...")
		info = GameInfo()
		try:
			info.teamId = net.Uint8.getFrom(iterator) # Find out which team we are on this computer
			info.mapFile = net.String.getFrom(iterator) # Map filename
			info.scoreLimit = net.Uint16.getFrom(iterator) # Score limit
			info.enableRespawn = net.Boolean.getFrom(iterator) # Whether we should respawn our local player
			info.type = net.Uint8.getFrom(iterator) # Game type
		except AssertionError:
			engine.log.warning("Error while processing game setup information.")
			return
		self.localTeamID = info.teamId
		self.backend.loadMap(info.mapFile)
		self.backend.scoreLimit = info.scoreLimit
		self.backend.enableRespawn = info.enableRespawn
		self.backend.type = info.type
		if self.backend.type == SURVIVAL:
			self.unitSelector.disableUnits()
		self.unitSelector.show()
	
	def localStart(self, map):
		self.backend.loadMap(map)
	
	def setLocalTeamID(self, id):
		self.localTeamID = id
		self.unitSelector.reset()
	
	def reset(self):
		self.unitSelector.reset()
		self.unitSelector.show()
		self.matchReset()
		
	def matchReset(self):
		self.promptText.setText("")
		self.promptText.show()
		self.scoreText.show()
		if len(self.backend.map.platforms) > 0:
			pos = self.backend.map.platforms[0].getPosition()
			base.camera.setPos(pos - Vec3(3, 22, 0))
			base.camera.lookAt(pos)
		else:
			base.camera.setPos(Vec3(3, 22, 15))
			base.camera.lookAt(Point3(0, 0, 12))
		self.gameui.hide()
		self.matchInProgress = False
		self.localTeam = None
		self.spawnedOnce = False
	
	def handleSpacebar(self):
		if not self.matchInProgress and self.localTeam != None:
			if self.unitSelector.hidden:
				# Delete the player on the platform and show the buy screen
				player = self.localTeam.getPlayer()
				if player != None and player.active:
					player.delete(self.backend.entityGroup)
				self.localTeam.setPlayer(None)
				self.showBuyScreen()
	
	def showBuyScreen(self):
		self.unitSelector.clearPurchases()
		if self.backend.gameOver:
			self.promptText.setText("Next game in 10 seconds...")
		else:
			self.promptText.hide()
			self.unitSelector.show()
		self.gameui.hide()
	
	def endMatchCallback(self, winningTeam):
		self.endMatch(winningTeam) # For object-oriented inheritance nonsense
	
	def endMatch(self, winningTeam):
		self.backend.map.showPlatforms()
		self.localTeam.platformSpawnPlayer(self.backend.map.platforms[self.localTeam.lastMatchPosition].getPosition() + Vec3(0, 0, 2))
		self.gameui.showUsernames()
		
		if self.localTeam.isAlly(winningTeam):
			self.winSound.play()
		else:
			self.loseSound.play()
		
		self.matchReset()
		
		self.updateScoreText()
		self.promptText.show()

		gameOverText = ""
		gameText = "match"
		if self.backend.gameOver:
			gameOverText = "Game over! "
			gameText = "game"
			
			# Find the team that won the most matches
			if isinstance(self.backend, PointControlBackend):
				winningTeam = None
				highScore = 0
				for team in self.backend.entityGroup.teams:
					if team.matchScore > highScore:
						highScore = team.matchScore
						winningTeam = team
		self.promptText.setText(gameOverText + winningTeam.username + " wins the " + gameText + "! Spacebar to continue.")
	
	def updateScoreText(self):
		text = ""
		for team in self.backend.entityGroup.teams:
			text += " " + team.username + ": " + str(team.matchScore) + " "
		self.scoreText.setText(text)
		self.scoreText.show()

	def update(self):
		if self.localTeam == None:
			team = self.backend.entityGroup.getEntity(self.localTeamID)
			if team != None:
				team.setLocal(True)
				self.localTeam = team
				self.localTeam.resetScore()
				self.localTeam.setUsername(self.backend.username)
				self.unitSelector.setTeam(team)
				self.gameui.setTeams(self.backend.entityGroup.teams, team)
				self.updateScoreText()
		else:
			self.localTeam.respawnUnits()
			player = self.localTeam.getPlayer()
			if player == None or not player.active:
				if self.playerLastActive == -1:
					self.playerLastActive = engine.clock.time
				if engine.clock.time - self.playerLastActive > 1.0:
					if not self.buyScreenDisplayed:
						self.showBuyScreen()
						self.buyScreenDisplayed = True
					elif self.unitSelector.hidden:
						self.spectatorController.serverUpdate(self.backend.aiWorld, self.backend.entityGroup, None)
					if self.unitSelector.hidden and self.matchInProgress and (self.backend.enableRespawn or not self.spawnedOnce):
						self.spawnedOnce = True
						self.localTeam.respawnPlayer()
			else:
				self.playerLastActive = -1
				self.buyScreenDisplayed = False
			if self.gameui != None:
				self.gameui.update(self.backend.scoreLimit)
				self.unitSelector.update()

	def delete(self):
		engine.log.info("Deleting game.")
		
		if self.unitSelector != None:
			self.unitSelector.delete()
		
		if self.gameui != None:
			self.gameui.delete()
		
		self.winSound.stop()
		self.loseSound.stop()
		if not self.promptText.isEmpty():
			self.promptText.destroy()
		if not self.scoreText.isEmpty():
			self.scoreText.destroy()

class Tutorial(Game):
	def __init__(self, backend, index):
		engine.log.info("Starting tutorial.")
		Game.__init__(self, backend)
		self.backend.matchLimit = 10
		self.promptText.hide()
		self.scoreText.hide()
		if index < 2:
			self.unitSelector.hide()
		self.tutorialScreens = []
		self.messages = ["Find and capture the drop pods to earn money!", "Use your units to help defeat the enemy.", "Try using your special abilities."]
		visitorFont = loader.loadFont("menu/visitor2.ttf")
		self.messageText = OnscreenText(pos = (-engine.aspectRatio + 0.05, 0.9), align = TextNode.ALeft, scale = 0.07, fg = (1, 1, 1, 1), shadow = (0, 0, 0, 0.5), font = visitorFont, mayChange = True)	
		for i in range(4):
			image = OnscreenImage(image = "images/part" + str(i + 1) + ".jpg", pos = (0, 0, 0), scale = (1680.0/1050.0, 1, 1))
			image.hide()
			self.tutorialScreens.append(image)
		self.tutorialIndex = index
		render.hide()
		self.tutorialScreens[self.tutorialIndex].show()
		self.messageText.hide()
		self.enemyAiUnits = [(components.CHAINGUN, None), (components.SNIPER, None), (components.PISTOL, None)]
		self.enemyTeam = None
		self.matchStartTime = -1
	
	def handleSpacebar(self):
		if self.tutorialIndex == 3:
			self.backend.connected = False # Exit tutorial
		else:
			if render.isHidden():
				render.show()
				self.backend.map.hidePlatforms()
				self.tutorialScreens[self.tutorialIndex].hide()
				if self.tutorialIndex == 2:
					self.showBuyScreen(True)
				else:
					self.startMatch()
			else:
				Game.handleSpacebar(self)
	
	def endMatch(self, winningTeam):
		if self.localTeam.isAlly(winningTeam):
			self.winSound.play()
		else:
			self.loseSound.play()
		self.matchReset()
	
	def reset(self):
		Game.reset(self)
		self.unitSelector.hide()
	
	def showBuyScreen(self, override = False):
		if self.tutorialIndex >= 2 and (self.matchInProgress or override):
			Game.showBuyScreen(self)
	
	def startMatch(self):
		if not self.matchInProgress:
			self.matchStartTime = engine.clock.time
			if self.tutorialIndex == 0:
				self.localTeam.setPrimaryWeapon(components.CHAINGUN)
				self.localTeam.setSecondaryWeapon(components.SNIPER)
				self.localTeam.setSpecial(None)
				self.enemyAiUnits = [(components.SHOTGUN, None)]
				self.backend.scoreLimit = 400
			elif self.tutorialIndex == 1:
				self.localTeam.setPrimaryWeapon(components.SHOTGUN)
				self.localTeam.setSecondaryWeapon(components.GRENADE_LAUNCHER)
				self.localTeam.setSpecial(None)
				self.localTeam.purchaseUnit(components.PISTOL, None)
				self.localTeam.purchaseUnit(components.MOLOTOV_THROWER, None)
				self.enemyAiUnits = choice([[(components.GRENADE_LAUNCHER, None), (components.SNIPER, None), (None, None)], [(components.CHAINGUN, None), (components.SHOTGUN, None), (None, None)], [(components.PISTOL, None), (components.SNIPER, None), (None, None)]])
				self.backend.scoreLimit = 800
			elif self.tutorialIndex == 2:
				self.enemyAiUnits = choice([[(components.SHOTGUN, controllers.CLOAK_SPECIAL), (components.SNIPER, None), (components.PISTOL, None)], [(components.GRENADE_LAUNCHER, controllers.CLOAK_SPECIAL), (components.CHAINGUN, controllers.SHIELD_SPECIAL), (None, None)], [(components.PISTOL, None), (components.MOLOTOV_THROWER, controllers.SHIELD_SPECIAL), (components.SHOTGUN, None)]])
				self.backend.scoreLimit = 1200
			if self.tutorialIndex <= 2:
				self.messageText.setText(self.messages[self.tutorialIndex])
				self.messageText.show()
				
			# Purchase AI units
			self.enemyTeam = self.backend.entityGroup.teams[1]
			self.enemyTeam.setLocal(True)
			self.enemyTeam.setUsername("Computer")
			self.enemyTeam.controller.tutorialMode = True
			self.enemyTeam.resetScore()
			for u in self.enemyAiUnits:
				self.enemyTeam.purchaseUnit(u[0], u[1])
		
		if self.tutorialIndex == 2:
			Game.startMatch(self)
		else:
			self.spawnedOnce = False
			self.matchInProgress = True
			self.winSound.stop()
			self.loseSound.stop()
			self.gameui.show()
			self.promptText.hide()
			self.scoreText.hide()
	
	def endMatchCallback(self, winningTeam):
		localTeam = self.localTeam
		Game.endMatchCallback(self, winningTeam)
		player = localTeam.getPlayer()
		if player != None and player.active:
			player.delete(self.backend.entityGroup)
		localTeam.setPlayer(None)
		self.messageText.hide()
		render.hide()
		self.tutorialIndex += 1
		self.tutorialScreens[self.tutorialIndex].show()
		localTeam.controller.addMoney(1000)
		self.unitSelector.hide()
		self.enemyTeam.resetScore()
		self.enemyTeam.score = 0
	
	def update(self):
		if self.matchStartTime != -1:
			if engine.clock.time - self.matchStartTime < 2:
				blend = (engine.clock.time - self.matchStartTime) / 2.0
				self.messageText["fg"] = (1, 1, 1, blend)
				self.messageText["scale"] = 0.06 + (1.0 - blend) * 0.4
			else:
				self.messageText["scale"] = 0.06
				self.messageText["fg"] = (1, 1, 1, 1)
				self.matchStartTime = -1
		noTeamYet = False
		if self.localTeam == None:
			noTeamYet = True
		Game.update(self)
		if noTeamYet and self.localTeam != None and self.tutorialIndex > 0: # We have a team now!
			self.localTeam.controller.addMoney(2000)
		if self.enemyTeam != None:
			self.enemyTeam.respawnUnits()

	def hideTutorialScreen(self):
		render.show()
		self.tutorialScreens[self.tutorialIndex].hide()
	
	def delete(self):
		engine.log.info("Ending tutorial.")
		Game.delete(self)
		self.messageText.destroy()
		for screen in self.tutorialScreens:
			screen.removeNode()

import math
class MainMenu(DirectObject):
	def __init__(self, skipIntro = False):
		render.show()
		engine.renderLit.show() # In case we just got back from the tutorial, which hides everything sometimes.
		engine.Mouse.hideCursor()
		self.backgroundSound = audio.FlatSound("menu/background.ogg", volume = 0.3)
		self.backgroundSound.setVolume(0)
		self.backgroundSound.setLoop(True)
		self.clickSound = audio.FlatSound("menu/click.ogg", volume = 0.3)
		self.active = True
		self.accept("escape", self.escape)
		self.accept("mouse1", self.click)
		self.cameraDistance = 20
	
		self.globe = loader.loadModel("menu/Globe")
		self.globe.reparentTo(render)
		self.globe.setTransparency(TransparencyAttrib.MAlpha)
		self.globe.setColor(Vec4(1, 1, 1, 0.6))
		self.globe.setTwoSided(True)
		self.globe.setRenderModeWireframe()
		
		self.mouse = engine.Mouse()
		
		self.overlay = camera.attachNewNode("overlay")
		self.overlay.setTransparency(TransparencyAttrib.MAlpha)
		self.overlay.setColor(Vec4(1, 1, 1, 0))
		self.overlay.setPos(0, 0, 0)
		self.overlay.setPos(0, self.cameraDistance, 0)
		
		self.overlay1 = loader.loadModel("menu/overlay1")
		self.overlay1.setScale(4)
		self.overlay1.setTwoSided(True)
		self.overlay1.setRenderModeWireframe()
		self.overlay1.reparentTo(self.overlay)
		
		self.overlay2 = loader.loadModel("menu/overlay2")
		self.overlay2.setScale(4)
		self.overlay2.setTwoSided(True)
		self.overlay2.setRenderModeWireframe()
		self.overlay2.reparentTo(self.overlay)
		
		self.overlay3 = loader.loadModel("menu/overlay3")
		self.overlay3.setScale(4)
		self.overlay3.setTwoSided(True)
		self.overlay3.setRenderModeWireframe()
		self.overlay3.setR(uniform(0, 360))
		self.overlay3.setP(uniform(0, 360))
		self.overlay3.setH(uniform(0, 360))
		self.overlay3.reparentTo(self.overlay)
		
		self.overlay4 = loader.loadModel("menu/overlay3")
		self.overlay4.setScale(4)
		self.overlay4.setTwoSided(True)
		self.overlay4.setRenderModeWireframe()
		self.overlay4.setH(uniform(0, 360))
		self.overlay4.setR(uniform(0, 360))
		self.overlay4.setP(uniform(0, 360))
		self.overlay4.reparentTo(self.overlay)
		
		self.text = loader.loadModel("menu/text")
		self.text.setScale(4)
		self.text.setTwoSided(True)
		self.text.reparentTo(self.overlay)
		
		self.selector = loader.loadModel("menu/selector")
		self.selector.setScale(4)
		self.selector.setTwoSided(True)
		self.selector.reparentTo(self.overlay)
		
		self.selectedItem = 0
		
		self.skyBox = loader.loadModel("menu/skybox")
		self.skyBox.setScale(self.cameraDistance + 2)
		self.skyBox.setRenderModeWireframe()
		self.skyBox.setTwoSided(True)
		self.skyBox.reparentTo(render)
		self.skyBox.setTransparency(TransparencyAttrib.MAlpha)
		self.skyBox.setColor(Vec4(1, 1, 1, 0))
		
		cmbg = CardMaker("background")
		size = 50
		cmbg.setFrame(-size * engine.aspectRatio, size * engine.aspectRatio, -size, size)
		self.background = camera.attachNewNode(cmbg.generate())
		self.background.setTexture(loader.loadTexture("menu/background.jpg"))
		self.background.setPos(0, size * 1.25, 0)
		self.background.setDepthWrite(False)
		
		self.belt = JunkBelt(5)
		
		self.angle = uniform(0, 360)
		self.period = 60
		self.uiAngle = 0
		
		self.logo = OnscreenImage(image = "menu/logo.png", pos = (0, 0, 0), scale = ((512.0 / 175.0) * 0.075, 0, 0.075))
		self.logo.setTransparency(TransparencyAttrib.MAlpha)
		self.logo.setColor(1, 1, 1, 0)
		self.logo.setBin("transparent", 0)
		
		self.loadingScreen = OnscreenImage(image = "menu/loading.jpg", pos = (0, 0, 0), scale = (1680.0 / 988.0, 0, 1))
		self.loadingScreen.hide()
		
		self.skipToEndOfTutorial = skipIntro
		
		self.introText = None
		global firstBoot
		self.introTime = 2
		if firstBoot and not skipIntro:
			self.introTime = 4
			visitorFont = loader.loadFont("menu/visitor2.ttf")
			self.introText = OnscreenText(pos = (0, 0), scale = 0.2, align = TextNode.ACenter, fg = (1, 1, 1, 1), shadow = (0, 0, 0, 0.5), font = visitorFont, mayChange = True, text = "et1337 presents")
		self.showLogin = firstBoot
		firstBoot = False
		
		self.hostList = ui.HostList(self.startClient)
		self.mapList = ui.MapList(self.startServer)
		self.loginDialog = ui.LoginDialog(self.setUsername)
		self.loginDialogShown = False
		
		self.introSound = audio.FlatSound("menu/intro.ogg", volume = 0.15)
		self.introSound.play()
		
		self.clientConnectAddress = None
		self.serverMapName = None
		self.serverMode = 0 # 0 for normal, 1 for tutorial
		self.serverGameType = 0 # 0 for deathmatch, 1 for survival
		
		self.username = "Unnamed"
		
		self.chatLog = ui.ChatLog(verticalOffset = -0.9, displayTime = 60.0, maxChats = 16, chatBoxAlwaysVisible = True, showOwnChats = False)
		self.chatLog.hide()
		self.chatConnection = GlobalChatConnection()
		
		self.startTime = -1
		self.goTime = -1
	
	def escape(self):
		if self.hostList.visible:
			self.hostList.hide()
		elif self.mapList.visible:
			self.mapList.hide()
	
	def startClient(self, host):
		self.clickSound.play()
		self.hostList.hide()
		self.loadingScreen.show()
		self.clientConnectAddress = host
		self.goTime = engine.clock.time
	
	def startServer(self, map, gametype):
		if not (self.serverMode == 1 and gametype == 1): # Tutorial works on Point Control maps.
			self.clickSound.play()
			self.mapList.hide()
			self.loadingScreen.show()
			self.serverMapName = map
			self.serverGameType = gametype
			self.goTime = engine.clock.time
	
	def setUsername(self, username):
		self.clickSound.play()
		self.username = username
		engine.savedUsername = self.username
		engine.saveConfigFile()
		self.loginDialog.hide()
		self.chatLog.setUsername(self.username)
		self.chatLog.show()

	def update(self):
		if not self.active:
			return
		net.context.readTick()
		if self.startTime == -1:
			self.startTime = engine.clock.time
		elapsedTime = engine.clock.time - self.startTime
		if elapsedTime < self.introTime:
			blend = elapsedTime / self.introTime
			if self.introText != None:
				self.introText["scale"] = 0.05 + (blend * 0.15)
				self.introText["fg"] = Vec4(1, 1, 1, (1 - blend)**.5)
				self.introText["shadow"] = Vec4(1, 1, 1, (1 - blend)**.5 * 0.5)
			self.angle += engine.clock.timeStep * (1 - blend)
			self.cameraDistance = 20 + (1 - blend)**2 * 200
		elif elapsedTime < self.introTime + 2:
			self.cameraDistance = 20
			blend = (elapsedTime - self.introTime) / 2
			self.overlay.setColor(Vec4(1, 1, 1, blend))
			self.logo.setColor(1, 1, 1, blend)
			self.skyBox.setColor(Vec4(1, 1, 1, blend))
			if not self.backgroundSound.isPlaying():
				self.backgroundSound.play()
			self.backgroundSound.setVolume(blend * 0.5)
			if self.introText != None:
				self.introText["fg"] = Vec4(1, 1, 1, 0)
		else:
			self.cameraDistance = 20
			self.overlay.setColor(Vec4(1, 1, 1, 1))
			self.logo.setColor(1, 1, 1, 1)
			self.skyBox.setColor(Vec4(1, 1, 1, 1))
			self.backgroundSound.setVolume(0.5)
		
		if elapsedTime > self.introTime:
			if not self.loginDialogShown and self.showLogin:
				self.loginDialog.show()
				self.loginDialogShown = True
			elif self.chatLog.hidden and not self.showLogin:
				self.chatLog.show()
		
		self.chatConnection.update()
		self.chatLog.update()
		
		self.uiAngle -= engine.clock.timeStep * 2
		self.text.setR(self.uiAngle)

		self.hostList.update()
		self.mapList.update()
		self.loginDialog.update()
		self.mouse.update()
		vector = Vec3(self.mouse.getX(), self.mouse.getY(), 0)
		vector.normalize()
		self.mouse.setX(vector.getX() * 0.1)
		self.mouse.setY(vector.getY() * 0.1)
		angle = math.degrees(math.atan2(-vector.getX(), -vector.getY())) + 180
		angle -= self.uiAngle
		while angle < 0:
			angle += 360
		while angle > 360:
			angle -= 360
		if not self.hostList.visible:
			self.selectedItem = int(angle/ 90.0)
		self.selector.setR(self.uiAngle + self.selectedItem * 90)
		
		self.overlay1.setR(self.overlay1.getR() - engine.clock.timeStep * 2)
		self.overlay2.setR(self.overlay2.getR() + engine.clock.timeStep * 2)
		self.overlay3.setH(self.overlay3.getH() + engine.clock.timeStep * 10)
		self.overlay4.setP(self.overlay4.getP() - engine.clock.timeStep * 10)
		self.belt.update()
		self.angle += engine.clock.timeStep * 0.025
		camera.setPos(math.cos(self.angle) * self.cameraDistance, math.sin(self.angle) * self.cameraDistance, math.cos(elapsedTime / 45 + 2) * 2)
		camera.lookAt(Point3(0, 0, 0))
		
		backend = None
		game = None
		
		if self.goTime != -1 and engine.clock.time - self.goTime > 0.25:
			if self.clientConnectAddress != None:
				self.delete()
				online.connectTo(self.clientConnectAddress)
				backend = ClientBackend(self.clientConnectAddress, self.username)
				game = Game(backend)
			elif self.serverMapName != None:
				if self.serverMode == 0:
					# Normal server mode
					self.delete()
					if self.serverGameType == 0:
						backend = PointControlBackend(True, self.username) # Deathmatch
					else:
						backend = SurvivalBackend(True, self.username) # Survival
					game = Game(backend)
					game.localStart(self.serverMapName)
				elif self.serverMode == 1:
					# Tutorial mode
					self.delete()
					backend = PointControlBackend(False, self.username)
					game = Tutorial(backend, 2 if self.skipToEndOfTutorial else 0)
					game.localStart(self.serverMapName)

		net.context.writeTick()
		return backend, game
	
	def click(self):
		if self.mapList.visible or self.hostList.visible or self.loginDialog.visible or engine.clock.time - self.startTime < self.introTime + 0.5:
			return
		self.clickSound.play()
		if self.selectedItem == 0: # Join
			self.hostList.show()
		elif self.selectedItem == 1: # Tutorial
			self.mapList.show()
			self.serverMode = 1
		elif self.selectedItem == 2: # Exit
			engine.exit()
		elif self.selectedItem == 3: # Host
			self.mapList.show()
			self.serverMode = 0
	
	def delete(self):
		self.loadingScreen.destroy()
		self.hostList.delete()
		self.mapList.delete()
		self.loginDialog.delete()
		self.active = False
		self.overlay.removeNode()
		self.belt.delete()
		self.background.removeNode()
		self.globe.removeNode()
		self.skyBox.removeNode()
		self.ignoreAll()
		self.logo.destroy()
		if self.introText != None:
			self.introText.destroy()
		self.introSound.stop()
		self.backgroundSound.stop()
		self.chatLog.delete()
		self.chatConnection.delete()

class JunkBelt:
	def __init__(self, radius):
		self.radius = radius
		junkFiles = ["menu/junk1", "menu/junk2", "menu/junk3", "menu/junk4", "menu/junk5"]
		self.models = []
		self.avels = []
		self.instances = []
		for file in junkFiles:
			node = loader.loadModel(file)
			node.setScale(0.01)
			node.setRenderModeWireframe()
			self.models.append(node)
		for _ in range(750):
			instance = render.attachNewNode("junk")
			angle = uniform(0, 2 * math.pi)
			height = uniform(-0.5, 0.5)
			radius = (uniform(0, 1)**3) * self.radius * 2
			radius += self.radius
			hpr = Vec3(uniform(0, 360), uniform(0, 360), uniform(0, 360))
			speed = 75
			self.avels.append(Vec3(uniform(-speed, speed), uniform(-speed, speed), uniform(-speed, speed)))
			instance.setPos(math.cos(angle) * radius, math.sin(angle) * radius, height)
			instance.setHpr(hpr)
			model = choice(self.models)
			model.instanceTo(instance)
			instance.reparentTo(render)
			self.instances.append(instance)

	def update(self):
		for i in range(len(self.instances)):
			self.instances[i].setHpr(self.instances[i].getHpr() + (self.avels[i] * engine.clock.timeStep))
	
	def delete(self):
		for instance in self.instances:
			instance.removeNode()
		for model in self.models:
			model.removeNode()

def _urlEncode(s):
		"""I don't want to depend on urllib."""
		HexCharacters = "0123456789abcdef"
		r = ""
		for c in s:
			if c in HexCharacters:
				o = ord(c)
				r += "%" + _cleanCharHex(c)
			else:
				r += c
		return r

def _cleanCharHex(c):
	HexCharacters = "0123456789abcdef"
	o = ord(c)
	r = HexCharacters[o / 16]
	r += HexCharacters[o % 16]
	return r

import time
class GlobalChatConnection(DirectObject):
	def __init__(self, host = "http://a3p.sourceforge.net/chat"):
		self.accept("chat-outgoing", self.sendChat)
		self.lastPoll = 0
		self.lastReceivedId = 0
		self.host = host
		self.firstRequest = True
	
	def sendChat(self, username, message):
		self.request(self.host + "/post.php", "user=" + _urlEncode(username) + "&msg=" + _urlEncode(message))
	
	def update(self):
		if engine.clock.time - self.lastPoll > 3.0:
			self.lastPoll = engine.clock.time
			self.request(self.host + "/get.php", "i=" + str(self.lastReceivedId), self.chatCallback)
	
	def chatCallback(self, data):
		lines = data.split("\n")
		self.lastReceivedId = lines[0]
		for line in lines[1:]:
			parts = line.split("\t")
			if len(parts) == 2:
				messenger.send("chat-incoming", parts)

	def request(self, url, params, callback = None):
		http = HTTPClient()
		channel = http.makeChannel(True)
		channel.beginPostForm(DocumentSpec(url), params)
		rf = Ramfile()
		channel.downloadToRam(rf)
		def downloadTask(channel, rf, downloadCallback, task):
			if channel.run():
				return task.cont
			if not channel.isDownloadComplete():
				if downloadCallback != None:
					downloadCallback("")
			else:
				if downloadCallback != None:
					downloadCallback(rf.getData())
			return task.done
		taskMgr.add(downloadTask, "urlRequest", appendTask = True, extraArgs = [channel, rf, callback])
	
	def delete(self):
		self.ignoreAll()