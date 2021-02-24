from time import sleep
import copy


MOVEMENT_SLEEP = 0.1                # Amount of time to wait between steps.
MOVEMENT_STEP = 10                   # Amount to move in an axis (x or y).


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
        prev_status = self.status
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

            # Battery drain
            if "battery_status" in vars(self):
                self.battery_status -= 0.0001

            sleep(MOVEMENT_SLEEP)
        self.status = prev_status
        return


class Agv(Robot):
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

    def move(self, target):
        ''' (OVERRIDDEN) Stationary Robots can't move! Do nothing. '''
        pass


class MobileRobot(Robot):
    '''Mobile Robots have a robotic arm, and can move around the Shopfloor'''

    def __init__(self, _id, name, namespace, description, _type, initial_position=[0, 0, 0], initial_orientation=[0, 0, 0, 0], current_station=None):
        super().__init__(_id, name, namespace, description, _type, initial_position=initial_position,
                         initial_orientation=initial_orientation, current_station=current_station)
        self.battery_status = 1.0


class Station:
    ''' The Stations are where the Robot execute Operations and Process Steps '''

    def __init__(self, _id, name, namespace, description):
        self.header = Header(_id, name, namespace, description)
        self.status = "OPERABLE"  # SETUP, OPERABLE, UNKNOWN, ERROR


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
