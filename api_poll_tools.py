"""
Module api_poll_tools.py
"""
import time
from calendar import timegm
import logging

def test_times_straddle_minute( time_1,time_2, minutes ):
    """
    Tests if start of a minute or list of minutes is between time1 and time2.

    minute can be an int or list of minutes and it is assumed to be the start
    of the minute (seconds is 0)
    time_1 and time_2 are in seconds since the start of epoch_time
    and can be any order.
    """
    if type(minutes) is int:
        minutes = [minutes]
    # calculate the start of the minute for within last hour
    this_minute = list(time.gmtime(max(time_1,time_2)))
    this_minute[5] = 0 # set seconds to 0
    for minute in minutes:
        this_minute[4] = minute # set minute
        # convert back to timestamp as it is easier to move back 1 hour
        this_minute_timestamp = timegm(time.struct_time(tuple(this_minute)))
        # check if minute is after the larger timestamp
        # if so move back 1 hour
        if this_minute_timestamp > max(time_1,time_2):
            this_minute_timestamp -= 3600
        if ( this_minute_timestamp <= max(time_1,time_2) and \
             this_minute_timestamp >= min(time_1,time_2)):
            return True
    return False

def main():
    # test test_times_straddle_minute
    time_15m41s = 941
    time_16m41s = 1001
    test16after = 16 # True
    test10after = 10 # False
    list_true = [20, 0 ,59, test16after] # true
    list_false = [1, 2, 4, 55] #False
    list_empty = []
    broken1 = [1, 60, 61, 1000] # some out of range
    broken2 = "2"
    broken3 = [1, 2, 'wer']
    broken4 = False
    tests = [test16after,test10after ,list_true,list_false, list_empty,
             broken1, broken2, broken3, broken4 ]
    print("***")
    for test in tests:
        print(f'testing: {test} ')
        try:
            x = test_times_straddle_minute(time_16m41s,time_15m41s, test )
            print(f'result {x}')
        except:
            print(f'Exception error:') # {sys.exc_info()[0]}')
        print("***")
