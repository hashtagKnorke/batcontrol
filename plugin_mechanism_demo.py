from consumer.consumer import Consumer

def main():
    # Discover available consumer plugins
    Consumer.discover_consumers(plugin_base_dir="consumer_plugins")

    # Load consumers from the YAML configuration file
    Consumer.load_consumers_config(config_path="consumer_plugins/consumers_config.yaml")

    # Get the list of consumer instances
    consumers = Consumer.get_consumers()

    # Example usage of the consumers
    for consumer in consumers:
        print(f"Created consumer[{consumer}] with number: {consumer.consumer_num}")
        consumer.shutdown()

if __name__ == "__main__":
    main()
