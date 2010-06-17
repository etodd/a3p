<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
<head>
	<title>A3P - Acquire, Attack, Asplode, Pwn!</title>
	<link href="../style.css" type="text/css" rel="stylesheet"/>
	<link rel="shortcut icon" type="image/x-icon" href="../icon.ico"/>
	<script src="../RunPanda3D.js" language="javascript"></script>
	<script type="text/javascript"> 
	function PluginFail()
	{
		alert("The Panda3D plugin failed to load. Please reload the page. If this message persists, please restart the browser, or uninstall and reinstall the plugin.");
	}
	function LoadGame()
	{
		var wrapper = document.getElementById("wrapper");
		wrapper.innerHTML += P3D_RunContent("data", "game.p3d", "id", "game",
			  "width", "928", "height", "600", "auto_start", "1", "username", "<?php echo base64_decode($_REQUEST["u"]);?>",
			  "onPluginFail", "PluginFail()", "onPythonStop", "OnStop()", "splash_img", "http://a3p.sourceforge.net/play/loading.png")
	}
	</script>
</head>
<body style="height: 100%;" onload="LoadGame()">
	<div class="Container" style="width: 1200px; margin-top: 0px; text-align: center;">
		<div style="width: 928px; margin-left: auto; margin-right: auto; margin-top: 50px;" id="wrapper">
		</div>
		<div style="color: white; margin-top: 5px;">Can't see the game? <a href="http://www.panda3d.org/download/panda3d-runtime-1.0.0/Panda3D-Runtime-1.0.0.exe">Install this plugin</a> and restart your browser.</div>
	</div>
</div>
</body>
</html>