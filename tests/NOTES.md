# Testing notes

## Modem tests

* ResponseErrorException, ResponseErrorLoginCsrfException, ResponseErrorLoginRequiredException
  * Login session has timed out ( seems to happen after 2-3 minutes or a few logins
  * "100003: No rights (needs login)"
* LoginErrorUsernamePasswordOverrunException
  * Login blocked by modem ( 3 password failures in one minute from same IP#? as this poller runs from) need to wait 60 sec

* try wrong hostname
* try turning modem off
* try nc ...
* web server (login will fail I guess...)
* web server that accepts any login?

## Zabbix server tests

* connect to wrong server/wrong port 
  * ( connection refused) "[Errno 111] Connection refused"
* connect to non existing hostname 
  * "[Errno 113] No route to host"
* connect to wrong listening port ( eg. ```nc -l -p 10051 -q 600```
  * 'pyzabbix.sender:Sending failed: Connection to ('localhost', 10051) timed out after10 seconds'
  * 'timed out'

* pause the Zabbix server VM.
