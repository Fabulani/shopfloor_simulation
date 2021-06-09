"""
    Barebones implementation of a scenario with a shutdown state. The goal was
    to implement a way to exit the scenario. 
    
    Possible applications: multiple scenarios must be executed. Use the shutdown
    state to exit one scenario and then start another from a top-level file.

    State flow: State01 -> State02 -> Shutdown (end)
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

        while Scenario.is_active:
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
        sleep(STATE_SLEEP)

    def next(self):
        return Scenario.state02


class State02(State):
    def run(self):
        sleep(STATE_SLEEP)

    def next(self):
        return Scenario.shutdown


class Shutdown(State):
    def run(self):
        Scenario.is_active = False
        sleep(STATE_SLEEP)

    def next(self):
        return Scenario.shutdown


# State definition
Scenario.state01 = State01()
Scenario.state02 = State02()
Scenario.shutdown = Shutdown()

# Boolean to control state machine shutdown
Scenario.is_active = True
