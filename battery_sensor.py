#!/usr/bin/env python3
# if your python3 location is elsewhere, run: whereis python3 via cli & edit the line accordingly

"""
Generate an XML file for PRTG to probe and get statistical data
from a non-networked APC UPS battery (running a raspberry pi)
"""

import subprocess

def obtain_status():
    """ Ping the battery stats from Nut """

    # in testing, the input voltage fluctuated when put on battery
    # so we'll use that as an error factor - adjust to suit
    input_voltage = "121.6"
    on_battery = "0"

    # tc/tech closet is hardcoded, see readme for why
    battery_results = subprocess.Popen(
        ['upsc tc > /dev/stdout 2> /dev/null'], # redirect 'Init SSL without certificate database'
        stdout=subprocess.PIPE,
        universal_newlines=True, # removes the bytes indicator & single quotes
        shell=True               # extra overhead, but not a huge deal if you only ping once an hr
    )


    # prepare the xml loop prefix
    print("<prtg>")

    for line in battery_results.stdout:
        line = prettify(line) # strip newlines and replace . to spaces + capitalize words

        # utilize a list to generate arrays for channel and value difference
        statuses = line.split(':')

        if statuses[0] == 'Ups Model':
            banner_model = "Model: " + statuses[1]
        else:
            banner_model = ""
        if statuses[0] == 'Ups Serial':
            banner_serial = " Serial: " + statuses[1]
        else:
            banner_serial = ""

        # if there's a fluctuation in battery voltage, assume its running on battery
        # or something is worth mentioning
        trim_value = statuses[1].lstrip().replace(' ', '.')
        if statuses[0] == 'Input Voltage' and trim_value != input_voltage:
            on_battery = "1"

        if trash(statuses[0]) != 'remove':
            generate_xml(
                statuses[0],          # channel name
                statuses[0],          # channel name again, which determines the DOWN trigger
                statuses[0],          # channel name again, which determines the WARN trigger
                statuses[1].lstrip() #val w/ leading space stripped; left from : separation
            )

    # always display the model and serial
    if on_battery == "1":
        # note that <error>1</error> seems to trigger No data when the sensor is tripped
        # best to manually set via channel, for now
        #print("<error>1</error>")
        print("<text>Input voltage fluctuation " + banner_model + banner_serial + "</text>")
    else:
        print("<text>" + banner_model + banner_serial + "</text>")

    # close the xml loop suffix
    print("</prtg>")

def prettify(line):
    """ De-clutter a long line of multi-functions on a string """
    output = line.rstrip().replace('.', ' ').title()

    return output


def trash(channel):
    """ Useless returns we don't need to monitor """

    # everything referenced here is disregarded!
    if channel in (
            'Device Mfr',
            'Device Model',
            'Device Serial',
            'Ups Vendorid',
            'Ups Timer Start',
            'Ups Timer Shutdown',
            'Ups Timer Reboot',
            'Ups Test Result',
            'Ups Productid',
            'Ups Mfr Date',
            'Ups Firmware Aux',
            'Ups Firmware',
            'Ups Delay Start',
            'Ups Delay Shutdown',
            'Ups Beeper Status',
            'Ups Mfr',
            'Ups Model',
            'Ups Serial',
            'Ups Status',
            'Output Voltage Nominal',
            'Input Transfer Reason',
            'Input Transfer High',
            'Input Transfer Low',
            'Input Sensitivity',
            'Driver Version Internal',
            'Driver Version Data',
            'Driver Version',
            'Driver Parameter Synchronous',
            'Driver Parameter Port',
            'Driver Parameter Pollinterval',
            'Driver Parameter Pollfreq',
            'Driver Name',
            'Device Type',
            'Battery Voltage Nominal',
            'Battery Type',
            'Battery Runtime Low',
            'Battery Mfr Date',
            'Battery Charge Warning',
            'Battery Charge Low'
    ):
        return 'remove'

    return None


