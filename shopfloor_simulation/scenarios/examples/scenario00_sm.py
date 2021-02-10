''' Minimum Working Example: State Machine with conditional transitions. '''
# Initial -> State01 -> State02 -> State01 (repeat)
#                               -> State03 (if go_to_state03) -> State01 (repeat)

from shopfloor_simulation.state_machine import State, StateMachine


class Scenario_00(StateMachine):
    def __init__(self):
        # Initial state
        StateMachine.__init__(self, Scenario_00.initial_state)

    def runAll(self):
        global go_to_state03
        i = 0
        while True:
            if (i == 3):
                # Enable transition to State 03.
                go_to_state03 = True
            elif (i == 6):
                # Stop the State Machine.
                break
            self.currentState = self.currentState.next()
            self.currentState.run()
            i += 1


class Initial(State):
    ''' Initial state. '''

    def run(self):
        print("Initial State executed!")

    def next(self):
        return Scenario_00.state_01


class State01(State):
    ''' State 01: transition to State 02. '''

    def run(self):
        print("State 01 executed!")

    def next(self):
        return Scenario_00.state_02


class State02(State):
    ''' State 02: transition back to State 01, or to State 03 if `go_to_state03` is True. '''

    def run(self):
        print("State 02 executed!")

    def next(self):
        ''' Conditional transition: '''
        if (go_to_state03):
            return Scenario_00.state_03
        else:
            return Scenario_00.state_01


class State03(State):
    ''' State 03: end the State Machine. '''

    def run(self):
        print("State 03 executed!")

    def next(self):
        return Scenario_00.state_01


# Static variable initialization (State registration):
Scenario_00.entities = []  # Necessary because of MQTT. #TODO
Scenario_00.initial_state = Initial()
Scenario_00.state_01 = State01()
Scenario_00.state_02 = State02()
Scenario_00.state_03 = State03()

# Transition variable
go_to_state03 = False
