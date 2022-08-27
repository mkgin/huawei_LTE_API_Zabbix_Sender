#
# Huawei LTE modem monitor for Zabbix
#
# - monitor, store last and only report changes for some parameters send data to Zabbix.
# - collect timestamps
#
# - for some items, send timestamp , mark what was last sent
# - tested with a 4G-LTE modem ( Huawei B535-232) so I may have missed some parameters
#   the would be interesting to 5G (or 3G)
#

from huawei_lte_api.Client import Client #https://github.com/Salamek/huawei-lte-api
from huawei_lte_api.Connection import Connection
from huawei_lte_api.exceptions import \
    ResponseErrorException, \
    ResponseErrorLoginRequiredException, \
    ResponseErrorNotSupportedException, \
    ResponseErrorSystemBusyException, \
    ResponseErrorLoginCsrfException, \
    ResponseErrorWrongSessionToken, \
    RequestFormatException
from pyzabbix import ZabbixMetric, ZabbixSender #https://py-zabbix.readthedocs.io/en/latest/sender.html
import pprint
import time
import sys  # to report errors
import logging
import os
import yaml


log_level =''
zabbix_sender_setting = ''
modem_url = ''
monitored_hostname = ''
minimum_polling_interval = ''

def load_config():
    # basic config
    # api config
    config = {}
    current_path = os.getcwd()
    # should really just loop through config files.
    # and maybe allow one to be specified as an argument
    configfile_default = f'{current_path}/config.yml'
    configfile_own = f'{current_path}/own_config.yml'
    print( current_path,configfile_default, configfile_own)
    if os.path.isfile(configfile_default):
        config = yaml.safe_load(open(configfile_default))
    else:
        print("Missing: ",configfile_default )
    if os.path.isfile(configfile_own):
        config.update(yaml.safe_load(open(configfile_own)))
    else:
        print("Missing",configfile_own )
    global modem_url, zabbix_sender_setting,monitored_hostname, minimum_polling_interval,log_level
    modem_url=config['modem_url']
    zabbix_sender_setting=config['zabbix_sender_setting']
    monitored_hostname = config['monitored_hostname']
    minimum_polling_interval = config['minimum_polling_interval']
    log_level = config['log_level']
    logging.basicConfig(level=logging.DEBUG) #FIX this
    

#todo
#parsed = "txpower"
key_prefix = 'huawei.lte' # name for the start of the zabbix key... rest is the api endpoint and api key (for the value)

# endpoint 'device.signal'
# what to parse "PPusch:7dBm PPucch:-3dBm PSrs:-40dBm PPrach:7dBm"

# always interesting sent every polling interval
always_interesting = ['rsrq', 'rsrp', 'rssi', 'sinr', 'txpower' ]
# changes_interesting are sent when changed or when the last result is older than the last one to be sent.
# when there is a change in value, the previous value is sent also (with timestamp of the previous interval
# the idea of this is to make graphs look nicer.
changes_interesting_10min =  ['pci' ,'cell_id','band','nei_cellid']
changes_interesting_1hour =  ['ims','tac','mode', "rrc_status",'plmn','lteulfreq', 'ltedlfreq', 'enodeb_id', 'ulbandwidth','dlbandwidth' ]
interesting = always_interesting +  changes_interesting_10min + changes_interesting_1hour
polling_interval = 60

api_config = {}

# 100003: No rights (needs login)
#

