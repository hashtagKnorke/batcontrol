import logging
from baseclass import HeatpumpBaseclass

# Configure the logger
logger = logging.getLogger("__main__")


class SilentHeatpump(HeatpumpBaseclass):
    """
    SilentHeatpump class inherits from HeatpumpBaseclass and is a silent stub that
    does nothing and does not create any logging noise.
    """

    def __init__(self):
        logger.info("[SilentHeatpump] Initializing SilentHeatpump")
        pass

    def activate_mqtt(self):
        pass

    def refresh_api_values(self):
        pass

    def ensure_strategy_for_time_window(self, start_time, end_time):
        pass

    def set_heatpump_parameters(self, net_consumption, prices):
        pass
