import paho.mqtt.client as mqtt
import threading
import logging
from time import sleep
import json

from shopfloor_simulation.mqtt_utils import MqttGeneric

# Always import the desired scenario 'as Scenario' to keep the code compatible.
from shopfloor_simulation.scenarios.scenario01 import ShopFloor as Scenario


class ShopfloorPublisher(MqttGeneric):
    ''' MQTT Publisher that handles the Shopfloor's entities payloads. '''

    def mqtt_loop(self, run_event):
        '''(OVERRIDDEN) Starts the MQTT communication. Updates and sends payloads every loop.'''
        # TODO: update and send payloads only when necessary
        self.client.loop_start()
        while run_event.is_set():
            for entity in Scenario.entities:
                entity.mqtt_update_payload()
                entity.mqtt_send_payload(self.client)
                sleep(0.01)
            sleep(self.run_event_check_sleep)
        self.client.loop_stop()
        print("[" + self.name + "] Shutting down.")

    @staticmethod
    def on_publish(client, userdata, mid):
        '''(OVERRIDDEN) The callback for when a message is published. Do nothing.'''
        pass


class ShopfloorSubscriber(MqttGeneric):
    ''' MQTT Subscriber that influences the simulation according to received messages. '''

    def on_message(self, client, userdata, msg):
        ''' (OVERRIDDEN) The callback for when a PUBLISH message is received from the server. '''
        try:
            content = json.loads(msg.payload.decode("utf-8"))
            print("[" + self.name + "] Received: " + str(content))
        except:
            print("[" + self.name + "] Unrecognized: " + str(msg.payload))


if __name__ == "__main__":

    # Create event for syncing thread shut down.
    run_event = threading.Event()
    run_event.set()

    # Create and connect MQTT interface objects
    shopfloor_publisher = ShopfloorPublisher(name="MQTT-P")
    publish_thread = threading.Thread(
        target=shopfloor_publisher.mqtt_loop,
        args=[run_event])
    publish_thread.start()

    # For the subscriber, include the subscribed topics
    shopfloor_subscriber = ShopfloorSubscriber(
        name="MQTT-S",
        subscribed_topics=["freeaim/echo/ShopfloorSubscriber"])
    subscribe_thread = threading.Thread(
        target=shopfloor_subscriber.mqtt_loop,
        args=[run_event])
    subscribe_thread.start()

    # Wait so MQTT connects and threads are started
    sleep(1)

    # Allow the use of a keyboard interrupt to stop the program
    try:
        # Start simulation
        Scenario().runAll()
    except KeyboardInterrupt:
        print("[THREADS] Attempting to close threads.")
    except:
        print("[ERROR] Unexpected error:")
        logging.exception('')

    # Clear the run_event to shutdown threads.
    run_event.clear()

    # Wait for the threads to finish
    publish_thread.join()
    subscribe_thread.join()

    print("[THREADS] All threads closed. Exiting main thread.")
