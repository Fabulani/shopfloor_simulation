import json
import paho.mqtt.client as mqtt
import mqtt_utils
import threading
import logging
from time import sleep
from random import randint
from mpmath import *
from math import sqrt
from mqtt_utils import MqttGeneric

# MQTT Setup
MQTT_HOST = "mqtt.fluux.io"  # Alternatives: "mqtt.eclipse.org", "mqtt.fluux.io"
MQTT_PORT = 1883
MQTT_SLEEP_INTERVAL = 0.1             # Amount of time between MQTT's run_event check
MQTT_TOPIC_INIT = "freeaim/echo/"   # Initial part of the MQTT topic.

# Other configuration constants
STATE_SLEEP = 2                     # Amount of time to wait between states.
AMOUNT_STATES_TO_RUN = 999          # Amount of states to run before the simulation ends. Set it to a very high number for continuous simulation.
MOVEMENT_SLEEP = 0.1                # Amount of time to wait between steps.
MOVEMENT_STEP = 5                   # Amount to move in an axis (x or y).

### STATE MACHINE SETUP ###
# The State Machine is a cycle: Idle -> OP10 -> TransitionToOP20 -> OP20 -> ... -> TransitionToIdle -> Idle 
# Note about TransitionToOP10: this State was discarded since all the robots are already positioned correctly in the TransitionToIdle State.
# This means that OP10 can start without having to move Robots around from the previous State (Idle). This is not the case for other OPs.


class State:
    def run(self):
        assert 0, "run not implemented"

    def next(self):
        assert 0, "next not implemented"


class StateMachine:
    def __init__(self, initialState):
        self.currentState = initialState
        self.currentState.run()
    # Template method:

    def runAll(self, inputs):
        for i in inputs:
            self.currentState = self.currentState.next()
            self.currentState.run()


class ShopFloor(StateMachine):
    def __init__(self):
        # Initial state
        StateMachine.__init__(self, ShopFloor.idle)


class Idle(State):
    '''Idle State where nothing happens'''
    def run(self):
        print("[STATE] Idle")
        sleep(STATE_SLEEP)

    def next(self):
        return ShopFloor.op10


class OP10(State):
    def run(self):
        print("[STATE] OP10 - Sub Assy of a cross member")
        J1.begin_step(Station1.op)
        J1.status = 'underway'
        S1.status = 'busy'
        S2.status = 'busy'
        A1.status = 'busy'
        S1.update_tcp()
        S2.update_tcp()

        sleep(STATE_SLEEP)
        J1.complete_step(Station1.op)
        S1.reset()
        S2.reset()

    def next(self):
        return ShopFloor.transition_to_op20


class OP20(State):
    def run(self):
        print("[STATE] OP20 - Assy of various members")
        J1.begin_step(Station2.op)
        S4.status = 'busy'
        M1.status = 'busy'
        M2.status = 'busy'        
        S4.update_tcp()
        M1.update_tcp()
        M2.update_tcp()

        sleep(STATE_SLEEP)
        J1.complete_step(Station2.op)
        S4.reset()

    def next(self):
        return ShopFloor.transition_to_op30


class OP30(State):
    def run(self):
        print("[STATE] OP30 - Assy of various members")
        J1.begin_step(Station3.op)
        S3.status = 'busy'
        S3.update_tcp()
        M1.update_tcp()
        M2.update_tcp()

        sleep(STATE_SLEEP)
        J1.complete_step(Station3.op)
        S3.reset()

    def next(self):
        return ShopFloor.transition_to_op40


class OP40(State):
    def run(self):
        print("[STATE] OP40 - Assy of various members")
        J1.begin_step(Station4.op)
        S5.status = 'busy'
        S6.status = 'busy'
        S5.update_tcp()
        S6.update_tcp()
        M1.update_tcp()
        M2.update_tcp()

        sleep(STATE_SLEEP)
        J1.complete_step(Station4.op)
        S5.reset()
        S6.reset()
        M1.reset()
        M2.reset()

    def next(self):
        return ShopFloor.transition_to_op50


class OP50(State):
    def run(self):
        print("[STATE] OP50 - Measurement process using portable metrology for frame geometry check")
        J1.begin_step(Station5.op)

        sleep(STATE_SLEEP)
        J1.complete_step(Station5.op)

    def next(self):
        return ShopFloor.transition_to_op60


class OP60(State):
    def run(self):
        print("[STATE] OP60 - Manual disassembly to recirculate demo parts")
        J1.begin_step(Station6.op)

        sleep(STATE_SLEEP)
        J1.complete_step(Station6.op)
        J1.status = 'completed'

    def next(self):
        return ShopFloor.transition_to_idle


class TransitionToIdle(State):
    '''Transition State from OP60 to Idle'''
    def run(self):
        print("[STATE] TransitionToIdle")
        for entity in entities:
            entity.reset()
        sleep(5)
    
    def next(self):
        return ShopFloor.idle


