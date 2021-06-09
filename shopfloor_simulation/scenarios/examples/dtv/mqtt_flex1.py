"""
    Digital Twin Viewer example scenario for flexibility 1 with MQTT subscribing
    to a flexibility topic, and a publishing AGV.
"""

import threading
from time import sleep

from shopfloor_simulation.entities import Agv
from shopfloor_simulation.mqtt_utils import DTVMqttClient
from shopfloor_simulation.settings import ROOT_TOPIC
from shopfloor_simulation.state_machine import State, StateMachine

STATE_SLEEP = 1  # Amount of time to wait between states.
SCENARIO_NAME = __file__.split("\\")[-1].replace(".py", "")
FLEXIBILITY = 1  # The flexibility of this scenario (similar to its id)


class Scenario(StateMachine):
    def __init__(self, scenario_manager):
        print("[#] Initializing Scenario " + SCENARIO_NAME)

        # The reference to the Scenario Manager
        Scenario.manager = scenario_manager

        # Start the State Machine
        StateMachine.__init__(self, Scenario.initialize)

    def runAll(self):
        # Boolean to control state machine shutdown
        Scenario.is_active = True

        prev_state_info = ""
        state_info = ""
        repeats = 0  # How many times has the same state_info been repeated

        while Scenario.is_active:
            # Transition to the next state
            self.current_state = self.current_state.next()

            # Print state log and update values
            prev_state_info, state_info, repeats = self.log_state_flow(
                prev_state_info, state_info, repeats)

            # Run the current state
            self.current_state.run()

        print("[#] Scenario " + SCENARIO_NAME + " has been shut down.")


class Initialize(State):
    def run(self):
        # Initialize MQTT client object
        Scenario.mqtt = DTVMqttClient(
            name="MQTT-" + SCENARIO_NAME,
            subscribed_topics=[ROOT_TOPIC + "scenario_manager/flexibility"],
            publishing_entities=Scenario.publishing_entities,
            scenario_manager=Scenario.manager,
            scenario=Scenario
        )

        # Thread for parallel continuous publishing
        Scenario.mqtt_thread = threading.Thread(
            target=Scenario.mqtt.publish_thread,
            args=[Scenario.run_event]
        )

        # Enable the run_event
        Scenario.run_event.set()

        # Start the MQTT thread
        Scenario.mqtt_thread.start()

        sleep(STATE_SLEEP)

    def next(self):
        return Scenario.state01


class State01(State):
    def run(self):
        A1.move_robot([0, 100, 0])
        A1.move_thread.join()
        sleep(STATE_SLEEP)

    def next(self):
        return Scenario.state02


class State02(State):
    def run(self):
        A1.move_robot([0, 0, 0])
        A1.move_thread.join()
        sleep(STATE_SLEEP)

    def next(self):
        # This Scenario is identified by flexibility 1
        if Scenario.manager.selected_flexibility != FLEXIBILITY:
            return Scenario.shutdown
        return Scenario.state01


class Shutdown(State):
    def run(self):
        # Disable the scenario.
        Scenario.is_active = False

        # Clear the run_event to shutdown threads.
        Scenario.run_event.clear()

        # Wait for the threads to finish.
        Scenario.mqtt_thread.join()

        sleep(STATE_SLEEP)

    def next(self):
        return Scenario.initialize


# Instantiate AGV
A1 = Agv("Agv-001", "A1", "robots", "I'm AGV 001!", "agv",
         initial_position=(0, 0, 0), initial_orientation=[0, 0, 0, 0])

Scenario.publishing_entities = [A1]

# State definition
Scenario.initialize = Initialize()
Scenario.state01 = State01()
Scenario.state02 = State02()
Scenario.shutdown = Shutdown()

# Create event for syncing thread shut down.
Scenario.run_event = threading.Event()
