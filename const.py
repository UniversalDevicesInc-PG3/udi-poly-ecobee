

modeMap = {
  'off': 0,
  'heat': 1,
  'cool': 2,
  'auto': 3,
  'auxHeatOnly': 4
}

equipmentStatusMap = {
  'off': 0,
  'heatPump': 1,
  'compCool1': 2,
  'heatPump2': 3,
  'heatPump3': 4,
  'compCool2': 5,
  'auxHeat1': 6,
  'auxHeat2': 7,
  'auxHeat3': 8
}

windMap = {
  '0': 0,
  'N': 1,
  'NNE': 2,
  'NE': 3,
  'ENE': 4,
  'E': 5,
  'ESE': 6,
  'SE': 7,
  'SSE': 8,
  'S': 9,
  'SSW': 10,
  'SW': 11,
  'WSW': 12,
  'W': 13,
  'WNW': 14,
  'NW': 15,
  'NNW': 16
}

transitionMap = {
  'running': 0,
  'nextTransition': 1,
  'indefinite': 2
}

fanMap = {
  'auto': 0,
  'on': 1,
}

ecoMap = {
  'unknown': -1,
  'disabled': 0,
  'enabled': 1,
}

driversMap = {
  'ECO_CTR': [
    { 'driver': 'ST', 'value': 1, 'uom': '25', 'name': 'Controller Status' },
    { 'driver': 'GV1', 'value': 0, 'uom': '2', 'name': 'HomeKit hub connected' },
    { 'driver': 'GV3', 'value': 0, 'uom': '2', 'name': 'Authorized / Paired' },
    { 'driver': 'GV4', 'value': 0, 'uom': '25', 'name': 'HomeKit WebSocket' },
    { 'driver': 'GV5', 'value': 0, 'uom': '25', 'name': 'HomeKit MQTT' },
  ],
  'EcobeeF': [
    { 'driver': 'ST',     'value': 0,  'uom': '17', 'name': 'Temperature' },
    { 'driver': 'CLISPH', 'value': 0,  'uom': '17', 'name': 'Heat Setpoint'  },
    { 'driver': 'CLISPC', 'value': 0,  'uom': '17', 'name': 'Cool Setpoint'  },
    { 'driver': 'CLIMD',  'value': 0,  'uom': '67', 'name': 'Mode'  },
    { 'driver': 'CLIFS',  'value': 0,  'uom': '68', 'name': 'Fan Mode'  },
    { 'driver': 'CLIHUM', 'value': 0,  'uom': '22', 'name': 'Humidity'  },
    { 'driver': 'CLIHCS', 'value': 0,  'uom': '25', 'name': 'Heat/Cool State'  },
    { 'driver': 'CLIFRS', 'value': 0,  'uom': '80', 'name': 'Fan State'  },
    { 'driver': 'GV1',    'value': 0,  'uom': '22', 'name': 'Humidification Setpoint'  },
    { 'driver': 'CLISMD', 'value': 0,  'uom': '25', 'name': 'Hold Type'  },
    { 'driver': 'GV4',    'value': 0,  'uom': '25', 'name': 'Fan On Time'  },
    { 'driver': 'GV3',    'value': 0,  'uom': '25', 'name': 'Climate Type'  },
    { 'driver': 'GV5',    'value': 0,  'uom': '22', 'name': 'Dehumidification Setpoint'  },
    { 'driver': 'GV6',    'value': 0,  'uom': '25', 'name': 'Smart Home-Away'  },
    { 'driver': 'GV7',    'value': 0,  'uom': '25', 'name': 'Follow Me'  },
    { 'driver': 'GV8',    'value': 0,  'uom': '2',  'name': 'Connected'  },
    { 'driver': 'GV9',    'value': 1,  'uom': '25', 'name': 'Weather'  },
    { 'driver': 'GV10',   'value': 10, 'uom': '56', 'name': 'Backlight On Intensity'  },
    { 'driver': 'GV11',   'value': 10, 'uom': '56', 'name': 'Backlight Sleep Intensity'  },
    { 'driver': 'GV17',   'value': 0,  'uom': '25', 'name': 'ECO+'  }
  ],
  'EcobeeC': [
    { 'driver': 'ST',     'value': 0,  'uom': '4', 'name': 'Temperature' },
    { 'driver': 'CLISPH', 'value': 0,  'uom': '4', 'name': 'Heat Setpoint'  },
    { 'driver': 'CLISPC', 'value': 0,  'uom': '4', 'name': 'Cool Setpoint'  },
    { 'driver': 'CLIMD',  'value': 0,  'uom': '67', 'name': 'Mode'  },
    { 'driver': 'CLIFS',  'value': 0,  'uom': '68', 'name': 'Fan Mode'  },
    { 'driver': 'CLIHUM', 'value': 0,  'uom': '22', 'name': 'Humidity'  },
    { 'driver': 'CLIHCS', 'value': 0,  'uom': '25', 'name': 'Heat/Cool State'  },
    { 'driver': 'CLIFRS', 'value': 0,  'uom': '80', 'name': 'Fan State'  },
    { 'driver': 'GV1',    'value': 0,  'uom': '22', 'name': 'Humidification Setpoint'  },
    { 'driver': 'CLISMD', 'value': 0,  'uom': '25', 'name': 'Hold Type'  },
    { 'driver': 'GV4',    'value': 0,  'uom': '25', 'name': 'Fan On Time'  },
    { 'driver': 'GV3',    'value': 0,  'uom': '25', 'name': 'Climate Type'  },
    { 'driver': 'GV5',    'value': 0,  'uom': '22', 'name': 'Dehumidification Setpoint'  },
    { 'driver': 'GV6',    'value': 0,  'uom': '25', 'name': 'Smart Home-Away'  },
    { 'driver': 'GV7',    'value': 0,  'uom': '25', 'name': 'Follow Me'  },
    { 'driver': 'GV8',    'value': 0,  'uom': '2',  'name': 'Connected'  },
    { 'driver': 'GV9',    'value': 1,  'uom': '25', 'name': 'Weather'  },
    { 'driver': 'GV10',   'value': 10, 'uom': '56', 'name': 'Backlight On Intensity'  },
    { 'driver': 'GV11',   'value': 10, 'uom': '56', 'name': 'Backlight Sleep Intensity'  },
    { 'driver': 'GV17',   'value': 0,  'uom': '25', 'name': 'ECO+'  }
  ],
  # HomeKit hub path: subset of EcobeeF/C (see README "HomeKit thermostat node").
  'EcobeeHKF': [
    { 'driver': 'ST',     'value': 0,  'uom': '17', 'name': 'Temperature' },
    { 'driver': 'CLISPH', 'value': 0,  'uom': '17', 'name': 'Heat Setpoint'  },
    { 'driver': 'CLISPC', 'value': 0,  'uom': '17', 'name': 'Cool Setpoint'  },
    { 'driver': 'CLIMD',  'value': 0,  'uom': '67', 'name': 'Mode'  },
    { 'driver': 'CLIFS',  'value': 0,  'uom': '68', 'name': 'Fan Mode'  },
    { 'driver': 'CLIHUM', 'value': 0,  'uom': '22', 'name': 'Humidity'  },
    { 'driver': 'CLIHCS', 'value': 0,  'uom': '25', 'name': 'Heat/Cool State'  },
    { 'driver': 'CLIFRS', 'value': 0,  'uom': '80', 'name': 'Fan State'  },
    { 'driver': 'GV1',    'value': 0,  'uom': '22', 'name': 'Humidification Setpoint'  },
    { 'driver': 'CLISMD', 'value': 0,  'uom': '25', 'name': 'Hold Type'  },
    { 'driver': 'GV3',    'value': 0,  'uom': '25', 'name': 'Climate / program (from hub)'  },
  ],
  'EcobeeHKC': [
    { 'driver': 'ST',     'value': 0,  'uom': '4', 'name': 'Temperature' },
    { 'driver': 'CLISPH', 'value': 0,  'uom': '4', 'name': 'Heat Setpoint'  },
    { 'driver': 'CLISPC', 'value': 0,  'uom': '4', 'name': 'Cool Setpoint'  },
    { 'driver': 'CLIMD',  'value': 0,  'uom': '67', 'name': 'Mode'  },
    { 'driver': 'CLIFS',  'value': 0,  'uom': '68', 'name': 'Fan Mode'  },
    { 'driver': 'CLIHUM', 'value': 0,  'uom': '22', 'name': 'Humidity'  },
    { 'driver': 'CLIHCS', 'value': 0,  'uom': '25', 'name': 'Heat/Cool State'  },
    { 'driver': 'CLIFRS', 'value': 0,  'uom': '80', 'name': 'Fan State'  },
    { 'driver': 'GV1',    'value': 0,  'uom': '22', 'name': 'Humidification Setpoint'  },
    { 'driver': 'CLISMD', 'value': 0,  'uom': '25', 'name': 'Hold Type'  },
    { 'driver': 'GV3',    'value': 0,  'uom': '25', 'name': 'Climate / program (from hub)'  },
  ],
  'EcobeewAQF': [
    { 'driver': 'ST',     'value': 0,  'uom': '17', 'name': 'Temperature' },
    { 'driver': 'CLISPH', 'value': 0,  'uom': '17', 'name': 'Heat Setpoint'  },
    { 'driver': 'CLISPC', 'value': 0,  'uom': '17', 'name': 'Cool Setpoint'  },
    { 'driver': 'CLIMD',  'value': 0,  'uom': '67', 'name': 'Mode'  },
    { 'driver': 'CLIFS',  'value': 0,  'uom': '68', 'name': 'Fan Mode'  },
    { 'driver': 'CLIHUM', 'value': 0,  'uom': '22', 'name': 'Humidity'  },
    { 'driver': 'CLIHCS', 'value': 0,  'uom': '25', 'name': 'Heat/Cool State'  },
    { 'driver': 'CLIFRS', 'value': 0,  'uom': '80', 'name': 'Fan State'  },
    { 'driver': 'GV1',    'value': 0,  'uom': '22', 'name': 'Humidification Setpoint'  },
    { 'driver': 'CLISMD', 'value': 0,  'uom': '25', 'name': 'Hold Type'  },
    { 'driver': 'GV4',    'value': 0,  'uom': '25', 'name': 'Fan On Time'  },
    { 'driver': 'GV3',    'value': 0,  'uom': '25', 'name': 'Climate Type'  },
    { 'driver': 'GV5',    'value': 0,  'uom': '22', 'name': 'Dehumidification Setpoint'  },
    { 'driver': 'GV6',    'value': 0,  'uom': '25', 'name': 'Smart Home-Away'  },
    { 'driver': 'GV7',    'value': 0,  'uom': '25', 'name': 'Follow Me'  },
    { 'driver': 'GV8',    'value': 0,  'uom': '2',  'name': 'Connected'  },
    { 'driver': 'GV9',    'value': 1,  'uom': '25', 'name': 'Weather'  },
    { 'driver': 'GV10',   'value': 10, 'uom': '56', 'name': 'Backlight On Intensity'  },
    { 'driver': 'GV11',   'value': 10, 'uom': '56', 'name': 'Backlight Sleep Intensity'  },
    { 'driver': 'GV17',   'value': 0,  'uom': '25', 'name': 'ECO+'  },
    { 'driver': 'VOCLVL', 'value': 0,  'uom': '56', 'name': 'VOC Level' },
    { 'driver': 'CO2LVL', 'value': 0,  'uom': '56', 'name': 'CO2 Level' },
    { 'driver': 'GV12',   'value': 0,  'uom': '25', 'name': 'Air Quality Accuracy' },
    { 'driver': 'GV13',   'value': 0,  'uom': '56', 'name': 'Actual Air Quality Score' },
    { 'driver': 'GV14',   'value': 0,  'uom': '25', 'name': 'Air Quality Score' },
    { 'driver': 'GV15',   'value': 0,  'uom': '25', 'name': 'VOC Score' },
    { 'driver': 'GV16',   'value': 0,  'uom': '25', 'name': 'CO2 Score' },
  ],
  'EcobeewAQC': [
    { 'driver': 'ST',     'value': 0,  'uom': '4', 'name': 'Temperature' },
    { 'driver': 'CLISPH', 'value': 0,  'uom': '4', 'name': 'Heat Setpoint'  },
    { 'driver': 'CLISPC', 'value': 0,  'uom': '4', 'name': 'Cool Setpoint'  },
    { 'driver': 'CLIMD',  'value': 0,  'uom': '67', 'name': 'Mode'  },
    { 'driver': 'CLIFS',  'value': 0,  'uom': '68', 'name': 'Fan Mode'  },
    { 'driver': 'CLIHUM', 'value': 0,  'uom': '22', 'name': 'Humidity'  },
    { 'driver': 'CLIHCS', 'value': 0,  'uom': '25', 'name': 'Heat/Cool State'  },
    { 'driver': 'CLIFRS', 'value': 0,  'uom': '80', 'name': 'Fan State'  },
    { 'driver': 'GV1',    'value': 0,  'uom': '22', 'name': 'Humidification Setpoint'  },
    { 'driver': 'CLISMD', 'value': 0,  'uom': '25', 'name': 'Hold Type'  },
    { 'driver': 'GV4',    'value': 0,  'uom': '25', 'name': 'Fan On Time'  },
    { 'driver': 'GV3',    'value': 0,  'uom': '25', 'name': 'Climate Type'  },
    { 'driver': 'GV5',    'value': 0,  'uom': '22', 'name': 'Dehumidification Setpoint'  },
    { 'driver': 'GV6',    'value': 0,  'uom': '25', 'name': 'Smart Home-Away'  },
    { 'driver': 'GV7',    'value': 0,  'uom': '25', 'name': 'Follow Me'  },
    { 'driver': 'GV8',    'value': 0,  'uom': '2',  'name': 'Connected'  },
    { 'driver': 'GV9',    'value': 1,  'uom': '25', 'name': 'Weather'  },
    { 'driver': 'GV10',   'value': 10, 'uom': '56', 'name': 'Backlight On Intensity'  },
    { 'driver': 'GV11',   'value': 10, 'uom': '56', 'name': 'Backlight Sleep Intensity'  },
    { 'driver': 'GV17',   'value': 0,  'uom': '25', 'name': 'ECO+'  },
    { 'driver': 'VOCLVL', 'value': 0,  'uom': '56', 'name': 'VOC Level' },
    { 'driver': 'CO2LVL', 'value': 0,  'uom': '56', 'name': 'CO2 Level' },
    { 'driver': 'GV12',   'value': 0,  'uom': '25', 'name': 'Air Quality Accuracy' },
    { 'driver': 'GV13',   'value': 0,  'uom': '56', 'name': 'Actual Air Quality Score' },
    { 'driver': 'GV14',   'value': 0,  'uom': '25', 'name': 'Air Quality Score' },
    { 'driver': 'GV15',   'value': 0,  'uom': '25', 'name': 'VOC Score' },
    { 'driver': 'GV16',   'value': 0,  'uom': '25', 'name': 'CO2 Score' },
  ],
  'EcobeeSensorF': [
    { 'driver': 'ST', 'value': 0, 'uom': '17', 'name': 'Temperature' },
    { 'driver': 'GV1', 'value': 0, 'uom': '25', 'name': 'Occupancy' },
    { 'driver': 'GV2', 'value': 0, 'uom': '2', 'name': 'Responding' },
    { 'driver': 'BATLVL', 'value': 0, 'uom': '51', 'name': 'Battery Level' },
    { 'driver': 'BATLOW', 'value': 0, 'uom': '2', 'name': 'Battery Low' },
  ],
  'EcobeeSensorC': [
    { 'driver': 'ST', 'value': 0, 'uom': '4', 'name': 'Temperature' },
    { 'driver': 'GV1', 'value': 0, 'uom': '25', 'name': 'Occupancy' },
    { 'driver': 'GV2', 'value': 0, 'uom': '2', 'name': 'Responding' },
    { 'driver': 'BATLVL', 'value': 0, 'uom': '51', 'name': 'Battery Level' },
    { 'driver': 'BATLOW', 'value': 0, 'uom': '2', 'name': 'Battery Low' },
  ],
  'EcobeeSensorHF': [
    { 'driver': 'ST', 'value': 0, 'uom': '17', 'name': 'Temperature' },
    { 'driver': 'GV1', 'value': 0, 'uom': '25', 'name': 'Occupancy' },
    { 'driver': 'GV2', 'value': 0, 'uom': '2', 'name': 'Responding' },
    { 'driver': 'CLIHUM', 'value': -1, 'uom': '22', 'name': 'Humidity' },
    { 'driver': 'BATLVL', 'value': 0, 'uom': '51', 'name': 'Battery Level' },
    { 'driver': 'BATLOW', 'value': 0, 'uom': '2', 'name': 'Battery Low' },
  ],
  'EcobeeSensorHC': [
    { 'driver': 'ST', 'value': 0, 'uom': '4', 'name': 'Temperature' },
    { 'driver': 'GV1', 'value': 0, 'uom': '25', 'name': 'Occupancy' },
    { 'driver': 'GV2', 'value': 0, 'uom': '2', 'name': 'Responding' },
    { 'driver': 'CLIHUM', 'value': -1, 'uom': '22', 'name': 'Humidity' },
    { 'driver': 'BATLVL', 'value': 0, 'uom': '51', 'name': 'Battery Level' },
    { 'driver': 'BATLOW', 'value': 0, 'uom': '2', 'name': 'Battery Low' },
  ],
  'EcobeeWeatherF': [
    { 'driver': 'ST',  'value': 0, 'uom': '17', 'name': 'Temperature' },
    { 'driver': 'GV1', 'value': 0, 'uom': '22', 'name': 'Humidity' },
    { 'driver': 'GV2', 'value': 0, 'uom': '22', 'name': 'POP' },
    { 'driver': 'GV3', 'value': 0, 'uom': '17', 'name': 'High Temp' },
    { 'driver': 'GV4', 'value': 0, 'uom': '17', 'name': 'Low Temp' },
    { 'driver': 'GV5', 'value': 0, 'uom': '48', 'name': 'Wind Speed' },
    { 'driver': 'GV6', 'value': 0, 'uom': '25', 'name': 'Wind Direction' },
    { 'driver': 'GV7', 'value': 0, 'uom': '25', 'name': 'Sky' },
    { 'driver': 'GV8', 'value': 0, 'uom': '25', 'name': 'Symbol' },
    { 'driver': 'GV9', 'value': 0, 'uom': '25', 'name': 'Weather' }
  ],
  'EcobeeWeatherC': [
    { 'driver': 'ST',  'value': 0, 'uom': '4', 'name': 'Temperature' },
    { 'driver': 'GV1', 'value': 0, 'uom': '22', 'name': 'Humidity' },
    { 'driver': 'GV2', 'value': 0, 'uom': '22', 'name': 'POP' },
    { 'driver': 'GV3', 'value': 0, 'uom': '4', 'name': 'High Temp' },
    { 'driver': 'GV4', 'value': 0, 'uom': '4', 'name': 'Low Temp' },
    { 'driver': 'GV5', 'value': 0, 'uom': '48', 'name': 'Wind Speed' },
    { 'driver': 'GV6', 'value': 0, 'uom': '25', 'name': 'Wind Direction' },
    { 'driver': 'GV7', 'value': 0, 'uom': '25', 'name': 'Sky' },
    { 'driver': 'GV8', 'value': 0, 'uom': '25', 'name': 'Symbol' },
    { 'driver': 'GV9', 'value': 0, 'uom': '25', 'name': 'Weather' }
  ],
  'EcobeeSensorMSD': [
    { 'driver': 'ST', 'value': 0, 'uom': '17', 'name': 'Temperature' },
  ],
}

