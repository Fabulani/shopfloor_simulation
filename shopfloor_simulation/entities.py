from time import sleep
import copy
import random
from shopfloor_simulation.settings import ROOT_TOPIC
import threading as th
from queue import Queue

MOVEMENT_SLEEP = 0.01                # Amount of time to wait between steps.
MOVEMENT_STEP = 2                   # Amount to move in an axis (x or y).


class Header:
    ''' The header is the same for all entities, and it contains basic identification information about them. '''

    def __init__(self, _id, name, namespace, description):
        self._id = _id
        self.name = name
        self._namespace = namespace
        self.description = description


class Robot:
    '''The Robots work on the products and can be either stationary, mobile or agvs'''

    def __init__(self, _id, name, namespace, description, _type, initial_position=[0, 0, 0], initial_euler=[0, 0, 0], initial_orientation=[0, 0, 0, 0], current_station: Header = None):
        self.header = Header(_id, name, namespace, description)
        self.type = _type  # agv, stationary, or mobile
        self.status = "IDLE"  # INIT, IDLE, BUSY, TRANSPORT, PAUSED, UNKNOWN, ERROR
        self.initial_pose = {
            "position": initial_position,
            "orientation": initial_orientation
        }
        self.initial_pose_negative = {
            "position": [initial_position[0], initial_position[1]*-1, initial_position[2]],
            "orientation": initial_orientation
        }
        self.pose = copy.deepcopy(self.initial_pose)
        self.pose_negative = copy.deepcopy(self.initial_pose_negative)
        self.position_negative_y = [initial_position[0],
                                    initial_position[1]*-1, initial_position[2]]
        self.pose2 = "PE," + \
            ','.join(map(str, self.position_negative_y)) + \
            ','+','.join(map(str, initial_euler))
        self.euler = initial_euler
        self.current_station = current_station
        self.robotMode = "AUTOMATIC"
        self.motionPossible = True
        self.move_thread = None

    def reset(self):
        '''Reset the Robot's attributes. Used when the Robot has to go back to it's initial State.'''
        self.move_robot(self.initial_pose["position"])
        self.status = 'IDLE'
        return

    def move_robot(self, target):
        self.move_thread = th.Thread(
            target=self.move_robot_thread, args=[target])
        self.move_thread.start()
        # self.move_robot_thread(target)

    def move_robot_thread(self, target):
        '''
        Change position incrementally in a linear movement interpolated by the current position and the target position.

        `target`: xyz coordinates for the Robot's destination.
        '''
        prev_status = self.status
        self.status = "TRANSPORT"

        current_pos = {"x": self.pose["position"][0],
                       "y": self.pose["position"][1],
                       "z": self.pose["position"][2]}
        target_pos = {"x": target[0], "y": target[1], "z": target[2]}

        # Distances (dx and dy are the sides of the triangle in a 2D plane)K
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

            # Calculate steps for each axis
            for xyz in target_pos.keys():
                distance = target_pos[xyz] - current_pos[xyz]
                if (distance > 0 and abs(distance) > MOVEMENT_STEP):
                    current_pos[xyz] += MOVEMENT_STEP
                elif (distance < 0 and abs(distance) > MOVEMENT_STEP):
                    current_pos[xyz] -= MOVEMENT_STEP
                else:
                    # Target is very close. Snap to it.
                    current_pos[xyz] = target_pos[xyz]

            # Update the Robot's positions
            self.pose["position"] = [current_pos["x"],
                                     current_pos["y"],
                                     current_pos["z"]]
            self.pose2 = "PE,"+str(current_pos["x"])+","+str(-1*current_pos["y"])+","+str(
                current_pos["z"])+','+','.join(map(str, self.euler))
            # Battery drain
            if "battery_status" in vars(self):
                self.battery_status -= 0.0001

            sleep(MOVEMENT_SLEEP)
        self.status = prev_status
        return

    def move_object_absolute(self, target):
        ''' Change position incrementally in a linear movement interpolated by the current position and the target position as an absolute value.
        y is negative in live_topic,
        `target`: xyz coordinates for the Objects's destination.'''
        pass

    def set_position(self, target, euler=[0, 0, 0]):
        self.pose["position"] = [target[0],
                                 target[1],
                                 target[2]]
        self.pose2 = "PE,"+str(target[0])+","+str(target[1]) + \
            ","+str(target[2])+','+','.join(map(str, euler))


