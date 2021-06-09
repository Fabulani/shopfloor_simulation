import copy
from time import sleep
from shopfloor_simulation.state_machine import State, StateMachine
from shopfloor_simulation.entities import StationaryRobot, MobileRobot, Agv, Station, Job, ProcessStep, Operation, Zone, Structure, facility, area, TwinAgv
from shopfloor_simulation.mqtt_utils import JobManager, ShopfloorPublisher, ROOT_TOPIC
import threading as th

STATE_SLEEP = 2  # Amount of time to wait between states.
CAD_PATH = "C:\Git\WZL\2020_Team_Visualization\Visualization\ThingWorx\shopfloor_simulation\shopfloor_simulation\twin_scripts\CAD"  # ! Update the PAtH
EVENT_SLEEP = 0.01

''' Helper function definitions '''
# These functions are specific to this scenario.


def create_job(jobname, process_steps: list):
    ''' Create a new Job and add it to the Job Queue.

        - The Job ID is determined by the lenght of the Job queue.
        - The new Job does a deepcopy of the ProcessSteps to create entirely new
        and independent Process Steps.
        - The new Job is then appended to the appropriate lists and its topic
        is initialized.
    '''
    #! ISSUE
    #! Deepcopy solves the issues of Jobs overwriting info on other Job objects,
    #! but it doesn't solve the issue of overwriting the PS's and OP's
    #! MQTT topics. Still, inside the Job topic, the PS and OP info should be OK.
    #! This issue might be ignored since the Jobs are now being used to store
    #! PS and its OP data inside Thingworx: Jobs > InfoTable(PS) > InfoTable(OP)

    job_id = Shopfloor.job_count + 1

    # Format the Job ID so it's always a 3-digit string.
    if job_id < 10:
        job_id_str = "00" + str(job_id)
    elif job_id < 100:
        job_id_str = "0" + str(job_id)
    else:
        job_id_str = str(job_id)
    new_job = Job(
        _id="Job-" + job_id_str,
        name="Job " + job_id_str + " " + jobname,
        namespace="jobs",
        description="I'm Job " + job_id_str + "!",
        process_steps=process_steps
    )

    # Setup the new Job in the simulation
    Shopfloor.job_queue.append(new_job)
    Shopfloor.publishing_entities.append(new_job)
    Shopfloor.publisher.initialize_single_topic(new_job)
    Shopfloor.job_count += 1

    # Setup the Job's process steps
    for ps in new_job.process_steps:
        for op in ps.operations:
            Shopfloor.publishing_entities.append(op)
            Shopfloor.publisher.initialize_single_topic(op)
        Shopfloor.publishing_entities.append(ps)
        Shopfloor.publisher.initialize_single_topic(ps)


def check_job_status_then_change_state(current_state, next_state):
    ''' Wrapper for the logic to check the Job status before state transition.

        Since it's more straightfoward to have this check inside every State's
        `next()` method (to avoid logic spaghetti in the StateMachine class),
        this function will wrap the logic for easier maintenance.

        Check the current Job status:
        - If it's `IN_PROGRESS`, maintain normal state flow.
        - If it's `ON_HOLD`, assign the current state to the prev_state variable
        and then transition to the OnHold State.
    '''
    if Shopfloor.current_job.status == "IN_PROGRESS":
        return next_state
    elif Shopfloor.current_job.status == "ON_HOLD":
        Shopfloor.prev_state = current_state
        return Shopfloor.on_hold


''' State Machine and States setup. '''
# The State Machine Diagram can be found here:
# https://whimsical.com/shopfloor-simulation-state-machine-diagram-QUKKNykbMkyLasnx6ysvqB@2Ux7TurymLB2WJEDGpE5


