import controllers
import net
import engine
from direct.showbase.DirectObject import DirectObject
from random import random
from direct.distributed.PyDatagram import PyDatagram
from direct.distributed.PyDatagramIterator import PyDatagramIterator
from pandac.PandaModules import Vec3, Quat, Vec4
from Queue import Queue # So we have the Empty exception

class HighResVec3(net.Object):
	def addTo(self, datagram):
		x = net.HighResFloat(self.data.getX())
		y = net.HighResFloat(self.data.getY())
		z = net.HighResFloat(self.data.getZ())
		x.addTo(datagram)
		y.addTo(datagram)
		z.addTo(datagram)
	@staticmethod
	def getFrom(iterator):
		return Vec3(net.HighResFloat.getFrom(iterator), net.HighResFloat.getFrom(iterator), net.HighResFloat.getFrom(iterator))
class StandardVec3(net.Object):
	def addTo(self, datagram):
		x = net.StandardFloat(self.data.getX())
		y = net.StandardFloat(self.data.getY())
		z = net.StandardFloat(self.data.getZ())
		x.addTo(datagram)
		y.addTo(datagram)
		z.addTo(datagram)	
	@staticmethod
	def getFrom(iterator):
		return Vec3(net.StandardFloat.getFrom(iterator), net.StandardFloat.getFrom(iterator), net.StandardFloat.getFrom(iterator))
class StandardQuat(net.Object):
	def addTo(self, datagram):
		x = net.StandardFloat(self.data.getX())
		y = net.StandardFloat(self.data.getY())
		z = net.StandardFloat(self.data.getZ())
		w = net.StandardFloat(self.data.getW())
		x.addTo(datagram)
		y.addTo(datagram)
		z.addTo(datagram)	
		w.addTo(datagram)
	@staticmethod
	def getFrom(iterator):
		return Quat(net.StandardFloat.getFrom(iterator), net.StandardFloat.getFrom(iterator), net.StandardFloat.getFrom(iterator), net.StandardFloat.getFrom(iterator))
class HighResVec4(net.Object):
	def addTo(self, datagram):
		x = net.HighResFloat(self.data.getX())
		y = net.HighResFloat(self.data.getY())
		z = net.HighResFloat(self.data.getZ())
		w = net.HighResFloat(self.data.getW())
		x.addTo(datagram)
		y.addTo(datagram)
		z.addTo(datagram)	
		w.addTo(datagram)
	@staticmethod
	def getFrom(iterator):
		return Vec4(net.HighResFloat.getFrom(iterator), net.HighResFloat.getFrom(iterator), net.HighResFloat.getFrom(iterator), net.HighResFloat.getFrom(iterator))
class LowResVec3(net.Object):
	def addTo(self, datagram):
		x = net.LowResFloat(self.data.getX())
		y = net.LowResFloat(self.data.getY())
		z = net.LowResFloat(self.data.getZ())
		x.addTo(datagram)
		y.addTo(datagram)
		z.addTo(datagram)
	@staticmethod
	def getFrom(iterator):
		return Vec3(net.LowResFloat.getFrom(iterator), net.LowResFloat.getFrom(iterator), net.LowResFloat.getFrom(iterator))
class SmallVec3(net.Object):
	def addTo(self, datagram):
		x = net.SmallFloat(self.data.getX())
		y = net.SmallFloat(self.data.getY())
		z = net.SmallFloat(self.data.getZ())
		x.addTo(datagram)
		y.addTo(datagram)
		z.addTo(datagram)
	@staticmethod
	def getFrom(iterator):
		return Vec3(net.SmallFloat.getFrom(iterator), net.SmallFloat.getFrom(iterator), net.SmallFloat.getFrom(iterator))
