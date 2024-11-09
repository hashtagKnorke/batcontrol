class Heatpump(object):
    def __new__(cls, config:dict):
        # renaming of parameters max_charge_rate -> max_grid_charge_rate
        

        if config['type'].lower() == 'thermia':
            from .Thermia import ThermiaHeatpump
            return ThermiaHeatpump(config['user'], config['password'])
 #       elif config['type'].lower() == 'testdriver':
 #           from .testdriver import Testdriver
 #           return Testdriver(config['max_grid_charge_rate'])
        else:
            raise RuntimeError(f'[Heatpump] Unkown Heatpump type {config["type"]}')
