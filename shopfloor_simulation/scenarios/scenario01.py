import copy
from time import sleep
from shopfloor_simulation.state_machine import State, StateMachine
from shopfloor_simulation.entities import StationaryRobot, MobileRobot, Agv, Station, Job, ProcessStep, Operation
from shopfloor_simulation.mqtt_utils import JobManager, ShopfloorPublisher


STATE_SLEEP = 0.5  # Amount of time to wait between states.


''' Helper function definitions '''
# These functions are specific to this scenario.


def create_job():
    ''' Create a new Job and add it to the Job Queue.

        - The Job ID is determined by the lenght of the Job queue.
        - The new Job does a deepcopy of the ProcessSteps to create entirely new
        and independent Process Steps.
        - The new Job is then appended to the appropriate lists and its topic
        is initialized.
    '''
    ''' #! ISSUE
    #! Deepcopy solves the issues of Jobs overwriting info on other Job objects,
    #! but it doesn't solve the issue of overwriting the PS's and OP's
    #! MQTT topics. Still, inside the Job topic, the PS and OP info should be OK.
    '''
    job_id = Shopfloor.job_count + 1
    new_job = Job(
        _id="JOB-" + str(job_id),
        name="J" + str(job_id),
        namespace="jobs",
        description="I'm Job " + str(job_id) + "!",
        process_steps=[
            copy.deepcopy(Ps00),
            copy.deepcopy(Ps01),
            copy.deepcopy(Ps02),
            copy.deepcopy(Ps03),
            copy.deepcopy(Ps04),
            copy.deepcopy(Ps05),
            copy.deepcopy(Ps06)]
    )
    Shopfloor.job_queue.append(new_job)
    Shopfloor.publishing_entities.append(new_job)
    Shopfloor.publisher.initialize_single_topic(new_job)
    Shopfloor.job_count += 1

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


class OP00(State):
    def run(self):
        Shopfloor.current_job.begin_process_step(0)

        sleep(STATE_SLEEP)
        Shopfloor.current_job.finish_process_step(0)

    def next(self):
        return check_job_status_then_change_state(Shopfloor.op00, Shopfloor.op10)


class OP10(State):
    def run(self):
        Shopfloor.current_job.begin_process_step(1)

        S1.status = 'BUSY'
        S2.status = 'BUSY'
        A1.status = 'BUSY'
        A1.current_station = Station1.header

        sleep(STATE_SLEEP)
        Shopfloor.current_job.finish_process_step(1)
        S1.reset()
        S2.reset()

    def next(self):
        return check_job_status_then_change_state(Shopfloor.op10, Shopfloor.transition_to_op20)


class OP20(State):
    def run(self):
        A1.current_station = Station2.header
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
        A1.current_station = Station3.header
        M1.current_station = Station3.header
        M2.current_station = Station3.header
        Shopfloor.current_job.begin_process_step(3)
        S3.status = 'BUSY'

        sleep(STATE_SLEEP)
        Shopfloor.current_job.finish_process_step(3)
        S3.reset()

    def next(self):
        return check_job_status_then_change_state(Shopfloor.op30, Shopfloor.transition_to_op40)


class OP40(State):
    def run(self):
        A1.current_station = Station4.header
        M1.current_station = Station4.header
        M2.current_station = Station4.header
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
        A1.current_station = Station5.header
        Shopfloor.current_job.begin_process_step(5)

        sleep(STATE_SLEEP)
        Shopfloor.current_job.finish_process_step(5)

    def next(self):
        return check_job_status_then_change_state(Shopfloor.op50, Shopfloor.transition_to_op60)


class OP60(State):
    def run(self):
        A1.current_station = Station6.header
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
        A1.current_station = Station1.header
        M1.current_station = Station2.header
        M2.current_station = Station2.header
        create_job()
        sleep(5)

    def next(self):
        return Shopfloor.idle


class TransitionToOP20(State):
    '''Transition State from OP10 to OP20'''

    def run(self):
        A1.move_robot((370, 530, 0))
        sleep(STATE_SLEEP)

    def next(self):
        return check_job_status_then_change_state(Shopfloor.transition_to_op20, Shopfloor.op20)


class TransitionToOP30(State):
    '''Transition State from OP20 to OP30'''

    def run(self):
        M1.move_robot((600, 360, 0))
        M2.move_robot((600, 470, 0))
        A1.move_robot((480, 400, 0))
        sleep(STATE_SLEEP)

    def next(self):
        return check_job_status_then_change_state(Shopfloor.transition_to_op30, Shopfloor.op30)


class TransitionToOP40(State):
    '''Transition State from OP30 to OP40'''

    def run(self):
        M1.move_robot((375, 245, 0))
        M2.move_robot((375, 345, 0))
        A1.move_robot((250, 300, 0))
        sleep(STATE_SLEEP)

    def next(self):
        return check_job_status_then_change_state(Shopfloor.transition_to_op40, Shopfloor.op40)


class TransitionToOP50(State):
    '''Transition State from OP40 to OP50'''

    def run(self):
        A1.move_robot((250, 200, 0))
        sleep(STATE_SLEEP)

    def next(self):
        return check_job_status_then_change_state(Shopfloor.transition_to_op50, Shopfloor.op50)


class TransitionToOP60(State):
    '''Transition State from OP50 to OP60'''

    def run(self):
        A1.move_robot((250, 100, 0))
        sleep(STATE_SLEEP)

    def next(self):
        return check_job_status_then_change_state(Shopfloor.transition_to_op60, Shopfloor.op60)


