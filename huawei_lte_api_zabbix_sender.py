"""  Huawei LTE modem monitor for Zabbix

https://github.com/mkgin/huawei_LTE_API_Zabbix_Sender

This script monitors a compatible Huawei Modem (4G, LTE, 5G) via the
huawei_lte_api module and reports values to a Zabbix server using the
py-zabbix module.

Items to be monitored are configured in a YAML configuration file. Items
can be sent to the server each time polled, at defined intervals or
whem a change in value is detected. For a given API endpoint, all items
are polled at or near the the shortest reporting rate in that endpoint.
If unchanged, items with longer reporting rates when a change is observed
or when the time since last report sent is exceeded. When a change is observed,
for such an item, the value (unchanged) from the previous polling is sent
to the server as well as the current value.

In the event of a brief connection errors to the Zabbix server, the retrieved
items (and timestamps) are queued to be reported when the connection is again
possible). For longer interruptions, the results can be stored to a file and
manually updated later.
"""

import pprint
import time
import sys  # to report errors
import logging
import os
import socket #for errors from ZabbixSender
from huawei_lte_api.Client import Client #https://github.com/Salamek/huawei-lte-api
from huawei_lte_api.Connection import Connection
from huawei_lte_api.exceptions import \
    ResponseErrorLoginRequiredException, \
    ResponseErrorNotSupportedException, \
    ResponseErrorSystemBusyException, \
    ResponseErrorLoginCsrfException, \
    ResponseErrorWrongSessionToken, \
    LoginErrorUsernamePasswordOverrunException, \
    ResponseErrorException, \
    RequestFormatException
from pyzabbix import ZabbixMetric, ZabbixSender, ZabbixResponse
# https://py-zabbix.readthedocs.io/en/latest/sender.html
# ZabbixResponse might not be needed
import yaml


log_level =''
zabbix_sender_setting = ''
modem_url = ''
monitored_hostname = ''
minimum_polling_interval = ''
global changed_count, stale_count, not_changed_count, not_stale_count
changed_count = 0
stale_count = 0
not_changed_count = 0
not_stale_count = 0

def load_config():
    """Loads the YAML config first from config.yml, then own_config.yml"""
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

    global modem_url, zabbix_sender_setting,monitored_hostname
    global minimum_polling_interval,log_level, do_it_once, do_zabbix_send
    global zabbix_send_failed_time_max, zabbix_send_failed_items_max

    modem_url=config['modem_url']
    zabbix_sender_setting=config['zabbix_sender_setting']
    monitored_hostname = config['monitored_hostname']
    minimum_polling_interval = config['minimum_polling_interval']
    do_it_once = config['do_it_once']
    do_zabbix_send = config['do_zabbix_send']
    log_level = config['log_level']
    logging.basicConfig(level=logging.INFO) #FIX this

    zabbix_send_failed_time_max  = 900 # TODO add to default config
    zabbix_send_failed_items_max = 500 # TODO add to default config

def save_zabbix_packet_to_disk(object):
    """Saves unsent items to Disk"""
    logging.warning(f'TEST: save_zabbix_packet_to_disk: NOT IMPLEMENTED YET' )

def get_api_endpoint():
    """Gets data from endpoint"""
    # function! connect to API endpoint ( as api_endpoint ) or eventually
    # callable python object... and (return dictionary)
    # TODO: use the api_endpoint
    # FIXME: modem_url is global
    try:
        with Connection(modem_url) as connection:
            client = Client(connection)
            stuff = client.device.signal()
            logging.debug(f'Connected on first try' )
    except LoginErrorUsernamePasswordOverrunException as error_msg:
        # happens if too many failed logins on the front end (from same IP?)
        logging.warning('Too many failed logins to modem: {0}'.format(error_msg))
        logging.warning('Sleeping one minute before trying again')
        # handle this...
        time.sleep(60)
        with Connection(modem_url) as connection:
            client = Client(connection)
            stuff = client.device.signal()
    except ( ResponseErrorException, ResponseErrorLoginCsrfException,\
            ResponseErrorLoginRequiredException ) as error_msg:
        logging.warning('Reconnecting due to error: {0}'.format(error_msg))
        reconnect_count += 1
        logging.warning(f'Reconnect count: {reconnect_count}' )
        with Connection(modem_url) as connection:
            client = Client(connection)
            stuff = client.device.signal()
    except:
        logging.error('Unexpected error: {0}' .sys.exc_info()[0])
        raise
    return stuff

