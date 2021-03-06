

from udi_interface import Node,LOGGER

from copy import deepcopy
from const import driversMap
from node_funcs import *

class Sensor(Node):
    def __init__(self, controller, primary, address, name, id, parent):
      super().__init__(controller.poly, primary, address, name)
      self.type = 'sensor'
      # self.code = code
      self.parent = parent
      self.id = id
      self.drivers = deepcopy(driversMap[self.id])
      controller.poly.subscribe(controller.poly.START,                  self.handler_start, address) 

    def handler_start(self):
      self.query()

    def update(self, sensor):
      LOGGER.debug("{}:update:".format(self.address))
      LOGGER.debug("{}:update: sensor={}".format(self.address,sensor))
      updates = {
          'GV1': 2 # Default is N/A
      }
      # Cross reference from sensor capabilty to driver
      xref = {
        'temperature': 'ST',
        'humidity': 'CLIHUM',
        'occupancy': 'GV1',
        'responding': 'GV2',
        'dryContact': 'GV3',
        'airQualityAccuracy': False,
        'airQuality': False,
        'vocPPM': False,
        'co2PPM': False,
        'airPressure': False
      }
      for item in sensor['capability']:
          if item['type'] in xref:
            if xref[item['type']] is not False:
              val = item['value']
              if val == "true":
                val = 1
              elif val == "false":
                val = 0
              if item['type'] == 'temperature':
                # temperature unknown seems to mean the sensor is not responding.s
                if val == 'unknown':
                  updates[xref['responding']] = 0
                else:
                  updates[xref['responding']] = 1
                  val = self.parent.tempToDriver(val,True,False)
              if val is not False:
                updates[xref[item['type']]] = val
          else:
            LOGGER.error("{}:update: Unknown capabilty: {}".format(self.address,item))
      LOGGER.debug("{}:update: updates={}".format(self.address,updates))
      for key, value in updates.items():
        self.setDriver(key, value)

    def query(self, command=None):
      self.reportDrivers()

    hint = '0x01030200'
    commands = {'QUERY': query, 'STATUS': query}
