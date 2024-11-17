import inspect
import logging

from ThermiaOnlineAPI.const import CAL_FUNCTION_EVU_MODE
from ThermiaOnlineAPI.model.HeatPump import ThermiaHeatPump
from ThermiaOnlineAPI.model.Schedule import Schedule
import mqtt_api
from .baseclass import HeatpumpBaseclass
from typing import Optional


from ThermiaOnlineAPI import Thermia 
from ThermiaOnlineAPI.utils import utils
from typing import List, Tuple
from datetime import datetime
import pytz

class HighPriceHandlingStrategy:
            def __init__(self, start_time: datetime, end_time: datetime, schedule: Schedule):
                self.start_time = start_time
                self.end_time = end_time
                self.schedule = schedule

            def __repr__(self):
                return f"HighPriceHandlingStrategy(schedule={self.schedule})"


logger = logging.getLogger('__main__')
logger.info(f'[Heatpump] loading module ')


class ThermiaHeatpump(HeatpumpBaseclass):
    heat_pump: ThermiaHeatPump = None
    mqtt_api: Optional['mqtt_api.MqttApi'] = None
    high_price_strategies: dict[datetime, HighPriceHandlingStrategy] = {}


    def __init__(self, user, password) -> None:
        super().__init__()
        self.user = user
        self.password = password

        self.ensure_connection()

    def ensure_connection(self):
        if not self.heat_pump:
            try:
                thermia = Thermia(self.user, self.password)
                logger.debug("Connected: " + str(thermia.connected))

                if not thermia.heat_pumps:
                    raise Exception("No heat pumps found in account")
                heat_pump = thermia.heat_pumps[0]
                self.heat_pump = heat_pump
                logger.debug("initialized HeatPump" + str(self.heat_pump))
                logger.debug("current supply line temperature: " + str(heat_pump.supply_line_temperature))
            except Exception as e:
                logger.error(f"Failed to connect to Thermia: {e}")
                self.heat_pump = None

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
        self.ensure_connection()
        
        if self.mqtt_api and self.heat_pump:
            try:
                self.heat_pump.update_data()
                self.mqtt_api.generic_publish(
                    self._get_mqtt_topic() + 'xx_supply_line_temperature', self.heat_pump.supply_line_temperature)
                for name, value in self._get_all_properties(self.heat_pump):
                    logger.debug(f"[Heatpump]   publish {name}: {value}")
                    # Ensure the value is a supported type
                    if not isinstance(value, (str, bytearray, int, float, type(None))):
                        value = str(value)
                    self.mqtt_api.generic_publish(
                        self._get_mqtt_topic() + name, value
                    )
                logger.debug(f'[Heatpump] API values refreshed')
            except Exception as e:
                logger.error(f"Failed to refresh API values: {e}")
        
            
    def _get_all_properties(self, obj):
        for name, method in inspect.getmembers(obj.__class__, lambda m: isinstance(m, property)):
            yield name, getattr(obj, name)
       
    def _plan_for_high_price_window(self, start_time: datetime, end_time: datetime):
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
        ## round to full minutes
        start_time = start_time.replace(second=0, microsecond=0)
        end_time = end_time.replace(second=0, microsecond=0)

        # Adjust start and end times for time zone of heatpump 
        tz_name = self.heat_pump.installation_timezone
        start_time = utils.adjust_times_for_timezone(start_time,tz_name)
        end_time = utils.adjust_times_for_timezone(end_time,tz_name)
        
        duration = end_time - start_time
        logger.info(f'[ThermiaHeatpump] Planning for high price window starting at {start_time}, duration: {duration}')
        
        # Check if a strategy already exists for the given start time
        if start_time in self.high_price_strategies:
            existing_strategy = self.high_price_strategies[start_time]
            logger.info(f'[ThermiaHeatpump] High price handling strategy already exists for start time {start_time}: {existing_strategy}')
            return
        

         
        planned_schedule = Schedule(start=start_time, end=end_time, functionId=CAL_FUNCTION_EVU_MODE)
        schedule = self.heat_pump.add_new_schedule(planned_schedule)
        high_price_strategy = HighPriceHandlingStrategy(start_time, end_time, schedule)
        logger.info(f'[ThermiaHeatpump] Created high price handling strategy: {high_price_strategy}')

        self.high_price_strategies[start_time] = high_price_strategy
        logger.info(f'[ThermiaHeatpump] Stored high price handling strategy for start time {start_time}')

 #   def api_set_max_grid_charge_rate(self, max_grid_charge_rate: int):
 #       if max_grid_charge_rate < 0:
 #           logger.warning(
 #               f'[Heatpump] API: Invalid max_grid_charge_rate {max_grid_charge_rate}')
 #           return
 #       logger.info(
 #           f'[Heatpump] API: Setting max_grid_charge_rate: {max_grid_charge_rate}W')
 #       self.max_grid_charge_rate = max_grid_charge_rate
