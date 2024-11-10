import inspect
import logging

from ThermiaOnlineAPI.model.HeatPump import ThermiaHeatPump
import mqtt_api
from .baseclass import HeatpumpBaseclass
from typing import Optional


from ThermiaOnlineAPI import Thermia


logger = logging.getLogger('__main__')
logger.info(f'[Heatpump] loading module ')


class ThermiaHeatpump(HeatpumpBaseclass):
    heat_pump: ThermiaHeatPump
    mqtt_api: Optional['mqtt_api.MqttApi'] = None

    def __init__(self, user, password) -> None:
        super().__init__()
        self.user = user
        self.password = password

        thermia = Thermia(user, password)

        logger.debug("Connected: " + str(thermia.connected))

        heat_pump = thermia.heat_pumps[0]
        self.heat_pump = heat_pump
        logger.debug("initialized HeatPump" + str(self.heat_pump))
        logger.debug("current supply line temperature: " + str(heat_pump.supply_line_temperature))

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
        logger.info(f'[Heatpump] Activating MQTT')
        logger.debug(f'[Heatpump] MQTT topic: {self._get_mqtt_topic()}')
        logger.debug(f'[Heatpump] MQTT driver: {self.mqtt_api}')
        # /set is appended to the topic
 #       self.mqtt_api.register_set_callback(self._get_mqtt_topic(
 #       ) + 'max_grid_charge_rate', self.api_set_max_grid_charge_rate, int)
 
    def refresh_api_values(self):
        logger.debug(f'[Heatpump] Refreshing API values')
        if self.mqtt_api and self.heat_pump:
            self.heat_pump.update_data()
            self.mqtt_api.generic_publish(
                self._get_mqtt_topic() + 'supply_line_temperature', self.heat_pump.supply_line_temperature)
            for name, value in self._get_all_properties(self.heat_pump):
                logger.debug(f"[Heatpump]   publish {name}: {value}")
                # Ensure the value is a supported type
                if not isinstance(value, (str, bytearray, int, float, type(None))):
                    value = str(value)
                self.mqtt_api.generic_publish(
                    self._get_mqtt_topic() + name, value
                )
        logger.debug(f'[Heatpump] API values refreshed')
            
    def _get_all_properties(self, obj):
        for name, method in inspect.getmembers(obj.__class__, lambda m: isinstance(m, property)):
            yield name, getattr(obj, name)
       

 #   def api_set_max_grid_charge_rate(self, max_grid_charge_rate: int):
 #       if max_grid_charge_rate < 0:
 #           logger.warning(
 #               f'[Heatpump] API: Invalid max_grid_charge_rate {max_grid_charge_rate}')
 #           return
 #       logger.info(
 #           f'[Heatpump] API: Setting max_grid_charge_rate: {max_grid_charge_rate}W')
 #       self.max_grid_charge_rate = max_grid_charge_rate