class EntitySnapshot(net.Object):
	def __init__(self):
		self.pos = Vec3()
		self.quat = Quat()
		self.time = 0
		self.empty = True

	def takeSnapshot(self, entity):
		self.pos = entity.getPosition()
		self.quat = Quat(entity.getQuaternion())
		self.time = engine.clock.getTime()
		self.empty = False

	def addTo(self, datagram):
		pos = HighResVec3(self.pos)
		quat = StandardQuat(self.quat)
		pos.addTo(datagram)
		quat.addTo(datagram)
		
	@staticmethod
	def getFrom(iterator):
		es = EntitySnapshot()
		es.pos = HighResVec3.getFrom(iterator)
		es.quat = StandardQuat.getFrom(iterator)
		es.time = engine.clock.getTime()
		es.empty = False
		return es
	
	def commitTo(self, entity):
		entity.setQuaternion(self.quat)
		entity.setPosition(self.pos)
	
	def lerp(self, snapshot, scale):
		result = EntitySnapshot()
		result.pos = self.pos + ((snapshot.pos - self.pos) * scale)
		result.quat = self.quat + ((snapshot.quat - self.quat) * scale)
		result.empty = False
		return result

	def setFrom(self, snapshot):
		self.pos = Vec3(snapshot.pos)
		self.quat = Quat(snapshot.quat)
		self.time = engine.clock.getTime()
		self.empty = snapshot.empty
	
	def almostEquals(self, snapshot):
		return self.quat.almostEqual(snapshot.quat, 2) and self.pos.almostEqual(snapshot.pos, 0.2)
	
