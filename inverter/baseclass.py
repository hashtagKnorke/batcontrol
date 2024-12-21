""" Parent Class for implementing inverters and test drivers"""

class InverterBaseclass(object):
    def set_mode_force_charge():
        raise RuntimeError("[Inverter Base Class] Function 'set_mode_force_charge' not implemented")

    def set_mode_allow_discharge():
        raise RuntimeError("[Inverter Base Class] Function 'set_mode_allow_discharge' not implemented")

    def set_mode_avoid_discharge():
        raise RuntimeError("[Inverter Base Class] Function 'set_mode_avoid_discharge' not implemented")

    def get_designed_capacity():
        """ Returns the designed maximum capacity of the battery in kWh,
            which does not include MIN_SOC , MAX_SOC or other restrictions.
        """
        return self.get_capacity()

    def get_capacity():
        """ Returns the designed maximum capacity of the battery in kWh,
            which does not include MIN_SOC , MAX_SOC or other restrictions.
        """
        raise RuntimeError("[Inverter Base Class] Function 'get_free_capacity' not implemented")

    def get_stored_energy(self):
        """ Returns the stored energy in the battery in kWh """
        current_soc = self.get_SOC()
        capa = self.get_capacity()
        energy = current_soc/100*capa
        if energy < 0:
            return 0
        return energy

    def get_stored_usable_energy(self):
        """ Returns the stored energy in the battery in kWh which can be used .
            It reduces the amount by the minimum SOC.
        """
        current_soc = self.get_SOC()
        capa = self.get_capacity()
        energy = (current_soc-self.min_soc)/100*capa
        if energy < 0:
            return 0
        return energy

    def get_free_capacity():
        raise RuntimeError("[Inverter Base Class] Function 'get_free_capacity' not implemented")

    def get_max_capacity():
        raise RuntimeError("[Inverter Base Class] Function 'get_max_soc' not implemented")

    def get_SOC():
        raise RuntimeError("[Inverter Base Class] Function 'get_SOC' not implemented")

    def activate_mqtt():
        raise RuntimeError("[Inverter Base Class] Function 'activate_mqtt' not implemented")

    def refresh_api_values():
        raise RuntimeError("[Inverter Base Class] Function 'refresh_api_values' not implemented")

    # Used to implement the mqtt basic topic.
    # Currently there is only one inverter, so the number is hardcoded
    def _get_mqtt_topic(self):
        return 'inverters/0/'

    def shutdown():
        pass
