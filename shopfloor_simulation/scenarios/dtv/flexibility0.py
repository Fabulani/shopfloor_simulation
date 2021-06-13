import copy
import threading as th
from time import sleep

from shopfloor_simulation.entities import (Agv, Job, MobileRobot, Operation,
                                           ProcessStep, Station,
                                           StationaryRobot, Structure, TwinAgv,
                                           Zone, area, facility)
from shopfloor_simulation.mqtt_utils import DTVMqttClient
from shopfloor_simulation.settings import ROOT_TOPIC
from shopfloor_simulation.state_machine import SimulatedScenario, State

# Path to CAD files folder
CAD_PATH = "C:\Git\WZL\2020_Team_Visualization\Visualization\ThingWorx\shopfloor_simulation\shopfloor_simulation\twin_scripts\CAD"

# Scenario specific properties
SCENARIO_NAME = __file__.split("\\")[-1].replace(".py", "")  # Filename w/o ext
FLEXIBILITY = 0  # The flexibility of this scenario (similar to its id)
STATE_SLEEP = 2  # Amount of time to wait between states.
EVENT_SLEEP = 0.01


''' State Machine and States setup. '''


class Shopfloor(SimulatedScenario):
    def __init__(self, scenario_manager):
        print("[#] Initializing Scenario " + SCENARIO_NAME)

        # The reference to the Scenario Manager
        Shopfloor.manager = scenario_manager

        # Add the Scenario Manager to the publishing entities list
        Shopfloor.publishing_entities.append(scenario_manager)

        # Start the State Machine
        SimulatedScenario.__init__(self, Shopfloor.initialize)

    def runAll(self):
        # Boolean to control state machine shutdown
        Shopfloor.is_active = True

        # State flow logging variables
        prev_state_info = ""
        state_info = ""
        repeats = 0  # How many times has the same state_info been repeated

        while Shopfloor.is_active:
            # Update the Shopfloor Jobs' statuses
            Shopfloor.update_jobs(self=Shopfloor)

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
        # Initialize Job management related variables
        Shopfloor.job_queue = []  # Queue with incoming Jobs
        Shopfloor.job_update_queue = []  # Queue with updates regarding Jobs' status
        Shopfloor.job_count = 0  # How many Jobs have been created
        Shopfloor.current_job = None  # Will store ref to Job objects

        # Initialize MQTT client object
        Shopfloor.mqtt = DTVMqttClient(
            name="MQTT-" + SCENARIO_NAME,
            subscribed_topics=[
                ROOT_TOPIC + "scenario_manager/DTV-000/+",
                ROOT_TOPIC + "jobs/+/status",
                "/VR/viewer_info/tooltip_request"
            ],
            publishing_entities=Shopfloor.publishing_entities,
            scenario_manager=Shopfloor.manager,
            scenario=Shopfloor,
            run_event_check_sleep=EVENT_SLEEP
        )

        # Thread for parallel continuous publishing
        Shopfloor.mqtt_thread = th.Thread(
            target=Shopfloor.mqtt.publish_thread,
            args=[Shopfloor.run_event],
            daemon=True
        )

        # Enable the run_event
        Shopfloor.run_event.set()

        # Start the MQTT thread
        Shopfloor.mqtt_thread.start()

        # Create 3 Jobs
        Shopfloor.create_job(Shopfloor, "Porsche1", [
                             Ps00, Ps01, Ps02, Ps03, Ps04, Ps05, Ps06])
        Shopfloor.create_job(Shopfloor, "Porsche2", [Ps03, Ps04, Ps05, Ps06])
        Shopfloor.create_job(Shopfloor, "Porsche3", [Ps05, Ps06])

        sleep(3)

    def next(self):
        return Shopfloor.idle


class Shutdown(State):
    def run(self):
        # Disable the scenario.
        Shopfloor.is_active = False

        # Clear the run_event to shutdown threads.
        Shopfloor.run_event.clear()

        # Wait for the MQTT thread to finish.
        Shopfloor.mqtt_thread.join()

        sleep(STATE_SLEEP)

    def next(self):
        return Shopfloor.initialize


