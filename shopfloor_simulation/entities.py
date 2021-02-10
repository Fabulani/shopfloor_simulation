from time import sleep
import json
from random import randint
from mpmath import *
from math import sqrt
from .mqtt_utils import MqttGeneric

TOPIC_ROOT = "freeaim/echo/"        # Root of the MQTT topic.
MOVEMENT_SLEEP = 0.1                # Amount of time to wait between steps.
MOVEMENT_STEP = 5                   # Amount to move in an axis (x or y).


class Station:
    '''The Stations are where the Robots work on the Products'''

    def __init__(self, position, operation_type):
        self.pos = position
        self.op = operation_type


class Robot:
    '''The Robots work on the products and can be either static, mobile or agvs'''

    def __init__(self, initial_position: tuple = (0, 0, 0), initial_status: str = "idle", robot_type: str = "?", name: str = "Robot", mqtt_topic: str = "Robot-Topic-001"):
        self.initial_pos = initial_position
        self.pos = initial_position
        self.angle = 0
        self.status = initial_status
        self.type = robot_type
        self.name = name
        self.tcp = (0, 0, 0)  # Tool center point
        # MQTT
        self.mqtt_topic = TOPIC_ROOT + mqtt_topic
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

    def move_robot(self, target: tuple):
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
        raise NotImplementedError(
            "Each Robot has a specific MQTT payload. Please implement this in each child class.")

    def mqtt_send_payload(self, mqtt_client):
        '''Publish the MQTT payload via the MQTT protocol. If the payload is the same as the previous one, it will be ignored.'''
        if self.mqtt_payload != self.prev_mqtt_payload:
            mqtt_client.publish(
                self.mqtt_topic, json.dumps(self.mqtt_payload), 0)
            self.prev_mqtt_payload = self.mqtt_payload
        return


class AGV(Robot):
    '''AGVs are responsible for moving the Products around the Shopfloor'''

    def update_tcp(self):
        raise NotImplementedError(
            "AGVs don't have robotic arms, as such it can't update its tool center point value.")

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
        raise NotImplementedError(
            "Static Robots can't move around the shop floor.")

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

    def __init__(self, mqtt_topic, pending_steps: list = ["OP10", "OP20", "OP30", "OP40", "OP50", "OP60"]):
        self.status = "pending"
        self.pending = pending_steps
        self.completed = []
        self.current_step = "-"
        self.current_progress = 0  # Job progress in percentage
        # MQTT
        self.mqtt_topic = TOPIC_ROOT + mqtt_topic
        self.mqtt_payload = {}
        self.prev_mqtt_payload = {}

    def update_progress(self):
        '''Update current progress on the Job in percentage'''
        self.current_progress = round(
            len(self.completed)/(len(self.completed) + len(self.pending))*100, 2)

    def begin_step(self, step_name: str):
        '''Update the current step with the specified step name. If the step is not in the pending list, or it's not a "-" step (for transitions), raise an Exception'''
        if step_name in self.pending:
            self.current_step = step_name
        else:
            raise Exception(
                "The specified step is not in the Job's pending steps list.")

    def complete_step(self, step_name: str):
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
            mqtt_client.publish(
                self.mqtt_topic, json.dumps(self.mqtt_payload), 0)
            self.prev_mqtt_payload = self.mqtt_payload
        return


class ShopfloorManager(MqttGeneric):
    ''' Receives commands from MQTT and influences the simulation accordingly. '''

    def __init__(self):
        self.last_action = ""
        self.action = ""

    def stop_job(self):
        pass