class TwinAgv(Robot):
    '''AGVs are responsible for moving the Products around the Shopfloor'''

    def __init__(self, _id, name, namespace, description, _type, Zone, jtpath="", facility_type="", initial_position=[0, 0, 0], initial_euler=[0, 0, 0], initial_orientation=[0, 0, 0, 0], current_station=None):
        super().__init__(_id, name, namespace, description, _type, initial_position=initial_position, initial_euler=initial_euler,
                         initial_orientation=initial_orientation, current_station=current_station)
        self.battery_status = 1.0  # Battery percentage = battery_status*100
        self.facility_type = facility_type
        self.jtpath = jtpath
        self.position = initial_position
        self.euler = initial_euler
        self.facility = facility(name, self.position, self.euler,
                                 Zone, jtpath=self.jtpath, facility_type=self.facility_type)
        self.mover = mover(name+"_mover", name, ROOT_TOPIC +
                           namespace+"/"+str(_id)+"/pose2", Zone)


class Agv(Robot):
    def __init__(self, _id, name, namespace, description, _type, initial_position=[0, 0, 0], initial_orientation=[0, 0, 0, 0], current_station=None):
        super().__init__(_id, name, namespace, description, _type, initial_position=initial_position,
                         initial_orientation=initial_orientation, current_station=current_station)
        self.battery_status = 1.0  # Battery percentage = battery_status*100


class StationaryRobot(Robot):
    '''Stationary Robots have a robotic arm, but can't move around the Shopfloor'''

    def __init__(self, _id, name, namespace, description, _type, initial_position=[0, 0, 0], initial_orientation=[0, 0, 0, 0], current_station=None):
        super().__init__(_id, name, namespace, description, _type, initial_position=initial_position,
                         initial_orientation=initial_orientation, current_station=current_station)

    def move(self, target):
        ''' (OVERRIDDEN) Stationary Robots can't move! Do nothing. '''
        pass


class MobileRobot(Robot):
    '''Mobile Robots have a robotic arm, and can move around the Shopfloor'''

    def __init__(self, _id, name, namespace, description, _type, initial_position=[0, 0, 0], initial_orientation=[0, 0, 0, 0], current_station=None):
        super().__init__(_id, name, namespace, description, _type, initial_position=initial_position,
                         initial_orientation=initial_orientation, current_station=current_station)
        self.battery_status = 1.0

#NEW RCH#########################################


class Structure:
    def __init__(self, _id, name, namespace, description):
        self.header = Header(_id, name, namespace, description)
        self.zones = {}

    def add_zone(self, zone):
        self.zones.update({zone.header.name: {
                          "state_topic": ROOT_TOPIC+zone.header._namespace+"/"+zone.header.name+"/state"}})


class Zone:
    def __init__(self, _id, name, namespace, description, Structure):
        self.header = Header(_id, name, namespace, description)
        self.facilities = []
        self.areas = []
        self.boxes = []
        self.texts = []
        self.movers = []
        self.state = {"facilities": self.facilities, "areas": self.areas,
                      "boxes": self.boxes, "texts": self.texts, "movers": self.movers}
        Structure.add_zone(self)

    def update_state(self):
        self.state = {"facilities": self.facilities, "areas": self.areas,
                      "boxes": self.boxes, "texts": self.texts, "movers": self.movers}

    def add_facility(self, facility):
        self.facilities.append(facility)

    def add_area(self, area):
        self.areas.append(area)

    def add_mover(self, mover):
        self.movers.append(mover)


class facility():
    def __init__(self, name, position, euler, Zone, jtpath="", facility_type="",):
        self.name = name
        if jtpath != "":
            self.jtpath = jtpath
        elif facility_type == "":
            print(
                "[ERROR] Either jtpath or facility_type have to be inserted for facility " + str(self.name) + ".")
        else:
            self.facility_type = facility_type
        self.position = position
        self.euler = euler
        Zone.add_facility(self)