class OnHold(State):
    ''' Stop the simulation by doing nothing and loop on itself.

        This State will be triggered if the current Job has status `ON_HOLD`.
        It'll go back to the previous state if the current Job status goes back
        to `IN_PROGRESS`.
    '''

    def run(self):
        sleep(STATE_SLEEP)

    def next(self):
        if Shopfloor.manager.selected_flexibility != Shopfloor.flexibility:
            return Shopfloor.shutdown
        elif Shopfloor.current_job.status == "IN_PROGRESS":
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
        Shopfloor.update_current_job(self=Shopfloor)
        sleep(STATE_SLEEP)

    def next(self):
        if Shopfloor.manager.selected_flexibility != Shopfloor.flexibility:
            return Shopfloor.shutdown
        elif Shopfloor.current_job == None:
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
        return Shopfloor.check_job_status_then_change_state(Shopfloor, Shopfloor.begin_job, Shopfloor.op00, Shopfloor.shutdown)
        # check for process step list and which ohne is the next one
        # once all steps are done, go to finish state


class OP00(State):
    def run(self):
        Shopfloor.current_job.begin_process_step(0)

        sleep(STATE_SLEEP)
        Shopfloor.current_job.finish_process_step(0)

    def next(self):
        return Shopfloor.check_job_status_then_change_state(Shopfloor, Shopfloor.op00, Shopfloor.transition_to_op10, Shopfloor.shutdown)


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
        return Shopfloor.check_job_status_then_change_state(Shopfloor, Shopfloor.op10, Shopfloor.transition_to_op20, Shopfloor.shutdown)


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
        return Shopfloor.check_job_status_then_change_state(Shopfloor, Shopfloor.op20, Shopfloor.transition_to_op30, Shopfloor.shutdown)


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
        return Shopfloor.check_job_status_then_change_state(Shopfloor, Shopfloor.op30, Shopfloor.transition_to_op40, Shopfloor.shutdown)


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
        return Shopfloor.check_job_status_then_change_state(Shopfloor, Shopfloor.op40, Shopfloor.transition_to_op50, Shopfloor.shutdown)


class OP50(State):
    def run(self):
        A1.current_station = Station15.header
        Shopfloor.current_job.begin_process_step(5)

        sleep(STATE_SLEEP)
        Shopfloor.current_job.finish_process_step(5)

    def next(self):
        return Shopfloor.check_job_status_then_change_state(Shopfloor, Shopfloor.op50, Shopfloor.transition_to_op60, Shopfloor.shutdown)


class OP60(State):
    def run(self):
        A1.current_station = Station16.header
        Shopfloor.current_job.begin_process_step(6)

        sleep(STATE_SLEEP)
        Shopfloor.current_job.finish_process_step(6)

    def next(self):
        return Shopfloor.check_job_status_then_change_state(Shopfloor, Shopfloor.op60, Shopfloor.finish_job, Shopfloor.shutdown)


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
        Shopfloor.create_job(Shopfloor, "Porsche1", [
                             Ps00, Ps01, Ps02, Ps03, Ps04, Ps05, Ps06])
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
        return Shopfloor.check_job_status_then_change_state(Shopfloor, Shopfloor.transition_to_op10, Shopfloor.op10, Shopfloor.shutdown)


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
        return Shopfloor.check_job_status_then_change_state(Shopfloor, Shopfloor.transition_to_op20, Shopfloor.op20, Shopfloor.shutdown)


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
        return Shopfloor.check_job_status_then_change_state(Shopfloor, Shopfloor.transition_to_op30, Shopfloor.op30, Shopfloor.shutdown)


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
        return Shopfloor.check_job_status_then_change_state(Shopfloor, Shopfloor.transition_to_op40, Shopfloor.op40, Shopfloor.shutdown)


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
        return Shopfloor.check_job_status_then_change_state(Shopfloor, Shopfloor.transition_to_op50, Shopfloor.op50, Shopfloor.shutdown)


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
        return Shopfloor.check_job_status_then_change_state(Shopfloor, Shopfloor.transition_to_op60, Shopfloor.op60, Shopfloor.shutdown)


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


# Initialize State flow variables
Shopfloor.prev_state = None  # Will store a ref to the previous State
Shopfloor.flexibility = FLEXIBILITY  # The scenario's flexibility id

# Initialize thread related variables
Shopfloor.run_event = th.Event()

# Stationary variable initialization (State registration):
Shopfloor.initialize = Initialize()
Shopfloor.shutdown = Shutdown()
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
