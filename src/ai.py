from direct.showbase.DirectObject import DirectObject
from pandac.PandaModules import *
from random import randint, random, choice
import math
import sys

import engine
import entities
import net
import components
import controllers
import threading
import time

ACCURACY = 0.7 # Relative probability of an AI droid hitting its target.

currentWorld = None
pathRequests = []
pathFindThread = None

class PathRequest:
	def __init__(self, callback, aiNode, targetAiNode, position, targetPosition, radius):
		self.callback = callback
		self.aiNode = aiNode
		self.targetAiNode = targetAiNode
		self.position = position
		self.targetPosition = targetPosition
		self.radius = radius

def init():
	global pathFindThread
	pathFindThread = threading.Thread(target = pathWorker)
	pathFindThread.setDaemon(True)
	pathFindThread.start()

def pathWorker():
	global pathRequests, currentWorld
	while True:
		if len(pathRequests) > 0:
			req = pathRequests.pop(0)
			req.callback(currentWorld.navMesh.findPathFromNodes(req.aiNode, req.targetAiNode, req.position, req.targetPosition, req.radius))
			del req
		if len(pathRequests) > 5:
			del pathRequests[:]
		time.sleep(0.01)

def requestPath(callback, aiNode, targetAiNode, position, targetPosition, radius):
	request = PathRequest(callback, aiNode, targetAiNode, position, targetPosition, radius)
	pathRequests.append(request)

