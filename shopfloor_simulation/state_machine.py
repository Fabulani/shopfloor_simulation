from shopfloor_simulation.entities import Job
import copy

''' State Machine and State definition '''
# as described in: https://python-3-patterns-idioms-test.readthedocs.io/en/latest/StateMachine.html


class State:
    '''
    Defines a State inside a State Machine.
    Any states created should inherit from this class.
    '''

    def run(self):
        ''' What happens inside the State. '''
        assert 0, "run not implemented"

    def next(self):
        ''' Rules for deciding which should the next State be. '''
        assert 0, "next not implemented"


class StateMachine:
    '''
    Defines a State Machine.
    Any state machine created should inherit from this class.
    '''

    def __init__(self, initial_state):
        ''' Set and run the initial State. '''
        self.current_state = initial_state
        self.current_state.run()

    def runAll(self):
        ''' Run States indefinitly, according to the rules set inside its `next` methods. '''
        while True:
            self.current_state = self.current_state.next()
            self.current_state.run()

    def log_state_flow(self, prev_state_info, state_info, repeats):
        """
            Print the current state in every transition. Repeated states will
            increase a counter in the log.

            Initialize `prev_state_info`, `state_info`, and `repeats` outside of
            the StateMachine loop (inside the runAll method) and pass them to this
            method inside the loop.

            An example implementation can be found in `scenarioXX.py`.
        """

        # Format the state's class name into a string.
        state_info = "[#] " + self.current_state.__class__.__name__

        if state_info != prev_state_info and repeats > 0:
            # New state, and previous logs were repeating. Add a newline to avoid overwriting it.
            repeats = 0
            print("\n" + state_info)
        elif state_info != prev_state_info and repeats == 0:
            # New state, and previous logs weren't repeating. Print normally.
            print(state_info)
        else:
            # Repeated state. Increment the counter and print on the same line.
            repeats += 1
            print(state_info + " x" + str(repeats), end='\r')

        # Update prev_state_info
        prev_state_info = state_info

        # Return updated values
        return prev_state_info, state_info, repeats


class SimulatedScenario(StateMachine):
    def __init__(self, initial_state):
        # MQTT related properties
        self.mqtt = None  # A ref to the MQTT Client object
        self.resettable_entities = []  # Objects that have a reset() method
        self.publishing_entities = []  # Objects that will publish via MQTT

        # Job related properties
        self.job_queue = []  # Queue with incoming Jobs
        self.job_update_queue = []  # Queue with updates regarding Jobs' status
        self.job_count = 0  # How many Jobs have been created
        self.current_job = None  # Will store ref to Job objects

        # State flow related properties
        self.manager = None  # A ref to the Scenario Manager
        self.is_active = True  # Signals if the state machine should keep running
        self.prev_state = None  # Will store a ref to the previous State
        self.flexibility = None  # The flexibility id of the scenario

        # Threading related properties
        self.run_event = None  # threading.run_event() for synced thread shut down

        # Set and run the initial State
        self.current_state = initial_state
        self.current_state.run()

    def check_job_status_then_change_state(self, current_state, next_state, shutdown_state):
        ''' Wrapper for the logic to check the Job status before state transition.

            Since it's more straightfoward to have this check inside every State's
            `next()` method (to avoid logic spaghetti in the StateMachine class),
            this function will wrap the logic for easier maintenance.

            Check the current Job status:
            - If it's `IN_PROGRESS`, maintain normal state flow.
            - If it's `ON_HOLD`, assign the current state to the prev_state variable
            and then transition to the OnHold State.
        '''

        # Selected flexibility was changed. Transition to shutdown to allow Scenario change.
        if self.flexibility != self.manager.selected_flexibility:
            return shutdown_state

        # Job is set to IN_PROGRESS again. Continue state flow.
        elif self.current_job.status == "IN_PROGRESS":
            return next_state

        # Job is still ON_HOLD. Stay in the on_hold state
        elif self.current_job.status == "ON_HOLD":
            self.prev_state = current_state
            return self.on_hold

    def update_current_job(self):
        """ Update the ref to the current job, if a Job with status IN_PROGRESS
            exists in the job queue.
        """
        job_incoming = len(self.job_queue) > 0
        if job_incoming:
            for job in self.job_queue:
                if job.status == "IN_PROGRESS":
                    self.current_job = job
                    return

    def update_jobs(self):
        ''' Search the Job Queue and update the Jobs with their new statuses.

            Check if there are Job updates. For every one of them, search the
            `job_queue` for a matching id and apply the new status.
        '''
        if len(self.job_update_queue) > 0:
            # Loop through the new Job updates
            for (job_id, new_status) in self.job_update_queue:
                # Loop through the existing Jobs inside the job_queue
                for job in self.job_queue:
                    # Search for a matching id. If found, apply the new status
                    if job.header._id == job_id:
                        job.status = new_status
                        break
            # Empty the update queue
            self.job_update_queue = []

    def create_job(self, jobname, process_steps: list):
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

        job_id = self.job_count + 1

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
            process_steps=[copy.deepcopy(ps) for ps in process_steps]
        )

        # Setup the new Job in the simulation
        self.job_queue.append(new_job)
        self.publishing_entities.append(new_job)
        self.mqtt.initialize_single_topic(new_job)
        self.job_count += 1

        # Setup the Job's process steps
        for ps in new_job.process_steps:
            for op in ps.operations:
                self.publishing_entities.append(op)
                self.mqtt.initialize_single_topic(op)
            self.publishing_entities.append(ps)
            self.mqtt.initialize_single_topic(ps)
