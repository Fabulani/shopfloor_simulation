"""
    Barebones implementation of a scenario with a conditional shutdown state. 
    The goal was to implement conditional state transitions. 
    
    Possible applications: only transition to a certain state if a condition applies,
    for example a flag is triggered signaling a shutdown.

    State flow: State01 <-(loop)-> State02 -(condition)-> Shutdown (end)
"""

from time import sleep
from shopfloor_simulation.state_machine import State, StateMachine

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


# State definition
Scenario.state01 = State01()
Scenario.state02 = State02()
Scenario.shutdown = Shutdown()

# Boolean to control state machine shutdown
Scenario.isActive = True

# Counter for how many times the State Machine has looped
Scenario.loop_counter = 0
