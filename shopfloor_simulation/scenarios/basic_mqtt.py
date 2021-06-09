"""
    Barebones implementation of a scenario with MQTT communication. 
    The goal was to implement publish/subscribe functionality via MQTT and use
    received data to manipulate the state flow. 
    
    Possible applications: implementations that require MQTT, such as waiting for
    a Job status topic to change to "IN_PROGRESS" before transitioning to a state.

    State flow: State01 <-(loop)-> State02 -(condition)-> Shutdown (end)
"""

from time import sleep
from shopfloor_simulation.state_machine import State, StateMachine
from shopfloor_simulation.mqtt_utils import JobManager, ShopfloorPublisher, ROOT_TOPIC

STATE_SLEEP = 1  # Amount of time to wait between states.
SCENARIO_NAME = __file__.split("\\")[-1].replace(".py", "")


class Scenario(StateMachine):
    def __init__(self):
        print("[SCENARIO] Initializing Scenario " + SCENARIO_NAME)

        # Initial state
        print("[STATE] State01")
        StateMachine.__init__(self, Scenario.state01)

    def runAll(self):
        ''' (OVERRIDDEN) Print the current state before executing it. '''
        prev_state_info = "[STATE] State01"
        state_info = ''
        repeats = 0  # How many times has the same state_info been repeated

        while Scenario.isActive:
            # Transition to the next state
            self.current_state = self.current_state.next()

            # Print state log and update values
            prev_state_info, state_info, repeats = self.log_state_flow(
                prev_state_info, state_info, repeats)

            # Run the current state
            self.current_state.run()

        print("[SCENARIO] Scenario " + SCENARIO_NAME + " has been shut down.")


class State01(State):
    def run(self):
        Scenario.loop_counter += 1
        sleep(STATE_SLEEP)

    def next(self):
        return Scenario.state02


class State02(State):
    def run(self):
        sleep(STATE_SLEEP)

    def next(self):
        if Scenario.loop_counter > 2:
            return Scenario.shutdown
        else:
            return Scenario.state01


class Shutdown(State):
    def run(self):
        Scenario.isActive = False
        sleep(STATE_SLEEP)

    def next(self):
        return Scenario.shutdown


class MqttClient(MqttGeneric):
    ''' 
        Handle MQTT communication for this scenario.
    '''

    def __init__(self, host=MQTT_HOST, port=MQTT_PORT, username=MQTT_USERNAME, password=MQTT_PASSWORD, run_event_check_sleep=0.1, subscribed_topics=[], name='MQTT', root_topic=ROOT_TOPIC):
        super().__init__(host=host, port=port, username=username, password=password,
                         run_event_check_sleep=run_event_check_sleep, subscribed_topics=subscribed_topics, name=name, root_topic=root_topic)
        self.job_update_queue = []

    def on_message(self, client, userdata, msg):
        # The topic should look like this: ROOT_TOPIC/scenario_manager/<property>
        property_name = msg.topic.split('/')[-1]

        if property_name == "flexibility":
            Scenario.flexibility

            client.publish("/VR/viewer_info/tooltip", json.dumps({"name": "A1", "tooltiplines": [
                           "Object: <b>"+str(msg.payload.decode("utf-8"))+"</>"]}), 0)
        else:
            try:
                # A Job Status was published. Check it out.
                new_status = msg.payload.decode("utf-8")

                # The topic should be something like this: ROOT_TOPIC/jobs/<job_id>/status
                # Get the Job ID
                topic_parts = msg.topic.split('/')
                job_id = topic_parts[-2]
                self.job_update_queue.append((job_id, new_status))
            except:
                print("[" + self.name + "] Unrecognized: " + str(msg.payload))


# State definition
Scenario.state01 = State01()
Scenario.state02 = State02()
Scenario.shutdown = Shutdown()

# Boolean to control state machine shutdown
Scenario.isActive = True

# Counter for how many times the State Machine has looped
Scenario.loop_counter = 0

# MQTT Publisher and Subscriber
Scenario.publisher = ShopfloorPublisher(
    name="MQTT-P")
Scenario.subscriber = JobManager(
    name="MQTT-S",
    subscribed_topics=[ROOT_TOPIC])