class NetManager(DirectObject):
	def __init__(self):
		self.lastPacketUpdate = 0
		self.spawnPackets = []
		self.deletePackets = []
		self.clientSpawnPacketRequests = []
		self.chatPackets = []
		self.lastStatsLog = engine.clock.getTime()
		self.incomingPackets = 0
		self.totalIncomingPacketSize = 0
		self.outgoingPackets = 0
		self.totalOutgoingPacketSize = 0
		self.requestedEntitySpawns = dict()
		self.accept("chat-outgoing", self.chatHandler)
	
	def spawnEntity(self, entity):
		p = entity.controller.buildSpawnPacket()
		self.spawnPackets.append(p)
	
	def chatHandler(self, username, message):
		p = net.Packet()
		p.add(net.Uint8(net.PACKET_CHAT))
		p.add(net.String(username))
		p.add(net.String(message))
		self.chatPackets.append(p)
	
	def deleteEntity(self, entity, killed = False):
		p = entity.controller.buildDeletePacket(killed)
		self.deletePackets.append(p)
	
	def processPacket(self, packet, backend, sender = None):
		iterator = PyDatagramIterator(packet)
		lastId = "None"
		lastController = "None"
		try:
			rebroadcast = True
			while iterator.getRemainingSize() > 0:
				type = net.Uint8.getFrom(iterator)
				if type == net.PACKET_CONTROLLER:
					id = net.Uint8.getFrom(iterator)
					entity = backend.entityGroup.getEntity(id)
					if entity != None:
						lastId = str(id)
						lastController = entity.controller
						entity.controller.clientUpdate(backend.aiWorld, backend.entityGroup, iterator)
					else:
						engine.log.warning("Received controller packet with no matching entity. ID: " + str(id) + " Last entity updated: " + lastId + " - controller: " + str(lastController))
						if sender != None and ((not id in self.requestedEntitySpawns.keys()) or (engine.clock.getTime() - self.requestedEntitySpawns[id] > 2.0)): # Only send a request once every two seconds
							p = net.Packet()
							p.add(net.Uint8(net.PACKET_CLIENTREQUESTSPAWNPACKET))
							p.add(net.Uint8(id))
							net.context.send(p, sender)
							self.requestedEntitySpawns[id] = engine.clock.getTime()
							engine.log.info("Sending request for missing entity spawn packet. ObjectEntity ID: " + str(id))
						return rebroadcast
				elif type == net.PACKET_SPAWN:
					controllerType = net.Uint8.getFrom(iterator)
					entity = controllers.types[controllerType].readSpawnPacket(backend.aiWorld, backend.entityGroup, iterator)
					if entity.getId() in self.requestedEntitySpawns.keys():
						del self.requestedEntitySpawns[entity.getId()]
					if entity != None and backend.entityGroup.getEntity(entity.getId()) == None:
						backend.entityGroup.addEntity(entity)
					elif entity != None:
						engine.log.warning("Spawned entity " + str(entity.getId()) + " already exists. Cancelling spawn.")
						entity.delete(backend.entityGroup, killed = False, localDelete = False)
				elif type == net.PACKET_DELETE:
					id = net.Uint8.getFrom(iterator)
					entity = backend.entityGroup.getEntity(id)
					killed = net.Boolean.getFrom(iterator)
					if entity != None:
						if killed: # The boolean indicates that the entity was not only deleted, it was killed. Also, let the entity know this was a remote delete packet.
							entity.kill(backend.aiWorld, backend.entityGroup, False)
						else:
							entity.delete(backend.entityGroup, False, False)
				elif type == net.PACKET_CLIENTREQUESTSPAWNPACKET:
					self.clientSpawnPacketRequests.append((net.Uint8.getFrom(iterator), sender))
					rebroadcast = False
				elif type == net.PACKET_SETUP:
					messenger.send("client-setup", [iterator])
				elif type == net.PACKET_CHAT:
					messenger.send("chat-incoming", [net.String.getFrom(iterator), net.String.getFrom(iterator)]) # Username and message
				elif type == net.PACKET_ENDMATCH:
					engine.log.info("Received match end packet.")
					messenger.send("end-match", [iterator])
				elif type == net.PACKET_CLIENTMATCHREADY:
					messenger.send("client-match-ready", [iterator])
					rebroadcast = False
				elif type == net.PACKET_NEWCLIENT:
					messenger.send("server-new-connection", [sender, net.String.getFrom(iterator)]) # Sender address and username
					rebroadcast = False
				elif type == net.PACKET_DISCONNECT:
					engine.log.info(net.addressToString(sender) + " disconnected.")
					messenger.send("disconnect", [sender])
					rebroadcast = False
				elif type == net.PACKET_SERVERFULL:
					messenger.send("server-full")
				elif type == net.PACKET_CONFIRMREGISTER:
					messenger.send("lobby-confirm-register")
					rebroadcast = False
				elif type == net.PACKET_EMPTY:
					rebroadcast = False
				elif type == net.PACKET_CLIENTREADY:
					rebroadcast = False
					messenger.send("client-ready", [sender])
				elif type == net.PACKET_NEWCLIENTNOTIFICATION:
					address = net.String.getFrom(iterator)
					port = net.Uint16.getFrom(iterator)
					# Make sure we get all the data out of the packet to ensure proper processing.
					# This packet has already been handled by the NetContext.
				else:
					rebroadcast = False
		except AssertionError:
			engine.log.warning("Packet iteration failed. Discarding packet.")
		return rebroadcast

	def update(self, backend):
		# Only send out an update packet if we need to
		packetUpdate = False
		if engine.clock.getRealTime() - self.lastPacketUpdate >= net.SERVER_TICK:
			packetUpdate = True
			self.lastPacketUpdate = engine.clock.getRealTime() # Reset packet update timer
		
		spawnPacket = net.Packet()
		if len(self.spawnPackets) > 0 and packetUpdate:
			for p in self.spawnPackets:
				spawnPacket.add(p)
			del self.spawnPackets[:]
		
		entityList = backend.entityGroup.entities.values()
		updatedEntities = []
		controllerPacket = net.Packet()
		for entity in (x for x in entityList if x.active and x.isLocal):
			# Do a server update for local entities.
			# The controller packet is only sent if we've exceeded the regular packet update interval.
			p = entity.controller.serverUpdate(backend.aiWorld, backend.entityGroup, packetUpdate)
			if p != None and entity.controller.needsToSendUpdate():
				controllerPacket.add(p)
				updatedEntities.append(entity)

		# Make sure we update our own copy of the entities.
		if len(controllerPacket.dataObjects) > 0:
			data = PyDatagram()
			controllerPacket.addTo(data)
			self.processPacket(data, backend)
		
		deletePacket = net.Packet()
		if len(self.deletePackets) > 0 and packetUpdate:
			for p in self.deletePackets:
				deletePacket.add(p)
			del self.deletePackets[:]
		
		if packetUpdate:
			outboundPacket = net.Packet()
			outboundPacket.add(spawnPacket)
			outboundPacket.add(controllerPacket)
			outboundPacket.add(deletePacket)
			for chat in self.chatPackets:
				outboundPacket.add(chat)
			del self.chatPackets[:]
			for request in self.clientSpawnPacketRequests:
				entity = backend.entityGroup.getEntity(request[0])
				if entity != None:
					if net.netMode == net.MODE_CLIENT:
						outboundPacket.add(entity.controller.buildSpawnPacket())
					else:
						temp = net.Packet()
						temp.add(entity.controller.buildSpawnPacket())
						net.context.send(temp, request[1])
					engine.log.info("Sending missed spawn packet (ID " + str(request[0]) + ") to client " + net.addressToString(request[1]))
				else:
					engine.log.warning("Client requested spawn packet for non-existent entity.")
			del self.clientSpawnPacketRequests[:]
			if outboundPacket.getSize() > 0:
				net.context.broadcast(outboundPacket)
				self.outgoingPackets += 1
				#self.totalOutgoingPacketSize += outboundPacket.getLength() # Need to find a way to do this

		packets = net.context.readTick()
		for packet in packets:
			data = PyDatagram(packet[0])
			rebroadcast = self.processPacket(data, backend, packet[1])
			self.incomingPackets += 1
			self.totalIncomingPacketSize += len(packet[0])
			if net.netMode == net.MODE_SERVER and rebroadcast:
				net.context.broadcastDatagramExcept(data, packet[1])
				self.outgoingPackets += 1
				self.totalOutgoingPacketSize += len(packet[0])
		del packets

		if len(entityList) > len(updatedEntities):
			for entity in (x for x in entityList if x.active and not x in updatedEntities):
				entity.controller.clientUpdate(backend.aiWorld, backend.entityGroup)
		
		if engine.enableNetworkStatistics and engine.clock.getTime() - self.lastStatsLog > 5.0:
			inAverage = 0
			outAverage = 0
			if self.incomingPackets > 0:
				inAverage = round(self.totalIncomingPacketSize / self.incomingPackets)
			if self.outgoingPackets > 0:
				outAverage = round(self.totalOutgoingPacketSize / self.outgoingPackets)
			inRate = round(self.totalIncomingPacketSize / (engine.clock.getTime() - self.lastStatsLog))
			outRate = round(self.totalOutgoingPacketSize / (engine.clock.getTime() - self.lastStatsLog))
			engine.log.debug("Incoming Stats - Packets/sec: " + str(self.incomingPackets / (engine.clock.getTime() - self.lastStatsLog)) + " Average size (bytes): " + str(inAverage) + " Bytes/sec: " + str(inRate))
			engine.log.debug("Outgoing Stats - Packets/sec: " + str(self.outgoingPackets / (engine.clock.getTime() - self.lastStatsLog)) + " Average size (bytes): " + str(outAverage) + " Bytes/sec: " + str(outRate))
			self.incomingPackets = 0
			self.totalIncomingPacketSize = 0
			self.outgoingPackets = 0
			self.totalOutgoingPacketSize = 0
			self.lastStatsLog = engine.clock.getTime()
		
		clientAddress = [] if net.netMode == net.MODE_SERVER else [net.context.hostConnection]
		emptyPacket = net.Packet()
		emptyPacket.add(net.Uint8(net.PACKET_EMPTY))
		for client in (x for x in net.context.activeConnections.values() + clientAddress if net.timeFunction() - x.lastSentPacketTime > 0.5 and x.ready):
			net.context.send(emptyPacket, client.address)
			self.outgoingPackets += 1
			#self.totalOutgoingPacketSize += emptyPacket.getLength() # Need to find a way to do this
		
		net.context.writeTick()
			
	def delete(self):
		self.ignoreAll()