def get_interesting_values( prefix, endpoint , key, value, time ):
    """Returns list of interesting values.

    Interesting depends on how they are defined
    always, changed or stale. If changed, the
    previously polled (unchanged) value is also sent.
    All interesting values are sent the first time they are changed.
    """
    logging.debug( f'get_interesting_values( {prefix}, {endpoint} , {key}, {value} {time} )' )
    # check for stale and changes 
    # track last reported time last values
    # return interesting / stale  current and  
    #  assumption is made that if there is no change then the value from the "epoch_time_last"
    # is the same as the last sent value.
    # 'last sent' might be a better way to describe this.
    #lastchanged = {} # time last sent
    #lastvalue = {}
    #lastpolled = {} # time of last poll
    global changed_count, stale_count, not_changed_count, not_stale_count
    ivlist = []
    #zapacket=[]
    k=key
    v=value
    if k in always_interesting:
        ivlist = ivlist + [ ZabbixMetric( monitored_hostname,
            f'{prefix}.{endpoint}.{k}' , v, time ) ]
    elif ( k in interesting ) and (k not in lastchanged): #or lastvalue...
        logging.debug(f"{k} not in lastchanged {k not in lastchanged}")
        ivlist = ivlist + [ ZabbixMetric( monitored_hostname,
            f'{prefix}.{endpoint}.{k}' , v, time ) ]
        lastchanged[k] = time
        lastpolled[k] = time
        lastvalue[k] = v
    elif k in interesting: #changes_interesting_10min or k in changes_interesting_1hour:
        # for now we'll handle the same and test
        if  ( not lastvalue[k] == v
             or (k in changes_interesting_10min and ( time - lastchanged[k] > one_hour ))
             or (k in changes_interesting_1hour and ( time - lastchanged[k] > ten_minutes ))
            ):
            # if value changed. send previous data from previous
            #interval with last interval if not equal.
            if not lastvalue[k] == v:
                #logging.debug(f'{k} changed from {lastvalue[k]} to {v}')
                logging.info(f'{k} changed from {lastvalue[k]} to {v}')
                changed_count += 1
                not_stale_count += 1
                if lastpolled[k] > lastchanged[k]:
                    ivlist = ivlist + [ ZabbixMetric( monitored_hostname ,
                        f'{prefix}.{endpoint}.{k}' ,lastvalue[k] , lastpolled[k] ) ]
                    logging.debug(f'{k} changed before last check sending previous interval sending previous data from {epoch_time - lastchanged[k]} sec')
            else:
                logging.debug(f'{k} data is stale after {time - lastchanged[k]} sec')
                stale_count += 1
                not_changed_count += 1
            ivlist = ivlist + [ ZabbixMetric( monitored_hostname ,
                f'{prefix}.{endpoint}.{k}' , v, time ) ]
            lastchanged[k] = time
            lastpolled[k] = time # update for next time 
            lastvalue[k] = v
        else:
            lastpolled[k] = time # update for next time
            not_changed_count += 1
            not_stale_count += 1
            logging.debug(f'{k} not changed/not stale or too old {time - lastchanged[k]} ')
    else:
        logging.debug(f'{k} is not interesting: {k} : {v}')
    return ivlist

def send_zabbix_packet():
    """Sends zabbix packet to server(s)"""
    logging.warning(f'TEST: NOT IMPLEMENTED YET' )
    return
    

#todo
#parsed = "txpower"

# what to parse "PPusch:7dBm PPucch:-3dBm PSrs:-40dBm PPrach:7dBm"

# always interesting sent every polling interval
always_interesting = ['rsrq', 'rsrp', 'rssi', 'sinr', 'txpower' ]
# changes_interesting are sent when changed or when the last result is older
# than the last one to be sent. When there is a change in value, the previous
# value is sent also (with timestamp of the previous interval
# the idea of this is to make graphs look nicer.
changes_interesting_10min =  ['pci' ,'cell_id','band','nei_cellid']
changes_interesting_1hour =  ['ims','tac','mode', "rrc_status",'plmn','lteulfreq', 'ltedlfreq',
                              'enodeb_id', 'ulbandwidth','dlbandwidth' ]
