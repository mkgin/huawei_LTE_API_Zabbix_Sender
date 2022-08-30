#
# Huawei LTE modem monitor for Zabbix
#
#
# - monitor, store last and only report changes for some parameters send data to Zabbix.
# - collect timestamps
#
# - for some items, send timestamp , mark what was last sent and send when
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
from pyzabbix import ZabbixMetric, ZabbixSender, ZabbixResponse  #https://py-zabbix.readthedocs.io/en/latest/sender.html
import pprint
import time
import sys  # to report errors
import logging
import os
import yaml
import socket #for errors from ZabbixSender

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
    logging.warning(f'TEST: save_zabbix_packet_to_disk: NOT IMPLEMENTED YET' )

#todo
#parsed = "txpower"
key_prefix = 'huawei.lte' # name for the start of the zabbix key...
#rest is the api endpoint and api key (for the value)

# endpoint 'device.signal'
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
    ten_minutes = 600
    one_hour = 3600
    load_config()
    logging.basicConfig(level=logging.INFO)
    zasender = ZabbixSender(zabbix_sender_setting)
    epoch_time_start = int(time.time())
    zabbix_send_failed_time = 0
    with Connection(modem_url) as connection:
        client = Client(connection)
        count = 1
        lastchanged={}
        lastvalue={}
        #counters
        zabbix_server_processed = 0
        zabbix_server_failed = 0
        zabbix_server_total = 0
        changed_count = 0
        stale_count = 0
        not_changed_count = 0
        not_stale_count = 0
        reconnect_count = 0
        zapacket = []
        while True:
            api_endpoint = 'device.signal' #hack until able to parse api endpoints and keys from yaml config
            try:
                stuff = client.device.signal()
            except ( ResponseErrorException, ResponseErrorLoginCsrfException, ResponseErrorLoginRequiredException ) as error_msg:
                logging.warning('Reconnecting due to error: {0}'.format(error_msg))
                reconnect_count += 1
                logging.warning(f'Reconnect count: {reconnect_count}' )
                with Connection(modem_url) as connection:
                    client = Client(connection)
                    stuff = client.device.signal()
            except LoginErrorUsernamePasswordOverrunException as error_msg:
                # happens if too many failed logins on the front end (from same IP?)
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
                    if  ( not lastvalue[k] == v
                         or (k in changes_interesting_10min and (epoch_time - lastchanged[k] > one_hour ))
                         or (k in changes_interesting_1hour and (epoch_time - lastchanged[k] > ten_minutes ))
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

            epoch_time_last = epoch_time
            #pprint.pp(lastchanged)
            #zaserver_response={}
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
                    # if sending fails, zabbix server may be restarting or server rebooting.
                    # maybe it gets sent after the next polling attempt.
                    # if zapacket is more than x items or if failure time greater than x) save to disk

                    if zabbix_send_failed_time == 0 : #first fail (after successfully sending or saving)
                        zabbix_send_failed_time = epoch_time
                        # could set defaults for failed item sending timeout and count.
                    if  ( epoch_time - zabbix_send_failed_time > zabbix_send_failed_time_max #900
                        or len(zapacket) > zabbix_send_failed_items_max #500
                        ):
                        logging.error(f'Zabbix Sender failed {epoch_time - zabbix_send_failed_time} seconds ago and {len(zapacket)} items pending.\nWill try to dump them to disk')
                        save_zabbix_packet_to_disk(zapacket)
                        zabbix_send_failed_time = epoch_time #
                        zapacket = [] #it's saved now ok to erase
                        # clear keys from lastchanged so fresh values are collected to be sent next time
                        lastchanged={}
                except:
                    logging.error("Unexpected error:", sys.exc_info()[0])
                    raise
            else:
                print('***** TEST: not sending *****')
                pprint.pp(zapacket )
                zapacket = []
            print(f'*** Time: {epoch_time} poll count: {count} uptime: {epoch_time - epoch_time_start} ***')
            print(f'*** stale:not {stale_count}:{not_stale_count} , changed:not {changed_count}:{not_changed_count} ***')
            print(f'*** zabbix_server totals, processed: {zabbix_server_processed} failed: {zabbix_server_failed} total: {zabbix_server_total} ***')
            count += 1
            if not do_it_once:
                time.sleep(polling_interval)
                # break in to smaller sleeps so one can Ctrl-C?
            else:
                print('*** Exiting: do_it_once: True ***')
                break
main()
