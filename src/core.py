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

import gc
from random import uniform, choice

# Game type constants
DEATHMATCH = 0
SURVIVAL = 1

deathmatchMaps = ["impact", "verdict", "orbit", "arena", "complex", "grid"]
survivalMaps = ["matrix"]

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
		self.lastGc = engine.clock.getRealTime()
		self.scoreLimit = 1500
		self.username = username
		self.enableRespawn = True
		self.startTime = engine.clock.getTime()
		self.gameOver = False
		self.matchLimit = 3
		self.matchNumber = 0

	def setGame(self, game):
		self.game = game

	def update(self):
		if self.active:
			if engine.clock.getRealTime() - self.lastGc > 10:
				gc.collect()
				self.lastGc = engine.clock.getRealTime()
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
		for client in net.context.activeConnections:
			net.context.activeConnections[client].ready = False
			self.sendSetupPackets(client)
		if self.game != None:
			self.game.setLocalTeamID(self.entityGroup.teams[0].getId())
	
	def setGame(self, game):
		Backend.setGame(self, game)
		self.numClients += 1 # Count ourselves as a client since we have a Game attached
		self.clients.append(("127.0.0.1", 0)) # Reserve a spot here; we are our own client.
	
	def lobbyServerRegistrationCallback(self):
		if not self.registrationConfirmed:
			engine.log.info("Lobby server registration succeeded!")
		self.registrationConfirmed = True
	
	def update(self):
		Backend.update(self)
		if self.active:
			if self.gameOver and engine.clock.getTime() - self.gameOverTime > 10:
				self.loadMap(choice(self.maps)) # self.maps is defined by our descendants
			if self.registerHost:
				registerDelay = 15.0 if self.registrationConfirmed else 2.0
				if engine.clock.getRealTime() - self.lastRegister > registerDelay:
					if not self.registrationConfirmed:
						engine.log.info("Lobby server registration failed.")
					self.registrationConfirmed = False
					online.registerHost(self.username, self.map.name)
					self.lastRegister = engine.clock.getRealTime()
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
			self.gameOverTime = engine.clock.getTime()
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
		self.podSpawnDelay = 20
		self.lastPodSpawn = 0
		self.lastPodSpawnCheck = 0
		self.maps = deathmatchMaps # List of all valid maps for this gametype
	
	def update(self):
		ServerBackend.update(self)
		if engine.clock.getTime() - self.lastPodSpawnCheck > 0.5:
			numPods = 1 if self.numClients <= 2 else 2
			self.lastPodSpawnCheck = engine.clock.getTime()
			if engine.clock.getTime() - self.lastPodSpawn > self.podSpawnDelay\
			and len([1 for x in self.entityGroup.entities.values() if isinstance(x, entities.DropPod)]) < numPods\
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
					pos = entry.getSurfacePoint(render) + Vec3(0, 0, 1.0)
					break
			if pos == None or self.aiWorld.navMesh.getNode(pos) == None:
				queue = None
		pod = entities.DropPod(controllers.DropPodController())
		pod.controller.setFinalPosition(pos)
		self.entityGroup.spawnEntity(pod)
		self.lastPodSpawn = engine.clock.getTime()

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
		self.zombieTeam.name = "Zombies"
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
			self.gameOverTime = engine.clock.getTime()
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
				self.zombieSpawnTime = engine.clock.getTime()
			else:
				if deadPlayers == self.numClients:
					self.endMatch(self.zombieTeam)
				elif self.zombiesSpawned and engine.clock.getTime() - self.zombieSpawnTime > self.zombieTeam.controller.spawnDelay + 1.0 and len([x for x in self.entityGroup.entities.values() if isinstance(x, entities.Actor) and x.team.isAlly(self.zombieTeam)]) == 0:
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
	
	def update(self):
		if self.active:
			if not self.connected:
				engine.exit()
			Backend.update(self)
	
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
		visitorFont = loader.loadFont("images/visitor2.ttf")
		self.promptText = OnscreenText(pos = (0, 0.85), scale = 0.1, fg = (0.7, 0.7, 0.7, 1), shadow = (0, 0, 0, 0.5), font = visitorFont, mayChange = True)
		self.scoreText = OnscreenText(pos = (0, 0.92), scale = 0.1, fg = (0.7, 0.7, 0.7, 1), shadow = (0, 0, 0, 0.5), font = visitorFont, mayChange = True)			
		self.winSound = audio.FlatSound("sounds/win.ogg")
		self.loseSound = audio.FlatSound("sounds/lose.ogg")
		self.errorSound = audio.FlatSound("sounds/error.ogg")
		
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

		self.accept("escape", engine.Mouse.showCursor)
		self.accept("space", self.handleSpacebar)
		self.backend.setGame(self)
		self.spawnedOnce = False
		self.spectatorController = controllers.SpectatorController()

	def startMatch(self):
		# Must buy at least one weapon
		# Can't buy two of the same weapon
		if self.unitSelector.getPrimaryWeapon() == None or self.unitSelector.getPrimaryWeapon() == self.unitSelector.getSecondaryWeapon():
			self.errorSound.play()
			return
		
		self.backend.map.hidePlatforms()
		
		self.spawnedOnce = False
		
		self.matchInProgress = True

		self.winSound.stop()
		self.loseSound.stop()

		weaponSelections = self.unitSelector.getUnitWeapons()
		specialSelections = self.unitSelector.getUnitSpecials()
		for i in range(len(weaponSelections)):
			self.localTeam.purchaseUnit(weaponSelections[i], specialSelections[i])
		
		self.localTeam.setPrimaryWeapon(self.unitSelector.getPrimaryWeapon())
		self.localTeam.setSecondaryWeapon(self.unitSelector.getSecondaryWeapon())
		self.localTeam.setSpecial(self.unitSelector.getSpecial())

		self.gameui.show()
		self.unitSelector.hide()
		self.promptText.hide()
		self.scoreText.hide()
	
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
		self.backend.map.showPlatforms()
		
		if self.localTeam.isAlly(winningTeam):
			self.winSound.play()
		else:
			self.loseSound.play()
		
		self.localTeam.platformSpawnPlayer(self.backend.map.platforms[self.localTeam.lastMatchPosition].getPosition() + Vec3(0, 0, 2))
		
		self.matchReset()
		
		self.gameui.showUsernames()
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
		self.promptText.setText(gameOverText + winningTeam.name + " wins the " + gameText + "! Spacebar to continue.")
	
	def updateScoreText(self):
		text = ""
		for team in self.backend.entityGroup.teams:
			text += " " + team.name + ": " + str(team.matchScore) + " "
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
				if self.unitSelector.hidden:
					self.spectatorController.serverUpdate(self.backend.aiWorld, self.backend.entityGroup, None)
				if self.matchInProgress and (self.backend.enableRespawn or not self.spawnedOnce):
					self.spawnedOnce = True
					self.localTeam.respawnPlayer()
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
		self.unitSelector.hide()
		self.tutorialScreens = []
		for i in range(4):
			image = OnscreenImage(image = "images/part" + str(i + 1) + ".png", pos = (0, 0, 0), scale = (1.25, 1, 1))
			image.hide()
			self.tutorialScreens.append(image)
		self.tutorialIndex = index
		render.hide()
		self.tutorialScreens[self.tutorialIndex].show()
		self.enemyAiUnits = [(components.CHAINGUN, None), (components.SNIPER, None), (components.PISTOL, None)]
	
	def reset(self):
		Game.reset(self)
		self.unitSelector.hide()
	
	def showBuyScreen(self):
		self.hideTutorialScreen()
		if self.tutorialIndex == 2 and self.unitSelector.hidden:
			self.unitSelector.show()
		else:
			self.unitSelector.hide()
			self.startMatch()
	
	def startMatch(self):
		if self.tutorialIndex >= len(self.tutorialScreens) - 1:
			engine.exit()
		render.show()
		self.backend.map.hidePlatforms()
		self.tutorialScreens[self.tutorialIndex].hide()
		if self.tutorialIndex == 0:
			self.localTeam.setPrimaryWeapon(components.CHAINGUN)
			self.localTeam.setSecondaryWeapon(components.SNIPER)
			self.localTeam.setSpecial(None)
			self.enemyAiUnits = [(components.CHAINGUN, None)]
			self.backend.scoreLimit = 400
		elif self.tutorialIndex == 1:
			self.localTeam.setPrimaryWeapon(components.SHOTGUN)
			self.localTeam.setSecondaryWeapon(components.GRENADE_LAUNCHER)
			self.localTeam.setSpecial(None)
			self.localTeam.purchaseUnit(components.PISTOL, None)
			self.localTeam.purchaseUnit(components.MOLOTOV_THROWER, None)
			self.enemyAiUnits = [(components.GRENADE_LAUNCHER, None), (components.SNIPER, None), (components.PISTOL, None)]
			self.backend.scoreLimit = 600
		elif self.tutorialIndex == 2:
			self.enemyAiUnits = [(components.SHOTGUN, controllers.CLOAK_SPECIAL), (components.SNIPER, controllers.SHIELD_SPECIAL), (components.PISTOL, None)]
			self.backend.scoreLimit = 1000
		
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

		# Purchase AI units
		team = self.backend.entityGroup.teams[1]
		team.setLocal(True)
		team.controller.tutorialMode = True
		team.resetScore()
		for u in self.enemyAiUnits:
			team.purchaseUnit(u[0], u[1])
	
	def endMatchCallback(self, winningTeam):
		localTeam = self.localTeam
		Game.endMatchCallback(self, winningTeam)
		player = localTeam.getPlayer()
		if player != None and player.active:
			player.delete(self.backend.entityGroup)
		localTeam.setPlayer(None)
		render.hide()
		self.tutorialIndex += 1
		self.tutorialScreens[self.tutorialIndex].show()
		localTeam.controller.addMoney(1000)
		self.unitSelector.hide()
		team = self.backend.entityGroup.teams[1]
		team.resetScore()
		team.score = 0
	
	def update(self):
		noTeamYet = False
		if self.localTeam == None:
			noTeamYet = True
		Game.update(self)
		if noTeamYet and self.localTeam != None and self.tutorialIndex > 0: # We have a team now!
			self.localTeam.controller.addMoney(2000)
		self.backend.entityGroup.teams[1].respawnUnits()

	def hideTutorialScreen(self):
		render.show()
		self.tutorialScreens[self.tutorialIndex].hide()
	
	def delete(self):
		engine.log.info("Ending tutorial.")
		Game.delete(self)
		for screen in self.tutorialScreens:
			screen.removeNode()