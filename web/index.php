<?php
require_once('common.php');
$name = "Unnamed";
$loggedin = array_key_exists("name", $_REQUEST) || array_key_exists(LACE_NAME_COOKIE, $_COOKIE);
if($loggedin)
{
	$name = array_key_exists("name", $_REQUEST) ? $_REQUEST["name"] : $_COOKIE[LACE_NAME_COOKIE];
	validateSession();
}
?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
<head>
	<title>A3P - Acquire, Attack, Asplode, Pwn!</title>
	<link href="../style.css" type="text/css" rel="stylesheet"/>
	<link rel="shortcut icon" type="image/x-icon" href="../icon.ico"/>
	<script src="../RunPanda3D.js" language="javascript"></script>
	<script type="text/javascript">
	var name = "<?php echo $name;?>";
	</script>
	<script type="text/javascript" src="scripts.js"></script>
	<?php if($loggedin) require_once('scripts/lace.js.php'); ?>
</head>
<body onload="Initialize()">
	<div class="Container" style="width: 1200px; margin-top: 150px;">
		<?php
		if($loggedin)
		{
		?>
		<div id="lace">
			<?php
				// Include the content file.
				require_once('lib/includes/lace.inc.php');
			?>
		</div>
		<div style="width: 928px;" id="wrapper">
			<div id="gametype" class="dialog" style="font-size: x-large;">
				<b>Choose game type</b>
				<ul>
					<li><a href="javascript:Hide('gametype'); Show('maps');">Deathmatch</a></li>
					<li><a href="javascript:Hide('gametype'); Show('survivalmaps');">Survival</a></li>
				</ul>
				<button onclick="Hide('gametype'); Show('menu');">Back</button>
			</div>
			<div id="maps" class="dialog" style="font-size: x-large;">
				<b>Choose map</b>
				<ul>
					<li><a href="javascript:StartServer('arena');">[4P] Arena</a></li>
					<li><a href="javascript:StartServer('impact');">[4P] Impact</a></li>
					<li><a href="javascript:StartServer('orbit');">[3P] Orbit</a></li>
					<li><a href="javascript:StartServer('complex');">[2P] Complex</a></li>
					<li><a href="javascript:StartServer('verdict');">[2P] Verdict</a></li>
					<li><a href="javascript:StartServer('grid');">[2P] Grid</a></li>
				</ul>
				<button onclick="Hide('maps'); Show('gametype');">Back</button>
			</div>
			<div id="tutmaps" class="dialog" style="font-size: x-large;">
				<b>Choose map</b>
				<ul>
					<li><a href="javascript:StartTutorial('arena');">[4P] Arena</a></li>
					<li><a href="javascript:StartTutorial('impact');">[4P] Impact</a></li>
					<li><a href="javascript:StartTutorial('orbit');">[3P] Orbit</a></li>
					<li><a href="javascript:StartTutorial('complex');">[2P] Complex</a></li>
					<li><a href="javascript:StartTutorial('verdict');">[2P] Verdict</a></li>
					<li><a href="javascript:StartTutorial('grid');">[2P] Grid</a></li>
				</ul>
				<button onclick="Hide('tutmaps'); Show('menu');">Back</button>
			</div>
			<div id="survivalmaps" class="dialog" style="font-size: x-large;">
				<b>Choose map</b>
				<ul>
					<li><a href="javascript:StartSurvival('matrix');">[4P] Matrix</a></li>
				</ul>
				<button onclick="Hide('survivalmaps'); Show('gametype');">Back</button>
			</div>
			<div id="hosts" class="dialog" style="text-align: left;">
				<iframe style="width: 100%; height: 200px;" id="hostsFrame" src="http://et1337.ath.cx/hosts.html"></iframe>
				<button onclick="ShowHosts();" style="float: right;">Refresh</button>
				<button onclick="Hide('hosts'); Show('menu');">Back</button>
			</div>
			<div id="menu" class="dialog" style="font-size: x-large;">
				<h1>ASPLODE</h1>
				<ul>
					<li><a href="javascript:Hide('menu'); Show('gametype');">Host</a></li>
					<li><a href="javascript:Hide('menu'); ShowHosts();">Join</a></li>
					<li><a href="javascript:Hide('menu'); Show('tutmaps');">Tutorial</a></li>
				</ul>
			</div>
		</div>
		<script type="text/javascript">
		LoadGame();
		</script>
		<?php
		}
		else
		{
		?>
		<div style="margin-top: 200px; width: 650px; margin-left: auto; margin-right: auto; background-color: white; padding: 10px;">
			<div style="width: 300px; float: right;">
				<h3>Login</h3>
				<form id="form1" method="post">
					<table>
						<tr><td>Username <small>(just come up with one. We are very serious about security here.)</small></td><td><input type="text" name="name"/></td></tr>
						<tr><td></td><td><input type="submit" value="Login"/></td></tr>
					</table>
				</form>
			</div>
			<div style="width: 300px;">
				<h3>New players</h3>
				<a href="/install">Install the plugin first</a>
			</div>
			<br style="clear: both;"/>
		</div>
		<?php
		}
		?>
	</div>
</div>
</body>
</html>