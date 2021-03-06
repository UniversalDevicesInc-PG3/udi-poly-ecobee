

from udi_interface import Node,LOGGER
    
from copy import deepcopy
from const import driversMap,windMap
from node_funcs import *

class Weather(Node):
    def __init__(self, controller, primary, address, name, useCelsius, forecast, weather):
        super().__init__(controller.poly, primary, address, name)
        self.type = 'forecast' if forecast else 'weather'
        self.forecastNum = 1 if forecast else 0
        self.useCelsius = useCelsius
        self.id = 'EcobeeWeatherC' if self.useCelsius else 'EcobeeWeatherF'
        self.drivers = deepcopy(driversMap[self.id])
        self.initial_weather = weather
        controller.poly.subscribe(controller.poly.START,                  self.handler_start, address) 
        controller.poly.subscribe(controller.poly.CONFIGDONE,             self.handler_config_done) 
        controller.poly.subscribe(controller.poly.ADDNODEDONE,            self.handler_add_node_done) 

    def handler_start(self):
        LOGGER.debug('enter')

    def handler_config_done(self):
        LOGGER.debug('enter')
        self.update(self.initial_weather)
        self.query()
        LOGGER.debug('exit')

    def handler_add_node_done(self, data):
        LOGGER.debug('enter')
        if not data['address'] == self.address:
          return
        self.update(self.initial_weather)
        self.query()
        LOGGER.debug('exit')

    def update(self, weather):
      try:
        currentWeather = weather['forecasts'][self.forecastNum]
      except IndexError:
        LOGGER.error("Weather can not update no weather['forecasts'][{}] in weather={}".format(self.forecastNum,weather))
        return
      windSpeed = 0
      if self.type == 'weather' and currentWeather['windSpeed'] == 0 and weather['forecasts'][5]['windSpeed'] > 0:
        windSpeed = weather['forecasts'][5]['windSpeed']
      else:
        windSpeed = currentWeather['windSpeed']

      tempCurrent = currentWeather['temperature'] / 10 if currentWeather['temperature'] != 0 else 0
      tempHeat = currentWeather['tempHigh'] / 10 if currentWeather['tempHigh'] != 0 else 0
      tempCool = currentWeather['tempLow'] / 10 if currentWeather['tempLow'] != 0 else 0
      if self.useCelsius:
        tempCurrent = toC(tempCurrent)
        tempHeat = toC(tempHeat)
        tempCool = toC(tempCool)
      updates = {
        'ST': tempCurrent,
        'GV1': currentWeather['relativeHumidity'],
        'GV2': currentWeather['pop'],
        'GV3': tempHeat,
        'GV4': tempCool,
        'GV5': windSpeed,
        'GV6': windMap[currentWeather['windDirection']],
        'GV7': weather['forecasts'][5]['sky'] if currentWeather['sky'] == -5002 else currentWeather['sky'],
        'GV8': currentWeather['weatherSymbol'],
        'GV9': currentWeather['weatherSymbol']
      }
      for key, value in updates.items():
        self.setDriver(key, value)

    def query(self, command=None):
        self.reportDrivers()

    hint = '0x010b0100'
    commands = {'QUERY': query, 'STATUS': query}
