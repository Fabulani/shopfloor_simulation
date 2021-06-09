import paho.mqtt.client as mqtt
import threading
import logging
from time import sleep


# Always import the desired scenario 'as Scenario' to keep the code compatible.
from shopfloor_simulation.scenarios.dtv.flexibility0 import Shopfloor as Scenario_flexibility0
from shopfloor_simulation.scenarios.dtv.flexibility1 import Shopfloor as Scenario_flexibility1
from shopfloor_simulation.entities import DigitalTwinViewerManager


if __name__ == "__main__":
    # List of scenarios
    scenarios = [Scenario_flexibility0, Scenario_flexibility1]

    # Scenario Manager object
    dtv_manager = DigitalTwinViewerManager(scenarios)

    # Run scenarios
    try:
        print("[#] Scenario Manager initialized. Starting Scenarios.")

        while dtv_manager.is_enabled:
            dtv_manager.load_scenario()

        print("[#] Scenario Manager disabled. Shutting down.")

    # Allow the use of a keyboard interrupt to stop the program
    except KeyboardInterrupt:
        print("\n[W] Keyboard Interrupt detected. Shutting down.")

    # Handle unexpected errors
    except:
        print("\n[!] Unexpected error:")
        logging.exception('')