class Shopfloor(StateMachine):
    def __init__(self):
        # Initial state
        print("[STATE] Idle")
        StateMachine.__init__(self, Shopfloor.idle)

    def runAll(self):
        ''' (OVERRIDDEN) Print the current state before executing it. '''
        prev_state_info = "[STATE] Idle"
        state_info = ''
        repeats = 0  # How many times has the same state_info been repeated

        while True:
            # Update the Shopfloor Jobs' statuses
            Shopfloor.subscriber.update_jobs(Shopfloor.job_queue)

            # Transition to the next state
            self.current_state = self.current_state.next()

            # If the info is the same as before, print it on the same line.
            state_info = "[STATE] " + self.current_state.__class__.__name__
            if state_info != prev_state_info:
                repeats = 0
                print(state_info)
            else:
                repeats += 1
                print(state_info + " x" + str(repeats), end='\r')

            # Update prev_state_info
            prev_state_info = state_info

            # Run the current state
            self.current_state.run()


class OnHold(State):
    ''' Stop the simulation by doing nothing and loop on itself.

        This State will be triggered if the current Job has status `ON_HOLD`.
        It'll go back to the previous state if the current Job status goes back
        to `IN_PROGRESS`.
    '''

    def run(self):
        sleep(STATE_SLEEP)

    def next(self):
        if Shopfloor.current_job.status == "IN_PROGRESS":
            return Shopfloor.prev_state
        elif Shopfloor.current_job.status == "ON_HOLD":
            return Shopfloor.on_hold
        else:
            # Keep looping on_hold if the status is not recognized.
            # TODO: proper state for unknown status and other variants.
            return Shopfloor.on_hold


class Idle(State):
    ''' Check the Job Queue and its Jobs.

    If there are Jobs and at least one of them has the `IN_PROGRESS` status,
    transition to the `BeginJob` State after assigning the Job to
    `Shopfloor.current_job`. Otherwise, loop back to this state.
    '''

    def run(self):
        job_incoming = len(Shopfloor.job_queue) > 0
        if job_incoming:
            for job in Shopfloor.job_queue:
                if job.status == "IN_PROGRESS":
                    Shopfloor.current_job = job
                    break
        sleep(STATE_SLEEP)

    def next(self):
        if Shopfloor.current_job == None:
            return Shopfloor.idle
        else:
            return Shopfloor.begin_job


class BeginJob(State):
    ''' Begin work on the current Job by first moving the Robots into position. '''

    def run(self):
        ''' A note about the BeginJob State and Robot's movement.

        Since this simulation is for a single type of Job, the Robot's initial
        pose is already the correct position for beginning this Job. Different
        types of Jobs might require a different position, as such this is the
        State to reposition them before effectively doing work.
        '''
        sleep(STATE_SLEEP)

    def next(self):
        return check_job_status_then_change_state(Shopfloor.begin_job, Shopfloor.op00)
        # check for process step list and which ohne is the next one
        # once all steps are done, go to finish state


class OP00(State):
    def run(self):
        Shopfloor.current_job.begin_process_step(0)

        sleep(STATE_SLEEP)
        Shopfloor.current_job.finish_process_step(0)

    def next(self):
        return check_job_status_then_change_state(Shopfloor.op00, Shopfloor.transition_to_op10)


class OP10(State):
    def run(self):
        Shopfloor.current_job.begin_process_step(1)

        S1.status = 'BUSY'
        S2.status = 'BUSY'
        A1.status = 'BUSY'
        A1.current_station = Station11.header

        sleep(STATE_SLEEP)
        Shopfloor.current_job.finish_process_step(1)
        S1.reset()
        S2.reset()

    def next(self):
        return check_job_status_then_change_state(Shopfloor.op10, Shopfloor.transition_to_op20)


class OP20(State):
    def run(self):
        A1.current_station = Station12.header
        Shopfloor.current_job.begin_process_step(2)
        S4.status = 'BUSY'
        M1.status = 'BUSY'
        M2.status = 'BUSY'

        sleep(STATE_SLEEP)
        Shopfloor.current_job.finish_process_step(2)
        S4.reset()

    def next(self):
        return check_job_status_then_change_state(Shopfloor.op20, Shopfloor.transition_to_op30)


