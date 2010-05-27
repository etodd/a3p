from pandac.PandaModules import *
import engine
import net

from direct.distributed.PyDatagram import PyDatagram

LOBBY_SERVER_ADDRESS = "et1337.ath.cx"
LOBBY_SERVER_PORT = 1337
address = (LOBBY_SERVER_ADDRESS, LOBBY_SERVER_PORT)
	
def registerHost(username, map, players, playerSlots):
	p = net.Packet()
	p.add(net.Uint8(net.PACKET_REGISTERHOST))
	p.add(net.String(username))
	p.add(net.String(map))
	p.add(net.Uint8(players))
	p.add(net.Uint8(playerSlots))
	net.context.send(p, address)

def getHosts():
	engine.log.info("Requesting host list from lobby server")
	p = net.Packet()
	p.add(net.Uint8(net.PACKET_REQUESTHOSTLIST))
	net.context.send(p, address)

def connectTo(ip, port = None):
	if port == None:
		if ip.find(":") != -1:
			ip, port = ip.split(":")
		else:
			port = 1337
		port = int(port)
	engine.log.info("Notifying lobby server of intention to connect to " + ip + ":" + str(port))
	p = net.Packet()
	p.add(net.Uint8(net.PACKET_CLIENTCONNECTNOTIFICATION))
	p.add(net.String(ip))
	p.add(net.Uint16(port))
	net.context.send(p, address)