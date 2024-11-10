import time
import os
import logging
import json
import hashlib
import requests

from ThermiaOnlineAPI.model.HeatPump import ThermiaHeatPump
import mqtt_api
from .baseclass import HeatpumpBaseclass
from typing import Optional
from datetime import datetime, timedelta
import sys


from ThermiaOnlineAPI import Thermia


logger = logging.getLogger('__main__')
logger.info(f'[Heatpump] loading module ')


def hash_utf8(x):
    if isinstance(x, str):
        x = x.encode("utf-8")
    return hashlib.md5(x).hexdigest()


def strip_dict(original):
    # return unmodified original if its not a dict
    if not type(original) == dict:
        return original
    stripped_copy = {}
    for key in original.keys():
        if not key.startswith('_'):
            stripped_copy[key] = original[key]
    return stripped_copy

class ThermiaHeatpump(HeatpumpBaseclass):
    heat_pump: ThermiaHeatPump
    mqtt_api: Optional['mqtt_api.MqttApi'] = None

    def __init__(self, user, password) -> None:
        super().__init__()
        self.login_attempts = 0
        self.address = "aa"
        self.capacity = -1
        self.max_grid_charge_rate = 0
        self.max_pv_charge_rate = 0
        self.nonce = 0
        self.user = user
        self.password = password

        thermia = Thermia(user, password)

        print("Connected: " + str(thermia.connected))

        heat_pump = thermia.heat_pumps[0]
        self.heat_pump = heat_pump
        #heat_pump.debug()
        print("current supply line temperature: " + str(heat_pump.supply_line_temperature))

    def __del__(self):
        # nothing so far
        pass

       
   # Start API functions
   # MQTT publishes all internal values.
   #
   # Topic is: base_topic + '/heatpumps/0/'
   #
    def activate_mqtt(self, api_mqtt_api):
        self.mqtt_api = api_mqtt_api
        # /set is appended to the topic
 #       self.mqtt_api.register_set_callback(self._get_mqtt_topic(
 #       ) + 'max_grid_charge_rate', self.api_set_max_grid_charge_rate, int)
 
    def refresh_api_values(self):
        if self.mqtt_api & self.heat_pump:
            self.heat_pump.update_data()
            self.mqtt_api.generic_publish(
                self._get_mqtt_topic() + 'supply_line_temperature', self.heat_pump.supply_line_temperature)
            for attr in vars(self.heat_pump):
                value = getattr(self.heat_pump, attr)
                self.mqtt_api.generic_publish(
                    self._get_mqtt_topic() + attr, value
                )
            
           

 #   def api_set_max_grid_charge_rate(self, max_grid_charge_rate: int):
 #       if max_grid_charge_rate < 0:
 #           logger.warning(
 #               f'[Heatpump] API: Invalid max_grid_charge_rate {max_grid_charge_rate}')
 #           return
 #       logger.info(
 #           f'[Heatpump] API: Setting max_grid_charge_rate: {max_grid_charge_rate}W')
 #       self.max_grid_charge_rate = max_grid_charge_rate

   