import paho.mqtt.client as mqtt
import threading
import logging
from time import sleep


# Always import the desired scenario 'as Scenario' to keep the code compatible.
# from shopfloor_simulation.scenarios.scenario01 import Shopfloor as Scenario
from shopfloor_simulation.scenarios.scenarioTwinViewer1 import Shopfloor as Scenario


if __name__ == "__main__":

    # Create event for syncing thread shut down.
    run_event = threading.Event()
    run_event.set()

    # Create and connect MQTT interface objects
    publish_thread = threading.Thread(
        target=Scenario.publisher.mqtt_loop,
        args=[run_event])
    publish_thread.start()

    # For the subscriber, include the subscribed topics
    subscribe_thread = threading.Thread(
        target=Scenario.subscriber.mqtt_loop,
        args=[run_event])
    subscribe_thread.start()

    # Wait so MQTT connects and threads are started
    sleep(1)

    # Allow the use of a keyboard interrupt to stop the program
    try:
        # Start simulation
        Scenario().runAll()
    except KeyboardInterrupt:
        print("\n[THREADS] Attempting to close threads.")
    except:
        print("\n[ERROR] Unexpected error:")
        logging.exception('')

    # Clear the run_event to shutdown threads.
    run_event.clear()

    # Wait for the threads to finish
    publish_thread.join()
    subscribe_thread.join()

    print("[THREADS] All threads closed. Exiting main thread.")
