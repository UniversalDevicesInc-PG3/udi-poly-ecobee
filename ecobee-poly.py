#!/usr/bin/env python
# 
from udi_interface import Interface,LOGGER
import sys

""" Grab My Controller Node """
from nodes import VERSION, Controller
from nodes.backends.homekit import HomeKitSensor, HomeKitThermostat

if __name__ == "__main__":
    try:
        polyglot = Interface([Controller, HomeKitThermostat, HomeKitSensor])
        polyglot.start(VERSION)
        polyglot.updateProfile()
        Controller(polyglot, 'controller', 'controller', 'Ecobee Controller')
        polyglot.runForever()
    except (KeyboardInterrupt, SystemExit):
        LOGGER.warning("Received interrupt or exit...")
        polyglot.stop()
    except Exception as err:
        LOGGER.error('Excption: {0}'.format(err), exc_info=True)
    sys.exit(0)