class TransitionToOP20(State):
    '''Transition State from OP10 to OP20'''
    def run(self):
        print("[STATE] TransitionToOP20")
        A1.move_robot(Station2.pos)
        sleep(STATE_SLEEP)
    
    def next(self):
        return ShopFloor.op20


class TransitionToOP30(State):
    '''Transition State from OP20 to OP30'''
    def run(self):
        print("[STATE] TransitionToOP30")
        M1.move_robot((600, 360, 0))
        M2.move_robot((600, 470, 0))
        A1.move_robot(Station3.pos)
        sleep(STATE_SLEEP)
    
    def next(self):
        return ShopFloor.op30


class TransitionToOP40(State):
    '''Transition State from OP30 to OP40'''
    def run(self):
        print("[STATE] TransitionToOP40")
        M1.move_robot((375, 245, 0))
        M2.move_robot((375, 345, 0))
        A1.move_robot(Station4.pos)
        sleep(STATE_SLEEP)
    
    def next(self):
        return ShopFloor.op40


class TransitionToOP50(State):
    '''Transition State from OP40 to OP50'''
    def run(self):
        print("[STATE] TransitionToOP50")
        A1.move_robot(Station5.pos)
        sleep(STATE_SLEEP)
    
    def next(self):
        return ShopFloor.op50


class TransitionToOP60(State):
    '''Transition State from OP50 to OP60'''
    def run(self):
        print("[STATE] TransitionToOP60")
        A1.move_robot(Station6.pos)
        sleep(STATE_SLEEP)
    
    def next(self):
        return ShopFloor.op60


### SHOPFLOOR ENTITIES SETUP ###

class Station:
    '''The Stations are where the Robots work on the Products'''
    def __init__(self, position, operation_type):
        self.pos = position
        self.op = operation_type


class Robot:
    '''The Robots work on the products and can be either static, mobile or agvs'''
    def __init__(self, initial_position:tuple=(0, 0, 0), initial_status:str="idle", robot_type:str="?", name:str="Robot", mqtt_topic:str="Robot-Topic-001"):
        self.initial_pos = initial_position
        self.pos = initial_position
        self.angle = 0
        self.status = initial_status
        self.type = robot_type
        self.name = name
        self.tcp = (0, 0, 0)  # Tool center point
        # MQTT
        self.mqtt_topic = MQTT_TOPIC_INIT + mqtt_topic
        self.mqtt_payload = {}
        self.prev_mqtt_payload = {}

    def reset(self):
        '''Reset the Robot's attributes. Used when the Robot has to go back to it's initial State.'''
        if self.type != "static":
            self.move_robot(self.initial_pos)
        self.status = 'idle'
        self.tcp = (0, 0, 0)
        return

    def update_tcp(self):
        '''Update the Robot's Tool Center Point (tcp) with random numbers'''
        self.tcp = (randint(0, 100), randint(0, 100), randint(0, 100))
        return

    def move_robot(self, target:tuple):
        '''
        Change position incrementally in a linear movement interpolated by the current position and the target position.
        
        `target`: xyz coordinates for the Robot's destination.
        '''
        self.status = "moving"

        current_pos = {"x": self.pos[0], "y": self.pos[1], "z": self.pos[2]}
        target_pos = {"x": target[0], "y": target[1], "z": target[2]}

        # Distances (dx and dy are the sides of the triangle in a 2D plane)
        dx = target_pos["x"] - current_pos["x"]
        dy = target_pos["y"] - current_pos["y"]
        dz = target_pos["z"] - current_pos["z"]

        # Angle between dx and hypotenuse (2D plane, rad)
        self.angle = float(atan2(dy, dx))

        # Pathing: change current_pos by a value of MOVEMENT_STEP until it equals target_pos
        target_reached = False
        while not target_reached:            
            # Calculate steps for x axis
            dx = target_pos["x"] - current_pos["x"]
            if (dx > 0 and abs(dx) > MOVEMENT_STEP):
                current_pos["x"] += MOVEMENT_STEP
            elif (dx < 0 and abs(dx) > MOVEMENT_STEP):
                current_pos["x"] -= MOVEMENT_STEP
            else:
                # Target is very close. Snap to it.
                current_pos["x"] = target_pos["x"]

            # Calculate a step for y axis
            dy = target_pos["y"] - current_pos["y"]
            if (dy > 0 and abs(dy) > MOVEMENT_STEP):
                current_pos["y"] += MOVEMENT_STEP
            elif (dy < 0 and abs(dy) > MOVEMENT_STEP):
                current_pos["y"] -= MOVEMENT_STEP
            else:
                # Target is very close. Snap to it.
                current_pos["y"] = target_pos["y"]

            # Calculate a step for z axis
            dz = target_pos["z"] - current_pos["z"]
            if (dz > 0 and abs(dz) > MOVEMENT_STEP):
                current_pos["z"] += MOVEMENT_STEP
            elif (dz < 0 and abs(dz) > MOVEMENT_STEP):
                current_pos["z"] -= MOVEMENT_STEP
            else:
                # Target is very close. Snap to it.
                current_pos["z"] = target_pos["z"]

            # Update the Robot's positions
            self.pos = (current_pos["x"], current_pos["y"], current_pos["z"])

            # Check if the target destination has been reached
            if (current_pos["x"] == target_pos["x"] and current_pos["y"] == target_pos["y"] and current_pos["z"] == target_pos["z"]):
                target_reached = True

            sleep(MOVEMENT_SLEEP)
        self.status = "idle"
        return

    def mqtt_update_payload(self):
        '''Update the Robot's MQTT payload with its data. Needs to be implemented for each type of Robot.'''
        raise NotImplementedError("Each Robot has a specific MQTT payload. Please implement this in each child class.")

    def mqtt_send_payload(self, mqtt_client):
        '''Publish the MQTT payload via the MQTT protocol. If the payload is the same as the previous one, it will be ignored.'''
        if self.mqtt_payload != self.prev_mqtt_payload:
            mqtt_client.publish(self.mqtt_topic, json.dumps(self.mqtt_payload), 0)
            self.prev_mqtt_payload = self.mqtt_payload
        return