def main():
    ten_minutes = 600
    one_hour = 3600
    load_config()
    logging.basicConfig(level=logging.DEBUG)
    zasender = ZabbixSender(zabbix_sender_setting)
    epoch_time_start = int(time.time())
    with Connection(modem_url) as connection:
        client = Client(connection)    
        count = 1
        lastchanged={}
        lastvalue={}
        changed_count = 0
        stale_count = 0
        not_changed_count = 0
        not_stale_count = 0
        reconnect_count = 0
        while( count < 2 ):
            zapacket = []
            api_endpoint = 'device.signal' #hack until able to parse api endpoints and keys from yaml config
            try:
                stuff = client.device.signal()
            except ( ResponseErrorException, ResponseErrorLoginCsrfException, ResponseErrorLoginRequiredException ) as error_msg:
                logging.warning('Reconnecting due to error: {0}'.format(error_msg))
                reconnect_count += 1
                logging.warning('Reconnect count:' ,reconnect_count )
                with Connection(modem_url) as connection:
                    client = Client(connection)
                    stuff = client.device.signal()
            except LoginErrorUsernamePasswordOverrunException as error_msg:
                # happens if too many failed logins on the front end (from same IP?)
                # blocks failing ip only? login state -1 means one ip is blocked.
                #
                logging.warning('Too many failed logins to modem: {0}'.format(error_msg))
                logging.warning('Sleeping one minute before trying again')
            except:
                logging.error("Unexpected error:", sys.exc_info()[0])
                raise
            # handle error... renew connection?
            epoch_time = int(time.time())
            for k,v in stuff.items():
                # if k in parsed, parse it  TODO (make a new function for it)
                if k in always_interesting:
                    zapacket = zapacket + [ ZabbixMetric( monitored_hostname , f'{key_prefix}.{api_endpoint}.{k}' , v, epoch_time ) ]
                elif ( k in interesting ) and (k not in lastchanged): #or lastvalue...
                    logging.debug(f"{k} not in lastchanged {k not in lastchanged}")
                    zapacket = zapacket + [ ZabbixMetric( monitored_hostname , f'{key_prefix}.{api_endpoint}.{k}' , v, epoch_time ) ]
                    lastchanged[k] = epoch_time
                    lastvalue[k] = v
                elif k in interesting: #changes_interesting_10min or k in changes_interesting_1hour:
                    # for now we'll handle the same and test
                    if ( not lastvalue[k] == v
                         or (k in changes_interesting_10min and (epoch_time - lastchanged[k] > one_hour ))
                         or (k in changes_interesting_1hour and (epoch_time - lastchanged[k] > ten_minutes ))
                         #or  True
                         ):
                        # if value changed. send previous data from previous interval with last interval if not equal.
                        if not lastvalue[k] == v:
                            logging.debug(f'{k} changed from {lastvalue[k]} to {v}')
                            changed_count += 1
                            not_stale_count += 1
                            if epoch_time_last > lastchanged[k]:
                                zapacket = zapacket + [ ZabbixMetric( monitored_hostname , f'{key_prefix}.{api_endpoint}.{k}' ,lastvalue[k] ,epoch_time_last) ]
                                logging.debug(f'{k} changed before last check sending previous interval sending previous data from {epoch_time - lastchanged[k]} sec')
                        else:
                            logging.debug(f'{k} data is stale after {epoch_time - lastchanged[k]} sec')
                            stale_count += 1
                            not_changed_count += 1
                        zapacket = zapacket + [ ZabbixMetric( monitored_hostname , f'{key_prefix}.{api_endpoint}.{k}' , v, epoch_time ) ]
                        lastchanged[k] = epoch_time
                        lastvalue[k] = v
                    else:
                        not_changed_count += 1
                        not_stale_count += 1
                        logging.debug(f'{k} not changed/not stale or too old {epoch_time - lastchanged[k]} ')
                else:
                    z=1
                    logging.debug(f'{k} is not interesting: {k} : {v}')
            print(f'*** Time: {epoch_time} poll count: {count} uptime: {epoch_time - epoch_time_start} ***')
            print(f'*** stale:not {stale_count}:{not_stale_count} , changed:not {changed_count}:{not_changed_count} ***')
            #pprint.pp(zapacket)
                   
            epoch_time_last = epoch_time
            #pprint.pp(lastchanged)
            pprint.pp(zapacket )
            zasender.send(zapacket)
            count += 1
            time.sleep(polling_interval)
main()