# IoX UOM: 4 = Celsius, 17 = Fahrenheit, 67 = thermostat mode.
UOM_CELSIUS = '4'
UOM_FAHRENHEIT = '17'
UOM_TSTAT_MODE = '67'

THERMOSTAT_TEMP_DRIVERS = frozenset({'ST', 'CLISPH', 'CLISPC'})


def temperature_uom(use_celsius: bool) -> str:
    """IoX temperature UOM for the current display units."""
    return UOM_CELSIUS if use_celsius else UOM_FAHRENHEIT


def restore_template_uoms(drivers, template) -> int:
    """Force each driver UOM to match *template*. Returns how many rows changed.

    PG3 ``Node._updateDrivers`` copies stored UOM from the database. After a
    Fahrenheit→Celsius nodedef switch those rows can stay UOM 17 (F) while values
    are written in Celsius — Admin Console shows °F and program IF uses F.
    """
    if not isinstance(drivers, list) or not isinstance(template, list):
        return 0
    want = {d.get('driver'): str(d.get('uom')) for d in template if d.get('driver')}
    changed = 0
    for d in drivers:
        key = d.get('driver')
        if not key or key not in want:
            continue
        if str(d.get('uom')) != want[key]:
            d['uom'] = want[key]
            changed += 1
    return changed


def driver_uom_from_list(drivers, driver: str):
    """Return the UOM string for *driver* from a ``driversMap``-style list, or None."""
    if not isinstance(drivers, list):
        return None
    for d in drivers:
        if d.get('driver') == driver:
            return d.get('uom')
    return None