class OP30(State):
    def run(self):
        A1.current_station = Station13.header
        M1.current_station = Station13.header
        M2.current_station = Station13.header
        Shopfloor.current_job.begin_process_step(3)
        S3.status = 'BUSY'

        sleep(STATE_SLEEP)
        Shopfloor.current_job.finish_process_step(3)
        S3.reset()

    def next(self):
        return check_job_status_then_change_state(Shopfloor.op30, Shopfloor.transition_to_op40)


class OP40(State):
    def run(self):
        A1.current_station = Station14.header
        M1.current_station = Station14.header
        M2.current_station = Station14.header
        Shopfloor.current_job.begin_process_step(4)
        S5.status = 'BUSY'
        S6.status = 'BUSY'

        sleep(STATE_SLEEP)
        Shopfloor.current_job.finish_process_step(4)
        S5.reset()
        S6.reset()
        M1.reset()
        M2.reset()

    def next(self):
        return check_job_status_then_change_state(Shopfloor.op40, Shopfloor.transition_to_op50)


class OP50(State):
    def run(self):
        A1.current_station = Station15.header
        Shopfloor.current_job.begin_process_step(5)

        sleep(STATE_SLEEP)
        Shopfloor.current_job.finish_process_step(5)

    def next(self):
        return check_job_status_then_change_state(Shopfloor.op50, Shopfloor.transition_to_op60)


class OP60(State):
    def run(self):
        A1.current_station = Station16.header
        Shopfloor.current_job.begin_process_step(6)

        sleep(STATE_SLEEP)
        Shopfloor.current_job.finish_process_step(6)

    def next(self):
        return check_job_status_then_change_state(Shopfloor.op60, Shopfloor.finish_job)


class FinishJob(State):
    ''' Do anything needed to finish the Job. '''

    def run(self):
        Shopfloor.current_job.status = "DONE"
        Shopfloor.job_queue.remove(Shopfloor.current_job)

        # Remove PS and OPs from the publishing entities
        for ps in Shopfloor.current_job.process_steps:
            for op in ps.operations:
                Shopfloor.publishing_entities.remove(op)
            Shopfloor.publishing_entities.remove(ps)

        Shopfloor.current_job = None
        sleep(STATE_SLEEP)

    def next(self):
        return Shopfloor.reset


class Reset(State):
    '''Reset all Shopfloor resettable entities to their initial state.'''

    def run(self):
        for entity in Shopfloor.resettable_entities:
            entity.reset()
        A1.current_station = Station11.header
        M1.current_station = Station12.header
        M2.current_station = Station12.header
        create_job("Porsche1", [copy.deepcopy(Ps00), copy.deepcopy(Ps01), copy.deepcopy(
            Ps02), copy.deepcopy(Ps03), copy.deepcopy(Ps04), copy.deepcopy(Ps05), copy.deepcopy(Ps06)])
        sleep(5)

    def next(self):
        return Shopfloor.idle


class TransitionToOP10(State):
    def run(self):
        # start as threads
        th1 = th.Thread(target=P1.move_robot_thread, args=[Station11_pos])
        th2 = th.Thread(target=P2.move_robot_thread, args=[init_pos_1])
        th3 = th.Thread(target=P3.move_robot_thread, args=[init_pos_2])
        th4 = th.Thread(target=P4.move_robot_thread, args=[init_pos_3])
        th5 = th.Thread(target=P5.move_robot_thread, args=[init_pos_4])
        th6 = th.Thread(target=P6.move_robot_thread, args=[init_pos_5])
        th1.start()
        th2.start()
        th3.start()
        th4.start()
        th5.start()
        th6.start()
        th1.join()

    def next(self):
        return check_job_status_then_change_state(Shopfloor.transition_to_op10, Shopfloor.op10)