class area():
    def __init__(self, position, area_type, width, depth, Zone):
        self.position = position
        self.area_type = area_type
        self.width = width
        self.depth = depth
        Zone.add_area(self)


class mover():
    def __init__(self, name, target, live_topic, Zone, offset_position=[0, 0, 0], offset_euler=[0, 0, 0]):
        self.name = name
        self.target = target
        self.live = True
        self.live_topic = live_topic
        self.offset_position = offset_position
        self.offset_euler = offset_euler
        Zone.add_mover(self)

###############################################


class Station(Zone):
    def __init__(self, _id, name, namespace, description):
        self.header = Header(_id, name, namespace, description)
        self.state = {"facilities": 0}
        self.status = "OPERABLE"  # SETUP, OPERABLE, UNKNOWN, ERROR


class Job:
    ''' For the Shopfloor simulation, only one Job is repeatedly executed, consisting of a list of process steps (PSs) '''

    def __init__(self, _id, name, namespace, description, process_steps: list):
        self.header = Header(_id, name, namespace, description)
        self.status = "IDLE"  # CREATED, IDLE, IN_PROGRESS, ON_HOLD, DONE, ERROR, UNKNOWN
        self.process_steps = process_steps  # Also determines order of execution of PSs
        self.progress = 0  # In percentage
        self.is_real = random.choice([True, False])  # Real or simulated Job

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

    def begin_process_step(self, _id):
        ''' Change status of the Ps and its Op to IN_PROGRESS. '''
        self.process_steps[_id].status = "IN_PROGRESS"
        self.process_steps[_id].operations[0].status = "IN_PROGRESS"

    def finish_process_step(self, _id):
        ''' Change status of the Ps and its Op to DONE, then update progress. '''
        self.process_steps[_id].status = "DONE"
        self.process_steps[_id].operations[0].status = "DONE"
        self.process_steps[_id].operations[0].progress = 100
        self.process_steps[_id].update_progress()
        self.update_progress()


class ProcessStep:
    ''' Part of a Job, consists of Operations and is executed in some Station '''

    def __init__(self, _id, name, namespace, description, operations: list, station: Header, nextPs="", prevPs=""):
        self.header = Header(_id, name, namespace, description)
        self.status = "IDLE"  # CREATED, IDLE, IN_PROGRESS, ON_HOLD, DONE, ERROR, UNKNOWN
        self.operations = operations
        self.progress = 0  # In percentage
        self.station = station
        self.nextProcessStep = nextPs  # The id of the PS to be executed next
        self.prevProcessStep = prevPs  # The id of the PS that must be executed beforehand

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
        self.status = "IDLE"  # CREATED, IDLE, IN_PROGRESS, ON_HOLD, DONE, ERROR, UNKNOWN
        self.progress = 0  # In percentage


class DigitalTwinViewerManager():
    """ 
        Scenario Manager for the Digital Twin Viewer related scenarios.

        Enables the execution of selected `scenarios` by their `flexibility`.
    """

    def __init__(self, scenarios, allowed_flexibility: list[int] = [0, 1]):
        self.header = Header("DTV-000", "DTV Scenario Manager",
                             "scenario_manager", "Scenario Manager for DTV related scenarios.")
        self.scenarios = scenarios  # List, tuple or dict of scenarios
        self.selected_flexibility = 0  # Determines which scenario should be loaded
        self.allowed_flexibility = allowed_flexibility
        self.efficiency = 0  # From 0 to 1
        self.is_enabled = True  # Flag that enables the manager

    def load_scenario(self):
        """ Scenario will be loaded according to the selected flexibility. """

        # Selected flexibility must be one of these values, otherwise reset to 0
        if self.selected_flexibility not in self.allowed_flexibility:
            self.selected_flexibility = 0

        # Run the scenario
        self.scenarios[self.selected_flexibility](self).runAll()
