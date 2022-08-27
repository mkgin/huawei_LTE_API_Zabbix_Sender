# Huawei LTE modem monitor for Zabbix

* monitor certain parameters from a Huawei modem using the huawei-lte-api
* reports values to a zabbix server
* values can be reported each time polled or reported only when changed or after certain intervals

* uses the following libraries from Pypi
  * https://github.com/Salamek/huawei-lte-api
  * https://py-zabbix.readthedocs.io/en/latest/sender.html

## Status

* Currently focused only on collecting data from the
  =huawei.lte.device.signal= part of the api 


##



## TODO

### Ideas / TODO,
  - Elegant way to handle other parts of the api  via config file 
    without making configuration to appear too difficult?
    * YAML?
  - items suitable for populating zabbix inventory
  - client.device.information
  - client.device.basic_information
  - client.device.antenna_type
  - client.monitoring.check_notifications
  - NTP /system clock SNtp.timeinfo
  - Net.current_plmn (operator name)
  - Monitoring.traffic_statistic (connect time)
  - certain IP addresses
  -  Sms.sms_count
  - are temperatures available
  - OnlineUpdate.status
  - security.. User.history_login