class AGV(Robot):
    '''AGVs are responsible for moving the Products around the Shopfloor'''
    def update_tcp(self):
        raise NotImplementedError("AGVs don't have robotic arms, as such it can't update its tool center point value.")

    def mqtt_update_payload(self):
        self.mqtt_payload = {
            "name": self.name,
            "type": self.type,
            "status": self.status,
            "pos_x": self.pos[0],
            "pos_y": self.pos[1],
            "pos_z": self.pos[2],
            "angle": self.angle,
        }


class StaticRobot(Robot):
    '''Static Robots have a robotic arm, but can't move around the Shopfloor'''
    def move_robot(self):
        raise NotImplementedError("Static Robots can't move around the shop floor.")

    def mqtt_update_payload(self):
        self.mqtt_payload = {
            "name": self.name,
            "type": self.type,
            "status": self.status,
            "pos_x": self.pos[0],
            "pos_y": self.pos[1],
            "pos_z": self.pos[2],
            "angle": self.angle,
            "tool_center_point_x": self.tcp[0],
            "tool_center_point_y": self.tcp[1],
            "tool_center_point_z": self.tcp[2],
        }


class MobileRobot(Robot):
    '''Mobile Robots have a robotic arm, and can move around the Shopfloor'''
    def mqtt_update_payload(self):
        self.mqtt_payload = {
            "name": self.name,
            "type": self.type,
            "status": self.status,
            "pos_x": self.pos[0],
            "pos_y": self.pos[1],
            "pos_z": self.pos[2],
            "angle": self.angle,
            "tool_center_point_x": self.tcp[0],
            "tool_center_point_y": self.tcp[1],
            "tool_center_point_z": self.tcp[2],
        }


class Job():
    '''For the Shopfloor simulation, only one Job is repeatedly executed, consisting of a list of processes (OPs)'''
    def __init__(self, mqtt_topic, pending_steps:list=["OP10", "OP20", "OP30", "OP40", "OP50", "OP60"]):
        self.status = "pending"
        self.pending = pending_steps
        self.completed = []
        self.current_step = "-"
        self.current_progress = 0  # Job progress in percentage
        # MQTT
        self.mqtt_topic = MQTT_TOPIC_INIT + mqtt_topic
        self.mqtt_payload = {}
        self.prev_mqtt_payload = {}

    def update_progress(self):
        '''Update current progress on the Job in percentage'''
        self.current_progress = round(len(self.completed)/(len(self.completed) + len(self.pending))*100, 2)

    def begin_step(self, step_name:str):
        '''Update the current step with the specified step name. If the step is not in the pending list, or it's not a "-" step (for transitions), raise an Exception'''
        if step_name in self.pending:
            self.current_step = step_name
        else:
            raise Exception("The specified step is not in the Job's pending steps list.")

    def complete_step(self, step_name:str):
        '''Remove the completed step from the pending list and append it to the completed list'''
        self.pending.remove(step_name)
        self.completed.append(step_name)
        self.current_step = "-"
        self.update_progress()

    def reset(self):
        self.status = "pending"
        self.pending = ["OP10", "OP20", "OP30", "OP40", "OP50", "OP60"]
        self.completed = []
        self.current_step = "-"
        self.current_progress = 0

    def mqtt_update_payload(self):
        self.mqtt_payload = {
            "name": "J1",
            "status": self.status,
            "current_progress": self.current_progress,
            "current_step": self.current_step,
            "pending": self.pending,
            "completed": self.completed
        }
    
    def mqtt_send_payload(self, mqtt_client):
        '''Publish the MQTT payload via the MQTT protocol. If the payload is the same as the previous one, it will be ignored.'''
        if self.mqtt_payload != self.prev_mqtt_payload:
            mqtt_client.publish(self.mqtt_topic, json.dumps(self.mqtt_payload), 0)
            self.prev_mqtt_payload = self.mqtt_payload
        return


