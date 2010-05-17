# Evan Todd 2010

GAME_NAME = "A3P"
VERSION_CODE = "v0.6"
COPYRIGHT = "Evan Todd 2010"

from pandac.PandaModules import loadPrcFileData
loadPrcFileData("", "window-type none") 
from direct.showbase.ShowBase import ShowBase
from direct.showbase.DirectObject import DirectObject
from pandac.PandaModules import *
import sys

ShowBase() 
base.makeDefaultPipe()
base.openDefaultWindow()

import src.engine as engine
import src.audio as audio
import src.online as online
import src.net as net
import src.core as core
import src.ui as ui

from direct.gui.OnscreenText import OnscreenText
visitorFont = loader.loadFont("menu/visitor2.ttf")
text = OnscreenText(pos = Vec3(0, 0, 0), text = "A3P is installed!\nHit 'play' to get started.", align = TextNode.ACenter, scale = 0.1, fg = (1, 1, 1, 1), shadow = (0, 0, 0, 0.5), font = visitorFont, mayChange = False)

run()