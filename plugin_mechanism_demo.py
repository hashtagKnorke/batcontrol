from consumer.consumer import Consumer
import logging
import sys

def main():
    loglevel = logging.DEBUG
    logger = logging.getLogger(__name__)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s",
                              "%Y-%m-%d %H:%M:%S")

    streamhandler = logging.StreamHandler(sys.stdout)
    streamhandler.setFormatter(formatter)

    logger.addHandler(streamhandler)

    logger.setLevel(loglevel)

    logger.info('[DEMO] Starting plugin mechanism demo')


    # Discover available consumer plugins
    Consumer.discover_consumers(plugin_base_dir="config/consumer_plugins")

    # Load consumers from the YAML configuration file
    Consumer.load_consumers_config(config_path="config/consumer_plugins/consumers_config.yaml")

    # Get the list of consumer instances
    consumers = Consumer.get_consumers()

    # Example usage of the consumers
    for consumer in consumers:
        logger.info(f"[DEMO] Created consumer[{consumer}] with number: {consumer.consumer_num} ")
        consumer.shutdown()

if __name__ == "__main__":
    main()