class TransitionToOP20(State):
    '''Transition State from OP10 to OP20'''

    def run(self):
        # start as threads
        th1 = th.Thread(target=P1.move_robot_thread, args=[Station12_pos])
        th2 = th.Thread(target=P2.move_robot_thread, args=[Station11_pos])
        th3 = th.Thread(target=P3.move_robot_thread, args=[init_pos_1])
        th4 = th.Thread(target=P4.move_robot_thread, args=[init_pos_2])
        th5 = th.Thread(target=P5.move_robot_thread, args=[init_pos_3])
        th6 = th.Thread(target=P6.move_robot_thread, args=[init_pos_4])
        th1.start()
        th2.start()
        th3.start()
        th4.start()
        th5.start()
        th6.start()
        th2.join()

    def next(self):
        return check_job_status_then_change_state(Shopfloor.transition_to_op20, Shopfloor.op20)


class TransitionToOP30(State):
    '''Transition State from OP20 to OP30'''

    def run(self):
        th1 = th.Thread(target=P1.move_robot_thread, args=[Station13_pos])
        th2 = th.Thread(target=P2.move_robot_thread, args=[Station12_pos])
        th3 = th.Thread(target=P3.move_robot_thread, args=[Station11_pos])
        th4 = th.Thread(target=P4.move_robot_thread, args=[init_pos_1])
        th5 = th.Thread(target=P5.move_robot_thread, args=[init_pos_2])
        th6 = th.Thread(target=P6.move_robot_thread, args=[init_pos_3])
        th1.start()
        th2.start()
        th3.start()
        th4.start()
        th5.start()
        th6.start()
        th1.join()

    def next(self):
        return check_job_status_then_change_state(Shopfloor.transition_to_op30, Shopfloor.op30)


class TransitionToOP40(State):
    '''Transition State from OP30 to OP40'''

    def run(self):
        th1 = th.Thread(target=P1.move_robot_thread, args=[Station14_pos])
        th2 = th.Thread(target=P2.move_robot_thread, args=[Station13_pos])
        th3 = th.Thread(target=P3.move_robot_thread, args=[Station12_pos])
        th4 = th.Thread(target=P4.move_robot_thread, args=[Station11_pos])
        th5 = th.Thread(target=P5.move_robot_thread, args=[init_pos_1])
        th6 = th.Thread(target=P6.move_robot_thread, args=[init_pos_2])
        th1.start()
        th2.start()
        th3.start()
        th4.start()
        th5.start()
        th6.start()
        th1.join()

    def next(self):
        return check_job_status_then_change_state(Shopfloor.transition_to_op40, Shopfloor.op40)


class TransitionToOP50(State):
    '''Transition State from OP40 to OP50'''

    def run(self):
        th1 = th.Thread(target=P1.move_robot_thread, args=[Station15_pos])
        th2 = th.Thread(target=P2.move_robot_thread, args=[Station14_pos])
        th3 = th.Thread(target=P3.move_robot_thread, args=[Station13_pos])
        th4 = th.Thread(target=P4.move_robot_thread, args=[Station12_pos])
        th5 = th.Thread(target=P5.move_robot_thread, args=[Station11_pos])
        th6 = th.Thread(target=P6.move_robot_thread, args=[init_pos_1])
        th1.start()
        th2.start()
        th3.start()
        th4.start()
        th5.start()
        th6.start()
        th1.join()

    def next(self):
        return check_job_status_then_change_state(Shopfloor.transition_to_op50, Shopfloor.op50)


class TransitionToOP60(State):
    '''Transition State from OP50 to OP60'''

    def run(self):
        th1 = th.Thread(target=P1.move_robot_thread, args=[Station16_pos])
        th2 = th.Thread(target=P2.move_robot_thread, args=[Station15_pos])
        th3 = th.Thread(target=P3.move_robot_thread, args=[Station14_pos])
        th4 = th.Thread(target=P4.move_robot_thread, args=[Station13_pos])
        th5 = th.Thread(target=P5.move_robot_thread, args=[Station12_pos])
        th6 = th.Thread(target=P6.move_robot_thread, args=[Station11_pos])
        th1.start()
        th2.start()
        th3.start()
        th4.start()
        th5.start()
        th6.start()
        th1.join()

    def next(self):
        return check_job_status_then_change_state(Shopfloor.transition_to_op60, Shopfloor.op60)


