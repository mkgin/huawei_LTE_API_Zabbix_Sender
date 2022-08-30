# Huawei LTE modem monitor for Zabbix

* monitors certain parameters from a Huawei modem using the [huawei-lte-api](https://github.com/Salamek/huawei-lte-api)
* sends values to a [Zabbix](https://www.zabbix.com/) server 

![Signal_Screenshot](Signal_Screenshot.png)

* values can be configured to be reported (sent) as follows:
    * each time polled
    * reported only when changed  (reports value from last polling interval too)
    * or after certain intervals

* uses the following libraries
    * https://github.com/Salamek/huawei-lte-api
	* https://github.com/adubkov/py-zabbix
        * https://py-zabbix.readthedocs.io/en/latest/sender.html

![SINR_Graph](SINR_Graph.png)

## Current status

* Currently focused only on collecting data from the
  =huawei.lte.device.signal= part of the api 
* Testing with python 3.9
* Testing on Huawei B535-333

* Handles connection problems to modem and zabbix moderately well
  (see tests/NOTES.md)

## next
* need to fix logging (configure levels)
* may more stuff configurable
* improve clarity of counter and timer printed info

### IDEAS / TODO,
  - handle other parts of the api via YAML config file 
    without making configuration to appear too difficult?
  - handle parsed arguments
  - generate a simple zabbix template?
  - items suitable for populating zabbix inventory
  - client.device.information
  - client.device.basic_information
  - client.device.antenna_type
  - client.monitoring.check_notifications
  - Net.current_plmn (operator name)
  - Monitoring.traffic_statistic (connect time)
  - certain IP addresses
  - Sms.sms_count
  - OnlineUpdate.status
  - User.history_login
