from time import sleep
import json
from random import randint
from mpmath import *
from math import sqrt
from .mqtt_utils import MqttGeneric
import copy


MOVEMENT_SLEEP = 0.1                # Amount of time to wait between steps.
MOVEMENT_STEP = 5                   # Amount to move in an axis (x or y).


class Header:
    ''' The header is the same for all entities, and it contains basic identification information about them. '''

    def __init__(self, _id, name, namespace, description):
        self._id = _id
        self.name = name
        self._namespace = namespace
        self.description = description


class Robot:
    '''The Robots work on the products and can be either stationary, mobile or agvs'''

    def __init__(self, _id, name, namespace, description, _type, initial_position=[0, 0, 0], initial_orientation=[0, 0, 0, 0], current_station: Header = None):
        self.header = Header(_id, name, namespace, description)
        self.type = _type  # agv, stationary, or mobile
        self.status = "IDLE"  # TODO: write other possible status here
        self.initial_pose = {
            "position": initial_position,
            "orientation": initial_orientation
        }
        self.pose = copy.deepcopy(self.initial_pose)
        self.current_station = current_station

    def reset(self):
        '''Reset the Robot's attributes. Used when the Robot has to go back to it's initial State.'''
        self.move_robot(self.initial_pose["position"])
        self.status = 'IDLE'
        return

    def move_robot(self, target):
        '''
        Change position incrementally in a linear movement interpolated by the current position and the target position.

        `target`: xyz coordinates for the Robot's destination.
        '''
        self.status = "MOVE"

        current_pos = {"x": self.pose["position"][0],
                       "y": self.pose["position"][1],
                       "z": self.pose["position"][2]}
        target_pos = {"x": target[0], "y": target[1], "z": target[2]}

        # Distances (dx and dy are the sides of the triangle in a 2D plane)
        dx = target_pos["x"] - current_pos["x"]
        dy = target_pos["y"] - current_pos["y"]
        dz = target_pos["z"] - current_pos["z"]

        # Pathing: change current_pos by a value of MOVEMENT_STEP until it equals target_pos
        target_reached = False
        while not target_reached:
            # Check if the target destination has been reached
            if (current_pos["x"] == target_pos["x"] and current_pos["y"] == target_pos["y"] and current_pos["z"] == target_pos["z"]):
                target_reached = True
                break

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
            self.pose["position"] = [current_pos["x"],
                                     current_pos["y"],
                                     current_pos["z"]]

            # Battery drain
            if "battery_status" in vars(self):
                self.battery_status -= 0.1

            sleep(MOVEMENT_SLEEP)
        self.status = "IDLE"
        return


class AGV(Robot):
    '''AGVs are responsible for moving the Products around the Shopfloor'''

    def __init__(self, _id, name, namespace, description, _type, initial_position=[0, 0, 0], initial_orientation=[0, 0, 0, 0], current_station=None):
        super().__init__(_id, name, namespace, description, _type, initial_position=initial_position,
                         initial_orientation=initial_orientation, current_station=current_station)
        self.battery_status = 1.0  # Battery percentage = battery_status*100


class StationaryRobot(Robot):
    '''Stationary Robots have a robotic arm, but can't move around the Shopfloor'''

    def __init__(self, _id, name, namespace, description, _type, initial_position=[0, 0, 0], initial_orientation=[0, 0, 0, 0], current_station=None):
        super().__init__(_id, name, namespace, description, _type, initial_position=initial_position,
                         initial_orientation=initial_orientation, current_station=current_station)


class MobileRobot(Robot):
    '''Mobile Robots have a robotic arm, and can move around the Shopfloor'''

    def __init__(self, _id, name, namespace, description, _type, initial_position=[0, 0, 0], initial_orientation=[0, 0, 0, 0], current_station=None):
        super().__init__(_id, name, namespace, description, _type, initial_position=initial_position,
                         initial_orientation=initial_orientation, current_station=current_station)
        self.battery_status = 1.0


class Job1:
    '''For the Shopfloor simulation, only one Job is repeatedly executed, consisting of a list of processes (OPs)'''

    def __init__(self, mqtt_topic, pending_steps: list = ["OP10", "OP20", "OP30", "OP40", "OP50", "OP60"]):
        self.header = Header("job", "job", "jobs", "a job")
        self.status = "pending"
        self.pending = pending_steps
        self.completed = []
        self.current_step = "-"
        self.current_progress = 0  # Job progress in percentage

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


class Station:
    ''' The Stations are where the Robot execute Operations and Process Steps '''

    def __init__(self, _id, name, namespace, description):
        self.header = Header(_id, name, namespace, description)
        self.status = "SETUP"  # SETUP, OPERABLE, UNKNOWN, ERROR


class Job:
    ''' For the Shopfloor simulation, only one Job is repeatedly executed, consisting of a list of process steps (PSs) '''

    def __init__(self, _id, name, namespace, description, process_steps: list):
        self.header = Header(_id, name, namespace, description)
        self.status = "CREATED"  # CREATED, IDLE, IN_PROGRESS, ON_HOLD, DONE, ERROR, UNKNOWN
        self.process_steps = process_steps  # Also determines order of execution of PSs
        self.progress = 0  # In percentage

    def update_progress(self):
        ''' Update current progress on the Job '''

        completed = 0
        pending = 0

        # Count completed/pending PSs
        for ps in self.process_steps:
            if ps.status == "DONE":
                completed += 1
            else:
                pending += 1

        # Calculate progress and round it to an integer number
        self.progress = round(completed/(completed + pending)*100, 0)

    def reset(self):
        ''' Reset both the Job, its ProcessSteps and Operations. '''

        # Set statuses to IDLE and progress to 0
        self.status = "IDLE"
        self.progress = 0
        for ps in self.process_steps:
            ps.status = "IDLE"
            ps.progress = 0
            for op in ps.operations:
                op.status = "IDLE"
                op.progress = 0


class ProcessStep:
    ''' Part of a Job, consists of Operations and is executed in some Station '''

    def __init__(self, _id, name, namespace, description, operations: list, station: Header):
        self.header = Header(_id, name, namespace, description)
        self.status = "CREATED"  # CREATED, IDLE, IN_PROGRESS, ON_HOLD, DONE, ERROR, UNKNOWN
        self.operations = operations
        self.progress = 0  # In percentage
        self.station = station

    def update_progress(self):
        ''' Update current progress on the Process Step '''

        completed = 0
        pending = 0

        # Count completed/pending PSs
        for op in self.operations:
            if op.status == "DONE":
                completed += 1
            else:
                pending += 1

        # Calculate progress and round it to an integer number
        self.progress = round(completed/(completed + pending)*100, 0)


class Operation:
    '''  Atomic element that consists of a specific Operation to be executed as part of a Process Step '''

    def __init__(self, _id, name, namespace, description):
        self.header = Header(_id, name, namespace, description)
        self.status = "CREATED"  # CREATED, IDLE, IN_PROGRESS, ON_HOLD, DONE, ERROR, UNKNOWN
        self.progress = 0  # In percentage
