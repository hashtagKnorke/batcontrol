""" Factory for consumer providers """

import pluggy
from .hookspecs import ConsumerInterface
import importlib.util
import os
import yaml
from typing import List


class Consumer:
    """ Factory and registry for consumer providers """
    MANIFEST_FILE_NAME = "manifest.yaml"
    IMPLEMENTATION_CLASS_KEY = "implementation_class"
    num_consumers = 0
    _pm = pluggy.PluginManager("consumer")
    _pm.add_hookspecs(ConsumerInterface)
    _consumers: List[ConsumerInterface] = []
    _manifest_dict: dict[str, dict] = {}

    @staticmethod
    def create_consumer(config: dict) -> ConsumerInterface:
        """ Select and configure a consumer based on the given configuration """

        consumer_name = config.get("name")
        plugin = config.get("plugin")

        # Check if the plugin name is present in the config
        consumer_class = Consumer._pm.get_plugin(name=plugin)
        if not consumer_class:
            raise ValueError(f"No consumer plugin found with name: {plugin}")

        consumer_config = config.get("config", {})

        # Check if the required config keys (defined in plugin manifest)
        # are present in the consumer config
        manifest = Consumer._manifest_dict.get(plugin)
        if manifest:
            required_config = manifest.get("required_config", [])
            for key in required_config:
                if key not in consumer_config:
                    raise ValueError(f"Missing required config key: {key}  for plugin {
                                     plugin} in consumer config for: {consumer_name}")

        # call constructor of plugin with the config
        consumer = consumer_class(consumer_config)
        consumer.consumer_num = Consumer.num_consumers
        Consumer.num_consumers += 1
        return consumer

    @staticmethod
    def discover_consumers(plugin_base_dir: str):
        """ Discover the available consumer classes """
        Consumer._pm.load_setuptools_entrypoints("consumer")

        # iterate over all subdirectories of plugin_base_dir
        for root, _, files in os.walk(plugin_base_dir):
            if Consumer.MANIFEST_FILE_NAME in files:
                manifest_path = os.path.join(root, Consumer.MANIFEST_FILE_NAME)
                with open(manifest_path, "r") as manifest_file:
                    manifest = yaml.safe_load(manifest_file)
                    implementation_class = manifest.get(
                        Consumer.IMPLEMENTATION_CLASS_KEY)
                    if implementation_class:
                        module_name, class_name = implementation_class.rsplit(".", 1)
                        module_path = os.path.join(root, f"{module_name}.py")
                        spec = importlib.util.spec_from_file_location(module_name, module_path)
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        consumer_name = Consumer._pm.register(getattr(module, class_name))
                        Consumer._manifest_dict[consumer_name] = manifest

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
