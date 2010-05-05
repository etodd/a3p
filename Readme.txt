A3P Source Code

GENERAL INFO

All Python code and visual assets by Evan Todd. Sounds from freesound.org,
modified with Audacity. Other software used: Blender, Inkscape, Gimp, Notepad++.

A3P makes use of the Panda3D engine, which is licensed under the Modified
BSD license. For more info, see Panda3D License.txt. A3P itself
uses the MIT License. For more information, see MIT License.txt.

RUNNING A3P FROM SOURCE

1. Download and install Panda3D: http://panda3d.org
   Currently, A3P requires at least version 1.7.0.
   Make sure you install Panda3D *within* the A3P source folder, to
   make things easier. If you know what you're doing, install it wherever
   you want.

2. Add the Panda3D Python directory to your system path. Then open a command
   prompt and navigate to the A3P source folder. If you have other Python
   installations, you may have to erase the PYTHONPATH environment variable.
   
3. Run this command:
   python main.py

4. To see more command line arguments, run this command:
   python main.py -h