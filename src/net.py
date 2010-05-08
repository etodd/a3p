import math
import socket
import os
import zlib
import time
import sys

from socket import *

netMode = 0

connection = None
initialized = False
context = None

# Packet types
PACKET_SETUP = 0
PACKET_CONTROLLER = 1
PACKET_SPAWN = 2
PACKET_DELETE = 3
PACKET_ENDMATCH = 4
PACKET_CLIENTMATCHREADY = 5 # Means the client user is ready to start the match
PACKET_NEWCLIENT = 6 # New client is connecting
PACKET_CLIENTREQUESTSPAWNPACKET = 7 # Client missed a spawn packet.
PACKET_DISCONNECT = 8 # Server or client disconnect
PACKET_SERVERFULL = 9 # Server can't take any more clients
PACKET_CHAT = 10 # Chat data
PACKET_EMPTY = 11 # No data. Used for establishing and maintaining connections.
PACKET_CLIENTREADY = 12

# For communication with lobby server
PACKET_REQUESTHOSTLIST = 13 # Client requesting the host list from the lobby server
PACKET_HOSTLIST = 14 # Packet contains host list
PACKET_REGISTERHOST = 15 # A host is notifying the lobby server of its existence
PACKET_NEWCLIENTNOTIFICATION = 16 # Lobby server notifying the server that a new client wishes to connect
PACKET_CLIENTCONNECTNOTIFICATION = 17 # Client notifying lobby server of its intention to connect to a host
PACKET_CONFIRMREGISTER = 18 # Lobby server confirms host registration

# Spawn types
SPAWN_PLAYER = 0
SPAWN_BOT = 1
SPAWN_PHYSICSENTITY = 2
SPAWN_GRENADE = 3
SPAWN_SPRINGBOARD = 4
SPAWN_GLASS = 5
SPAWN_TEAMENTITY = 6
SPAWN_MOLOTOV = 7
SPAWN_POD = 8

MODE_SERVER = 0
MODE_CLIENT = 1

SERVER_TICK = 0.03 # Transfer update packets 20 times per second

if sys.platform == "win32":
	timeFunction = time.clock
else:
	timeFunction = time.time

clientLimit = 0 # Number of clients we can accept

datagramType = None # If we're using Panda3D, this should be set to PyDatagram.

def init(localPort = None, newDatagramType = None):
	global context, initialized, datagramType
	datagramType = newDatagramType
	context = PythonNetContext(localPort)
	initialized = True

class NetworkContext:
	def __init__(self, arg, mode, localClientPort = None):
		pass
		# In client mode, arg is the address of the host to connect to.
		# In server mode, arg is the port to listen on.
		# If arg is None, the network thread does nothing.
	def readWorker(self):
		pass # To be called once inside a daemon thread. Reads packets into a queue.
	def writeWorker(self):
		pass # To be called once inside a daemon thread. Writes packets from a queue onto the network interface.
	def readTick(self):
		pass # Called in a loop.
	def writeTick(self):
		pass # Called in a loop.
	def delete(self):
		pass # Clean up.

class Connection:
	def __init__(self):
		self.address = ("", 0)
		self.lastPacketTime = timeFunction()
		self.lastSentPacketTime = 0
		self.ready = False

