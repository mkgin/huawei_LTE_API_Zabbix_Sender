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
#https://github.com/Salamek/huawei-lte-api
from huawei_lte_api.Client import Client
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
# https://py-zabbix.readthedocs.io/en/latest/sender.html
# ZabbixResponse might not be needed
from pyzabbix import ZabbixMetric, ZabbixSender, ZabbixResponse
import yaml
# Own libs
from api_poll_config import load_api_endpoint_key_config, \
     load_key_prefix_config, \
     load_polling_interval_minimum
from api_poll_tools import times_straddle_minute

log_level =''
#zabbix_sender_setting = ''
#modem_url = ''
#monitored_hostname = ''

# global counters
changed_count = 0
stale_count = 0
not_changed_count = 0
not_stale_count = 0
api_reconnect_count = 0 # modem api in this case
# Count data recieved from zabbix server
zabbix_server_processed = 0 #
zabbix_server_failed = 0    # Zabbix server did not accept (wrong key, wrong type of data)
zabbix_server_total = 0     #
zabbix_send_failed_time = 0

# TODO: have these as persistant variables only in get_interesting_values 
# storage for get_interesting_values()
lastchanged = {} # time last sent 
lastvalue = {}   # last value
lastpolled = {}  # time of last poll

# TODO: check where epoch_time is really needed...
epoch_time = 0

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
        logging.warning("Missing: ",configfile_default )
    if os.path.isfile(configfile_own):
        config.update(yaml.safe_load(open(configfile_own)))
    else:
        logging.warning("Missing",configfile_own )
    global zabbix_send_failed_time_max, zabbix_send_failed_items_max
    zabbix_send_failed_time_max  = 900 # TODO add to default config
    zabbix_send_failed_items_max = 500 # TODO add to default config
    return config


def save_zabbix_packet_to_disk():
    """Saves unsent items to Disk"""
    logging.warning(f'TEST: save_zabbix_packet_to_disk: NOT IMPLEMENTED YET' )

def get_api_endpoint( endpoint , modem_url):
    """Gets data from endpoint"""
    # connect to API endpoint ( as api_endpoint ) or eventually
    # callable python object... and (return dictionary)
    global api_reconnect_count
    client_endpoint= f'client.{endpoint}'
    logging.debug(client_endpoint )
    try:
        with Connection(modem_url) as connection:
            client = Client(connection)
            #stuff = client.device.signal()
            stuff = eval(client_endpoint)() #not sure if this is evil or insecure
            logging.debug(f'Connected on first try' )
    except LoginErrorUsernamePasswordOverrunException as error_msg:
        # happens if too many failed logins on the front end (from same IP?)
        logging.warning('Too many failed logins to modem: {0}'.format(error_msg))
        logging.warning('Sleeping one minute before trying again')
        # handle this...
        time.sleep(60)
        with Connection(modem_url) as connection:
            client = Client(connection)
            #stuff = client.device.signal()
            stuff = eval(client_endpoint)() #not sure if this is evil or insecure
    except ( ResponseErrorException, ResponseErrorLoginCsrfException,\
            ResponseErrorLoginRequiredException ) as error_msg:
        logging.warning('Reconnecting due to error: {0}'.format(error_msg))
        api_reconnect_count += 1
        logging.warning(f'Modem API reconnect count: {api_reconnect_count}' )
        with Connection(modem_url) as connection:
            client = Client(connection)
            #stuff = client.device.signal()
            stuff = eval(client_endpoint)() #not sure if this is evil or insecure
    except AttributeError:
        logging.error(f'Configuration error: endpoint: {endpoint} is not available')
        raise
    except:
        logging.error('Unexpected error: {0}' .sys.exc_info()[0])
        raise
    return stuff

