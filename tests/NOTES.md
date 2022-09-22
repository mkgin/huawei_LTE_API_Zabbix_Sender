# Testing notes

## Modem tests
* try wrong hostname
* try turning modem off
* try nc ...
* web server (login will fail I guess...)
* web server that accepts any login?

### Modem API connection errors
* ResponseErrorException, ResponseErrorLoginCsrfException, ResponseErrorLoginRequiredException
   * Login session has timed out ( seems to happen after 2-3 minutes or a few logins
    * "100003: No rights (needs login)"
* LoginErrorUsernamePasswordOverrunException
    * Login blocked by modem ( 3 password failures in one minute from same IP#? as this poller runs from) need to wait 60 sec
* ResponseErrorWrongSessionToken: 125003: Wrong Session Token
    * Not sure, token may have expired after running for about 9.5 days (was testing with another program at the same time)

* New error? 
    * RemoteDisconnected
    * ```
      File "/usr/lib/python3.9/http/client.py", line 276, in _read_status
      raise RemoteDisconnected("Remote end closed connection without"
      http.client.RemoteDisconnected: Remote end closed connection without response
	 ```
    * this may have been caused by this ...
    * ```
      huawei_lte_api_zabbix_sender.py:154:19: E0701: Bad except clauses order (ResponseErrorException is an ancestor class of LoginErrorUsernamePasswordOverrunException) (bad-except-order)
      ```
    * this is what happened first:
	* ```
	    File "/usr/lib/python3.9/http/client.py", line 276, in _read_status
    raise RemoteDisconnected("Remote end closed connection without"
http.client.RemoteDisconnected: Remote end closed connection without response
      ```
	* Connection error logging should be a bit more detailed
	    * get more info about the order of exceptions in order to be able to
	    handle them better

## Zabbix server tests

* connect to wrong server/wrong port 
  * ( connection refused) "[Errno 111] Connection refused"
* connect to non existing hostname 
  * "[Errno 113] No route to host"
* connect to wrong listening port ( eg. ```nc -l -p 10051 -q 600```
  * 'pyzabbix.sender:Sending failed: Connection to ('localhost', 10051) timed out after10 seconds'
  * 'timed out'

* pause the Zabbix server VM.

## Test the api configuration loader

* tests that it does what is supposed to
* breaking tests
  * YAML that was not formatted as expected might have caused and infinite loop... 
    or something that was long... get_sending_strategy calls itself, maybe should set some limit
