"""
api_poll_config.py

Loads configuration to handle API polling

- Creates a dictionaries for API endpoints containing items(keys) to store from an API
- Loads polling interval per endpoint
- Loads sending strategies which can be specified at different levels. 
- More information in the sample YAML configuration file

TODO: switch print statments to debug logs
TODO: handle endpoint polling interval
TODO: make it a module that returns the dictionary to main API poller
"""

import yaml
import pprint
import logging

# store the sending strategy for endpoints here...
# queried as sending_strategy[endpoint][key][strategy]
sending_strategy={}

def get_sending_strategy( sending_strategy, upper_strategy , sending_default ):
    """Reads sending strategy from a top level of the configuration data in sending_strategy.

       If there is no sending_strategy at the current level, the upper level or defaults are used.
    """
    sending_strategy_return = {}

    print(f'get_sending_strategy()\n    in: {sending_strategy}\n',
          f'  upper: {upper_strategy}\n',
          f'default: {sending_default}')
    # handle current level
    if 'always' in sending_strategy:
        if sending_strategy['always'] is True:
            sending_strategy_return = { 'always': True }
            return sending_strategy_return
    if 'stale' in sending_strategy:
        sending_strategy_return['stale'] = sending_strategy['stale']
    else:
        if 'fixed' in sending_strategy:
            sending_strategy_return['fixed'] = sending_strategy['fixed']
    if 'previous' in sending_strategy:
        print(f'sending_strategy_previous {sending_strategy}')
        if sending_strategy['previous'] is True:    ###???
            #sending_strategy_return.update( {'changes': True, 'previous': True} )
            sending_strategy_return.update( {'previous': True} )
            
        else:
            sending_strategy_return['previous'] = False
    if 'changes' in sending_strategy:
        if sending_strategy['changes'] is True:
            sending_strategy_return['changes'] = True
        else:
            sending_strategy_return['changes'] = False
    print(f'get_sending_strategy(): CURRENT: {sending_strategy_return} {type(sending_strategy_return)}',
          f'{len(sending_strategy_return)}' )
    #
    # if think we just need to check if nothing is set in the return variable
    # and repeat the above maybe with upper? if  then default?
    
    # use upper strategy if current is empty
    if len(sending_strategy_return) == 0:
        sending_strategy_return = upper_strategy
        print("EMPTY: using upper_strategy")
    # if the upper strategy was empty too evaluate defaults
    if len(sending_strategy_return) == 0:
        print("EMPTY: using calling ourself to get defaults")
        sending_strategy_return = get_sending_strategy( sending_default, {}, sending_default )

    print(f'get_sending_strategy(): RETURN: {sending_strategy_return}')
    print('*****')
    
    return sending_strategy_return

def sending_strategy_check( endpoint, key, strategy):
    """Check and returns a strategy's value for a key, otherwise, returns False"""
    if strategy in sending_strategy[endpoint][key]:
        return sending_strategy[endpoint][key][strategy]
    return False

def load_api_config_to_sending_strategy(api_config):
    

    #default sending strategy in top level
    sending_strategy_default= api_config['sending_strategy_default']
    pprint.pp(sending_strategy_default)

    # iterate endpoints
    endpoints = api_config['endpoint']
    pprint.pp(endpoints)
    for endpoint in endpoints:
        current_sending_strategy={}
        print( 'NAME***', endpoint['name'])
        print( 'polling_interval***', endpoint['polling_interval'])
        print( f'*** FOR1 {endpoint.keys()}' )
        sending_strategy_endpoint = get_sending_strategy( endpoint,
                                                          current_sending_strategy,
                                                          sending_strategy_default)
        print( f' sending_strategy_endpoint: {sending_strategy_endpoint}')
        sending_strategy[endpoint['name']] = {}
        # endpoint
        for keylist in endpoint.keys():
            print( f'FOR2 keylist: {keylist} in {endpoint.keys()}')
            
            print( f' sending_strategy_endpoint: {sending_strategy_endpoint}')
            # if type is dict check if it is a keylist and iterate
            if type (endpoint[keylist]) is dict:
                if 'keys' in endpoint[keylist]:
                    sending_strategy_keylist = get_sending_strategy( endpoint[keylist],
                                                             sending_strategy_endpoint,
                                                             sending_strategy_default)
                    for current_key in endpoint[keylist]['keys']:
                        print( f'FOR3a {current_key}' )
                        print( f'keys IS in current_key: {current_key}')
                        for k in endpoint[keylist]['keys']:
                             print( f'KEY: {k}')
                             kdict= { k : sending_strategy_keylist}
                             sending_strategy[endpoint['name']].update( kdict )
                    else:
                        print(f'FOR3a skipping {current_key}')
            # if type is not dict check if it is a keylist and iterate            
            else:
                if 'key' == keylist or 'keys' == keylist:
                #if keylist is "keys":
                #if 'keys' is keylist:
                    print(f'FOR3b keylist {keylist}  endpoint[keylist] {endpoint[keylist]}')
                    #print(f'FOR3b** keys in keylist {keylist} type {type(keylist)}')
                    for k in endpoint[keylist]: #['keys']:
                        print( f'KEY(keys): {k}')
                        kdict = { k : sending_strategy_endpoint}
                        sending_strategy[endpoint['name']].update( kdict )
                else:
                    print(f'FOR3b skipping {endpoint[keylist]} (not dict) or not a key list')
        print('*************')
    #return a big dictionary of dictionaries.

def main():
    
    api_config = yaml.safe_load(open('api_design_test.yml'))
    load_api_config_to_sending_strategy(api_config)
    pprint.pp(sending_strategy)

main()
