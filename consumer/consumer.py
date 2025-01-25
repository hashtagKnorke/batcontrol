""" Factory for consumer providers """

import pluggy
from .hookspecs import ConsumerInterface
import importlib.util
import os
import yaml
from typing import List

class Consumer:
    """ Factory and registry for consumer providers """
    # Instances of the consumer classes are created here
    num_consumers = 0
    _pm = pluggy.PluginManager("consumer")
    _pm.add_hookspecs(ConsumerInterface)
    _consumers: List[ConsumerInterface] = []

    @staticmethod
    def create_consumer(config: dict) -> ConsumerInterface:
        """ Select and configure a consumer based on the given configuration """
        
        consumer_name = config.get("name")
        plugin = config.get("plugin")
        consumer_class = Consumer._pm.get_plugin(name=plugin)
        if not consumer_class:
            raise ValueError(f"No consumer plugin found with name: {plugin}")
        
        consumer = consumer_class(config.get("config"))
        consumer.consumer_num = Consumer.num_consumers
        Consumer.num_consumers += 1
        return consumer
    
    @staticmethod
    def discover_consumers(plugin_base_dir: str):
        """ Discover the available consumer classes """
        Consumer._pm.load_setuptools_entrypoints("consumer")
        
        # Manually iterate over all subdirectories of plugin_base_dir
        for root, _, files in os.walk(plugin_base_dir):
            if "manifest.yaml" in files:
                manifest_path = os.path.join(root, "manifest.yaml")
                with open(manifest_path, "r") as manifest_file:
                    manifest = yaml.safe_load(manifest_file)
                    implementation_class = manifest.get("implementation_class")
                    if implementation_class:
                        module_name, class_name = implementation_class.rsplit(".", 1)
                        module_path = os.path.join(root, f"{module_name}.py")
                        spec = importlib.util.spec_from_file_location(module_name, module_path)
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        Consumer._pm.register(getattr(module, class_name))
                        if hasattr(module, 'register_plugin'):
                            module.register_plugin(Consumer._pm)
                        
        Consumer._pm.check_pending()

    @staticmethod
    def load_consumers_config(config_path: str):
        """ Load consumers from the YAML configuration file """
        with open(config_path, "r") as config_file:
            config = yaml.safe_load(config_file)
            for consumer_config in config.get("consumers", []):
                consumer = Consumer.create_consumer(consumer_config)
                Consumer._consumers.append(consumer)

    @staticmethod
    def get_consumers() -> List[ConsumerInterface]:
        """ Get the list of consumer instances """
        return Consumer._consumers