interesting = always_interesting +  changes_interesting_10min + changes_interesting_1hour

# will be determined from the smallest interval in the API configuration
polling_interval = 60
api_config = {} #TODO

def main():
    global ten_minutes, one_hour
    ten_minutes = 600
    one_hour = 3600
    
    load_config()
    logging.basicConfig(level=logging.INFO)
    zasender = ZabbixSender(zabbix_sender_setting)
    epoch_time_start = int(time.time())
    zabbix_send_failed_time = 0
    

    global lastchanged,lastvalue , lastpolled
    lastchanged = {} # time last sent
    lastvalue = {}
    lastpolled = {} # time of last poll

    #counters
    count = 1
    zabbix_server_processed = 0
    zabbix_server_failed = 0
    zabbix_server_total = 0
    #global changed_count, stale_count, not_changed_count, not_stale_count
##    changed_count = 0
##    stale_count = 0
##    not_changed_count = 0
##    not_stale_count = 0
    reconnect_count = 0
    zapacket = []
    key_prefix = 'huawei.lte' # name for the start of the zabbix key...
    while True:
        # new outer look to loop through end API endpoints
        api_endpoint = 'device.signal' #hack until able to parse api endpoints and keys from yaml config

        endpoint_data = get_api_endpoint()
        epoch_time = int(time.time())
        # iterate stuff and collect interesting (changed, stale, always interesting) items for an enpoint
        for k,v in endpoint_data.items():
            iv = get_interesting_values( prefix=key_prefix, endpoint=api_endpoint, key=k, value=v, time=epoch_time )

            #print( f'iv={iv} , {len(iv)}' )

            # add the items... to zapacket
            if len(iv) > 0:
                zapacket = zapacket + iv

        epoch_time_last = epoch_time # can get rid of this
        #pprint.pp(zapacket)
        
        # Function! send (queued) data to zabbix server
        if do_zabbix_send:
            try:
                zaserver_response = zasender.send(zapacket)
                zapacket = [] #it's sent now ok to erase
                zabbix_send_failed_time == 0 #in case it failed earlier
                zabbix_server_processed += zaserver_response.processed
                zabbix_server_failed += zaserver_response.failed
                zabbix_server_total += zaserver_response.total
                logging.debug(f'Zabbix Sender succeeded\n{zaserver_response}')
            except (socket.timeout, socket.error, ConnectionRefusedError ) as error_msg:
                logging.warning('Zabbix Sender Failed to send some or all: {0}'.format(error_msg))
                # if sending fails, Zabbix server may be restarting or rebooting.
                # maybe it gets sent after the next polling attempt.
                # if zapacket is more than x items or if failure time
                # greater than x save to disk
                if zabbix_send_failed_time == 0 : #first fail (after successful send or save)
                    zabbix_send_failed_time = epoch_time
                    # could set defaults for failed item sending timeout and count.
                if  ( epoch_time - zabbix_send_failed_time > zabbix_send_failed_time_max #900
                    or len(zapacket) > zabbix_send_failed_items_max #500
                    ):
                    logging.error(f'Zabbix Sender failed {epoch_time - zabbix_send_failed_time} seconds ago and {len(zapacket)} items pending.\nWill try to dump them to disk')
                    save_zabbix_packet_to_disk(zapacket)
                    zabbix_send_failed_time = epoch_time
                    zapacket = [] #it's saved now ok to erase
                    # clear keys from lastchanged so fresh values are collected to be sent next time
                    lastchanged={}
            except:
                logging.error(f'Unexpected error: {sys.exc_info()[0]}')
                raise
        else:
            print('***** TEST: not sending *****')
            pprint.pp(zapacket )
            zapacket = []
        print(f'*** Time: {epoch_time} poll count: {count}',
              f' uptime: {epoch_time - epoch_time_start} ***')
        print(f'*** stale:not {stale_count}:{not_stale_count},',
              f' changed:not {changed_count}:{not_changed_count} ***')
        print(f'*** zabbix_server processed: {zabbix_server_processed},',
              f' failed: {zabbix_server_failed}, total: {zabbix_server_total} ***')
        count += 1
        if not do_it_once:
            time.sleep(polling_interval)
            # break in to smaller sleeps so one can Ctrl-C?
        else:
            print('*** Exiting: do_it_once: True ***')
            break
main()
