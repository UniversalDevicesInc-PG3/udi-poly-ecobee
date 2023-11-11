import sys
import re
from udi_interface import Node,LOGGER
from copy import deepcopy
import json
from node_funcs import *
from nodes import Sensor, Weather
from const import modeMap,equipmentStatusMap,windMap,transitionMap,fanMap,driversMap,ecoMap


"""
 Address scheme:
 Devices: n<profile>_t<thermostatId> e.g. n003_t511892759243
 Thermostat Sensor: n<profile>_s<thermostatId> e.g. n003_s511892759243
 Current Weather: n<profile>_w<thermostatId> e.g. n003_w511892759243
 Forecast Weather: n<profile>_f<thermostatId> e.g. n003_f511892759243
 Sensors: n<profile>_s<sensor code> e.g. n003_rs_r6dr
""" 

class Thermostat(Node):
    def __init__(self, controller, primary, address, thermostatId, name, revData, fullData, useCelsius, idSuffix):
        LOGGER.debug(f"Adding: name={name} address={address} idSuffix={idSuffix}")
        #LOGGER.debug("fullData={}".format(json.dumps(fullData, sort_keys=True, indent=2)))
        self.controller = controller
        self.name = name
        self.thermostatId = thermostatId
        self.tstat = fullData['thermostatList'][0]
        self.program = self.tstat['program']
        self.settings = self.tstat['settings']
        self.useCelsius = useCelsius
        self.type = 'thermostat'
        self.id = f'Ecobee{idSuffix}C' if self.useCelsius else f'Ecobee{idSuffix}F'
        LOGGER.debug(f'id={self.id}')
        self.drivers = deepcopy(driversMap[self.id])
        self.id = '{}_{}'.format(self.id,thermostatId)
        self.revData = revData
        self.fullData = fullData
        # Will check wether we show weather later
        self.do_weather = None
        self.weather = None
        self.forcast = None
        self._gcde = {}
        self._gcidx = {}
        # We track our driver values because we need the value before it's been pushed.
        self.driver = dict()
        super().__init__(controller.poly, primary, address, name)
        controller.poly.subscribe(controller.poly.START,                  self.handler_start, address) 

    def handler_start(self):
        if 'remoteSensors' in self.tstat:
            #LOGGER.debug("{}:remoteSensors={}".format(self.address,json.dumps(self.tstat['remoteSensors'], sort_keys=True, indent=2)))
            for sensor in self.tstat['remoteSensors']:
                if 'id' in sensor and 'name' in sensor:
                    sensorAddress = self.getSensorAddress(sensor)
                    if sensorAddress is not None:
                        # Delete the old one if it exists
                        sensorAddressOld = self.getSensorAddressOld(sensor)
                        try:
                          fonode = self.controller.poly.getNode(sensorAddressOld)
                        except TypeError:
                          fonode = None
                          LOGGER.debug("caught getNode fail due to polyglot cloud bug? assuming old node not found")
                        if fonode is not None:
                            self.controller.Notices[fonode['address']] = f"Sensor created with new name, please delete old sensor with address '{fonode['address']}' in the Polyglot UI."
                        addS = False
                        # Add Sensor is necessary
                        # Did the nodedef id change?
                        nid = self.get_sensor_nodedef(sensor)
                        sensorName = get_valid_node_name('Ecobee - {}'.format(sensor['name']))
                        self.controller.add_node(Sensor(self.controller, self.address, sensorAddress,
                                                       sensorName, nid, self))
        self.check_weather()
        self.update(self.revData, self.fullData)
        self.query()

    def check_weather(self):
        # Initialize?
        if self.do_weather is None:
            try:
                dval = self.getDriver('GV9')
                LOGGER.debug('check_weather: Initial value GV9={}'.format(dval))
                dval = int(dval)
                # Set False if 0, otherwise True since initially it may be None?
                self.do_weather = False if dval == 0 else True
            except:
                LOGGER.error('check_weather: Failed to getDriver GV9, asuming do_weather=True')
                self.do_weather = True
        if self.do_weather:
            # we want some weather
            if self.weather is None:
                # and we don't have the nodes yet, so add them
                if 'weather' in self.tstat:
                    weatherAddress = 'w{}'.format(self.thermostatId)
                    weatherName = get_valid_node_name('Ecobee - Weather')
                    self.weather = self.controller.add_node(Weather(self.controller, self.address, weatherAddress, weatherName, self.useCelsius, False, self.tstat['weather']))
                    forecastAddress = 'f{}'.format(self.thermostatId)
                    forecastName = get_valid_node_name('Ecobee - Forecast')
                    self.forcast = self.controller.add_node(Weather(self.controller, self.address, forecastAddress, forecastName, self.useCelsius, True, self.tstat['weather']))
            else:
                self.weather.update(self.tstat['weather'])
                self.forcast.update(self.tstat['weather'])
        else:
            # we dont want weather
            if self.weather is not None:
                # we have the nodes, delete them
                self.controller.poly.delNode(self.weather.address)
                self.weather = None
                self.controller.poly.delNode(self.forcast.address)
                self.forcast = None


    def get_sensor_nodedef(self,sensor):
        # Given the ecobee sensor data, figure out the nodedef
        # {'id': 'rs:100', 'name': 'Test Sensor', 'type': 'ecobee3_remote_sensor', 'code': 'VRSP', 'inUse': False, 'capability': [{'id': '1', 'type': 'temperature', 'value': 'unknown'}, {'id': '2', 'type': 'occupancy', 'value': 'false'}]}
        # {'name': '', 'type': 'monitor_sensor', 'inUse': False, 'id': 'ei:0:1', 'capability': [{'type': 'dryContact', 'value': '0', 'id': ''}]}
        has_hum = False
        has_temp = False
        has_dry_contact = False
        has_occupancy = False
        if 'capability' in sensor:
            for cb in sensor['capability']:
                if cb['type'] == 'temperature':
                    has_temp = True
                elif cb['type'] == 'humidity':
                    has_hum = True
                elif cb['type'] == 'dryContact':
                    has_dry_contact = True
                elif cb['type'] == 'occupancy':
                    has_occupancy = True
        if sensor['type'] == 'monitor_sensor':
          if has_dry_contact:
            if has_hum or has_temp or has_occupancy:
              LOGGER.error("Currently Unsupported sensor has_dry_contact={} has_temp={} has_hum={} has_occupancy={}".format(has_dry_contact,has_temp,has_hum,has_occupancy))
              return False
            else:
              return 'EcobeeSensorMSD'
        else:
          CorF = 'C' if self.useCelsius else 'F'
          HorN = 'H' if has_hum else ''
          return 'EcobeeSensor{}{}'.format(HorN,CorF)

    def update(self, revData, fullData):
      LOGGER.debug('')
      #LOGGER.debug("fullData={}".format(json.dumps(fullData, sort_keys=True, indent=2)))
      #LOGGER.debug("revData={}".format(json.dumps(revData, sort_keys=True, indent=2)))
      if not 'thermostatList' in fullData:
        LOGGER.error("No thermostatList in fullData={}".format(json.dumps(fullData, sort_keys=True, indent=2)))
        return False
      self.revData = revData
      self.fullData = fullData
      self.tstat = fullData['thermostatList'][0]
      self.settings = self.tstat['settings']
      self.program  = self.tstat['program']
      self.events   = self.tstat['events']
      self._update()

    def _update(self):
      equipmentStatus = self.tstat['equipmentStatus'].split(',')
      #LOGGER.debug("settings={}".format(json.dumps(self.settings, sort_keys=True, indent=2)))
      self.runtime = self.tstat['runtime']
      self.aqp = None
      if 'energy' in self.tstat:
        self.energy = self.tstat['energy']
        LOGGER.debug(' energy={}'.format(json.dumps(self.energy, sort_keys=True, indent=2)))
        # "airQualityPreferences": "aqGood:101,aqPoor:201,vocGood:1601,vocPoor:7001,co2Good:753,co2Poor:1753",
        if 'airQualityPreferences' in self.energy and self.energy['airQualityPreferences'] != "":
          self.aqp = dict()
          for aqp in self.energy['airQualityPreferences'].split(','):
            aq = aqp.split(':')
            if len(aq) > 0:
              self.aqp[aq[0]] = int(aq[1])
        self.setECO(self.energy['energyFeatureState'])
      else:
        self.energy = None
        LOGGER.debug(' energy=None')
      LOGGER.debug(' runtime={}'.format(json.dumps(self.runtime, sort_keys=True, indent=2)))
      clihcs = 0
      for status in equipmentStatus:
        if status in equipmentStatusMap:
          clihcs = equipmentStatusMap[status]
          break
      # This is what the schedule says should be enabled.
      climateType = self.program['currentClimateRef']
      # And the default mode, unless there is an event
      self.clismd = 0
      # Is there an active event?
      LOGGER.debug('events={}'.format(json.dumps(self.events, sort_keys=True, indent=2)))
      # Find the first running event
      event_running = False
      for event in self.events:
          if event['running'] and event_running is False:
              event_running = event
              LOGGER.debug('running event: {}'.format(json.dumps(event, sort_keys=True, indent=2)))
      if event_running is not False:
        if event_running['type'] == 'hold':
            #LOGGER.debug("Checking: events={}".format(json.dumps(self.events, sort_keys=True, indent=2)))
            LOGGER.debug(" #events={} type={} holdClimateRef={}".
                         format(len(self.events),
                                event_running['type'],
                                event_running['holdClimateRef']))
            # This seems to mean an indefinite hold
            #  "endDate": "2035-01-01", "endTime": "00:00:00",
            if event_running['endTime'] == '00:00:00':
                self.clismd = transitionMap['indefinite']
            else:
                self.clismd = transitionMap['nextTransition']
            if event_running['holdClimateRef'] != '':
                climateType = event_running['holdClimateRef']
        elif event_running['type'] == 'vacation':
            climateType = 'vacation'
        elif event_running['type'] == 'autoAway':
            # name will alwys smartAway or smartAway?
            climateType = event_running['name']
            if climateType != 'smartAway':
                LOGGER.error('autoAway event name is "{}" which is not supported, using smartAway. Please notify developer.'.format(climateType))
                climateType = 'smartAway'
        elif event_running['type'] == 'autoHome':
            # name will alwys smartAway or smartHome?
            climateType = event_running['name']
            if climateType != 'smartHome':
                LOGGER.error('autoHome event name is "{}" which is not supported, using smartHome. Please notify developer.'.format(climateType))
                climateType = 'smartHome'
        elif event_running['type'] == 'demandResponse':
            # What are thse names?
            climateType = event_running['name']
            LOGGER.error('demandResponse event name is "{}" which is not supported, using demandResponse. Please notify developer.'.format(climateType))
            climateType = 'demandResponse'
        else:
            LOGGER.error('Unknown event type "{}" name "{}" for event: {}'.format(event_running['type'],event_running['name'],event))

      LOGGER.debug('climateType={}'.format(climateType))
      #LOGGER.debug("program['climates']={}".format(self.program['climates']))
      #LOGGER.debug("settings={}".format(json.dumps(self.settings, sort_keys=True, indent=2)))
      #LOGGER.debug("program={}".format(json.dumps(self.program, sort_keys=True, indent=2)))
      #LOGGER.debug("{}:update: equipmentStatus={}".format(self.address,equipmentStatus))
      # The fan is on if on, or we are in a auxHeat mode and we don't control the fan,
      if 'fan' in equipmentStatus or (clihcs >= 6 and not self.settings['fanControlRequired']):
        clifrs = 1
      else:
        clifrs = 0
      LOGGER.debug('clifrs={} (equipmentStatus={} or clihcs={}, fanControlRequired={}'
                   .format(clifrs,equipmentStatus,clihcs,self.settings['fanControlRequired'])
                   )
      LOGGER.debug('backlightOnIntensity={} backlightSleepIntensisty={}'.
                    format(self.settings['backlightOnIntensity'],self.settings['backlightSleepIntensity']))
      updates = {
        'ST': self.tempToDriver(self.runtime['actualTemperature'],True,False),
        'CLISPH': self.tempToDriver(self.runtime['desiredHeat'],True),
        'CLISPC': self.tempToDriver(self.runtime['desiredCool'],True),
        'CLIMD': modeMap[self.settings['hvacMode']],
        'CLIFS': fanMap[self.runtime["desiredFanMode"]],
        'CLIHUM': self.runtime['actualHumidity'],
        'CLIHCS': clihcs,
        'CLIFRS': clifrs,
        'GV1': self.runtime['desiredHumidity'],
        'CLISMD': self.clismd,
        'GV4': self.settings['fanMinOnTime'],
        'GV3': self.getClimateIndex(climateType),
        'GV5': self.runtime['desiredDehumidity'],
        'GV6': 1 if self.settings['autoAway'] else 0,
        'GV7': 1 if self.settings['followMeComfort'] else 0,
        'GV8': 1 if self.runtime['connected'] else 0,
        'GV10': self.settings['backlightOnIntensity'],
        'GV11': self.settings['backlightSleepIntensity'],
        'GV17': self.getECOIndex(),
      }
      if 'actualVOC' in self.runtime and int(self.runtime['actualVOC']) != -5002:
        updates['VOCLVL'] = self.runtime['actualVOC']
        updates['CO2LVL'] = self.runtime['actualCO2']
        updates['GV12'] = self.runtime['actualAQAccuracy']
        updates['GV13'] = self.runtime['actualAQScore']
        if self.energy is not None:
          # "airQualityPreferences": "aqGood:101,aqPoor:201,vocGood:1601,vocPoor:7001,co2Good:753,co2Poor:1753",
          if self.runtime['actualAQScore'] < self.aqp['aqGood']:
            updates['GV14'] = 1
          elif self.runtime['actualAQScore'] < self.aqp['aqPoor']:
            updates['GV14'] = 2
          else:
            updates['GV14'] = 3
          if self.runtime['actualVOC'] < self.aqp['vocGood']:
            updates['GV15'] = 1
          elif self.runtime['actualVOC'] < self.aqp['vocPoor']:
            updates['GV15'] = 2
          else:
            updates['GV15'] = 3
          if self.runtime['actualCO2'] < self.aqp['co2Good']:
            updates['GV16'] = 1
          elif self.runtime['actualCO2'] < self.aqp['co2Poor']:
            updates['GV16'] = 2
          else:
            updates['GV16'] = 3

      # Now the mobile also displays a "Excellent, Good, or Poor", there's a comma delimited string in the energy object 
      # (requires includeEnergy: true in the thermostat fetch) airQualityPreferences that looks like:
      # "airQualityPreferences": "aqGood:101,aqPoor:201,vocGood:1601,vocPoor:7001,co2Good:753,co2Poor:1753"

      for key, value in updates.items():
          LOGGER.debug('setDriver({},{})'.format(key,value))
          self.setDriver(key, value)

      # Update my remote sensors.
      for sensor in self.tstat['remoteSensors']:
          saddr = self.getSensorAddress(sensor)
          snode = self.controller.poly.getNode(saddr)
          if saddr is not None:
              if snode.primary == self.address:
                  snode.update(sensor)
              else:
                  LOGGER.debug("{}._update: remoteSensor {} is not mine.".format(self.address,saddr))
          else:
              LOGGER.error("{}._update: remoteSensor {} is not in our node list.".format(self.address,saddr))
      self.check_weather()

    def getClimateIndex(self,name):
      if name in climateMap:
          climateIndex = climateMap[name]
      else:
        if not name in self._gcidx[name]:
          LOGGER.error("Unknown climateType='{}' which is a known issue https://github.com/Einstein42/udi-ecobee-poly/issues/63".format(name))
          self._gcidx[name] = True
        climateIndex = climateMap['unknown']
      return climateIndex

    def getECOIndex(self):
       if self.energy['energyFeatureState'] in ecoMap:
          idx = ecoMap[self.energy['energyFeatureState']]
       else:
          LOGGER.error("Unknown energyFeatureStage {}".format(self.energy['energyFeatureState']))
          idx = 0
       LOGGER.debug("ECO energyFeatureState={} idx={}".format(self.energy['energyFeatureState'],idx))
       return idx
    
    def getCurrentClimateDict(self):
        return self.getClimateDict(self.program['currentClimateRef'])

    def getClimateDict(self,name):
      for cref in self.program['climates']:
        if name == cref['climateRef']:
            LOGGER.info('{}:getClimateDict: Returning {}'.format(self.address,cref))
            return cref
      # Only show the error one time.
      if not cref in self._gcde:
        self._gcde[cref] = True
        LOGGER.error('{}:getClimateDict: Unknown climateRef name {}'.format(self.address,name),exc_info=True)
      return None

    def getSensorAddressOld(self,sdata):
      # return the sensor address from the ecobee api data for one sensor
      if 'id' in sdata:
          return re.sub('\\:', '', sdata['id']).lower()[:12]
      return None

    def getSensorAddress(self,sdata):
      # Is it the sensor in the thermostat?
      if sdata['type'] == 'thermostat':
        # Yes, use the thermostat id
        return 's{}'.format(self.tstat['identifier'])
      # No, use the remote sensor code if available
      # {'id': 'rs:100', 'name': 'Test Sensor', 'type': 'ecobee3_remote_sensor', 'code': 'VRSP', 'inUse': False, 'capability': [{'id': '1', 'type': 'temperature', 'value': 'unknown'}, {'id': '2', 'type': 'occupancy', 'value': 'false'}]}
      if 'code' in sdata:
        return 'rs_{}'.format(sdata['code'].lower())
      #  {'name': '', 'type': 'monitor_sensor', 'inUse': False, 'id': 'ei:0:1', 'capability': [{'type': 'dryContact', 'value': '0', 'id': ''}]}
      if 'id' in sdata:
        return re.sub('\\:', '_', sdata['id']).lower()[:12]
      LOGGER.error("{}:getSensorAddress: Unable to determine sensor address for: {}".format(self.address,sdata))

    def query(self, command=None):
      self.reportDrivers()

    def getHoldType(self,val=None):
      if val is None:
          # They want the current value
          val = self.getDriver('CLISMD')
      # Return the holdType name, if set to Hold, return indefinite
      # Otherwise return nextTransition
      return getMapName(transitionMap,2) if int(val) == 2 else getMapName(transitionMap,1)

    def ecobeePost(self,command):
      LOGGER.debug('{}:ecobeePost: {}'.format(self.address,command))
      return self.controller.ecobeePost(self.thermostatId, command)

    def pushResume(self):
      LOGGER.debug('{}:setResume: Cancelling hold'.format(self.address))
      func = {
        'type': 'resumeProgram',
        'params': {
          'resumeAll': False
        }
      }
      if self.ecobeePost( {'functions': [func]}):
        # All cancelled, restore settings to program
        self.setScheduleMode(0)
        # This is what the current climate type says it should be
        self.setClimateSettings()
        self.events = list()
        return True
      LOGGER.error('{}:setResume: Post failed?'.format(self.address))
      return False

    def setClimateSettings(self,climateName=None):
      if climateName is None:
          climateName = self.program['currentClimateRef']
      # Set to what the current schedule says
      self.setClimateType(climateName)
      cdict = self.getClimateDict(climateName)
      self.setCool(cdict['coolTemp'],True)
      self.setHeat(cdict['heatTemp'],True)
      # TODO: cdict contains coolFan & heatFan, should we use those?
      self.setFanMode(cdict['coolFan'])
      # We assume fan goes off, next refresh will say what it really is.
      self.setFanState(0)

    def pushScheduleMode(self,clismd=None,coolTemp=None,heatTemp=None,fanMode=None):
      LOGGER.debug("pushScheduleMode: clismd={} coolTemp={} heatTemp={}".format(clismd,coolTemp,heatTemp))
      if clismd is None:
          clismd = int(self.getDriver('CLISMD'))
      elif int(clismd) == 0:
        return self.pushResume()
      # Get the new schedule mode, current if in a hold, or hold next
      clismd_name = self.getHoldType(clismd)
      if heatTemp is None:
          heatTemp = self.getDriver('CLISPH')
      if coolTemp is None:
          coolTemp = self.getDriver('CLISPC')
      params = {
        'holdType': clismd_name,
        'heatHoldTemp': self.tempToEcobee(heatTemp),
        'coolHoldTemp': self.tempToEcobee(coolTemp),
      }
      if fanMode is not None:
          params['fan'] = getMapName(fanMap,fanMode)
      func = {
        'type': 'setHold',
        'params': params
      }
      if self.ecobeePost({'functions': [func]}):
        self.setScheduleMode(clismd_name)
        self.setCool(coolTemp)
        self.setHeat(heatTemp)
        if fanMode is not None:
          ir = self.setFanMode(fanMode)
          if int(ir) == 1:
            self.setFanState(1)
          else:
            self.setFanState(0)

    def pushBacklight(self,val):
        LOGGER.debug('{}'.format(val))
        #
        # Push settings test
        #
        params = {
            "thermostat": {
                "settings": {
                    "backlightOnIntensity":val
                    }
                }
        }
        if self.ecobeePost(params):
            self.setBacklight(val)

    def setBacklight(self,val):
      self.setDriver('GV10', val)

    def pushBacklightSleep(self,val):
        LOGGER.debug('{}'.format(val))
        #
        # Push settings test
        #
        params = {
            "thermostat": {
                "settings": {
                'backlightSleepIntensity':val
                    }
                }
        }
        if self.ecobeePost(params):
            self.setBacklightSleep(val)

    def setBacklightSleep(self,val):
      self.setDriver('GV11', val)

    #
    # Set Methods for drivers so they are set the same way
    #
    def setScheduleMode(self,val):
      LOGGER.debug('{}:setScheduleMode: {}'.format(self.address,val))
      if not is_int(val):
          if val in transitionMap:
            val = transitionMap[val]
          else:
            LOGGER.error("{}:setScheduleMode: Unknown transitionMap name {}".format(self.address,val))
            return False
      self.setDriver('CLISMD',int(val))
      self.clismd = int(val)

    # Set current climateType
    # True = use current
    # string = looking name
    # int = just do it
    def setClimateType(self,val):
      if val is True:
        val = self.program['currentClimateRef']
      if not is_int(val):
        if val in climateMap:
          val = climateMap[val]
        else:
          LOGGER.error("Unknown climate name {}".format(val))
          return False
      self.setDriver('GV3',int(val))

    # Convert Tempearture used by ISY to Ecobee API value
    def tempToEcobee(self,temp):
      if self.useCelsius:
        return(toF(float(temp)) * 10)
      return(int(temp) * 10)

    # Convert Temperature for driver
    # FromE converts from Ecobee API value, and to C if necessary
    # By default F values are converted to int, but for ambiant temp we
    # allow one decimal.
    def tempToDriver(self,temp,fromE=False,FtoInt=True):
      try:
        temp = float(temp)
      except:
        LOGGER.error("{}:tempToDriver: Unable to convert '{}' to float")
        return False
      # Convert from Ecobee value, unless it's already 0.
      if fromE and temp != 0:
          temp = temp / 10
      if self.useCelsius:
        if fromE:
          temp = toC(temp)
        return(temp)
      else:
        if FtoInt:
          return(int(temp))
        else:
          return(temp)

    def setCool(self,val,fromE=False,FtoInt=True):
      dval = self.tempToDriver(val,fromE,FtoInt)
      LOGGER.debug('{}:setCool: {}={} fromE={} FtoInt={}'.format(self.address,val,dval,fromE,FtoInt))
      self.setDriver('CLISPC',dval)

    def setHeat(self,val,fromE=False,FtoInt=True):
      dval = self.tempToDriver(val,fromE,FtoInt)
      LOGGER.debug('{}:setHeat: {}={} fromE={} FtoInt={}'.format(self.address,val,dval,fromE,FtoInt))
      self.setDriver('CLISPH',dval)

    def setFanMode(self,val):
      if is_int(val):
          dval = val
      else:
          if val in fanMap:
            dval = fanMap[val]
          else:
            LOGGER.error("{}:Fan: Unknown fanMap name {}".format(self.address,val))
            return False
      LOGGER.debug('{}:setFanMode: {}={}'.format(self.address,val,dval))
      self.setDriver('CLIFS',dval)
      return dval

    def setFanState(self,val):
      if is_int(val):
          dval = val
      else:
          if val in fanMap:
            dval = fanMap[val]
          else:
            LOGGER.error("{}:Fan: Unknown fanMap name {}".format(self.address,val))
            return False
      LOGGER.debug('{}:setFanState: {}={}'.format(self.address,val,dval))
      self.setDriver('CLIFRS',dval)

    def setECO(self,val):
      if is_int(val):
          dval = val
      else:
          if val in ecoMap:
            dval = ecoMap[val]
          else:
            LOGGER.error("{}:ECO: Unknown ecoMap name {}".format(self.address,val))
            return False
      LOGGER.debug('{}:setECO: {}={}'.format(self.address,val,dval))
      self.setDriver('GV17',dval)

    def cmdSetPF(self, cmd):
      # Set a hold:  https://www.ecobee.com/home/developer/api/examples/ex5.shtml
      # TODO: Need to check that mode is auto,
      #LOGGER.debug("self.events={}".format(json.dumps(self.events, sort_keys=True, indent=2)))
      #LOGGER.debug("program={}".format(json.dumps(self.program, sort_keys=True, indent=2)))
      driver = cmd['cmd']
      if driver == 'CLISPH':
        return self.pushScheduleMode(heatTemp=cmd['value'])
      elif driver == 'CLISPC':
        return self.pushScheduleMode(coolTemp=cmd['value'])
      else:
        return self.pushScheduleMode(fanMode=cmd['value'])

    def cmdSetScheduleMode(self, cmd):
      '''
        Set the Schedule Mode, like running, or a hold
      '''
      if int(self.getDriver(cmd['cmd'])) == int(cmd['value']):
        LOGGER.debug("cmdSetScheduleMode: {}={} already set to {}".format(cmd['cmd'],self.getDriver(cmd['cmd']),cmd['value']))
      else:
        self.pushScheduleMode(cmd['value'])

    def cmdSetMode(self, cmd):
      if int(self.getDriver(cmd['cmd'])) == int(cmd['value']):
        LOGGER.debug("cmdSetMode: {} already set to {}".format(cmd['cmd'],int(cmd['value'])))
      else:
        name = getMapName(modeMap,int(cmd['value']))
        LOGGER.info('Setting Thermostat {} to mode: {} (value={})'.format(self.name, name, cmd['value']))
        if self.ecobeePost( {'thermostat': {'settings': {'hvacMode': name}}}):
          self.setDriver(cmd['cmd'], cmd['value'])

    # cmd={'address': 't<address>', 'cmd': 'GV3', 'value': '10', 'uom': '25', 'query': {'HoldType.uom25': '2'}}
    def cmdSetClimateType(self, cmd):
      LOGGER.debug('{}:cmdSetClimateType: {}={} query={}'.format(self.address,cmd['cmd'],cmd['value'],cmd['query']))
      # We don't check if this is already current since they may just want setpoints returned.
      climateName = getMapName(climateMap,int(cmd['value']))
      query = cmd['query']
      command = {
        'functions': [{
          'type': 'setHold',
          'params': {
            'holdType': self.getHoldType(query['HoldType.uom25']),
            'holdClimateRef': climateName
          }
        }]
      }
      if self.ecobeePost(command):
        self.setDriver(cmd['cmd'], cmd['value'])
        self.setDriver('CLISMD',query['HoldType.uom25'])
        # If we went back to current climate name that will reset temps, so reset isy
        #if self.program['currentClimateRef'] == climateName:
        self.setClimateSettings(climateName)

    def cmdSetFanOnTime(self, cmd):
      if int(self.getDriver(cmd['cmd'])) == int(cmd['value']):
        LOGGER.debug("cmdSetFanOnTime: {} already set to {}".format(cmd['cmd'],int(cmd['value'])))
      else:
        command = {
          'thermostat': {
            'settings': {
              'fanMinOnTime': cmd['value']
            }
          }
        }
        if self.ecobeePost( command):
          self.setDriver(cmd['cmd'], cmd['value'])

    def cmdSmartHome(self, cmd):
      if int(self.getDriver(cmd['cmd'])) == int(cmd['value']):
        LOGGER.debug("cmdSetSmartHome: {} already set to {}".format(cmd['cmd'],int(cmd['value'])))
      else:
        command = {
          'thermostat': {
            'settings': {
              'autoAway': True if cmd['value'] == '1' else False
            }
          }
        }
        if self.ecobeePost( command):
          self.setDriver(cmd['cmd'], cmd['value'])

    def cmdFollowMe(self, cmd):
      if int(self.getDriver(cmd['cmd'])) == int(cmd['value']):
        LOGGER.debug("cmdFollowMe: {} already set to {}".format(cmd['cmd'],int(cmd['value'])))
      else:
        command = {
          'thermostat': {
            'settings': {
              'followMeComfort': True if cmd['value'] == '1' else False
            }
          }
        }
        if self.ecobeePost( command):
          self.setDriver(cmd['cmd'], cmd['value'])

    def cmdSetDoWeather(self, cmd):
      LOGGER.debug(cmd)
      value = int(cmd['value'])
      if int(self.getDriver(cmd['cmd'])) == value:
        LOGGER.debug("cmdSetDoWeather: {} already set to {}".format(cmd['cmd'],value))
      else:
        self.setDriver(cmd['cmd'], value)
        self.do_weather = True if value == 1 else False
        self.check_weather()

    def cmdSetBacklight(self,cmd):
      self.pushBacklight(cmd['value'])

    def cmdSetBacklightSleep(self,cmd):
      self.pushBacklightSleep(cmd['value'])

    # TODO: This should set the drivers and call pushHold...
    def setPoint(self, cmd):
      LOGGER.debug(cmd)
      coolTemp = self.tempToDriver(self.getDriver('CLISPC'))
      heatTemp = self.tempToDriver(self.getDriver('CLISPH'))
      if 'value' in cmd:
        value = float(cmd['value'])
      else:
        value = 1
      if cmd['cmd'] == 'DIM':
          value = value * -1

      if self.settings['hvacMode'] == 'heat' or self.settings['hvacMode'] == 'auto':
        cmdtype = 'heatTemp'
        driver = 'CLISPH'
        heatTemp += value
        newTemp = heatTemp
      else:
        cmdtype = 'coolTemp'
        driver = 'CLISPC'
        coolTemp += value
        newTemp = coolTemp
      LOGGER.debug('{} {} {} {}'.format(cmdtype, driver, self.getDriver(driver), newTemp))
      #LOGGER.info('Setting {} {} Set Point to {}{}'.format(self.name, cmdtype, cmd['value'], 'C' if self.useCelsius else 'F'))
      if self.ecobeePost(
        {
          "functions": [
            {
              "type":"setHold",
              "params": {
                "holdType":  self.getHoldType(),
                "heatHoldTemp":self.tempToEcobee(heatTemp),
                "coolHoldTemp":self.tempToEcobee(coolTemp),
              }
            }
          ]
        }):
        self.setDriver(driver, newTemp)
        self.setDriver('CLISMD',transitionMap[self.getHoldType()])

    def cmdSetHumidity(self, cmd):
      LOGGER.debug(cmd)
      if int(self.getDriver(cmd['cmd'])) == int(cmd['value']):
        LOGGER.debug(f"cmdSetHumidity: {cmd['cmd']} already set to {cmd['value']}")
        return

      command = {
        'thermostat': {
          'settings': {
            'humidity': cmd["value"]
          }
        }
      }

      if self.ecobeePost(command):
        self.setDriver(cmd['cmd'], cmd['value'])

    def cmdSetDehumidity(self, cmd):
      if int(self.getDriver(cmd['cmd'])) == int(cmd['value']):
        LOGGER.debug(f"cmdSetDehumidity: {cmd['cmd']} already set to {cmd['value']}")
        return 

      command = {
        'thermostat': {
          'settings': {
            'dehumidifierLevel': cmd['value']
          }
        }
      }
      
      if self.ecobeePost(command):
        self.setDriver(cmd['cmd'], cmd['value'])

    def cmdSetECO(self, cmd):
      LOGGER.debug("cmdSetECO: cmd={} value={}".format(cmd['cmd'],cmd['value']))
      if int(self.getDriver(cmd['cmd'])) == int(cmd['value']):
        LOGGER.debug(f"cmdSetECO: {cmd['cmd']} already set to {cmd['value']}")
        return 

      res = None
      for val in ecoMap:
         if ecoMap[val] == int(cmd['value']):
            res = val
      if res is None:
         LOGGER.error('Unknown ECO val {}'.format(cmd['value']))
         return
      LOGGER.debug('Setting to {}'.format(res))

      command = {
        'thermostat': {
          'energy': {
            'energyFeatureState': res
          }
        }
      }
      
      if self.ecobeePost(command):
        self.setDriver(cmd['cmd'], cmd['value'])
  
    hint = '0x010c0100'
    commands = { 'QUERY': query,
                'CLISPH': cmdSetPF,
                'CLISPC': cmdSetPF,
                'CLIFS': cmdSetPF,
                'CLIMD': cmdSetMode,
                'CLISMD': cmdSetScheduleMode,
                'GV1': cmdSetHumidity,
                'GV3': cmdSetClimateType,
                'GV4': cmdSetFanOnTime,
                'GV5': cmdSetDehumidity,
                'GV6': cmdSmartHome,
                'GV7': cmdFollowMe,
                'BRT': setPoint,
                'DIM': setPoint,
                'GV9': cmdSetDoWeather,
                'GV10': cmdSetBacklight,
                'GV11': cmdSetBacklightSleep,
                'GV17': cmdSetECO
                 }
