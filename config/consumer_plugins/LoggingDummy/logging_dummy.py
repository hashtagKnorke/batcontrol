import pluggy
import numpy as np
from consumer.hookspecs import ConsumerInterface
from mqtt_api import MqttApi
import logging

hookimpl = pluggy.HookimplMarker("consumer")

logger = logging.getLogger('__main__')
logger.info('[LoggingDummy] loading module ')


class LoggingDummy(ConsumerInterface):
    
    def __init__(self):
        pass

    @hookimpl
    def post_init(self, dict_config: dict):
        # read prefix from configuration - defined as required in the manifest
        self._prefix = dict_config.get("prefix", "default")
        # read enable_stdout from configuration - NOT defined as required in the manifest
        self.enable_stdout = dict_config.get("enable_stdout", False)
        self.__log(f"Initializing consumer with config: {dict_config}")

    @hookimpl    
    def activate_mqtt(self, mqtt_api: MqttApi):
        self.__log(f"Activating MQTT")
        # ...implementation...
        pass

    @hookimpl    
    def refresh_api_values(self):
        self.__log(f"Refreshing API values")
        # ...implementation...
        pass

    @hookimpl    
    def _get_mqtt_topic(self):
        self.__log(f"Getting MQTT topic")
        # ...implementation...
        pass

    @hookimpl    
    def apply_energy_constraints(self, net_consumption: np.ndarray, prices: dict) -> np.ndarray[float]:
        self.__log(f"Applying energy constraints with net_consumption: {net_consumption} and prices: {prices}")
        # ...implementation...
        pass

    @hookimpl    
    def shutdown(self):
        self.__log(f"Shutting down consumer[{self}]")
        pass

    @hookimpl    
    def get_name(self) -> str:
        return f"LoggingDummy[{self._prefix}]"

    def __log(self, message: str):
        if self.enable_stdout:
            print(f"[{self._prefix}] {message}")
        logger.info(f"[{self._prefix}] {message}")
 
    def __str__(self): 
        return self.get_name()