class PythonNetContext(NetworkContext):
	def __init__(self, localPort = None):
		global netMode
		netMode = MODE_SERVER
		self.mode = MODE_SERVER
		if localPort == None:
			localPort = 1337
		self.port = localPort
		self.socket = socket(AF_INET, SOCK_DGRAM)
		self.bindSocket(localPort)
		self.socket.setblocking(0)
		self.clientConnected = False
		self.activeConnections = dict() # Server only - connected clients
		self.hostConnection = Connection() # Client only - connection to server
		self.writeQueue = []
		self.hostListCallback = None
		self.disconnectCallback = None
		self.connectionTimeout = 10.0
		self.clientUsername = "Unnamed"
		self.lastConnectionAttempt = 0
		self.connectionAttempts = 0
	
	def connectToServer(self, arg, username):
		global netMode
		netMode = MODE_CLIENT
		self.mode = MODE_CLIENT
		args = arg.split(":")
		ip = args[0]
		port = 1337
		if len(args) > 1:
			port = int(args[1])
		self.hostConnection.address = (str(ip), port)
		self.hostConnection.lastSentPacketTime = timeFunction()
		self.hostConnection.ready = True
		self.clientConnected = False
		self.clientUsername = username
	
	def listen(self):
		global netMode
		netMode = MODE_SERVER
		self.mode = MODE_SERVER
	
	def reset(self):
		global netMode
		netMode = MODE_SERVER # Default MODE_SERVER
		self.mode = MODE_SERVER
		self.clientConnected = False
		self.activeConnections.clear()
		self.hostConnection = Connection()
		self.connectionAttempts = 0
		del self.writeQueue[:]
	
	def bindSocket(self, port):
		bound = False
		tries = 0
		while not bound and tries < 10:
			try:
				self.socket.bind(("", port))
				bound = True
			except:
				time.sleep(0.25)
			tries += 1
	
	def clientConnect(self, username):
		if self.clientConnected:
			return
		datagram = CustomDatagram()
		datagram.addUint8(PACKET_NEWCLIENT)
		datagram.addString(username)
		self.sendDatagram(datagram, self.hostConnection.address)
		self.hostConnection.lastSentPacketTime = timeFunction()
	
	def serverConnect(self, clientAddress):
		if clientAddress in self.activeConnections:
			return
		data = CustomDatagram()
		p = Packet()
		p.add(Uint8(PACKET_EMPTY))
		p.addTo(data)
		self.sendDatagram(data, clientAddress)
	
	def removeClient(self, client):
		if client in self.activeConnections:
			del self.activeConnections[client]
	
	def addClient(self, client):
		if not client in self.activeConnections:
			connection = Connection()
			connection.address = client
			connection.lastSentPacketTime = timeFunction()
			self.activeConnections[client] = connection
	
	def resetConnectionStatuses(self):
		for connection in self.activeConnections.values():
			connection.ready = False
	
	def writeTick(self):
		for data in self.writeQueue:
			# data[0] = action code. 0 for broadcast or broadcastExcept. 1 for send.
			# for broadcasting, the given connection is excluded, if one is given.
			# for sending, the given connection is the only one we send the data to.
			compressedData = zlib.compress(data[1].getMessage())
			if data[0] == 0: # Broadcast
				for c in (x for x in self.activeConnections.values() if x.ready):
					c.lastSentPacketTime = timeFunction()
					self.socket.sendto(compressedData, c.address)
			elif data[0] == 1: # Send to specific machine
				self.socket.sendto(compressedData, data[2])
				if data[2] in self.activeConnections:
					self.activeConnections[data[2]].lastSentPacketTime = timeFunction()
				elif compareAddresses(data[2], self.hostConnection.address):
					self.hostConnection.lastSentPacketTime = timeFunction()
			elif data[0] == 2: # Broadcast, excluding one machine
				for c in (x for x in self.activeConnections.values() if x.ready and not compareAddresses(x.address, data[2])):
					self.socket.sendto(compressedData, c.address)
					c.lastSentPacketTime = timeFunction()
		del self.writeQueue[:]

	def readTick(self):
		if self.mode == MODE_SERVER:
			loadingTimeout = self.connectionTimeout * 2
			for client in self.activeConnections.values():
				if timeFunction() - client.lastPacketTime > (self.connectionTimeout if client.ready else loadingTimeout):
					del self.activeConnections[client.address]
					if self.disconnectCallback != None:
						self.disconnectCallback(client.address)
		elif self.mode == MODE_CLIENT:
			if self.clientConnected:
				if self.disconnectCallback != None and timeFunction() - self.hostConnection.lastPacketTime > self.connectionTimeout:
					self.disconnectCallback(self.hostConnection.address)
			else:
				if self.connectionAttempts < 10:
					if timeFunction() - self.lastConnectionAttempt > 0.25:
						self.clientConnect(self.clientUsername)
						self.connectionAttempts += 1
						self.lastConnectionAttempt = timeFunction()
				else:
					self.disconnectCallback(self.hostConnection.address)
	
		readQueue = []
		while True:
			try:
				message, address = self.socket.recvfrom(1024)
			except error:
				return readQueue
			if len(message) == 0:
				continue
			if address in self.activeConnections:
				self.activeConnections[address].lastPacketTime = timeFunction()
			message = zlib.decompress(message)
			iterator = CustomDatagram(message)
			if iterator.getRemainingSize() < 1:
				continue
			code = Uint8.getFrom(iterator)
			if code == PACKET_HOSTLIST:
				numHosts = Uint16.getFrom(iterator)
				hosts = []
				for _ in range(numHosts):
					ip = String.getFrom(iterator)
					port = Uint16.getFrom(iterator)
					user = String.getFrom(iterator)
					map = String.getFrom(iterator)
					hosts.append((user + " - " + map, ip + ":" + str(port)))
				#engine.log.debug("Received " + str(numHosts) + " hosts from lobby server.")
				if self.hostListCallback != None:
					self.hostListCallback(hosts)
			if self.mode == MODE_SERVER:
				if code == PACKET_NEWCLIENTNOTIFICATION:
					ip = String.getFrom(iterator)
					port = Uint16.getFrom(iterator)
					clientAddress = (ip, port)
					self.connectionAttempts = 0
					#engine.log.info("Received notification from lobby server of new client " + ip + ":" + str(port))
					self.serverConnect(clientAddress)
				elif code == PACKET_DISCONNECT:
					if address in self.activeConnections:
						del self.activeConnections[address]
				elif code == PACKET_CLIENTREADY:
					if address in self.activeConnections:
						self.activeConnections[address].ready = True
			elif self.mode == MODE_CLIENT:
				self.hostConnection.lastPacketTime = timeFunction()
				if not self.clientConnected:
					self.clientConnected = True
			readQueue.append((message, address))
		return readQueue
	
	def broadcastDatagram(self, datagram):
		"""For the server, broadcasts the given data packet to all connected clients.
		For clients, sends the datagram to the server."""
		if netMode == MODE_SERVER:
			self.writeQueue.append((0, datagram, None)) # Send to all clients
		else:
			self.writeQueue.append((1, datagram, self.hostConnection.address)) # Send to host
	
	def broadcastDatagramExcept(self, datagram, client):
		"""For the server, broadcasts the given data packet to all connected clients.
		For clients, sends the datagram to the server."""
		self.writeQueue.append((2, datagram, client))
	
	def sendDatagram(self, datagram, client = None):
		self.writeQueue.append((1, datagram, client))
	
	def broadcast(self, packet):
		d = datagramType()
		packet.addTo(d)
		self.broadcastDatagram(d)
	
	def broadcastExcept(self, packet, client):
		d = datagramType()
		packet.addTo(d)
		self.broadcastDatagramExcept(d, client)
	
	def send(self, packet, client = None):
		d = datagramType()
		packet.addTo(d)
		self.sendDatagram(d, client)

	def delete(self):
		p = Packet()
		p.add(Uint8(PACKET_DISCONNECT))
		data = CustomDatagram()
		p.addTo(data)
		self.broadcastDatagram(data)
		self.writeTick()
		time.sleep(0.25)
		self.socket.close()
	
