<?php
include "db.php";
if(isset($_POST["user"]) && isset($_POST["msg"]) && $_POST["user"] != "" && $_POST["msg"] != "")
{
	$user = addslashes($_POST["user"]);
	$msg = addslashes($_POST["msg"]);
	Query("INSERT INTO chats (user, msg) VALUES ('" . $user . "', '" . $msg . "');");
}
CloseConnection();
?>