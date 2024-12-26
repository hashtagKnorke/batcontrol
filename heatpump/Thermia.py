import inspect
import logging
import datetime

import numpy as np

from ThermiaOnlineAPI.const import (
    CAL_FUNCTION_EVU_MODE,
    CAL_FUNCTION_HOT_WATER_BLOCK,
    CAL_FUNCTION_REDUCED_HEATING_EFFECT,
)
from ThermiaOnlineAPI.model.HeatPump import ThermiaHeatPump
from ThermiaOnlineAPI.model.CalendarSchedule import CalendarSchedule
from mqtt_api import MQTT_API
from .baseclass import HeatpumpBaseclass
from typing import Optional, Dict


from ThermiaOnlineAPI import Thermia
from ThermiaOnlineAPI.utils import utils
from typing import List, Tuple
import pytz


class ThermiaHighPriceHandling:
    def __init__(
        self,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        schedule: CalendarSchedule,
    ):
        self.start_time = start_time
        self.end_time = end_time
        self.schedule = schedule

    def __repr__(self):
        return f"HighPriceHandlingStrategy(schedule={self.schedule})"


class ThermiaStrategySlot:
    def __init__(
        self,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        mode: str,
        price: float,
        consumption: float,
    ):
        self.start_time = start_time
        self.end_time = end_time
        self.mode = mode
        self.price = price
        self.consumption = consumption

    def setHandling(self, handler: ThermiaHighPriceHandling):
        self.handler = handler

    def __repr__(self):
        if hasattr(self, "handler"):
            return f"STRATEGY({self.start_time}-{self.end_time}:[{self.mode}]->{self.handler.schedule})"
        else:
            return f"STRATEGY({self.start_time}-{self.end_time}:[{self.mode}])"


logger = logging.getLogger("__main__")
logger.info(f"[Heatpump] loading module ")