# TODO: think about moving this to api_poll_tools
def get_interesting_values( prefix, endpoint_name , key, value, poll_time, endpt_key_conf , monitored_hostname ):
    """Returns list of interesting values as a zabbixmetric

    Interesting depends on how they are defined in endpt_key_conf
    always, changed or stale. If changed, the
    previously polled (unchanged) value is also sent.
    All interesting values are sent the first time they are changed.

    Was considering using something other than zabbixmetric, but it is simple
    enough, and easy to read, convert if needed later.
    """
    logging.debug( f'get_interesting_values( {prefix}, {endpoint_name} , {key}, {value} {poll_time} )' )
    global changed_count, stale_count, not_changed_count, not_stale_count
    ivlist = [] #interesting value list
    k=key
    v=value
    endp_dot_key = endpoint_name + '.' + k #long key for storing previous measurments and timestamps
    try:
        keyconf = endpt_key_conf[endpoint_name][k]
    except KeyError:
        logging.debug(f'{k} not in dict')
        return ivlist #return empty ivlist
    #if k in always_interesting:
    if 'always' in keyconf:
        if keyconf['always']: # This should always be true
            ivlist = ivlist + [ ZabbixMetric( monitored_hostname,
                f'{prefix}.{endpoint_name}.{k}' , v, poll_time ) ]
    # all not always keys that are in the dict are handled here
    # last value  and timestamps for the last change, last poll are stored
    elif ( endp_dot_key not in lastchanged): #or lastvalue...
        logging.debug(f'keyconf for {k} : {keyconf}')
        logging.debug(f"{k} not in lastchanged {k not in lastchanged}")
        ivlist = ivlist + [ ZabbixMetric( monitored_hostname,
            f'{prefix}.{endpoint_name}.{k}' , v, poll_time ) ]
        lastchanged[endp_dot_key] = poll_time
        lastpolled[endp_dot_key] = poll_time
        lastvalue[endp_dot_key] = v
    elif 'stale' in keyconf: 
        # check if we don't need to send anything, and return, then test.
        if ( (lastvalue[endp_dot_key] == v) and
             (poll_time - lastchanged[endp_dot_key] < keyconf['stale'])
           ):
            lastpolled[endp_dot_key] = poll_time # update for next time
            not_changed_count += 1
            not_stale_count += 1
            logging.debug(f'{k} not changed/not stale or too old {poll_time - lastchanged[endp_dot_key]} ')
            return ivlist #return empty ivlist
        else:
            # if value changed. send previous data from previous
            # interval with last interval if not equal.
            if not lastvalue[endp_dot_key] == v:
                logging.debug(f'{k} changed from {lastvalue[endp_dot_key]} to {v}')
                changed_count += 1
                not_stale_count += 1
                if lastpolled[endp_dot_key] > lastchanged[endp_dot_key]: #here is is
                    ivlist = ivlist + [ ZabbixMetric( monitored_hostname ,
                        f'{prefix}.{endpoint_name}.{k}' ,lastvalue[endp_dot_key],
                                                      lastpolled[endp_dot_key] ) ]
                    logging.debug(f'{k} changed before last check and previous set')
                    logging.debug(f'sending previous data from {poll_time - lastchanged[endp_dot_key]} sec')
            else:
                logging.debug(f'{k} data is stale after {poll_time - lastchanged[endp_dot_key]} sec')
                stale_count += 1
                not_changed_count += 1
            ivlist = ivlist + [ ZabbixMetric( monitored_hostname ,
                f'{prefix}.{endpoint_name}.{k}' , v, poll_time ) ]
            lastchanged[endp_dot_key] = poll_time
            lastpolled[endp_dot_key] = poll_time # update for next time
            lastvalue[endp_dot_key] = v
    elif 'fixed' in keyconf:
        # the fixed list should already be sorted when loading
        for minute in keyconf['fixed']:
            # check if minute between times
            if times_straddle_minute(lastchanged[endp_dot_key],poll_time,minute):
                logging.debug(f'send fixed minute: {minute}')
                ivlist = ivlist + [ ZabbixMetric( monitored_hostname,
                    f'{prefix}.{endpoint_name}.{k}' , v, poll_time ) ]
                lastchanged[endp_dot_key] = poll_time
                break
            else:
                logging.debug(f'not this minute: {minute}')
        #finish up (update info)
        lastpolled[endp_dot_key] = poll_time
    else:
        logging.warning(f'{endpoint_name}.{k} is not interesting: {k} : {v}\nAND SHOUND NOT EVEN BE AT THIS LINE')
        # should not make it here
    return ivlist

