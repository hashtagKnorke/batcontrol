import pluggy
import numpy as np
from consumer.hookspecs import ConsumerInterface
from mqtt_api import MqttApi

hookimpl = pluggy.HookimplMarker("consumer")

class LoggingDummy(ConsumerInterface):
    def __init__(self, dict_config: dict):
        self._prefix=dict_config.get("prefix", "default")
        self.log(f"Initializing consumer with config: {dict_config}")

    def log(self, message:str):
        print(f"[{self._prefix}] {message}")

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

@hookimpl
def consumer_get_class(name):
    if name == "MyConsumer":
        return LoggingDummy
    return None

# Register the hook implementation
def register_plugin(pm):
    pm.register(consumer_get_class)