class ThermiaHeatpump(HeatpumpBaseclass):
    heat_pump: Optional[ThermiaHeatPump] = None
    mqtt_client: Optional[MQTT_API] = None

    ## store all high price handlers to avoid duplicates and to be able to remove them
    high_price_handlers: dict[datetime.datetime, ThermiaHighPriceHandling] = {}

    ## max time that has already been planned, to avoid double planning
    already_planned_until: datetime

    ## store all strategies to be able to refer to them later
    high_price_strategies: dict[datetime.datetime, ThermiaStrategySlot] = {}

    ## config for the strategy
    # Set the maximum number of hours and the maximum duration for each mode
    # The strategy is to set the heat pump to the most energy saving mode in time slots
    # with the highest price first, but having a maximum number of hours and a maximum duration for each mode
    # and having a min trigger price for each mode
    ### EVU Block
    min_price_for_evu_block = 0.6
    max_evu_block_hours = 14
    max_evu_block_duration = 6
    ### Hot Water Block
    min_price_for_hot_water_block = 0.4
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

    def __init__(self, config: dict, timezone: pytz.timezone) -> None:
        """
        Initialize the ThermiaHeatpump instance.

        Parameters:
        -----------
        config : dict
            Configuration dictionary containing user credentials and other settings.
        timezone : pytz.timezone
            Timezone of the heat pump installation.
        """
        super().__init__()
        self.user = config["user"]
        self.password = config["password"]
        self.ensure_connection()
        self.batcontrol_timezone = timezone
        self.already_planned_until = (
            datetime.datetime.now()
            .astimezone(self.batcontrol_timezone)
            .replace(minute=0, second=0, microsecond=0)
        )

        ## fetch strategy params from config
        ### EVU Block
        self.min_price_for_evu_block = self.fetch_param_from_config(
            config, "min_price_for_evu_block", 0.6
        )
        self.max_evu_block_hours = self.fetch_param_from_config(
            config, "max_evu_block_hours", 14
        )
        self.max_evu_block_duration = self.fetch_param_from_config(
            config, "max_evu_block_duration", 6
        )
        ### Hot Water Block
        self.min_price_for_hot_water_block = self.fetch_param_from_config(
            config, "min_price_for_hot_water_block", 0.4
        )
        self.max_hot_water_block_hours = self.fetch_param_from_config(
            config, "max_hot_water_block_hours", 10
        )
        self.max_hot_water_block_duration = self.fetch_param_from_config(
            config, "max_hot_water_block_duration", 4
        )
        ### Reduced Heat
        self.min_price_for_reduced_heat = self.fetch_param_from_config(
            config, "min_price_for_reduced_heat", 0.3
        )
        self.max_reduced_heat_hours = self.fetch_param_from_config(
            config, "max_reduced_heat_hours", 14
        )
        self.max_reduced_heat_duration = self.fetch_param_from_config(
            config, "max_reduced_heat_duration", 6
        )
        self.reduced_heat_temperature = self.fetch_param_from_config(
            config, "reduced_heat_temperature", 20
        )
        ### Increased Heat
        self.max_price_for_increased_heat = self.fetch_param_from_config(
            config, "max_price_for_increased_heat", 0.2
        )
        self.min_energy_surplus_for_increased_heat = self.fetch_param_from_config(
            config, "min_energy_surplus_for_increased_heat", 1000
        )
        self.max_increased_heat_hours = self.fetch_param_from_config(
            config, "max_increased_heat_hours", 14
        )
        self.max_increased_heat_duration = self.fetch_param_from_config(
            config, "max_increased_heat_duration", 6
        )
        self.increased_heat_temperature = self.fetch_param_from_config(
            config, "increased_heat_temperature", 22
        )
        self.max_increased_heat_outdoor_temperature = self.fetch_param_from_config(
            config, "max_increased_heat_outdoor_temperature", 15
        )
        ### Hot Water Boost
        self.min_energy_surplus_for_hot_water_boost = self.fetch_param_from_config(
            config, "min_energy_surplus_for_hot_water_boost", 2500
        )
        self.max_hot_water_boost_hours = self.fetch_param_from_config(
            config, "max_hot_water_boost_hours", 1
        )

    def fetch_param_from_config(self, config: dict, name: str, default: float) -> float:
        if name in config:
            logger.debug(f"[Heatpump] fetching {name} from config: {config[name]}")
            return config[name]
        else:
            logger.debug(
                f"[Heatpump] using default for config {name}  default: {default}"
            )
            return default

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
                logger.debug(
                    "current supply line temperature: "
                    + str(heat_pump.supply_line_temperature)
                )
            except Exception as e:
                logger.error(f"Failed to connect to Thermia: {e}")
                self.heat_pump = None

    # Start API functions
    # MQTT publishes all internal values.
    #
    # Topic is: base_topic + '/heatpumps/0/'
    #
    def activate_mqtt(self, api_mqtt_api):
        self.mqtt_client = api_mqtt_api
        logger.info(f"[Heatpump] Activating MQTT")
        logger.debug(f"[Heatpump] MQTT topic: {self._get_mqtt_topic()}")
        logger.debug(f"[Heatpump] MQTT driver: {self.mqtt_client}")
        # /set is appended to the topic

    #       self.mqtt_api.register_set_callback(self._get_mqtt_topic(
    #       ) + 'max_grid_charge_rate', self.api_set_max_grid_charge_rate, int)

    def refresh_api_values(self):
        logger.debug(f"[Heatpump] Refreshing API values")
        self.ensure_connection()

        if self.mqtt_client and self.heat_pump:
            try:
                self.heat_pump.update_data()
                self.mqtt_client.generic_publish(
                    self._get_mqtt_topic() + "xx_supply_line_temperature",
                    self.heat_pump.supply_line_temperature,
                )
                for name, value in self._get_all_properties(self.heat_pump):
                    # Ensure the value is a supported type
                    if not isinstance(value, (str, bytearray, int, float, type(None))):
                        value = str(value)
                    self.mqtt_client.generic_publish(
                        self._get_mqtt_topic() + name, value
                    )
                logger.debug(f"[Heatpump] API values refreshed")

                # Publish all config values with config/ prefix
                config_topic_prefix = self._get_mqtt_topic() + "config/"
                self.mqtt_client.generic_publish(
                    config_topic_prefix + "min_price_for_evu_block",
                    self.min_price_for_evu_block,
                )
                self.mqtt_client.generic_publish(
                    config_topic_prefix + "max_evu_block_hours",
                    self.max_evu_block_hours,
                )
                self.mqtt_client.generic_publish(
                    config_topic_prefix + "max_evu_block_duration",
                    self.max_evu_block_duration,
                )
                self.mqtt_client.generic_publish(
                    config_topic_prefix + "min_price_for_hot_water_block",
                    self.min_price_for_hot_water_block,
                )
                self.mqtt_client.generic_publish(
                    config_topic_prefix + "max_hot_water_block_hours",
                    self.max_hot_water_block_hours,
                )
                self.mqtt_client.generic_publish(
                    config_topic_prefix + "max_hot_water_block_duration",
                    self.max_hot_water_block_duration,
                )
                self.mqtt_client.generic_publish(
                    config_topic_prefix + "min_price_for_reduced_heat",
                    self.min_price_for_reduced_heat,
                )
                self.mqtt_client.generic_publish(
                    config_topic_prefix + "max_reduced_heat_hours",
                    self.max_reduced_heat_hours,
                )
                self.mqtt_client.generic_publish(
                    config_topic_prefix + "reduced_heat_temperature",
                    self.reduced_heat_temperature,
                )
                self.mqtt_client.generic_publish(
                    config_topic_prefix + "max_price_for_increased_heat",
                    self.max_price_for_increased_heat,
                )
                self.mqtt_client.generic_publish(
                    config_topic_prefix + "min_energy_surplus_for_increased_heat",
                    self.min_energy_surplus_for_increased_heat,
                )
                self.mqtt_client.generic_publish(
                    config_topic_prefix + "max_increased_heat_hours",
                    self.max_increased_heat_hours,
                )
                self.mqtt_client.generic_publish(
                    config_topic_prefix + "max_increased_heat_duration",
                    self.max_increased_heat_duration,
                )
                self.mqtt_client.generic_publish(
                    config_topic_prefix + "increased_heat_temperature",
                    self.increased_heat_temperature,
                )
                self.mqtt_client.generic_publish(
                    config_topic_prefix + "max_increased_heat_outdoor_temperature",
                    self.max_increased_heat_outdoor_temperature,
                )
                self.mqtt_client.generic_publish(
                    config_topic_prefix + "min_energy_surplus_for_hot_water_boost",
                    self.min_energy_surplus_for_hot_water_boost,
                )
                self.mqtt_client.generic_publish(
                    config_topic_prefix + "max_hot_water_boost_hours",
                    self.max_hot_water_boost_hours,
                )

                logger.debug(f"[Heatpump] config values published to MQTT  ...")

                # Publish all strategy values with strategy/ prefix
                strategy_topic_prefix = self._get_mqtt_topic() + "strategy/"

                # Delete all existing high price handlers
                self.delete_all_mqtt_topics(
                    self._get_mqtt_topic() + "handler/high_price_handlers/"
                )

                for start_time, handler in self.high_price_handlers.items():
                    self.mqtt_client.generic_publish(
                        self._get_mqtt_topic()
                        + "handler/high_price_handlers/"
                        + start_time.strftime("%Y-%m-%d_%H:%M"),
                        handler.schedule.functionId,
                    )

                # Delete all existing high price strategies
                self.delete_all_mqtt_topics(
                    self._get_mqtt_topic() + "strategy/high_price_strategies/"
                )

                for start_time, strategy in self.high_price_strategies.items():
                    high_price_strategy_topic = (
                        self._get_mqtt_topic()
                        + "strategy/high_price_strategies/"
                        + start_time.strftime("%Y-%m-%d_%H:%M")
                    )
                    self.mqtt_client.generic_publish(
                        high_price_strategy_topic, strategy.mode
                    )
                    self.mqtt_client.generic_publish(
                        high_price_strategy_topic + "/price", strategy.price
                    )
                    self.mqtt_client.generic_publish(
                        high_price_strategy_topic + "/consumption", strategy.consumption
                    )
                    self.mqtt_client.generic_publish(
                        high_price_strategy_topic + "/mode", strategy.mode
                    )
                    self.mqtt_client.generic_publish(
                        high_price_strategy_topic + "/start_time",
                        strategy.start_time.strftime("%Y-%m-%d %H:%M"),
                    )
                    self.mqtt_client.generic_publish(
                        high_price_strategy_topic + "/start_time_stamp",
                        strategy.start_time.timestamp(),
                    )
                    self.mqtt_client.generic_publish(
                        high_price_strategy_topic + "/end_time",
                        strategy.end_time.strftime("%Y-%m-%d %H:%M"),
                    )
                    if hasattr(strategy, "handler"):
                        self.mqtt_client.generic_publish(
                            high_price_strategy_topic + "/handler",
                            strategy.handler.schedule.functionId,
                        )

                logger.debug(
                    f"[Heatpump] strategy values ({len(self.high_price_handlers)} handlers, {len(self.high_price_strategies)} strategies) published to MQTT"
                )

            except Exception as e:
                logger.error(f"[Heatpump] Failed to refresh API values: {e}")

    def delete_all_mqtt_topics(self, topic_prefix: str):
        """
        Delete all MQTT topics with the given prefix by publishing an empty retained message.

        :param topic_prefix: The prefix of the topics to delete
        """
        # Assuming self.mqtt_api has a method to list all topics with a given prefix
        # topics_to_delete = self.mqtt_api.list_topics_with_prefix(topic_prefix)
        # for topic in topics_to_delete:
        #    self.mqtt_api.generic_publish(topic, '', retain=True)

    def _get_all_properties(self, obj):
        for name, method in inspect.getmembers(
            obj.__class__, lambda m: isinstance(m, property)
        ):
            yield name, getattr(obj, name)

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

        duration = datetime.timedelta(
            hours=max_hour
        )  # add one hour to include the druartion of evenan single 1-hour slot

        curr_hour_start = (
            datetime.datetime.now()
            .astimezone(self.batcontrol_timezone)
            .replace(minute=0, second=0, microsecond=0)
        )

        max_timestamp = curr_hour_start + duration
        if self.heat_pump is not None and max_timestamp > self.already_planned_until:
            logger.debug(f"[BatCTRL:HP] Planning until {max_timestamp}")

            ## TODO: either full replan with purge of all strategies or just add new strategies and limit evaluation to new hours

            assumed_hourly_heatpump_energy_demand = 500  # watthour
            assumed_hotwater_reheat_energy_demand = 1500  # watthour
            assumed_hotwater_boost_energy_demand = 1500  # watthour

            heat_modes = ["N"] * max_hour

            # Sort hours by highest prices descending
            sorted_hours_by_price = sorted(
                range(max_hour), key=lambda h: prices[h], reverse=True
            )

            ### counters for this evaluation
            remaining_evu_block_hours = self.max_evu_block_hours
            remaining_hot_water_block_hours = self.max_hot_water_block_hours
            remaining_reduced_heat_hours = self.max_reduced_heat_hours
            remaining_increased_heat_hours = self.max_increased_heat_hours
            remaining_hot_water_boost_hours = self.max_hot_water_boost_hours

            # Iterate over hours sorted by price and set modes based on trigger price and max hours per day limits
            for h in sorted_hours_by_price:
                if (
                    net_consumption[h] < -self.min_energy_surplus_for_hot_water_boost
                    and remaining_hot_water_boost_hours > 0
                ):
                    heat_modes[h] = "W"
                    remaining_hot_water_boost_hours -= 1
                    logger.debug(
                        f"[BatCTRL:HP] Set Hot Water Boost at +{h}h due to high surplus {net_consumption[h]}"
                    )
                elif (
                    net_consumption[h] < -self.min_energy_surplus_for_increased_heat
                    or prices[h] <= self.max_price_for_increased_heat
                    and remaining_increased_heat_hours > 0
                ):
                    if (
                        self.heat_pump.outdoor_temperature
                        < self.max_increased_heat_outdoor_temperature
                    ):
                        heat_modes[h] = "H"
                        remaining_increased_heat_hours -= 1
                        if prices[h] <= self.max_price_for_increased_heat:
                            logger.debug(
                                f"[BatCTRL:HP] Set Increased Heat at +{h}h due to low price {prices[h]} and low outdoor temperature {self.heat_pump.outdoor_temperature}"
                            )
                        else:
                            logger.debug(
                                f"[BatCTRL:HP] Set Increased Heat at +{h}h due to high surplus {net_consumption[h]} and low outdoor temperature {self.heat_pump.outdoor_temperature}"
                            )
                    else:
                        heat_modes[h] = "N"
                        logger.debug(
                            f"[BatCTRL:HP] Set Normal Heat at +{h}h due to high surplus {net_consumption[h]} and high outdoor temperature {self.heat_pump.outdoor_temperature}"
                        )
                elif (
                    prices[h] >= self.min_price_for_evu_block
                    and remaining_evu_block_hours > 0
                ):
                    heat_modes[h] = "E"
                    remaining_evu_block_hours -= 1
                    logger.debug(
                        f"[BatCTRL:HP] Set EVU Block at +{h}h due to high price {prices[h]}"
                    )
                elif (
                    prices[h] >= self.min_price_for_hot_water_block
                    and remaining_hot_water_block_hours > 0
                ):
                    heat_modes[h] = "B"
                    remaining_hot_water_block_hours -= 1
                    logger.debug(
                        f"[BatCTRL:HP] Set Hot Water Block at +{h}h due to high price {prices[h]}"
                    )
                elif (
                    prices[h] >= self.min_price_for_reduced_heat
                    and remaining_reduced_heat_hours > 0
                ):
                    heat_modes[h] = "R"
                    remaining_reduced_heat_hours -= 1
                    logger.debug(
                        f"[BatCTRL:HP] Set Reduced Heat at +{h}h due to high price {prices[h]}"
                    )
                else:
                    heat_modes[h] = "N"
                    logger.debug(
                        f"[BatCTRL:HP] Set Normal Heat at +{h}h due to price {prices[h]}"
                    )

            # Evaluate the duration of each mode and downgrade to lower mode if necessary
            self.adjust_mode_duration(
                heat_modes, prices, "E", "B", self.max_evu_block_duration
            )
            self.adjust_mode_duration(
                heat_modes, prices, "B", "R", self.max_hot_water_block_duration
            )
            self.adjust_mode_duration(
                heat_modes, prices, "R", "N", self.max_reduced_heat_duration
            )
            self.adjust_mode_duration(
                heat_modes, prices, "H", "N", self.max_increased_heat_duration
            )

            logger.debug(f"[BatCTRL:HP] Adjusted Heatpump Modes: {heat_modes}")

            # Iterate over heat modes and handle windows of equal mode
            start_index = 0
            current_mode = heat_modes[0]

            # -------- here we start to convert indices into timestamps

            for i in range(1, max_hour):
                if heat_modes[i] != current_mode:
                    # Handle the range from start_index to i-1
                    self.applyMode(current_mode, start_index, i - 1)
                    start_index = i
                    current_mode = heat_modes[i]
            # Handle the last range
            self.applyMode(current_mode, start_index, max_hour)

            for i in range(max_hour):
                hours_until_range_start = datetime.timedelta(hours=i)
                range_duration = datetime.timedelta(
                    hours=1
                )  # add one hour to include the duration of evenan single 1-hour slot

                curr_hour_start = (
                    datetime.datetime.now()
                    .astimezone(self.batcontrol_timezone)
                    .replace(minute=0, second=0, microsecond=0)
                )
                start_time = curr_hour_start + hours_until_range_start
                end_time = start_time + range_duration

                self.high_price_strategies[start_time] = ThermiaStrategySlot(
                    start_time, end_time, heat_modes[i], prices[i], net_consumption[i]
                )

            self.cleanupHighPriceStrategies()

            self.already_planned_until = max_timestamp

        else:
            logger.debug(
                f"[BatCTRL:HP] No replanning necessary, already planned until {self.already_planned_until}"
            )
        return

    def adjust_mode_duration(
        self, heat_modes, prices, inspected_mode, downgrade_mode, max_mode_duration
    ):
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
                        logger.debug(
                            f"[BatCTRL:HP] Downgrade {inspected_mode} to {downgrade_mode} at +{start_index}h due to duration limit"
                        )
                        start_index += 1
                    else:
                        heat_modes[h] = downgrade_mode
                        logger.debug(
                            f"[BatCTRL:HP] Downgrade {inspected_mode} to {downgrade_mode} at +{h}h due to duration limit"
                        )
                    mode_duration = 0
                    start_index = -1
            else:
                mode_duration = 0
                start_index = -1

    def applyMode(self, mode, start_index, end_index):
        logger.debug(
            f"[BatCTRL:HP] Apply Mode {mode} from +{start_index}h to +{end_index}h"
        )

        hours_until_range_start = datetime.timedelta(hours=start_index)
        range_duration = datetime.timedelta(
            hours=end_index - start_index + 1
        )  # add one hour to include the druartion of evenan single 1-hour slot

        curr_hour_start = (
            datetime.datetime.now()
            .astimezone(self.batcontrol_timezone)
            .replace(minute=0, second=0, microsecond=0)
        )
        range_start_time = curr_hour_start + hours_until_range_start
        range_end_time = range_start_time + range_duration

        self.ensure_strategy_for_time_window(range_start_time, range_end_time, mode)

    def ensure_strategy_for_time_window(
        self, start_time: datetime, end_time: datetime, mode: str
    ):
        """
        check whether strategy for certain
        time window is already present or install if it is missing

        Args:
            start_time (datetime): The start time of the high price window.
            end_time (datetime): The end time of the high price window.
            mode (str): The mode of operation for the heat pump during the high price window.
        Raises:
            Error: If the method is not implemented by the subclass.
        """
        ## round to full hour
        start_time = start_time.replace(minute=0, second=0, microsecond=0)
        end_time = end_time.replace(minute=0, second=0, microsecond=0)

        # Adjust start and end times for time zone of heatpump
        tz_name = self.heat_pump.installation_timezone
        start_time = utils.adjust_times_for_timezone(start_time, tz_name)
        end_time = utils.adjust_times_for_timezone(end_time, tz_name)

        duration = end_time - start_time
        logger.info(
            f"[ThermiaHeatpump] Planning Strategy [{mode}] starting at {start_time}, duration: {duration}"
        )

        # Check if a strategy already exists for the given start time
        if start_time in self.high_price_handlers:
            existing_strategy = self.high_price_handlers[start_time]
            logger.info(
                f"[ThermiaHeatpump] price handler already exists for start time {start_time}: {existing_strategy}"
            )
            return

        schedule = self.install_schedule_in_heatpump(start_time, end_time, mode)
        if schedule:
            high_price_strategy = ThermiaHighPriceHandling(
                start_time, end_time, schedule
            )
            logger.info(
                f"[ThermiaHeatpump] Created high price handler: {high_price_strategy}"
            )
            self.high_price_handlers[start_time] = high_price_strategy
        self.cleanupHighPriceHandlers()

    def install_schedule_in_heatpump(
        self, start_time: datetime, end_time: datetime, mode: str
    ):
        """
        Installs a schedule in the heat pump based on the provided start time, end time, and mode.

        Args:
            start_time (datetime): The start time for the schedule.
            end_time (datetime): The end time for the schedule.
            mode (str): The mode for the schedule. Can be one of the following:
                - "E": EVU mode
                - "B": Hot water block
                - "R": Reduced heating effect
                - "H": Increased heating effect

        Returns:
            CalendarSchedule: The newly created schedule.

        Raises:
            ValueError: If an unknown mode is provided.
        """

        start_str = start_time.astimezone(self.batcontrol_timezone).strftime("%H:%M")
        end_str = end_time.astimezone(self.batcontrol_timezone).strftime("%H:%M")

        if mode == "E":
            planned_schedule = CalendarSchedule(
                start=start_time, end=end_time, functionId=CAL_FUNCTION_EVU_MODE
            )
            schedule = self.heat_pump.add_new_schedule(planned_schedule)
            logger.debug(
                f"[BatCTRL:HP] Set Heatpump to EVU block from {start_str} to {end_str}"
            )
            return schedule
        elif mode == "B":
            planned_schedule = CalendarSchedule(
                start=start_time, end=end_time, functionId=CAL_FUNCTION_HOT_WATER_BLOCK
            )
            schedule = self.heat_pump.add_new_schedule(planned_schedule)
            logger.debug(
                f"[BatCTRL:HP] Set Heatpump to Hot water BLOCK from {start_str} to {end_str}"
            )
            return schedule
        elif mode == "R":
            planned_schedule = CalendarSchedule(
                start=start_time,
                end=end_time,
                functionId=CAL_FUNCTION_REDUCED_HEATING_EFFECT,
                value=self.reduced_heat_temperature,
            )
            schedule = self.heat_pump.add_new_schedule(planned_schedule)
            logger.debug(
                f"[BatCTRL:HP] Set Heatpump to REDUCED Heating ({self.reduced_heat_temperature}) from {start_str} to {end_str}"
            )
            return schedule
        elif mode == "H":
            planned_schedule = CalendarSchedule(
                start=start_time,
                end=end_time,
                functionId=CAL_FUNCTION_REDUCED_HEATING_EFFECT,
                value=self.increased_heat_temperature,
            )
            schedule = self.heat_pump.add_new_schedule(planned_schedule)
            logger.debug(
                f"[BatCTRL:HP] Set Heatpump to INCREASED Heating ({self.increased_heat_temperature}) from {start_str} to {end_str}"
            )
            return schedule
        elif mode == "W":
            logger.debug(
                f"[BatCTRL:HP] TODO No impl for  Heatpump to Hot Water BOOST from {start_str} to {end_str}"
            )
            return
        elif mode == "N":
            logger.debug(
                f"[BatCTRL:HP] No change in Heatpump mode from {start_str} to {end_str}"
            )
            return
        else:
            logger.error(f"[ThermiaHeatpump] Unknown mode: {mode}")
            raise ValueError(f"Unknown mode: {mode}")

    def cleanupHighPriceStrategies(self):
        """
        Remove all high price strategies that are no longer valid.
        """
        logger.debug(
            f"[ThermiaHeatpump] Cleaning up high price strategies, currently {len(self.high_price_strategies)} strategies"
        )
        now = datetime.datetime.now(
            self.batcontrol_timezone
        )  # Make 'now' an aware datetime object in the heat pump's timezone
        now = utils.adjust_times_for_timezone(now, self.heat_pump.installation_timezone)

        strategies_to_remove = []

        for start_time, strategy in self.high_price_strategies.items():
            if start_time.timestamp() < now.timestamp():
                logger.debug(
                    f"[ThermiaHeatpump] Removing high price strategy for {start_time}, because it before now: {now})"
                )
                strategies_to_remove.append(start_time)

        for start_time in strategies_to_remove:
            del self.high_price_strategies[start_time]
            logger.debug(
                f"[ThermiaHeatpump] Removed high price strategy for {start_time}"
            )
            ## todo delete from mqtt

        logger.debug(
            f"[ThermiaHeatpump] Cleanup complete. Remaining strategies: {len(self.high_price_strategies)}"
        )

    def cleanupHighPriceHandlers(self):
        """
        Remove all high price handlers that are no longer valid.
        """
        logger.debug(
            f"[ThermiaHeatpump] Cleaning up high price handlers, currently {len(self.high_price_handlers)} handlers"
        )
        now = datetime.datetime.now(
            self.batcontrol_timezone
        )  # Make 'now' an aware datetime object in the heat pump's timezone
        now = utils.adjust_times_for_timezone(now, self.heat_pump.installation_timezone)
        handlers_to_remove = []

        for start_time, handler in self.high_price_handlers.items():
            end_time = handler.end_time
            if end_time.timestamp() < now.timestamp():
                logger.debug(
                    f"[ThermiaHeatpump] Removing high price handler for {start_time}-{end_time} , because it ends before now: {now})"
                )
                handlers_to_remove.append(start_time)

        for start_time in handlers_to_remove:
            del self.high_price_handlers[start_time]
            logger.debug(
                f"[ThermiaHeatpump] Removed high price handler for {start_time}"
            )
            #### todo delete from mqtt

        logger.debug(
            f"[ThermiaHeatpump] Cleanup complete. Remaining handlers: {len(self.high_price_handlers)}"
        )

    def __del__(self):
        """
        Destructor to clean up high price handlers and delete corresponding schedules in the Thermia API.
        """
        if self.heat_pump:
            for start_time, handler in self.high_price_handlers.items():
                try:
                    self.heat_pump.delete_schedule(handler.schedule)
                    logger.info(
                        f"[ThermiaHeatpump Destructor] Deleted schedule for high price handler starting at {start_time}"
                    )
                except Exception as e:
                    logger.error(
                        f"[ThermiaHeatpump Destructor] Failed to delete schedule for high price handler starting at {start_time}: {e}"
                    )
