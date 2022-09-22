"""
Module api_poll_tools.py
"""
import time
from calendar import timegm
def times_straddle_minute( time_1,time_2, minute ):
    """
    Checks whether the start of certain minute of an hour is between two
    timestamps time_1 and time_2 are epoch_time in seconds and can be any order.
    """
    # calculate the start of the minute for within last hour
    this_minute = list(time.gmtime(max(time_1,time_2)))
    this_minute[5] = 0 # set seconds to 0
    this_minute[4] = minute # set minute
    # convert back to timestamp as it is easier to move back 1 hour
    this_minute_timestamp = timegm(time.struct_time(tuple(this_minute)))
    # check if fixed minute is after minute, if so move back 1 hour
    if this_minute_timestamp > max(time_1,time_2):
        this_minute_timestamp -= 3600
    # test it end return
    return bool (
        this_minute_timestamp <= max(time_1,time_2)
        and this_minute_timestamp >= min(time_1,time_2))
