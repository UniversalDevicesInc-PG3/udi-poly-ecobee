"""Remote sensor node for HomeKit hub path (EcobeeSensorF/C/HF/HC)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, TYPE_CHECKING

from udi_interface import LOGGER, Node

from const import driversMap
from node_funcs import get_valid_node_name

if TYPE_CHECKING:
    from .Controller import HomeKitBackend


class HomeKitSensor(Node):
    hint = '0x01030200'

    def __init__(
        self,
        controller,
        primary: str,
        address: str,
        name: str,
        nodedef_id: str,
        use_celsius: bool,
        device_id_hub: str,
        aid: int,
        hk: 'HomeKitBackend',
    ):
        self.controller = controller
        self.device_id_hub = device_id_hub
        self.aid = int(aid)
        self.use_celsius = use_celsius
        self.hk = hk
        self.id = nodedef_id
        self.drivers = deepcopy(driversMap[nodedef_id])
        nm = get_valid_node_name(name)
        super().__init__(controller.poly, primary, address, nm)
        self.name = nm
        controller.poly.subscribe(controller.poly.START, self.handler_start, address)

    def handler_start(self):
        self.query()

    def set_driver_safe(self, driver: str, val: Any, report: bool = True) -> None:
        try:
            self.setDriver(driver, val, report=report, force=True)
        except Exception:
            LOGGER.debug('sensor setDriver %s=%r failed for %s', driver, val, self.address, exc_info=True)

    def apply_hub_characteristic(self, characteristic: str, value: Any) -> bool:
        from homekit_client.char_map import CharBucket, classify
        from homekit_client import hap_apply

        if classify(characteristic, 0) == CharBucket.UNKNOWN:
            return False
        hap_apply.apply_characteristic_to_sensor(self, characteristic, value, log=LOGGER)
        return True

    def query(self, cmd=None):
        if self.hk:
            self.hk.refresh_sensor(self)
        self.reportDrivers()

    commands = {'QUERY': query, 'STATUS': query}
