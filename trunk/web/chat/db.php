<?php
$host = "database-host";
$hostuser = "user";
$hostpasswd = "password";
$database = "database";
$connected = false;

function Connect()
{
	global $host, $hostuser, $hostpasswd, $database, $connected;
	if(!$connected)
	{
		$connected = true;
		mysql_connect($host, $hostuser, $hostpasswd) or $connected = false;
		mysql_select_db($database) or $connected = false;
		if(!$connected)
		{
			die();
		}
	}
}

function Query($query)
{
	global $connected;
	if(!$connected)
	{
		Connect();
	}
	$result = mysql_query($query) or die(mysql_error());
	return $result;
}

function CloseConnection()
{
	global $connected;
	mysql_close();
	$connected = false;
}
Connect();
?>