''' Entity and State Machine initialization. '''
# Define Station Positions for Products
init_pos_1 = [360, -800, 0]
init_pos_2 = [660, -800, 0]
init_pos_3 = [960, -800, 0]
init_pos_4 = [1260, -800, 0]
init_pos_5 = [1560, -800, 0]
init_pos_6 = [1860, -800, 0]
Station11_pos = [360, 550, 0]
Station12_pos = [360, 1650, 0]
Station13_pos = [360, 2750, 0]
Station14_pos = [360, 3850, 0]
Station15_pos = [360, 4950, 0]
Station16_pos = [360, 5000, 0]

# Instantiate general structure
Structure = Structure("Structure-001", "Structure1",
                      "structure", "Im a structure")

# Instantiate Zones
Station11 = Zone("Station11", "Station11", "stations",
                 "I'm Station 001!", Structure)
Station12 = Zone("Station12", "Station12", "stations",
                 "I'm Station 002!", Structure)
Station13 = Zone("Station13", "Station13", "stations",
                 "I'm Station 003!", Structure)
Station14 = Zone("Station14", "Station14", "stations",
                 "I'm Station 004!", Structure)
Station15 = Zone("Station15", "Station15", "stations",
                 "I'm Station 005!", Structure)
Station16 = Zone("Station16", "Station16", "stations",
                 "I'm Station 006!", Structure)
Robot1 = Zone("robotzone", "robotzone", "robots",
              "mobile robot area 1", Structure)
Halle = Zone("Halle", "Halle", "infrastructure", "Facility Layout", Structure)

Products = Zone("Products", "Products", "products",
                "Produktbeschreibung", Structure)

# Instantiate AGV
A1 = TwinAgv("Agv-001", "A1", "robots", "I'm AGV 001!", "agv", Robot1, facility_type="2", initial_euler=[0, 0, 0],
             initial_position=(1000, 0, 0), initial_orientation=[0, 0, 0, 0], current_station=Station11.header)

# Instantiate Mobile Robots
M1 = TwinAgv("MobileRobot-001", "M1", "robots", "I'm Mobile Robot 001!", "mobile", Robot1, facility_type="2", initial_euler=[0, 0, 0],
             initial_position=[1200, 0, 0], initial_orientation=[0, 0, 0, 0], current_station=Station12.header)
M2 = TwinAgv("MobileRobot-002", "M2", "robots", "I'm Mobile Robot 002!", "mobile", Robot1, facility_type="2", initial_euler=[0, 0, 0],
             initial_position=[1400, 0, 0], initial_orientation=[0, 0, 0, 0], current_station=Station12.header)

P1 = TwinAgv("Product-001", "P1", "products", "I'm product 001!", "mobile", Products, facility_type="Porsche_Panamera_Green_BP_2", initial_euler=[0, 0, 180],
             initial_position=init_pos_1, initial_orientation=[0, 0, 0, 0], current_station=Station11.header)

P2 = TwinAgv("Product-002", "P2", "products", "I'm product 002!", "mobile", Products, facility_type="Audi_a3_white", initial_euler=[0, 0, 180],
             initial_position=init_pos_2, initial_orientation=[0, 0, 0, 0], current_station=Station11.header)

P3 = TwinAgv("Product-003", "P3", "products", "I'm product 003!", "mobile", Products, facility_type="Audi_q2_red", initial_euler=[0, 0, 180],
             initial_position=init_pos_3, initial_orientation=[0, 0, 0, 0], current_station=Station11.header)

P4 = TwinAgv("Product-004", "P4", "products", "I'm product 004!", "mobile", Products, facility_type="BMW_i8_BP_red_2", initial_euler=[0, 0, 180],
             initial_position=init_pos_4, initial_orientation=[0, 0, 0, 0], current_station=Station11.header)

