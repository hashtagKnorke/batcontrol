import logging
from baseclass import HeatpumpBaseclass

# Configure the logger
logger = logging.getLogger('__main__')

class DummyHeatpump(HeatpumpBaseclass):
    def __init__(self):
        pass
     
    def activate_mqtt(self):
        logger.info("[DummyHeatpump] Activating MQTT")
        logger.debug(f"[DummyHeatpump] MQTT topic: {self._get_mqtt_topic()}")
        
    def refresh_api_values(self):
        logger.info("[DummyHeatpump] Refreshing API values")

    def _plan_for_high_price_window(self, start_time, end_time):
        logger.info(f"[DummyHeatpump] Planning for high price window from {start_time} to {end_time}")

    def set_heatpump_parameters(self, net_consumption, prices):
        logger.info(f"[DummyHeatpump] Setting heat pump parameters with net consumption {net_consumption} and prices {prices}")        