### MQTT Protocol Setup ###

class MqttManager(MqttGeneric):
    '''Handles MQTT protocol communication'''    
    def mqtt_loop(self, run_event):
        '''(OVERRIDDEN) Starts the MQTT communication. Designed to be used with the threading library. Shuts down when the run_event is cleared.'''
        self.client.loop_start()
        while run_event.is_set():
            for entity in entities:
                entity.mqtt_update_payload()
                entity.mqtt_send_payload(self.client)
                sleep(0.01)
            sleep(self.mqtt_sleep)
        self.client.loop_stop()
        print ("[MQTT] Shutting down MQTT.")

    @staticmethod
    def on_publish(client, userdata, mid):
        '''(OVERRIDDEN) The callback for when a message is published. Do nothing.'''
        pass


if __name__ == "__main__":
    # Instantiate Stations
    Station1 = Station((650, 160, 0), 'OP10')
    Station2 = Station((370, 530, 0), 'OP20')
    Station3 = Station((480, 400, 0), 'OP30')
    Station4 = Station((250, 300, 0), 'OP40')
    Station5 = Station((250, 200, 0), 'OP50')
    Station6 = Station((250, 100, 0), 'OP60')

    # Instantiate Static Robots
    S1 = StaticRobot((615, 100, 0), 'idle', 'static', "S1", "Static-Robot-001")
    S2 = StaticRobot((690, 100, 0), 'idle', 'static', "S2", "Static-Robot-002")
    S3 = StaticRobot((685, 415, 0), 'idle', 'static', "S3", "Static-Robot-003")
    S4 = StaticRobot((490, 600, 0), 'idle', 'static', "S4", "Static-Robot-004")
    S5 = StaticRobot((490, 320, 0), 'idle', 'static', "S5", "Static-Robot-005")
    S6 = StaticRobot((490, 270, 0), 'idle', 'static', "S6", "Static-Robot-006")

    # Instantiate Mobile Robots
    M1 = MobileRobot((450, 590, 0), 'idle', 'mobile', "M1", "Mobile-Robot-001")
    M2 = MobileRobot((450, 485, 0), 'idle', 'mobile', "M2", "Mobile-Robot-002")

    # Instantiate AGV
    A1 = AGV(Station1.pos, 'idle', "agv", "A1", "AGV-001")

    # Instantiate Jobs
    J1 = Job("Job-001", pending_steps=[Station1.op, Station2.op, Station3.op, Station4.op, Station5.op, Station6.op])

    # List of entities that need to be reset
    entities = [S1, S2, S3, S4, S5, S6, M1, M2, A1, J1]

    # Static variable initialization:
    ShopFloor.idle = Idle()
    ShopFloor.op10 = OP10()
    ShopFloor.op20 = OP20()
    ShopFloor.op30 = OP30()
    ShopFloor.op40 = OP40()
    ShopFloor.op50 = OP50()
    ShopFloor.op60 = OP60()
    ShopFloor.transition_to_idle = TransitionToIdle()
    ShopFloor.transition_to_op20 = TransitionToOP20()
    ShopFloor.transition_to_op30 = TransitionToOP30()
    ShopFloor.transition_to_op40 = TransitionToOP40()
    ShopFloor.transition_to_op50 = TransitionToOP50()
    ShopFloor.transition_to_op60 = TransitionToOP60()

    # Create event for syncing thread shut down.
    run_event = threading.Event()
    run_event.set()

    # Connect to MQTT
    mqtt_manager = MqttManager(MQTT_HOST, MQTT_PORT, mqtt_sleep=MQTT_SLEEP_INTERVAL)
    mqtt_thread = threading.Thread(target=mqtt_manager.mqtt_loop, args=[run_event])
    mqtt_thread.start()

    # Wait so MQTT connects and threads are started
    sleep(1)

    # Allow the use of a keyboard interrupt to stop the program
    try:
        # Start simulation
        ShopFloor().runAll(range(1, AMOUNT_STATES_TO_RUN))
    except KeyboardInterrupt:
        print("[THREADS] Attempting to close threads.") 
    except:
        print("[ERROR] Unexpected error:")
        logging.exception('')

    # Clear the run_event to shutdown threads.
    run_event.clear()

    # Wait for the threads to finish
    mqtt_thread.join()

    print ("[THREADS] All threads closed. Exiting main thread.")