def send_zabbix_packet(zabbix_packet , zabbix_sender_setting):
    """Sends zabbix packet to server(s)"""
    sending_status = False
    zasender = ZabbixSender(zabbix_sender_setting)
    global epoch_time, zabbix_server_processed, zabbix_server_failed, zabbix_server_total
    try:
        zaserver_response = zasender.send(zabbix_packet)
        zabbix_packet = [] #it's sent now ok to erase
        zabbix_send_failed_time = 0 #in case it failed earlier
        zabbix_server_processed += zaserver_response.processed
        zabbix_server_failed += zaserver_response.failed
        zabbix_server_total += zaserver_response.total
        logging.debug(f'Zabbix Sender succeeded\n{zaserver_response}')
        sending_status = True
    except (socket.timeout, socket.error, ConnectionRefusedError ) as error_msg:
        logging.warning('Zabbix Sender Failed to send some or all: {0}'.format(error_msg))
        # if sending fails, Zabbix server may be restarting or rebooting.
        # maybe it gets sent after the next polling attempt.
        # if zabbix_packet is more than x items or if failure time
        # greater than x save to disk
        if zabbix_send_failed_time == 0 : #first fail (after successful send or save)
            zabbix_send_failed_time = epoch_time
            # could set defaults for failed item sending timeout and count.
        if  ( epoch_time - zabbix_send_failed_time > zabbix_send_failed_time_max #900
            or len(zabbix_packet) > zabbix_send_failed_items_max #500
            ):
            logging.error(f'Zabbix Sender failed {epoch_time-zabbix_send_failed_time} seconds ago')
            logging.error(f'{len(zabbix_packet)} items pending.\nWill try to dump them to disk')
            save_zabbix_packet_to_disk(zabbix_packet)
            zabbix_send_failed_time = epoch_time
            zabbix_packet = [] #it's saved now ok to erase
            # clear keys from lastchanged so fresh values are collected to be sent next time
            lastchanged={}
    except:
        logging.error(f'Unexpected error: {sys.exc_info()[0]}')
        raise
    return sending_status

def main():
    config = load_config()
    modem_url=config['modem_url']
    # TODO: set logging with config['log_level']
    logging.basicConfig(level=logging.INFO)
    
    api_config = yaml.safe_load(open(config['api_poll_config']))
    key_prefix = load_key_prefix_config(api_config)
    minimum_polling_interval = load_polling_interval_minimum(api_config)
    endpoint_key_config = load_api_endpoint_key_config(api_config)
    endpoints = api_config['endpoint']
    epoch_time_start = int(time.time())
    zabbix_send_failed_time = 0
    #counters
    count = 1 # count for running a certain number of times, or just keeping track
    zapacket = [] # packet to be sent
    endpoint_polled_last={}
    
    while True:
        for endpoint in endpoints: # loop through end API endpoints
            epoch_time = int(time.time())
            # check endpoint_polled_last['endpoint'] and set if not
            try:
                endpoint_polled_last['endpoint']
            except KeyError:
                endpoint_polled_last['endpoint'] = 0
            # check if it is time to poll this endpoint
            if ( endpoint_polled_last['endpoint'] == 0 or
                 epoch_time - endpoint_polled_last['endpoint'] <= endpoint['polling_interval'] 
               ):
                endpoint_data = get_api_endpoint(endpoint['name'], config['modem_url'])
                endpoint_polled_last['endpoint'] = epoch_time
                # collect interesting(changed, stale, always interesting) items for an endpoint
                for k,v in endpoint_data.items():
                    iv = get_interesting_values( prefix=key_prefix, endpoint_name=endpoint['name'],
                                                 key=k, value=v, poll_time=epoch_time,
                                                 endpt_key_conf=endpoint_key_config,
                                                 monitored_hostname=config['monitored_hostname'] )
                    if len(iv) > 0:
                        zapacket = zapacket + iv
                    if len(iv) > 1:
                        # something changed and previous is sent too
                        endpoint_name = endpoint['name']
                        logging.info(f'more than one item in iv {endpoint_name}.{k}')
        if config['do_zabbix_send']: # send (queued) data to zabbix server
            send_status = send_zabbix_packet(zapacket , config['zabbix_sender_setting'])
            if send_status:
                zapacket = []
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
        print(f'*** api_reconnect_count: {api_reconnect_count} ***')
        count += 1
        if not config['do_it_once']:
            time.sleep(minimum_polling_interval)
            # break in to smaller sleeps so one can Ctrl-C out faster
        else:
            print('*** Exiting: do_it_once: True ***')
            break
    # while ends here
    # could send remaining packets if any, if we crashed.
main()