class World:
	"""The AI world models the world using a navigation mesh. AI entities navigate between edges in the mesh using an A* search algorithm.
	The AI world also contains the ODE world and space, and includes functions to test for collisions."""
	def __init__(self):
		global currentWorld
		currentWorld = self
		"Initializes the ODE world and space."
		self.grids = dict()
		self.navMesh = None
		self.spawnPoints = []
		self.docks = []
		if base.cTrav == 0:
			self.traverser = CollisionTraverser("collision_traverser")
			base.cTrav = self.traverser
		else:
			self.traverser = base.cTrav
			self.traverser.clearColliders()
		
		# Setup the physics world
		self.world = OdeWorld()
		# Create a space and add a contactgroup to it to add the contact joints
		self.space = OdeHashSpace()
		self.space.setAutoCollideWorld(self.world)
		self.contactGroup = OdeJointGroup()
		self.space.setAutoCollideJointGroup(self.contactGroup)
		self.space.setCollisionEvent("physicsCollision")
		
		self.world.setGravity(0, 0, -35)

		# Surface IDs: 0 - ground 1 - objects 2 - actors
		self.world.initSurfaceTable(3)
		self.world.setSurfaceEntry(0, 1, 1.0, 0.3, 7, 0.9, 0.00001, 0.0, 0.01)
		self.world.setSurfaceEntry(1, 1, 1.0, 0.3, 7, 0.9, 0.00001, 0.0, 0.01)
		self.world.setSurfaceEntry(1, 2, 1.0, 0.3, 7, 0.9, 0.00001, 0.0, 0.01)
		self.world.setSurfaceEntry(0, 2, 10.0, 0.3, 7, 0.9, 0.00001, 0.0, 0.01)
		self.world.setSurfaceEntry(2, 2, 0.2, 0.3, 7, 0.9, 0.00001, 0.0, 0.01)
		self.world.setSurfaceEntry(0, 0, 1.0, 0.3, 7, 0.9, 0.00001, 0.0, 0.01)
	
	def update(self):
		"Steps the ODE simulation."
		self.space.autoCollide()
		self.world.quickStep(engine.clock.timeStep)
		self.contactGroup.empty() # Clear the contact joints
	
	def getNearestDroid(self, entityGroup, pos):
		"Gets an entity on any opposing team with the smallest straight-line distance from the specified position."
		distance = -1
		droid = None
		for entity in (x for x in entityGroup.entities.values() if isinstance(x, entities.BasicDroid)):
			vector = pos - entity.getPosition()
			if vector.length() < distance or distance == -1:
				distance = vector.length()
				droid = entity
		return droid

	def getNearestEnemy(self, entityGroup, pos, team, includeCloakedUnits = False):
		"Gets an entity on any opposing team with the smallest straight-line distance from the specified position."
		distance = -1
		enemy = None
		for entity in (x for x in entityGroup.entities.values() if isinstance(x, entities.BasicDroid) and ((not x.cloaked) or includeCloakedUnits) and (not team.isAlly(x.team))):
			vector = pos - entity.getPosition()
			if vector.length() < distance or distance == -1:
				distance = vector.length()
				enemy = entity
		return enemy
	
	def getNearestDropPod(self, entityGroup, pos):
		"Gets the nearest drop pod."
		distance = -1
		pod = None
		for entity in (x for x in entityGroup.entities.values() if isinstance(x, entities.DropPod)):
			vector = pos - entity.getPosition()
			if vector.length() < distance or distance == -1:
				distance = vector.length()
				pod = entity
		return pod
	
	def getNearestSpawnPoint(self, pos):
		lowestDistance = -1
		returnValue = None
		for point in self.spawnPoints:
			vector1 = pos - point.getPosition()
			dist = vector1.length()
			if dist < lowestDistance or lowestDistance == -1:
				lowestDistance = dist
				returnValue = point
		return returnValue
	
	def getNearestDock(self, pos):
		lowestDistance = -1
		returnValue = None
		for point in self.docks:
			vector1 = pos - point.getPosition()
			dist = vector1.length()
			if dist < lowestDistance or lowestDistance == -1:
				lowestDistance = dist
				returnValue = point
		return returnValue
	
	def getNearestOpenSpawnPoint(self, team, entityGroup, pos, minRadius = 50):
		dockList = [team.dock] if team.dock != None else []
		points = sorted(dockList + self.spawnPoints, key = lambda x: (x.getPosition() - pos).length())
		enemies = [x for x in entityGroup.entities.values() if isinstance(x, entities.Actor) and x.team != team]
		for point in points:
			p = point.getPosition()
			open = True
			for enemy in enemies:
				if (enemy.getPosition() - p).length() < minRadius:
					open = False
					break
			if open:
				return p
		return points[0].getPosition()

	def getRandomSpawnPoint(self, zombieSpawnsOnly = False, team = None):
		if zombieSpawnsOnly:
			spawns = self.spawnPoints[1:]
		else:
			spawns = self.spawnPoints[:]
		if team != None and team.dock != None:
			spawns.append(team.dock)
		return choice(spawns).getPosition()
	
	def getRayCollisionQueue(self, rayNP, node = None):
		"""Gets a CollisionHandlerQueue containing all collisions along the specified ray.
		Only checks for collisions with the specified NodePath, if one is given."""
		queue = CollisionHandlerQueue()
		self.traverser.addCollider(rayNP, queue)
		if node == None:
			self.traverser.traverse(engine.renderLit)
		else:
			self.traverser.traverse(node)
		self.traverser.clearColliders()
		queue.sortEntries()
		return queue
		
	def getCollisionQueue(self, position, direction, node = None):
		"""Gets a CollisionHandlerQueue containing all collisions along the specified ray.
		Only checks for collisions with the specified NodePath, if one is given."""
		cNode = CollisionNode("cnode")
		nodepath = render.attachNewNode(cNode)
		cNode.setIntoCollideMask(BitMask32(0))
		cNode.setFromCollideMask(BitMask32(1))
		ray = CollisionRay(position.getX(), position.getY(), position.getZ(), direction.getX(), direction.getY(), direction.getZ())
		cNode.addSolid(ray)
		queue = CollisionHandlerQueue()
		self.traverser.addCollider(nodepath, queue)
		if node == None:
			self.traverser.traverse(engine.renderLit)
		else:
			self.traverser.traverse(node)
		self.traverser.clearColliders()
		nodepath.removeNode()
		queue.sortEntries()
		return queue
	
	def getRayFirstCollision(self, rayNP, node = None):
		"""Gets a CollisionEntry for the first collision along the specified ray.
		Only checks for collisions with the specified NodePath, if one is given."""
		queue = self.getRayCollisionQueue(rayNP, node)
		if queue.getNumEntries() > 0:
			return queue.getEntry(0)
		else:
			return None
	
	def getFirstCollision(self, position, direction, node = None):
		"""Gets a CollisionEntry for the first collision along the specified ray.
		Only checks for collisions with the specified NodePath, if one is given."""
		queue = self.getCollisionQueue(position, direction, node)
		if queue.getNumEntries() > 0:
			return queue.getEntry(0)
		else:
			return None
	
	def testCollisions(self, node, traversePath = None):
		if traversePath == None:
			traversePath = engine.renderLit
		"Tests for any and all collisions on the specified nodepath."
		queue = CollisionHandlerQueue()
		self.traverser.addCollider(node, queue)
		self.traverser.traverse(traversePath)
		self.traverser.clearColliders()
		queue.sortEntries()
		return queue
	
	def delete(self):
		"Destroys the ODE world. IMPORTANT: do not delete the AI world before deleting the entity group."
		for point in self.spawnPoints:
			point.delete()
		del self.spawnPoints[:]
		for dock in self.docks:
			dock.delete()
		del self.docks[:]
		if self.navMesh != None:
			self.navMesh.delete()
		self.world.destroy()
		self.space.destroy()

