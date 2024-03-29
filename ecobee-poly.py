#!/usr/bin/env python
# 
from udi_interface import Interface,LOGGER
import sys

""" Grab My Controller Node """
from nodes import VERSION,Controller

if __name__ == "__main__":
    try:
        polyglot = Interface([Controller])
        polyglot.start(VERSION)
        polyglot.updateProfile()
        polyglot.setCustomParamsDoc()
        Controller(polyglot, 'controller', 'controller', 'Ecobee Controller')
        polyglot.runForever()
    except (KeyboardInterrupt, SystemExit):
        LOGGER.warning("Received interrupt or exit...")
        polyglot.stop()
    except Exception as err:
        LOGGER.error('Excption: {0}'.format(err), exc_info=True)
    sys.exit(0)
