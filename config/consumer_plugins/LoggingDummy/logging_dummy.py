import pluggy
import numpy as np
from consumer.hookspecs import ConsumerInterface
from mqtt_api import MqttApi
import logging

hookimpl = pluggy.HookimplMarker("consumer")

logger = logging.getLogger('__main__')
logger.info('[LoggingDummy] loading module ')


class LoggingDummy(ConsumerInterface):
    def __init__(self, dict_config: dict):
        # read prefix from configuration - defined as required in the manifest
        self._prefix = dict_config.get("prefix", "default")
        # read enable_stdout from configuration - NOT defined as required in the manifest
        self.enable_stdout=dict_config.get("enable_stdout", False)
        self.log(f"Initializing consumer with config: {dict_config}")

    def log(self, message: str):
        if self.enable_stdout:
            print(f"[{self._prefix}] {message}")
        logger.info(f"[{self._prefix}] {message}")

    def activate_mqtt(self, mqtt_api: MqttApi):
        self.log(f"Activating MQTT")
        # ...implementation...
        pass

    def refresh_api_values(self):
        self.log(f"Refreshing API values")
        # ...implementation...
        pass

    def _get_mqtt_topic(self):
        self.log(f"Getting MQTT topic")
        # ...implementation...
        pass

    def apply_energy_constraints(self, net_consumption: np.ndarray, prices: dict) -> np.ndarray[float]:
        self.log(f"Applying energy constraints with net_consumption: {net_consumption} and prices: {prices}")
        # ...implementation...
        pass

    def shutdown(self):
        self.log(f"Shutting down consumer[{self}]")
        pass