navMeshCache = dict()
class NavMesh:
	def __init__(self, directory, filename):
		global navMeshCache
		self.edges = []
		self.nodes = []
		self.filename = filename
		if directory + "/" + self.filename in navMeshCache:
			navMesh = navMeshCache[directory + "/" + self.filename]
			self.edges = navMesh.edges
			self.nodes = navMesh.nodes
		else:
			node = loader.loadModel(directory + "/" + self.filename)
			self._processNode(node)
			node.removeNode()
			navMeshCache[directory + "/" + self.filename] = self
	
	def delete(self):
		pass
	
	def _processNode(self, node):
		geomNodeCollection = node.findAllMatches('**/+GeomNode')
		for nodePath in geomNodeCollection:
			geomNode = nodePath.node()
			self._processGeomNode(geomNode)
		for edge in self.edges:
			if len(edge.nodes) <= 1:
				# This edge isn't between two nodes, so we don't need to worry about it when pathfinding. 
				# But we still need it for determining which node an agent is in. 
				edge.navigable = False

	def _processGeomNode(self, geomNode):
		for i in range(geomNode.getNumGeoms()):
			geom = geomNode.getGeom(i)
			state = geomNode.getGeomState(i)
			self._processGeom(geom)

	def _processGeom(self, geom):
		vdata = geom.getVertexData()
		for i in range(geom.getNumPrimitives()):
			prim = geom.getPrimitive(i)
			self._processPrimitive(prim, vdata)

	def _processPrimitive(self, prim, vdata):
		vertex = GeomVertexReader(vdata, "vertex")
		prim = prim.decompose()
		def getVertex(index):
			vi = prim.getVertex(index)
			vertex.setRow(vi)
			return vertex.getData3f()
		for p in range(prim.getNumPrimitives()):
			s = prim.getPrimitiveStart(p)
			e = prim.getPrimitiveEnd(p)
			for i in range(s, e):
				v = getVertex(i)
				if i + 1 >= e:
					break
				v2 = getVertex(i + 1)
				edge1 = self.addEdge(v, v2)
				if i + 2 >= e:
					break
				v3 = getVertex(i + 2)
				edge2 = self.addEdge(v2, v3)
				edge3 = self.addEdge(v3, v)
				self.nodes.append(NavNode(edge1, edge2, edge3))

	def addEdge(self, v1, v2):
		edge = self._checkForEdge(v1, v2)
		if edge == None:
			edge = Edge(Vec3(v1), Vec3(v2))
			self.edges.append(edge)
		return edge
	
	def _checkForEdge(self, v1, v2):
		epsilon = 0.1
		for edge in self.edges:
			if (edge.a.almostEqual(v1, epsilon) and edge.b.almostEqual(v2, epsilon)) or (edge.a.almostEqual(v2, epsilon) and edge.b.almostEqual(v1, epsilon)):
				return edge
		return None

	def getNode(self, pos, radius = 1, lastKnownNode = None):
		if lastKnownNode != None:
			if lastKnownNode.containerTest(pos, radius):
				return lastKnownNode
			nodes = []
			for edge in lastKnownNode.edges:
				nodes += [x for x in edge.getNodes() if x != lastKnownNode and x.containerTest(pos, radius)]
			if len(nodes) == 0:
				nodes = [x for x in self.nodes if x.containerTest(pos, radius)]
		else:
			nodes = [x for x in self.nodes if x.containerTest(pos, radius)]
		size = len(nodes)
		if size == 0:
			return None
		if size > 1:
			highest = -100
			highestNode = None
			for node in nodes:
				if node.highest > highest and node.lowest < pos.getZ():
					highest = node.highest
					highestNode = node
			return highestNode
		return nodes[0]
	
	def findPath(self, startPos, endPos, radius = 1):
		"A* algorithm."
		startNode = self.getNode(startPos, radius)
		endNode = self.getNode(endPos, radius)
		return self.findPathFromNodes(startNode, endNode, startPos, endPos, radius)
	
	def findPathFromNodes(self, startNode, endNode, startPos, endPos, radius = 1):	
		# Clear pathfinding data
		for edge in self.edges:
			edge.closed = False
			edge.cameFrom = None
			edge.gScore = 0
			edge.hScore = 0
			edge.fScore = 0
			edge.open = False
		path = Path(startPos, endPos, startNode, endNode, radius)
		openEdges = startNode.edges[:]
		for edge in startNode.edges:
			edge.gScore = 0
			edge.hScore = edge.cost(endNode.center)
			edge.fScore = edge.hScore
			edge.open = True
		def compare(x, y):
			return (x.fScore > y.fScore) - (x.fScore < y.fScore)
		iterations = 0
		while len(openEdges) > 0:
			openEdges.sort(compare)
			currentEdge = openEdges.pop(0)
			if endNode in currentEdge.nodes:
				c = currentEdge
				path.add(currentEdge)
				while c.cameFrom != None:
					c = c.cameFrom
					path.add(c)
				path.clean()
				return path
			currentEdge.closed = True
			for neighbor in currentEdge.neighbors:
				if neighbor.navigable and not neighbor.closed:
					tentativeGScore = currentEdge.gScore + currentEdge.costToEdge(neighbor)
					tentativeIsBetter = False
					if not neighbor.open:
						neighbor.open = True
						openEdges.append(neighbor)
						neighbor.hScore = neighbor.cost(endNode.center)
						tentativeIsBetter = True
					elif tentativeGScore < neighbor.gScore:
						tentativeIsBetter = True
					if tentativeIsBetter:
						neighbor.cameFrom = currentEdge
						neighbor.gScore = tentativeGScore
						neighbor.fScore = neighbor.gScore + neighbor.hScore
			iterations += 1
			if iterations > 9:
				time.sleep(0.0)
				iterations = 0
		return None

