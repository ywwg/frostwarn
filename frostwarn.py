#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import getopt
import os.path
import smtplib
import sys
import time

import urllib.request, urllib.error, urllib.parse
import xml.sax
from xml.sax import make_parser
from xml.sax.handler import ContentHandler

FROST_WARN_THRESHOLD = 37

# weather.gov url for warwick, ma
WEATHER_XML_URL = "http://forecast.weather.gov/MapClick.php?lat=42.68212&lon=-72.33808&unit=0&lg=english&FcstType=dwml"
WEATHER_FORECAST_URL = "http://forecast.weather.gov/MapClick.php?lat=42.68212&lon=-72.33808&unit=0&lg=english"


class ForecastHandler(ContentHandler):
    def __init__(self):
        ContentHandler.__init__(self)
        self._in_temperature = False
        self._in_name = False
        self._in_mintemp_value = False
        self._current_name = ""
        self._temperatures = []

    def get_temperatures(self):
        # Only consider the next 5 or 6 days
        return self._temperatures[:6]

    def startElement(self, name, attrs):
        if name == "value":
            if self._current_name == "Daily Minimum Temperature":
                self._in_mintemp_value = True
        elif name == "temperature":
            self._in_temperature = True
        elif name == "name":
            self._in_name = True

    def endElement(self, name):
        if name == "temperature":
            self._in_temperature = False
            self._current_name = ""
        elif name == "name":
            self._in_name = False
        elif name == "value":
            self._in_mintemp_value = False

    def characters(self, content):
        if len(content) == 0:
            return

        if self._in_mintemp_value:
            #print "appending a temperature!",content
            self._temperatures.append(int(content))
        elif self._in_temperature and self._in_name:
            self._current_name = content


def get_forecast():
    xmldata = None
    for i in range(0, 5):
        try:
            xmldata = urllib.request.urlopen(WEATHER_XML_URL)
            break
        except:
            print("Error getting forecast, retrying ", i)
            time.sleep(10)
            pass

    if xmldata is None:
        print("Tried five without success, giving up")
        sys.exit(2)

    parser = make_parser()
    handler = ForecastHandler()
    parser.setContentHandler(handler)
    parser.parse(xmldata)

    forecast_temps = handler.get_temperatures()

    return forecast_temps


def send_email(msg, secrets):
    with smtplib.SMTP_SSL("newton.cx", 465) as smtp:
        smtp.login(secrets['user'], secrets['pass'])
        smtp.sendmail(secrets['to'], [secrets['from']],
            f"""From: Frost Warning <{secrets['from']}>
To: Owen Williams <{secrets['to']}>
Subject: Frost Warning!

There are cold temperatures in the forecast -- have you winterized?
{WEATHER_FORECAST_URL}
{msg}""")


if __name__ == '__main__':
    force = False
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   "fs:", ["force", "secret_file"])
    except getopt.GetoptError:
        print("-f to force, and -s or --secret_file (required)")
        sys.exit(1)

    secret_file = ""
    if len(opts) > 0:
        for o, a in opts:
            if o in ("-f", "--force"):
                force = True
            if o in ("-s", "--secret_file"):
                secret_file = a

    if secret_file == '':
        print ('Need a secrets file (-s)')
        sys.exit(1)

    secrets = {}
    with open(secret_file, 'r') as f:
        for l in f.readlines():
            try:
                key, val = l.split(' ')
                secrets[key] = val.strip()
            except:
                pass
    if 'user' not in secrets:
        print('Missing "user" in secrets file')
        sys.exit(1)
    if 'pass' not in secrets:
        print('Missing "pass" in secrets file')
        sys.exit(1)
    if 'from' not in secrets:
        print('Missing "from" in secrets file')
        sys.exit(1)
    if 'to' not in secrets:
        print('Missing "to" in secrets file')
        sys.exit(1)

    forecast_temps = get_forecast()
    temp_list = ", ".join([str(t) for t in forecast_temps])
    did_email = False
    if force:
        print("forced, sending")
        send_email("(forced) " + temp_list, secrets)
        sys.exit(0)

    for t in forecast_temps:
        if t <= FROST_WARN_THRESHOLD:
            did_email = True
            print("detected a frost event, emailing")
            send_email(temp_list, secrets)
    if not did_email:
        print("No frost, no email")