''' Entity and State Machine initialization. '''
# Instantiate Stations
Station1 = Station("Station-001", "Station1", "stations", "I'm Station 001!")
Station2 = Station("Station-002", "Station2", "stations", "I'm Station 002!")
Station3 = Station("Station-003", "Station3", "stations", "I'm Station 003!")
Station4 = Station("Station-004", "Station4", "stations", "I'm Station 004!")
Station5 = Station("Station-005", "Station5", "stations", "I'm Station 005!")
Station6 = Station("Station-006", "Station6", "stations", "I'm Station 006!")

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
                   [copy.deepcopy(Op00)], Station1.header)
Ps01 = ProcessStep("PS-001", "Ps01", "process_steps", "I'm Process Step 01!",
                   [copy.deepcopy(Op10)], Station1.header)
Ps02 = ProcessStep("PS-002", "Ps02", "process_steps", "I'm Process Step 02!",
                   [copy.deepcopy(Op20)], Station2.header)
Ps03 = ProcessStep("PS-003", "Ps03", "process_steps", "I'm Process Step 03!",
                   [copy.deepcopy(Op30)], Station3.header)
Ps04 = ProcessStep("PS-004", "Ps04", "process_steps", "I'm Process Step 04!",
                   [copy.deepcopy(Op40)], Station4.header)
Ps05 = ProcessStep("PS-005", "Ps05", "process_steps", "I'm Process Step 05!",
                   [copy.deepcopy(Op50)], Station5.header)
Ps06 = ProcessStep("PS-006", "Ps06", "process_steps", "I'm Process Step 06!",
                   [copy.deepcopy(Op60)], Station6.header)

# Instantiate Stationary Robots
S1 = StationaryRobot("Stationary-Robot-001", "S1", "robots", "I'm Stationary Robot 001!", "stationary",
                     initial_position=[615, 100, 0], initial_orientation=[0, 0, 0, 0], current_station=Station1.header)
S2 = StationaryRobot("Stationary-Robot-002", "S2", "robots", "I'm Stationary Robot 002!", "stationary",
                     initial_position=[690, 100, 0], initial_orientation=[0, 0, 0, 0], current_station=Station1.header)
S3 = StationaryRobot("Stationary-Robot-003", "S3", "robots", "I'm Stationary Robot 003!", "stationary",
                     initial_position=[685, 415, 0], initial_orientation=[0, 0, 0, 0], current_station=Station3.header)
S4 = StationaryRobot("Stationary-Robot-004", "S4", "robots", "I'm Stationary Robot 004!", "stationary",
                     initial_position=[490, 600, 0], initial_orientation=[0, 0, 0, 0], current_station=Station2.header)
S5 = StationaryRobot("Stationary-Robot-005", "S5", "robots", "I'm Stationary Robot 005!", "stationary",
                     initial_position=[490, 320, 0], initial_orientation=[0, 0, 0, 0], current_station=Station4.header)
S6 = StationaryRobot("Stationary-Robot-006", "S6", "robots", "I'm Stationary Robot 006!", "stationary",
                     initial_position=[490, 270, 0], initial_orientation=[0, 0, 0, 0], current_station=Station4.header)

# Instantiate Mobile Robots
M1 = MobileRobot("Mobile-Robot-001", "M1", "robots", "I'm Mobile Robot 001!", "mobile",
                 initial_position=[450, 590, 0], initial_orientation=[0, 0, 0, 0], current_station=Station2.header)
M2 = MobileRobot("Mobile-Robot-002", "M2", "robots", "I'm Mobile Robot 002!", "mobile",
                 initial_position=[450, 485, 0], initial_orientation=[0, 0, 0, 0], current_station=Station2.header)

# Instantiate AGV
A1 = Agv("AGV-001", "A1", "robots", "I'm AGV 001!", "agv",
         initial_position=(650, 160, 0), initial_orientation=[0, 0, 0, 0], current_station=Station1.header)

# List of entities that have the reset() method
Shopfloor.resettable_entities = [S1, S2, S3, S4, S5, S6,
                                 M1, M2,
                                 A1,
                                 ]

# List of entities that publish data to MQTT
Shopfloor.publishing_entities = [Station1, Station2, Station3, Station4, Station5, Station6,
                                 S1, S2, S3, S4, S5, S6,
                                 M1, M2,
                                 A1,
                                 ]

# Initialize Job management related variables
Shopfloor.job_queue = []
Shopfloor.job_count = 0  # How many Jobs have been created
Shopfloor.current_job = None  # Will store ref to Job objects
Shopfloor.prev_state = None  # Will store a ref to the previous State

# MQTT Publisher and Subscriber
Shopfloor.publisher = ShopfloorPublisher(
    name="MQTT-P",
    publishing_entities=Shopfloor.publishing_entities)
Shopfloor.subscriber = JobManager(
    name="MQTT-S",
    subscribed_topics=["freeaim/echo/jobs/+/status"])

# Create the first Job
create_job()

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
Shopfloor.transition_to_op20 = TransitionToOP20()
Shopfloor.transition_to_op30 = TransitionToOP30()
Shopfloor.transition_to_op40 = TransitionToOP40()
Shopfloor.transition_to_op50 = TransitionToOP50()
Shopfloor.transition_to_op60 = TransitionToOP60()