class NavNode:
	def __init__(self, edge1, edge2, edge3):
		self.highest = -10000
		self.lowest = 10000
		self.edges = []
		self.edgeNormals = [] # For containerTest
		self.center = Vec3()
		for e in [edge1, edge2, edge3]:
			self._addEdge(e)
		for edge in self.edges:
			self.center += edge.a + edge.b
		self.center /= len(self.edges) * 2 # Node center is only calculated once.
		up = Vec3(0, 0, 1)
		for edge in self.edges:
			toCenter = edge.center - self.center
			toCenter.setZ(0)
			toCenter.normalize()
			parallel = Vec3(edge.a.getX(), edge.a.getY(), 0) - Vec3(edge.b.getX(), edge.b.getY(), 0)
			parallel.setZ(0)
			parallel.normalize()
			normal = parallel.cross(up)
			reverseNormal = normal * -1
			if toCenter.dot(normal) < 0:
				self.edgeNormals.append(normal)
			else:
				self.edgeNormals.append(reverseNormal)
	
	def containerTest(self, p, radius = 1):
		p2 = Vec3(p.getX(), p.getY(), 0)
		if p.getZ() > self.highest + radius + 1 or p.getZ() < self.lowest - radius - 1:
			return False
		for i in range(len(self.edgeNormals)):
			vector = p2 - self.edges[i].flatCenter
			vector.normalize()
			if vector.dot(self.edgeNormals[i]) < 0:
				return False
		# To do: vertical test
		return True
	
	def _addEdge(self, edge):
		if not edge in self.edges:
			if edge.a.getZ() < self.lowest:
				self.lowest = edge.a.getZ()
			if edge.b.getZ() < self.lowest:
				self.lowest = edge.b.getZ()
			if edge.a.getZ() > self.highest:
				self.highest = edge.a.getZ()
			if edge.b.getZ() > self.highest:
				self.highest = edge.b.getZ()
			self.edges.append(edge)
			edge.addNode(self)
			for e in (x for x in self.edges if x != edge):
				edge.addNeighbor(e)
				e.addNeighbor(edge)