P5 = TwinAgv("Product-005", "P5", "products", "I'm product 005!", "mobile", Products, facility_type="ActrosBP_4", initial_euler=[0, 0, 180],
             initial_position=init_pos_5, initial_orientation=[0, 0, 0, 0], current_station=Station11.header)

P6 = TwinAgv("Product-006", "P6", "products", "I'm product 006!", "mobile", Products, facility_type="BMW_m2_coupe_BP_blue_4", initial_euler=[0, 0, 180],
             initial_position=init_pos_6, initial_orientation=[0, 0, 0, 0], current_station=Station11.header)
# Add Robots and AGVs to Robot-Zone
#Robot1.facilities.extend([A1.facility, M1.facility, M2.facility])
#Robot1.movers.extend([A1.mover, M1.mover, M2.mover])
# Robot1.update_state()

#Hallenfacility=facility("Halle",[4300,-3800,-2],[0,0,90], Halle,jtpath=CAD_PATH+"Halle_bereinigt.jt",)
Hallenareas = area([-600, -1440, -1], "WorkerArea", 4320, 8000, Halle)


# Halle.update_state()

# Initialise Areas:
Station11_area1 = area([0, 0, 0], "WorkerArea", 720, 1100, Station11)
Station12_area1 = area([0, 1100, 0], "WorkerArea", 720, 1100, Station12)
Station13_area1 = area([0, 2200, 0], "WorkerArea", 720, 1100, Station13)
Station14_area1 = area([0, 3300, 0], "WorkerArea", 720, 1100, Station14)

# Initialise Workers
Station11_worker1 = facility("operator11", [208, 510, 88], [
                             0, 0, 0],   Station11, facility_type="Brian_BP_5")
Station11_worker2 = facility("operator12", [208, 766, 88], [
                             0, 0, 0],   Station11, facility_type="Brian_BP_5")
Station11_worker3 = facility("operator13", [517, 645, 88], [
                             0, 0, 180], Station11, facility_type="Brian_BP_5")
Station12_worker1 = facility("operator21", [208, 1514, 88], [
                             0, 0, 0],  Station12, facility_type="Brian_BP_5")
Station12_worker2 = facility("operator22", [517, 1502, 88], [
                             0, 0, 180], Station12, facility_type="Brian_BP_5")
Station12_worker3 = facility("operator23", [573, 1801, 88], [
                             0, 0, 0],  Station12, facility_type="Brian_BP_5")
Station13_worker1 = facility("operator31", [208, 2652, 88], [
                             0, 0, 0],  Station13, facility_type="Brian_BP_5")
Station13_worker2 = facility("operator32", [517, 2645, 88], [
                             0, 0, 180], Station13, facility_type="Brian_BP_5")
Station14_worker1 = facility("operator41", [208, 3650, 88], [
                             0, 0, 0],  Station14, facility_type="Brian_BP_5")
Station14_worker2 = facility("operator42", [208, 4020, 88], [
                             0, 0, 0],  Station14, facility_type="Brian_BP_5")
Station14_worker3 = facility("operator43", [517, 3650, 88], [
                             0, 0, 180], Station14, facility_type="Brian_BP_5")
Station14_worker4 = facility("operator44", [517, 4020, 88], [
                             0, 0, 0],  Station14, facility_type="Brian_BP_5")

# Initialise Shelves
Station11_shelf1 = facility("Shelf11", [760, 150, 0], [
                            0, 0, 90], Station11, facility_type="14")
Station11_shelf2 = facility("Shelf12", [760, 400, 0], [
                            0, 0, 90], Station11, facility_type="14")
Station11_shelf3 = facility("Shelf13", [760, 650, 0], [
                            0, 0, 90], Station11, facility_type="14")
Station11_shelf4 = facility("Shelf14", [760, 900, 0], [
                            0, 0, 90], Station11, facility_type="14")
Station12_shelf1 = facility("Shelf21", [760, 1250, 0], [
                            0, 0, 90], Station12, facility_type="14")
