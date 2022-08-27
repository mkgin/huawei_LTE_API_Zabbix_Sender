# Default config. REMEMBER TO SET 'PASSWORD'
modem_url = 'http://admin:PASSWORD@192.168.8.1/'

# use zabbix config from host /etc/zabbix/zabbix_agentd.conf (ServerActive=...)
# zabbix-server need to allow zabbix trap connections)
zasender = ZabbixSender(use_config=True)
#ZabbixSender('hostname')
#ZabbixSender('IP ADDRESS')


# needs to be same as 'Host name 'configured in Zabbix front end
monitored_hostname = 'mymodem.local'
