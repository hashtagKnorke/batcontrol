""" Parent Class for implementing Heatpumps and test drivers"""

class HeatpumpBaseclass(object):
    def activate_mqtt():
        raise RuntimeError("[Heatpump Base Class] Function 'activate_mqtt' not implemented")

    def refresh_api_values():
        raise RuntimeError("[Heatpump Base Class] Function 'refresh_api_values' not implemented")

    # Used to implement the mqtt basic topic.
    # Currently there is only one Heatpump, so the number is hardcoded
    def _get_mqtt_topic(self):
        return 'heatpumps/0/'