def down_determinator(channel):
    """ An effort to avoid redundant if statements; determines what triggers a down sensor """

    # the special char prefix & suffixes are necessary for replacements in generate_xml()
    # there's probably a more efficient way to do this (without loads of conditionals)
    # maybe better to do [err] or [warn] instead of chars?.. future cleanup to-do
    msg_dropped = ' has exceeded normal levels&'
    channels = {
        'Ups Load' : [':90#', '^Utilization has peaked&'],
        'Output Voltage' : [':120#', '^' + channel + msg_dropped],
        'Output Frequency' : [':80#', '^' + channel + msg_dropped],
        'Input Voltage' : ['%90@', '%Running on battery!@'],
        'Battery Voltage' : [':29#', '^' + channel + msg_dropped],
        'Battery Temperature' : [':32#', '^' + channel + msg_dropped]
    }

    return channels.get(channel, "")


def warn_determinator(channel):
    """
    An effort to avoid redundant if statements; determines what triggers a warning sensor
    Pre-sets values in channel settings (click the dual wheel >  Enable alerting based on limits)
    """

    msg_dropped = ' has dropped&'
    channels = {
        'Ups Load' : [':80#', '^Utilization is peaking&'],
        'Output Voltage' : [':100#', '^' + channel + msg_dropped],
        'Output Frequency' : [':48#', '^' + channel + msg_dropped],
        'Input Voltage' : [':97#', '^' + channel + ' Running on battery!&'],
        'Battery Voltage' : [':22#', '^' + channel + msg_dropped],
        'Battery Temperature' : [':24#', '^' + channel + msg_dropped],
        'Battery Runtime' : [':1800#', '^' + channel + ' 30min of battery left!&'],
        'Battery Charge' : [':70#', '^' + channel + ' is low&']
    }

    return channels.get(channel, "")


def units(channel):
    """
    Generate the display units for each channel (shown in sensor.htm?id=x&tabid=1)
    """

    if channel is not None:
        if channel in ('Battery Charge', 'Ups Load'):
            unit_measurement = '%'
        elif channel == 'Battery Runtime':
            unit_measurement = 'seconds'
        elif channel == 'Battery Temperature':
            unit_measurement = '°'
        elif channel in ('Battery Voltage', 'Input Voltage', 'Output Voltage'):
            unit_measurement = 'volts'
        elif channel == 'Output Frequency':
            unit_measurement = 'Hz'
        else:
            unit_measurement = "Set unit measurement in settings of this sensor"

    return unit_measurement


def generate_xml(channel, down, warn, value):
    """ Build the XML fields """

    # clear any spaces, so this can be passed to a value in prtg
    value = value.replace(" ", ".")

    print("<result>")
    print("<channel>" + channel + "</channel>")
    print("<CustomUnit>" + units(channel) + "</CustomUnit>")

    if down != '':
        for threshold in down_determinator(channel):

            # very hacky replacements, but will suffice for now, vs multiple conditionals
            # i'd care about it more right now if this would be a highly trafficked script

            # the special chars are placeholders for error/warning default triggers
            # assuming your message will never include these characters..
            print(threshold
                  .replace(':', '<LimitMaxError>')
                  .replace('#', '</LimitMaxError>')
                  .replace('^', '<LimitErrorMsg>')
                  .replace('&', '</LimitErrorMsg>')
                  .replace('%', '<LimitMinError>')
                  .replace('@', '</LimitMinError>')
                 )

    if warn != '':
        for threshold in warn_determinator(channel):

            print(threshold
                  .replace(':', '<LimitMinWarning>')
                  .replace('#', '</LimitMinWarning>')
                  .replace('^', '<LimitWarningMsg>')
                  .replace('&', '</LimitWarningMsg>')
                 )

    # assume all values are floats, since prtg only accepts numeric values
    print("<float>1</float>")
    print("<DecimalMode>Auto</DecimalMode>")
    print("<value>" + value + "</value>")
    print("</result>")

# start the default function on each script load
obtain_status()
