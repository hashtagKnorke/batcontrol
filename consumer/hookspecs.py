import pluggy
import numpy as np
from mqtt_api import MqttApi

hookspec = pluggy.HookspecMarker("consumer")

class ConsumerInterface:
    @hookspec
    def consumer_get_class(name: str):
        """Return the consumer class for the given name."""

    @hookspec
    def activate_mqtt(self, mqtt_api: MqttApi):
        """
        Activates the MQTT functionality for the consumer.

        This method should be implemented by subclasses to provide the specific
        MQTT activation logic.

        Args:
            mqtt_api (mqtt_api.MqttApi): An instance of the MqttApi class to handle
                                         MQTT operations.

        Raises:
            Error: If the method is not implemented by the subclass.
        """

    @hookspec
    def refresh_api_values(self):
        """
        Refreshes the API values for the consumer.

        This method should be implemented by subclasses to update the consumer's
        data from the API. If not implemented, it raises a RuntimeError.

        Raises:
            RuntimeError: If the method is not implemented in the subclass.
        """

    @hookspec
    def _get_mqtt_topic(self):
        """
        Generates the MQTT topic for the consumer.

        Returns:
            str: The MQTT topic string for the consumer.
        """

    @hookspec
    def apply_energy_constraints(self, net_consumption: np.ndarray, prices: dict) -> np.ndarray[float]:
        """
        Set the parameters for the consumer based on net energy consumption and energy prices.
        Parameters:
        -----------
        net_consumption : np.ndarray
            An array representing the net energy consumption for each hour.
        prices : dict
            A dictionary where keys are hours and values are the corresponding energy prices.
        Returns:
        --------
        the energy consumption in W for each hour after applying the constraints.
        """

    @hookspec
    def shutdown(self):
        """
        Shuts down the system.

        This method is intended to perform any necessary cleanup and safely shut down the system.
        """