class Edge:
	def __init__(self, v1, v2):
		self.a = v1
		self.b = v2
		self.aToBVector = self.b - self.a
		self.aToBVector.normalize()
		self.center = (self.a + self.b) / 2
		self.flatCenter = Vec3(self.center.getX(), self.center.getY(), 0)
		self.neighbors = []
		self.nodes = []
		# Temporary pathfinding data
		self.closed = False
		self.open = False
		self.cameFrom = None
		self.gScore = 0
		self.hScore = 0
		self.fScore = 0
		self.navigable = True
	
	def intersects(self, c, d, radius = 0):
		def ccw(u,v,w):
			return (w.getY() - u.getY()) * (v.getX() - u.getX()) > (v.getY() - u.getY()) * (w.getX() - u.getX())
		a = self.a + (self.aToBVector * radius)
		b = self.b - (self.aToBVector * radius)
		return ccw(a, c, d) != ccw(b, c, d) and ccw(a, b, c) != ccw(a, b, d)

	def addNode(self, node):
		if node not in self.nodes:
			self.nodes.append(node)
	
	def cost(self, pos):
		# The cost is the distance from given point to the closer of our two corners.
		dist1 = (self.a - pos).length()
		dist2 = (self.b - pos).length()
		return min(dist1, dist2)
	
	def costToEdge(self, edge):
		# The cost is the distance between the two closest corners of the two edges.
		dist1 = (self.a - edge.a).length()
		dist2 = (self.b - edge.b).length()
		dist3 = (self.a - edge.b).length()
		dist4 = (self.b - edge.a).length()
		return min(dist1, dist2, dist3, dist4)
	
	def getNodes(self):
		return self.nodes
	
	def addNeighbor(self, e):
		if not e in self.neighbors:
			self.neighbors.append(e)
	
	def getNeighbors(self):
		return self.neighbors

class Path:
	def __init__(self, start = None, end = None, startNode = None, endNode = None, radius = 0):
		self.waypoints = []
		self.edges = []
		self.nodes = []
		if startNode != None and endNode != None:
			self.nodes = [endNode, startNode]
		self.radius = radius
		if start == None:
			self.start = None
			self.end = None
		else:
			self.start = Vec3(start)
			self.end = Vec3(end)
	def clean(self):
		i = len(self.waypoints) - 2
		while i > 0:
			if self.edges[i].intersects(self.waypoints[i - 1], self.waypoints[i + 1], self.radius):
				del self.waypoints[i]
				del self.edges[i]
			i -= 1
	def add(self, edge):
		self.edges.insert(0, edge)
		if len(self.edges) > 1:
			for node in edge.nodes:
				if node in self.edges[1].nodes:
					self.nodes.insert(1, node)
		aDist = (edge.a - self.end).length()
		bDist = (edge.b - self.end).length()
		if len(self.waypoints) > 1:
			last = self.waypoints[1]
			aDist += (edge.a - last).length()
			bDist += (edge.b - last).length()
		if aDist < bDist:
			self.waypoints.insert(0, edge.a + (edge.aToBVector * self.radius))
		else:
			self.waypoints.insert(0, edge.b - (edge.aToBVector * self.radius))
	def current(self):
		if len(self.waypoints) > 0:
			return self.waypoints[0]
		else:
			return None
	def next(self):
		if len(self.waypoints) > 0:
			self.waypoints.pop(0)
		return self.current()
	def hasNext(self):
		return len(self.waypoints) > 1
	def last(self):
		if len(self.waypoints) > 0:
			return self.waypoints[len(self.waypoints) - 1]
		else:
			return None
	def clear(self):
		del self.waypoints[:]
		del self.nodes[:]
		del self.edges[:]