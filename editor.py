from direct.directbase import DirectStart
from random import randint, random, uniform
from pandac.PandaModules import *
import math
import src.engine as engine
import src.ai as ai
import src.audio as audio
import src.entities as entities
import src.ui as ui
import src.net as net
import src.net2 as net2
import src.controllers as controllers

import sys

engine.loadConfigFile()

# Setup window
props = WindowProperties()
props.setCursorHidden(True)
props.setTitle("A3P Editor")
base.win.requestProperties(props)
base.setBackgroundColor(0, 0, 0)

filename = sys.argv[1]

engine.init()
net.init(net.MODE_SERVER)
aiWorld = ai.World()
netManager = net2.NetManager()
entityGroup = entities.EntityGroup(netManager)
ui = ui.EditorUI()
map = engine.Map()
map.load(filename, aiWorld, entityGroup)
base.disableAllAudio()

editor = controllers.EditController(aiWorld, entityGroup, map, ui)

def gameTask(task):
	global aiWorld
	global entityGroup
	global map
	global ui
	global editor

	engine.update()
	ui.update()
	editor.serverUpdate(aiWorld, entityGroup, None)
	map.update()
	engine.endUpdate()

	return task.cont

taskMgr.add(gameTask, "Game Task")

run()