def delete():
	global initialized, context
	initialized = False
	context.delete()

def stringToAddress(string):
	address = string.split(":")
	return (address[0], int(address[1]))

def addressToString(address):
	return address[0] + ":" + str(address[1])

def compareAddresses(a, b):
	return a[0] == b[0] and a[1] == b[1]

def copyAddress(a):
	return (a[0], a[1])

class Packet:
	def __init__(self):
		self.dataObjects = []
	def getSize(self):
		return len(self.dataObjects)
	def add(self, dataObject):
		assert isinstance(dataObject, Object) or isinstance(dataObject, Packet)
		if dataObject != None:
			self.dataObjects.append(dataObject)
	def addTo(self, datagram):
		for dataObject in self.dataObjects:
			dataObject.addTo(datagram)

class CustomDatagram:
	def __init__(self, x = ""):
		self.data = x
	def addUint8(self, x):
		self.data += chr(x)
	def getUint8(self):
		value = ord(self.data[0])
		self.data = self.data[1:]
		return value
	def addUint16(self, x):
		self.data += chr(x % 256) + chr(int(x) / 256)
	def getUint16(self):
		value = ord(self.data[0]) + ord(self.data[1]) * 256
		self.data = self.data[2:]
		return value
	def addString(self, x):
		self.addUint16(len(x))
		self.data += x
	def getString(self):
		length = self.getUint16()
		value = self.data[:length]
		self.data = self.data[length:]
		return value
	def getRemainingSize(self):
		return len(self.data)
	def getMessage(self):
		return self.data

def clamp(a, min, max):
	if min <= a <= max:
		return a
	if a < min:
		return min
	return max

class Object:
		data = None
		def __init__(self, data):
			self.data = data
		def addTo(self, datagram):
			pass
		@staticmethod
		def getFrom(iterator):
			pass
class HighResFloat(Object):
	def addTo(self, datagram):
		datagram.addFloat32(self.data)
	@staticmethod
	def getFrom(iterator):
		return iterator.getFloat32()
class StandardFloat(Object):
	def addTo(self, datagram):
		datagram.addInt16(clamp(int(self.data * 110.0), -32768, 32767))
	@staticmethod
	def getFrom(iterator):
		return float(iterator.getInt16()) / 110.0
class LowResFloat(Object):
	def addTo(self, datagram):
		datagram.addInt16(clamp(int(self.data * 50.0), -32768, 32767))
	@staticmethod
	def getFrom(iterator):
		return float(iterator.getInt16()) / 50.0
class SmallFloat(Object):
	def addTo(self, datagram):
		datagram.addInt8(clamp(int(self.data * (127.0 / 35.0)), -128, 127))
	@staticmethod
	def getFrom(iterator):
		return float(iterator.getInt8()) * (35.0 / 127.0)
class Uint8(Object):
	def addTo(self, datagram):
		datagram.addUint8(self.data)
	@staticmethod
	def getFrom(iterator):
		return iterator.getUint8()
class Uint16(Object):
	def addTo(self, datagram):
		datagram.addUint16(self.data)
	@staticmethod
	def getFrom(iterator):
		return iterator.getUint16()
class Uint32(Object):
	def addTo(self, datagram):
		datagram.addUint32(self.data)
	@staticmethod
	def getFrom(iterator):
		return iterator.getUint32()
class Int16(Object):
	def addTo(self, datagram):
		datagram.addInt16(self.data)
	@staticmethod
	def getFrom(iterator):
		return iterator.getInt16()
class String(Object):
	def addTo(self, datagram):
		datagram.addString(self.data)
	@staticmethod
	def getFrom(iterator):
		return iterator.getString()
class Boolean(Object):
	def addTo(self, datagram):
		datagram.addBool(self.data)
	@staticmethod
	def getFrom(iterator):
		return iterator.getBool()