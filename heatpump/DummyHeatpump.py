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
        
