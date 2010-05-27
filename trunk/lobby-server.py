# Evan Todd

GAME_NAME = "A3P"
VERSION_CODE = "v0.6"
COPYRIGHT = "Evan Todd 2010"

HOST_ADDRESS = "a3p.sourceforge.net"
EXPIRE_TIME = 30 # If we don't hear from a host in this amount of time, we assume it's down.

import sys
import datetime
import traceback

def showHelpInfo():
	# Print help information
	print GAME_NAME + " " + VERSION_CODE + " - " + COPYRIGHT
	print "Usage:"
	print "-p portnumber\t\tUse the specified port number for all communication"
	engine.exit()

if "-h" in sys.argv or "/?" in sys.argv or "--help" in sys.argv:
	showHelpInfo()

import src.net as net
import time

defaultPort = 1337

class Host:
	def __init__(self):
		self.ip = ""
		self.port = 0
		self.lastPing = 0
		self.user = ""
		self.map = ""
		self.players = 0
		self.playerSlots = 0

hosts = dict()

i = 1
while i < len(sys.argv):
	if sys.argv[i] == "-p":
		try:
			defaultPort = int(sys.argv[i + 1])
			i += 1
		except:
			showHelpInfo()
	else:
		showHelpInfo()
	i += 1

net.init(defaultPort)

def log(msg):
	logFile = open("lobby.csv", "a")
	logFile.write(str(datetime.datetime.now()) + "\t" + msg)
	logFile.close()

def updateHosts():
	global hosts
	deletedHosts = []
	timestamp = time.time()
	for key in hosts.keys():
		if timestamp - hosts[key].lastPing > EXPIRE_TIME:
			deletedHosts.append(key)
	for key in deletedHosts:
		del hosts[key]

def processPacket(originalData):
	data, address = originalData
	iterator = net.CustomDatagram(data)
	code = net.Uint8.getFrom(iterator)
	packet = net.Packet()
	data = net.CustomDatagram()
	if code == net.PACKET_REQUESTHOSTLIST:
		print "Sent " + str(len(hosts)) + " hosts to " + net.addressToString(address)
		updateHosts()
		packet.add(net.Uint8(net.PACKET_HOSTLIST))
		packet.add(net.Uint16(len(hosts.values())))
		for host in hosts.values():
			packet.add(net.String(host.ip))
			packet.add(net.Uint16(host.port))
			packet.add(net.String(host.user))
			packet.add(net.String(host.map))
			packet.add(net.Uint8(host.players))
			packet.add(net.Uint8(host.playerSlots))
		packet.addTo(data)
		net.context.sendDatagram(data, address)
	elif code == net.PACKET_REGISTERHOST:
		user = net.String.getFrom(iterator)
		map = net.String.getFrom(iterator)
		players = net.Uint8.getFrom(iterator)
		playerSlots = net.Uint8.getFrom(iterator)
		key = net.addressToString(address)
		if key in hosts.keys():
			host = hosts[key]
			host.lastPing = time.time()
			host.map = map
			host.user = user
			host.players = players
			host.playerSlots = playerSlots
			hosts[key] = host
			print "Refreshed host at " + net.addressToString(address)
		else:
			host = Host()
			host.ip = address[0]
			host.port = address[1]
			host.lastPing = time.time()
			host.map = map
			host.user = user
			host.players = players
			host.playerSlots = playerSlots
			hosts[key] = host
			print "Registered new host at " + net.addressToString(address)
			log("host\t" + user + "\t" + map + "\t" + net.addressToString(address) + "\n")
		updateHosts()
		p = net.Packet()
		p.add(net.Uint8(net.PACKET_CONFIRMREGISTER))
		p.addTo(data)
		net.context.sendDatagram(data, address)
	elif code == net.PACKET_CLIENTCONNECTNOTIFICATION:
		ip = net.String.getFrom(iterator)
		port = net.Uint16.getFrom(iterator)
		hostAddress = (ip, port)
		if ip + ":" + str(port) in hosts.keys():
			p = net.Packet()
			p.add(net.Uint8(net.PACKET_NEWCLIENTNOTIFICATION))
			p.add(net.String(address[0]))
			p.add(net.Uint16(address[1]))
			data = net.CustomDatagram()
			p.addTo(data)
			net.context.sendDatagram(data, hostAddress)
			print net.addressToString(address) + " connecting to " + net.addressToString(hostAddress)
			log(net.addressToString(address) + "\tconnecting to\t" + net.addressToString(hostAddress) + "\n")
		else:
			print net.addressToString(address) + " tried to connect to " + net.addressToString(hostAddress) + ", which is not a valid registered host."
			log(net.addressToString(address) + "\t tried to connect to\t" + net.addressToString(hostAddress) + "\n")
	else:
		print "Error - malformed packet"
print GAME_NAME + " " + VERSION_CODE + " - " + COPYRIGHT
print "Lobby server initialized."

def run():
	while True:
		try:
			for datagram in net.context.readTick():
				processPacket(datagram)
			net.context.writeTick()
			time.sleep(0.01)
			expiredHosts = [x for x in hosts.values() if time.time() - x.lastPing > EXPIRE_TIME]
			if len(expiredHosts) > 0:
				print "Removing expired host: " + expiredHosts[0].ip + ":" + str(expiredHosts[0].port)
				updateHosts()
		except:
			errorData = traceback.format_exc()
			print errorData
			log(errorData)
run()
