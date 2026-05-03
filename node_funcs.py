
import os
import re
import json
from typing import Any, Dict, Optional

# Keys internal to udi_interface.Custom (see site-packages/udi_interface/custom.py dump()).
_CUSTOM_INTERNAL_KEYS = frozenset({'poly', 'custom', '_rawdata', '_extradata'})


def customdata_user_snapshot(store: Any) -> Dict[str, Any]:
    """
    Build a JSON-serializable dict of user keys from ``udi_interface.Custom``.

    Never use :meth:`Custom.dump` for persistence or MQTT-related logic: ``dump()`` returns the
    full ``__dict__`` including the non-serializable ``poly`` reference.
    """
    if store is None:
        return {}
    try:
        out = {k: store[k] for k in store}
    except Exception:
        return {}
    for k in list(out.keys()):
        if k in _CUSTOM_INTERNAL_KEYS:
            del out[k]
    return out


def customdata_load_payload(data: Any) -> Optional[Dict[str, Any]]:
    """
    Normalize inbound customdata for :meth:`Custom.load`.

    If a full ``Custom.dump()`` blob was mistakenly passed (e.g. replay bug), recover the real
    user store from ``_rawdata`` so ``poly`` is never written into persisted customdata.
    """
    if data is None:
        return None
    if not isinstance(data, dict):
        return None
    if 'poly' in data and '_rawdata' in data:
        inner = data.get('_rawdata')
        if isinstance(inner, dict):
            return {k: v for k, v in inner.items() if k not in _CUSTOM_INTERNAL_KEYS}
    return {k: v for k, v in data.items() if k not in _CUSTOM_INTERNAL_KEYS}


def ltom(list):
    map = dict()
    i = 0
    for name in list:
        map[name] = i
        i += 1
    return map

# Wake up is not on all thermostats, so should only be included when supported
# https://www.ecobee.com/home/developer/api/documentation/v1/objects/Climate.shtml
# Should get this list from the thermostat
#  https://www.ecobee.com/home/developer/api/documentation/v1/objects/Program.shtml
# And add unknown since some code relies on that name existing.
climateList = [
    'away',
    'home',
    'sleep',
    'smart1',
    'smart2',
    'smart3',
    'smart4',
    'smart5',
    'smart6',
    'smart7',
    'vacation',
    'smartAway',
    'smartHome',
    'demandResponse',
    'unknown',
    'wakeup',
  ]
climateMap = ltom(climateList)

# Removes invalid charaters for ISY Node description
def get_valid_node_name(name):
    # Only allow utf-8 characters
    #  https://stackoverflow.com/questions/26541968/delete-every-non-utf-8-symbols-froms-string
    name = bytes(name, 'utf-8').decode('utf-8','ignore')
    # Remove <>`~!@#$%^&*(){}[]?/\;:"'` characters from name
    return re.sub(r"[<>`~!@#$%^&*(){}[\]?/\\;:\"']+", "", name)

def toC(tempF):
  # Round to the nearest .5
  return round(((tempF - 32) / 1.8) * 2) / 2

def toF(tempC):
  # Round to nearest whole degree
  return int(round(tempC * 1.8) + 32)

def getMapName(map,val):
  val = int(val)
  for name in map:
    if int(map[name]) == val:
      return name

def is_int(s):
    try:
        int(s)
        return True
    except ValueError:
        return False

def make_file_dir(file_path):
    directory = os.path.dirname(file_path)
    if not os.path.exists(directory):
        # TODO: Trap this?
        os.makedirs(directory)
    return True

def get_profile_info(logger):
    pvf = 'profile/version.txt'
    try:
        with open(pvf) as f:
            pv = f.read().replace('\n', '')
    except Exception as err:
        logger.error('get_profile_info: failed to read  file {0}: {1}'.format(pvf,err), exc_info=True)
        pv = 0
    f.close()
    return { 'version': pv }
