function PluginFail()
{
	alert("The Panda3D plugin failed to load. Please reload the page. If this message persists, please restart the browser, or uninstall and reinstall the plugin.");
}
function StartClient(host)
{
	var plugin = document.getElementById("game");
	plugin.main.go(2, 0, "Unnamed", "", host);
	Hide("hosts");
	ShowGame();
}
function StartServer(map)
{
	var plugin = document.getElementById("game");
	plugin.main.go(1, 0, name, map, "");
	Hide("maps");
	ShowGame();
}
function StartTutorial(map)
{
	var plugin = document.getElementById("game");
	plugin.main.go(3, 0, name, map, "");
	Hide("tutmaps");
	ShowGame();
}
function StartSurvival(map)
{
	var plugin = document.getElementById("game");
	plugin.main.go(1, 1, name, map, "");
	Hide("survivalmaps");
	ShowGame();
}
function Show(id)
{
	var x = document.getElementById(id);
	x.style.display = "block";
}
function Hide(id)
{
	document.getElementById(id).style.display = "none";
	document.getElementById("wrapper").focus();
}
function ShowGame()
{
	document.getElementById("game").style.visibility = "visible";
}
function HideGame()
{
	document.getElementById("game").style.visibility = "hidden";
}
function Initialize()
{
	document.getElementById("wrapper").errorHandler = function(msg) { alert(msg); }
}
function OnStop()
{
	var plugin = document.getElementById("game");
	plugin.parentNode.removeChild(plugin);
	LoadGame();
}
function LoadGame()
{
	var wrapper = document.getElementById("wrapper");
	wrapper.innerHTML += P3D_RunContent("data", "game.p3d", "id", "game",
		  "width", "928", "height", "600", "auto_start", "1",
		  "onPluginFail", "PluginFail()", "onPythonStop", "OnStop()", "onPythonLoad", "OnLoad()", "splash_img", "http://a3p.sourceforge.net/play/loading.png");
}
function OnLoad()
{
	HideGame();
	Hide("maps");
	Hide("tutmaps");
	Hide("hosts");
	Show("menu");
}
var xhttp = null;
function ShowHosts()
{
	Show("hosts");
	document.StartClient = StartClient;
	var hosts = document.getElementById("hostsFrame");
	hosts.src = "http://et1337.ath.cx/hosts.html?" + new Date().getTime();
}