Station12_shelf2 = facility("Shelf22", [760, 1500, 0], [
                            0, 0, 90], Station12, facility_type="14")
Station12_shelf3 = facility("Shelf23", [760, 1750, 0], [
                            0, 0, 90], Station12, facility_type="14")
Station12_shelf4 = facility("Shelf24", [760, 1900, 0], [
                            0, 0, 90], Station12, facility_type="14")
Station13_shelf1 = facility("Shelf31", [760, 2350, 0], [
                            0, 0, 90], Station13, facility_type="14")
Station13_shelf2 = facility("Shelf32", [760, 2600, 0], [
                            0, 0, 90], Station13, facility_type="14")
Station13_shelf3 = facility("Shelf33", [760, 2850, 0], [
                            0, 0, 90], Station13, facility_type="14")
Station13_shelf4 = facility("Shelf34", [760, 3100, 0], [
                            0, 0, 90], Station13, facility_type="14")
Station14_shelf1 = facility("Shelf41", [760, 3450, 0], [
                            0, 0, 90], Station14, facility_type="14")
Station14_shelf2 = facility("Shelf42", [760, 3700, 0], [
                            0, 0, 90], Station14, facility_type="14")
Station14_shelf3 = facility("Shelf43", [760, 3950, 0], [
                            0, 0, 90], Station14, facility_type="14")
Station14_shelf4 = facility("Shelf44", [760, 4200, 0], [
                            0, 0, 90], Station14, facility_type="14")

# Instantiate Operations
Op00 = Operation("OP-000", "Op00",
                 "operations", "Main frame preparation")
Op10 = Operation("OP-010", "Op10",
                 "operations", "Sub-assemble cross member")
Op20 = Operation("OP-020", "Op20",
                 "operations", "Assemble cross member")
Op30 = Operation("OP-030", "Op30",
                 "operations", "Assemble rear member")
Op40 = Operation("OP-040", "Op40",
                 "operations", "Assemble front member")
Op50 = Operation("OP-050", "Op50",
                 "operations", "Measurement")
Op60 = Operation("OP-060", "Op60",
                 "operations", "Disassembly")

# Instantiate Process Steps
Ps00 = ProcessStep("PS-000", "Ps00", "process_steps", "I'm Process Step 00!",
                   [copy.deepcopy(Op00)], Station11.header, nextPs="PS-001")
Ps01 = ProcessStep("PS-001", "Ps01", "process_steps", "I'm Process Step 01!",
                   [copy.deepcopy(Op10)], Station11.header, prevPs="PS-000", nextPs="PS-002")
Ps02 = ProcessStep("PS-002", "Ps02", "process_steps", "I'm Process Step 02!",
                   [copy.deepcopy(Op20)], Station12.header, prevPs="PS-001", nextPs="PS-003")
Ps03 = ProcessStep("PS-003", "Ps03", "process_steps", "I'm Process Step 03!",
                   [copy.deepcopy(Op30)], Station13.header, prevPs="PS-002", nextPs="PS-004")
Ps04 = ProcessStep("PS-004", "Ps04", "process_steps", "I'm Process Step 04!",
                   [copy.deepcopy(Op40)], Station14.header, prevPs="PS-003", nextPs="PS-005")
Ps05 = ProcessStep("PS-005", "Ps05", "process_steps", "I'm Process Step 05!",
                   [copy.deepcopy(Op50)], Station15.header, prevPs="PS-004", nextPs="PS-006")
Ps06 = ProcessStep("PS-006", "Ps06", "process_steps", "I'm Process Step 06!",
                   [copy.deepcopy(Op60)], Station16.header, prevPs="PS-005")

# Instantiate Stationary Robots
S1 = StationaryRobot("StationaryRobot-001", "S1", "robots", "I'm Stationary Robot 001!", "stationary",
                     initial_position=[615, 100, 0], initial_orientation=[0, 0, 0, 0], current_station=Station11.header)
