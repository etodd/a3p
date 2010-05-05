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

ACCURACY = 0.7 # Relative probability of an AI droid hitting its target.

class World:
	"""The AI world models the physics world as a series of grids, where each cell has a traversal cost associated with it.
	Portals can be created between grids, and AI entities navigate through the grids using an A* search algorithm.
	The AI world also contains the ODE world and space, and includes functions to test for collisions."""
	def __init__(self):
		"Initializes the ODE world and space."
		self.grids = dict()
		self.waypoints = dict()
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

	def addWaypoint(self, waypoint):
		self.waypoints[waypoint.id] = waypoint
	
	def removeWaypoint(self, waypoint):
		waypoint.delete()
		del self.waypoints[waypoint.id]
	
	def addSpawnPoint(self, point):
		self.spawnPoints.append(point)

	def deleteSpawnPoint(self, point):
		self.spawnPoints.remove(point)
	
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

	def getNearestWaypoint(self, pos):
		lowestDistance = -1
		returnValue = None
		for point in self.waypoints.values():
			vector1 = pos - point.position
			dist = vector1.length()
			if dist < lowestDistance or lowestDistance == -1:
				lowestDistance = dist
				returnValue = point
		return returnValue

	def getNearestWaypointOtherThan(self, pos, waypoint):
		lowestDistance = -1
		returnValue = None
		for point in (x for x in self.waypoints.values() if x != waypoint):
			vector1 = pos - point.position
			dist = vector1.length()
			if dist < lowestDistance or lowestDistance == -1:
				lowestDistance = dist
				returnValue = point
		return returnValue
	
	def getNearestSpawnPoint(self, pos):
		lowestDistance = -1
		returnValue = None
		for point in self.spawnPoints:
			vector1 = pos - point.getPosition()
			dist = vector1.length()
			if dist < lowestDistance or lowestDistance == -1:
				lowestDistance = dist
				returnValue = point
		return returnValue.getPosition()
	
	def getOpenSpawnPoint(self, team, entityGroup):
		largestSmallestDistance = -1
		returnValue = None
		enemies = [x for x in entityGroup.entities.values() if isinstance(x, entities.Actor) and x.team != team]
		dockpos = []
		if team.dock != None:
			dockpos = [team.dock.getPosition()]
		for point in dockpos + [x.getPosition() for x in self.spawnPoints]:
			smallestDistance = 10000000
			for enemy in enemies:
				dist = (point - enemy.getPosition()).length()
				if dist < smallestDistance:
					smallestDistance = dist
			if smallestDistance > largestSmallestDistance or returnValue == None:
				largestSmallestDistance = smallestDistance
				returnValue = point
		return returnValue

	def getRandomSpawnPoint(self):
		return choice(self.spawnPoints).getPosition()
	
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
	
	def findPath(self, startPos, endPos, avoidedWaypoint = None):
		if avoidedWaypoint != None:
			return self._find(self.getNearestWaypointOtherThan(startPos, avoidedWaypoint), self.getNearestWaypoint(endPos))
		else:
			return self._find(self.getNearestWaypoint(startPos), self.getNearestWaypoint(endPos))
	
	def _find(self, startPoint, endPoint):
		"A* algorithm."
		if len(self.waypoints) == 0:
			return None
		def reconstructPath(path, currentPoint):
			if currentPoint.cameFrom != None:
				reconstructPath(path, currentPoint.cameFrom)
				currentPoint.clear()
				path.add(currentPoint)
		self.clearPaths()
		path = Path()
		path.add(startPoint)
		openPoints = [startPoint]
		startPoint.gScore = 0
		startPoint.hScore = (startPoint.position - endPoint.position).length()
		startPoint.fScore = startPoint.hScore + startPoint.gScore
		while len(openPoints) > 0:
			openPoints.sort(lambda x, y: (x.fScore > y.fScore) - (x.fScore < y.fScore))
			currentPoint = openPoints.pop(0)
			if currentPoint == endPoint:
				reconstructPath(path, currentPoint)
				return path
			currentPoint.closed = True
			for link in currentPoint.links:
				neighbor = link.b
				if link.b == currentPoint:
					neighbor = link.a
				if neighbor.closed:
					continue
				tentativeGScore = currentPoint.gScore + link.distance
				tentativeIsBetter = False
				if not neighbor in openPoints:
					openPoints.append(neighbor)
					neighbor.hScore = (neighbor.position - endPoint.position).length()
					tentativeIsBetter = True
				elif tentativeGScore < neighbor.gScore:
					tentativeIsBetter = True
				if tentativeIsBetter:
					neighbor.cameFrom = currentPoint
					neighbor.gScore = tentativeGScore
					neighbor.fScore = neighbor.gScore + neighbor.hScore
		return None
	
	def clearPaths(self):
		for waypoint in self.waypoints.values():
			waypoint.clear()
	
	def delete(self):
		"Destroys the ODE world. IMPORTANT: do not delete the AI world before deleting the entity group."
		for point in self.spawnPoints:
			point.delete()
		del self.spawnPoints[:]
		for dock in self.docks:
			dock.delete()
		del self.docks[:]
		self.world.destroy()
		self.space.destroy()

class Waypoint:
	def __init__(self, id, pos):
		self.id = id
		self.position = Vec3(pos)
		self.links = []
		self.closed = False
		self.cameFrom = None
		self.gScore = 0
		self.hScore = 0
		self.fScore = 0
		
	def clear(self):
		self.closed = False
		self.cameFrom = None
		self.gScore = 0
		self.hScore = 0
		self.fScore = 0
		
	def link(self, waypoint):
		if waypoint != self:
			for link in self.links:
				if link.a == waypoint or link.b == waypoint:
					return # We're already linked
			link = WaypointLink(self, waypoint)
			self.links.append(link)
			waypoint.links.append(link)
	
	def delete(self):
		self.clear()
		for link in self.links:
			neighbor = link.b
			if link.b == self:
				neighbor = link.a
			neighbor.links.remove(link)
		del self.links[:]

class WaypointLink:
	def __init__(self, a, b):
		self.a = a
		self.b = b
		self.distance = (self.a.position - self.b.position).length()

class Path:
	def __init__(self):
		self.waypoints = []
	def add(self, point):
		self.waypoints.append(point)
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