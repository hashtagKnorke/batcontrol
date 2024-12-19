class Heatpump(object): 
    """
    Heatpump class factory that returns an instance of a specific heat pump type based on the provided configuration.

    Args:
        config (dict): Configuration dictionary containing the type of heat pump and necessary credentials.

    Returns:
        ThermiaHeatpump: If the type specified in the config is 'thermia'.
        DummyHeatpump: If the type specified in the config is 'dummy'.
        SilentHeatpump: If the type specified in the config is neither 'thermia' nor 'dummy'.

    Raises:
        KeyError: If the 'type' key is not present in the config dictionary.
    """
    def __new__(cls, config:dict):
        if config is None:
            return cls.default()
        elif 'type' not in config:
            return cls.default()
        else:
            if config['type'].lower() == 'thermia':
                from .Thermia import ThermiaHeatpump
                return ThermiaHeatpump(config['user'], config['password'])
            elif config['type'].lower() == 'dummy':
                from .DummyHeatpump import DummyHeatpump
                return DummyHeatpump()
            else: 
                return cls.default()
        
    @staticmethod
    def default():
        from .SilentHeatpump import SilentHeatpump
        return SilentHeatpump()    
 