S2 = StationaryRobot("StationaryRobot-002", "S2", "robots", "I'm Stationary Robot 002!", "stationary",
                     initial_position=[690, 100, 0], initial_orientation=[0, 0, 0, 0], current_station=Station11.header)
S3 = StationaryRobot("StationaryRobot-003", "S3", "robots", "I'm Stationary Robot 003!", "stationary",
                     initial_position=[685, 415, 0], initial_orientation=[0, 0, 0, 0], current_station=Station13.header)
S4 = StationaryRobot("StationaryRobot-004", "S4", "robots", "I'm Stationary Robot 004!", "stationary",
                     initial_position=[490, 600, 0], initial_orientation=[0, 0, 0, 0], current_station=Station12.header)
S5 = StationaryRobot("StationaryRobot-005", "S5", "robots", "I'm Stationary Robot 005!", "stationary",
                     initial_position=[490, 320, 0], initial_orientation=[0, 0, 0, 0], current_station=Station14.header)
S6 = StationaryRobot("StationaryRobot-006", "S6", "robots", "I'm Stationary Robot 006!", "stationary",
                     initial_position=[490, 270, 0], initial_orientation=[0, 0, 0, 0], current_station=Station14.header)


# List of entities that have the reset() method
Shopfloor.resettable_entities = [S1, S2, S3, S4, S5, S6,
                                 M1, M2,
                                 A1,
                                 ]

# List of entities that publish data to MQTT
Shopfloor.publishing_entities = [S1, S2, S3, S4, S5, S6,
                                 M1, M2,
                                 A1,
                                 P1, P2, P3, P4, P5, P6,
                                 Robot1, Structure, Halle, Station11, Station12, Station13, Station14, Station15, Station16, Products
                                 ]

# Initialize Job management related variables
Shopfloor.job_queue = []
Shopfloor.job_count = 0  # How many Jobs have been created
Shopfloor.current_job = None  # Will store ref to Job objects
Shopfloor.prev_state = None  # Will store a ref to the previous State

# MQTT Publisher and Subscriber
Shopfloor.publisher = ShopfloorPublisher(
    name="MQTT-P",
    publishing_entities=Shopfloor.publishing_entities,
    run_event_check_sleep=EVENT_SLEEP)

Shopfloor.subscriber = JobManager(
    name="MQTT-S",
    subscribed_topics=[ROOT_TOPIC+"jobs/+/status", "/VR/viewer_info/tooltip_request"])

# Create 3 Jobs

create_job("Porsche1", [copy.deepcopy(Ps00), copy.deepcopy(Ps01), copy.deepcopy(
    Ps02), copy.deepcopy(Ps03), copy.deepcopy(Ps04), copy.deepcopy(Ps05), copy.deepcopy(Ps06)])
create_job("Porsche2", [copy.deepcopy(Ps03), copy.deepcopy(
    Ps04), copy.deepcopy(Ps05), copy.deepcopy(Ps06)])
create_job("Porsche3", [copy.deepcopy(Ps05), copy.deepcopy(Ps06)])


# Stationary variable initialization (State registration):
Shopfloor.on_hold = OnHold()
Shopfloor.idle = Idle()
Shopfloor.begin_job = BeginJob()
Shopfloor.finish_job = FinishJob()
Shopfloor.op00 = OP00()
Shopfloor.op10 = OP10()
Shopfloor.op20 = OP20()
Shopfloor.op30 = OP30()
Shopfloor.op40 = OP40()
Shopfloor.op50 = OP50()
Shopfloor.op60 = OP60()
Shopfloor.reset = Reset()
Shopfloor.transition_to_op10 = TransitionToOP10()
Shopfloor.transition_to_op20 = TransitionToOP20()
Shopfloor.transition_to_op30 = TransitionToOP30()
Shopfloor.transition_to_op40 = TransitionToOP40()
Shopfloor.transition_to_op50 = TransitionToOP50()
Shopfloor.transition_to_op60 = TransitionToOP60()
