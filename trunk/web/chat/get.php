<?php
include "db.php";

function niceTime($time) {
	$delta = time() - $time;
	if ($delta < 60) {
		return 'less than a minute ago.';
	} else if ($delta < 120) {
		return 'about a minute ago.';
	} else if ($delta < (45 * 60)) {
		return floor($delta / 60) . ' minutes ago.';
	} else if ($delta < (90 * 60)) {
		return 'about an hour ago.';
	} else if ($delta < (24 * 60 * 60)) {
		return 'about ' . floor($delta / 3600) . ' hours ago.';
	} else if ($delta < (48 * 60 * 60)) {
		return '1 day ago.';
	} else {
		return floor($delta / 86400) . ' days ago.';
	}
}

if(isset($_POST["i"]) && $_POST["i"] != "" && is_numeric($_POST["i"]))
{
	$lastId = $_POST["i"];
	$result = Query("SELECT * FROM chats WHERE id > '" . $lastId . "' ORDER BY id DESC LIMIT 20;");
	$output = "";
	$firstRow = true;
	$lastSent = "NEVER";
	while($row = mysql_fetch_array($result))
	{
		if($firstRow)
		{
			$lastId = $row["id"];
			$lastSent = $row["time"];
			$firstRow = false;
		}
		$output = $row["user"] . "\t" . $row["msg"] . "\n" . $output;
	}
	$output = $lastId . "\n" . $output;
	if($_POST["i"] == "0")
	{
		$output = $output . "\nConsole\tWelcome to A3P. Last message sent " . ($lastSent == "NEVER" ? $lastSent : niceTime(strtotime($lastSent)));
	}
	echo $output;
}
CloseConnection();
?>