# This file contains the base class for the heatpump implementation. 
# The base class is used to define the interface for the heatpump implementation. 
from datetime import datetime
import mqtt_api
import numpy as np

""" Parent Class for implementing Heatpumps and test drivers"""

class HeatpumpBaseclass(object):
    def activate_mqtt(self, mqtt_api: mqtt_api):
        """
        Activates the MQTT functionality for the heat pump.

        This method should be implemented by subclasses to provide the specific
        MQTT activation logic.

        Args:
            mqtt_api (mqtt_api.MqttApi): An instance of the MqttApi class to handle
                                         MQTT operations.

        Raises:
            Error: If the method is not implemented by the subclass.
        """
        raise RuntimeError("[Heatpump Base Class] Function 'activate_mqtt' not implemented")

    def refresh_api_values(self):
        """
        Refreshes the API values for the heat pump.

        This method should be implemented by subclasses to update the heat pump's
        data from the API. If not implemented, it raises a RuntimeError.

        Raises:
            RuntimeError: If the method is not implemented in the subclass.
        """
        raise RuntimeError("[Heatpump Base Class] Function 'refresh_api_values' not implemented")

    # Used to implement the mqtt basic topic.
    # Currently there is only one Heatpump, so the number is hardcoded
    def _get_mqtt_topic(self):
        """
        Generates the MQTT topic for the heat pump.

        Returns:
            str: The MQTT topic string for the heat pump.
        """
        return 'heatpumps/0/'
    
    def ensure_strategy_for_time_window(self, start_time: datetime, end_time: datetime):
        """
        Plan for high price window.

        This method should be implemented by subclasses to provide the specific
        logic for planning for high price window.

        Args:
            start_time (datetime): The start time of the high price window.
            end_time (datetime): The end time of the high price window.
        Raises:
            Error: If the method is not implemented by the subclass.
        """
        raise RuntimeError("[Heatpump Base Class] Function '_plan_for_high_price_window' not implemented")
    
    def set_heatpump_parameters(self, net_consumption: np.ndarray, prices: dict):
        """
        Set the parameters for the heat pump based on net energy consumption and energy prices.
        Parameters:
        -----------
        net_consumption : np.ndarray
            An array representing the net energy consumption for each hour.
        prices : dict
            A dictionary where keys are hours and values are the corresponding energy prices.
        Returns:
        --------
        None
        """
        raise RuntimeError("[Heatpump Base Class] Function 'set_heatpump_parameters' not implemented")
