import inspect
import logging
import datetime

import numpy as np

from ThermiaOnlineAPI.const import CAL_FUNCTION_EVU_MODE
from ThermiaOnlineAPI.model.HeatPump import ThermiaHeatPump
from ThermiaOnlineAPI.model.Schedule import Schedule
import mqtt_api
from .baseclass import HeatpumpBaseclass
from typing import Optional


from ThermiaOnlineAPI import Thermia 
from ThermiaOnlineAPI.utils import utils
from typing import List, Tuple
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


    ## config for the strategy
    # Set the maximum number of hours and the maximum duration for each mode
    # The strategy is to set the heat pump to the most energy saving mode in time slots 
    # with the highest price first, but having a maximum number of hours and a maximum duration for each mode
    # and having a min trigger price for each mode
    ### EVU Block
    min_price_for_evu_block=0.6
    max_evu_block_hours = 14
    max_evu_block_duration = 6
    ### Hot Water Block
    min_price_for_hot_water_block=0.4
    max_hot_water_block_hours = 10
    max_hot_water_block_duration = 4
    ### Reduced Heat
    min_price_for_reduced_heat = 0.3
    max_reduced_heat_hours = 14
    max_reduced_heat_duration = 6
    reduced_heat_temperature = 18
    ### Increased Heat
    max_price_for_increased_heat = 0.2
    min_energy_surplus_for_increased_heat = 500  
    max_increased_heat_hours = 14
    max_increased_heat_duration = 6
    increased_heat_temperature = 22
    max_increased_heat_outdoor_temperature = 15
    ### Hot Water Boost
    min_energy_surplus_for_hot_water_boost = 2500  
    max_hot_water_boost_hours = 1
    

    def __init__(self, config:dict) -> None:
        super().__init__()
        self.user = config['user']
        self.password = config['password']
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
        Notes:
        ------
        This method determines the operating mode of the heat pump for each hour based on the net energy consumption
        and energy prices. The modes are:
            - "W": Hot water boost
            - "H": Heat increased temperature
            - "N": Heat normal
            - "R": Heat reduced temperature
            - "B": Hot water block
            - "E": EVU Block
        The method logs the decision-making process and applies the determined modes over continuous time windows.
        """
        # ensure availability of data
        max_hour = min(len(net_consumption), len(prices))

        assumed_hourly_heatpump_energy_demand = 500 # watthour
        assumed_hotwater_reheat_energy_demand = 1500 # watthour
        assumed_hotwater_boost_energy_demand = 1500 # watthour

        if self.heat_pump is not None:
            modes: list = [
            "H",  # Heat increased temperature
            "N",  # Heat normal
            "R",  # Heat reduced temperature
            "B",  # Hot water block
            "E",  # EVU Block
            "W",  # Hot water boost
            ]
            # set heatpump parameters
            heat_modes = ["N"] * max_hour


            
            # Sort hours by highest prices descending
            sorted_hours_by_price = sorted(range(max_hour), key=lambda h: prices[h], reverse=True)



            ### counters for this evaluation
            remaining_evu_block_hours = max_evu_block_hours
            remaining_hot_water_block_hours = max_hot_water_block_hours
            remaining_reduced_heat_hours = max_reduced_heat_hours
            remaining_increased_heat_hours = max_increased_heat_hours
            remaining_hot_water_boost_hours = max_hot_water_boost_hours

            
            # Iterate over hours sorted by price and set modes based on trigger price and max hours per day limits
            for h in sorted_hours_by_price:
                if net_consumption[h] < -min_energy_surplus_for_hot_water_boost and remaining_hot_water_boost_hours > 0:
                    heat_modes[h] = "W"
                    remaining_hot_water_boost_hours -= 1
                    logger.debug(f'[BatCTRL:HP] Set Hot Water Boost at +{h}h due to high surplus {net_consumption[h]}')
                elif net_consumption[h] < -min_energy_surplus_for_increased_heat or prices[h] <= max_price_for_increased_heat and remaining_increased_heat_hours > 0:    
                    if self.heat_pump.outdoor_temperature < max_increased_heat_outdoor_temperature:
                        heat_modes[h] = "H"
                        remaining_increased_heat_hours -= 1
                        logger.debug(f'[BatCTRL:HP] Set Increased Heat at +{h}h due to high surplus {net_consumption[h]} and low outdoor temperature {self.heat_pump.outdoor_temperature}')
                    else:
                        heat_modes[h] = "N"
                        logger.debug(f'[BatCTRL:HP] Set Normal Heat at +{h}h due to high surplus {net_consumption[h]} and high outdoor temperature {self.heat_pump.outdoor_temperature}')
                if prices[h] >= min_price_for_evu_block and remaining_evu_block_hours > 0:
                    heat_modes[h] = "E"
                    remaining_evu_block_hours -= 1
                    logger.debug(f'[BatCTRL:HP] Set EVU Block at +{h}h due to high price {prices[h]}')
                elif prices[h] >= min_price_for_hot_water_block and remaining_hot_water_block_hours > 0:
                    heat_modes[h] = "B"
                    remaining_hot_water_block_hours -= 1
                    logger.debug(f'[BatCTRL:HP] Set Hot Water Block at +{h}h due to high price {prices[h]}')
                elif prices[h] >= min_price_for_reduced_heat and remaining_reduced_heat_hours > 0:
                    heat_modes[h] = "R"
                    remaining_reduced_heat_hours -= 1
                    logger.debug(f'[BatCTRL:HP] Set Reduced Heat at +{h}h due to high price {prices[h]}')
                else:
                    heat_modes[h] = "N"
                    logger.debug(f'[BatCTRL:HP] Set Normal Heat at +{h}h due to price {prices[h]}')
           
            # Evaluate the duration of each mode and downgrade to lower mode if necessary
            self.adjust_mode_duration(heat_modes, prices,  "E", "B", max_evu_block_duration)
            self.adjust_mode_duration(heat_modes, prices,  "B", "R", max_hot_water_block_duration) 
            self.adjust_mode_duration(heat_modes, prices,  "R", "N", max_reduced_heat_duration)          
            self.adjust_mode_duration(heat_modes, prices,  "H", "N", max_increased_heat_duration)               
                        
            logger.debug(f'[BatCTRL:HP] Adjusted Heatpump Modes: {heat_modes}')

            # Iterate over heat modes and handle windows of equal mode
            start_index = 0
            current_mode = heat_modes[0]

            for i in range(1, max_hour):
                if heat_modes[i] != current_mode:
                    # Handle the range from start_index to i-1
                    self.applyMode(current_mode, start_index, i)
                    start_index = i
                    current_mode = heat_modes[i]

            # Handle the last range
            self.applyMode(current_mode, start_index, max_hour)
        return
    
    def adjust_mode_duration(self, heat_modes, prices, inspected_mode, downgrade_mode, max_mode_duration):
        """
        Adjust the duration of a specific heat mode and downgrade it if it exceeds the maximum allowed duration.

        Parameters:
        -----------
        heat_modes : list
            List of heat modes for each hour.
        prices : dict
            Dictionary of energy prices for each hour.
        inspected_mode : str
            The heat mode to inspect and potentially downgrade.
        downgrade_mode : str
            The heat mode to downgrade to if the inspected mode exceeds the maximum duration.
        max_mode_duration : int
            The maximum allowed duration for the inspected mode.

        Returns:
        --------
        None
        """
        mode_duration = 0
        start_index = -1

        for h in range(len(heat_modes)):
            if heat_modes[h] == inspected_mode:
                if start_index == -1:
                    start_index = h
                mode_duration += 1

                if mode_duration > max_mode_duration:
                    if prices[start_index] <= prices[h]:
                        heat_modes[start_index] = downgrade_mode
                        logger.debug(f'[BatCTRL:HP] Downgrade {inspected_mode} to {downgrade_mode} at +{start_index}h due to duration limit')
                        start_index += 1
                    else:
                        heat_modes[h] = downgrade_mode
                        logger.debug(f'[BatCTRL:HP] Downgrade {inspected_mode} to {downgrade_mode} at +{h}h due to duration limit')
                    mode_duration = 0
                    start_index = -1
            else:
                mode_duration = 0
                start_index = -1


    def applyMode(self, mode, start_index, end_index):
        logger.debug(f'[BatCTRL:HP] Apply Mode {mode} from +{start_index}h to +{end_index}h')   

        hours_until_range_start = datetime.timedelta(hours=start_index)
        range_duration = datetime.timedelta(hours=end_index-start_index+1)  # add one hour to include the druartion of evenan single 1-hour slot

        curr_hour_start = datetime.datetime.now().replace(minute=0, second=0, microsecond=0)
        range_start_time = curr_hour_start+hours_until_range_start
        range_end_time = range_start_time+range_duration
        
        
        start_str = range_start_time.astimezone(self.timezone).strftime("%H:%M")
        end_str = range_end_time.astimezone(self.timezone).strftime("%H:%M")
        if mode == "N":
            logger.debug(f'[BatCTRL:HP] Set Heatpump to NORMAL Heating from {start_str} to {end_str}') 
        elif mode == "R":
            logger.debug(f'[BatCTRL:HP] Set Heatpump to REDUCED Heating from {start_str} to {end_str}') 
        elif mode == "B":
            logger.debug(f'[BatCTRL:HP] Set Heatpump to Hot water BLOCK from {start_str} to {end_str}') 
        elif mode == "E":
            logger.debug(f'[BatCTRL:HP] Set Heatpump to EVU block from {start_str} to {end_str}') 
            self._plan_for_high_price_window(range_start_time, range_end_time)
        else:
            logger.error(f'[BatCTRL:HP] Unknown heatpump mode: {mode}')
            raise ValueError(f'Unknown heatpump mode: {mode}')
        

 #   def api_set_max_grid_charge_rate(self, max_grid_charge_rate: int):
 #       if max_grid_charge_rate < 0:
 #           logger.warning(
 #               f'[Heatpump] API: Invalid max_grid_charge_rate {max_grid_charge_rate}')
 #           return
 #       logger.info(
 #           f'[Heatpump] API: Setting max_grid_charge_rate: {max_grid_charge_rate}W')
 #       self.max_grid_charge_rate = max_grid_charge_rate
