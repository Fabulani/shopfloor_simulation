import json
from time import sleep
from random import randint
from mpmath import *
from math import sqrt
from shopfloor_simulation.state_machine import State, StateMachine
from shopfloor_simulation.entities import StaticRobot, MobileRobot, AGV, Station, Job, ShopfloorManager


STATE_SLEEP = 2  # Amount of time to wait between states.


''' State Machine and States setup. '''
# The State Machine is a cycle: Idle -> OP10 -> TransitionToOP20 -> OP20 -> ... -> TransitionToIdle -> Idle
# Note about TransitionToOP10: this State was discarded since all the robots are already positioned correctly in the TransitionToIdle State.
# This means that OP10 can start without having to move Robots around from the previous State (Idle). This is not the case for other OPs.


class ShopFloor(StateMachine):
    def __init__(self):
        # Initial state
        print("[STATE] Idle")
        StateMachine.__init__(self, ShopFloor.idle)

    def runAll(self):
        ''' (OVERRIDDEN) Print the current state before executing it. '''
        while True:
            self.currentState = self.currentState.next()
            print("[STATE] " + self.currentState.__class__.__name__)
            self.currentState.run()


class Idle(State):
    '''Idle State where nothing happens'''

    def run(self):
        sleep(STATE_SLEEP)

    def next(self):
        return ShopFloor.op10


class OP10(State):
    def run(self):
        J1.begin_step(Station1.op)
        J1.status = 'underway'
        S1.status = 'busy'
        S2.status = 'busy'
        A1.status = 'busy'
        S1.update_tcp()
        S2.update_tcp()

        sleep(STATE_SLEEP)
        J1.complete_step(Station1.op)
        S1.reset()
        S2.reset()

    def next(self):
        return ShopFloor.transition_to_op20


class OP20(State):
    def run(self):
        J1.begin_step(Station2.op)
        S4.status = 'busy'
        M1.status = 'busy'
        M2.status = 'busy'
        S4.update_tcp()
        M1.update_tcp()
        M2.update_tcp()

        sleep(STATE_SLEEP)
        J1.complete_step(Station2.op)
        S4.reset()

    def next(self):
        return ShopFloor.transition_to_op30


class OP30(State):
    def run(self):
        J1.begin_step(Station3.op)
        S3.status = 'busy'
        S3.update_tcp()
        M1.update_tcp()
        M2.update_tcp()

        sleep(STATE_SLEEP)
        J1.complete_step(Station3.op)
        S3.reset()

    def next(self):
        return ShopFloor.transition_to_op40


class OP40(State):
    def run(self):
        J1.begin_step(Station4.op)
        S5.status = 'busy'
        S6.status = 'busy'
        S5.update_tcp()
        S6.update_tcp()
        M1.update_tcp()
        M2.update_tcp()

        sleep(STATE_SLEEP)
        J1.complete_step(Station4.op)
        S5.reset()
        S6.reset()
        M1.reset()
        M2.reset()

    def next(self):
        return ShopFloor.transition_to_op50


class OP50(State):
    def run(self):
        J1.begin_step(Station5.op)

        sleep(STATE_SLEEP)
        J1.complete_step(Station5.op)

    def next(self):
        return ShopFloor.transition_to_op60


class OP60(State):
    def run(self):
        J1.begin_step(Station6.op)

        sleep(STATE_SLEEP)
        J1.complete_step(Station6.op)
        J1.status = 'completed'

    def next(self):
        return ShopFloor.transition_to_idle


class TransitionToIdle(State):
    '''Transition State from OP60 to Idle'''

    def run(self):
        for entity in ShopFloor.entities:
            entity.reset()
        sleep(5)

    def next(self):
        return ShopFloor.idle


class TransitionToOP20(State):
    '''Transition State from OP10 to OP20'''

    def run(self):
        A1.move_robot(Station2.pos)
        sleep(STATE_SLEEP)

    def next(self):
        return ShopFloor.op20


class TransitionToOP30(State):
    '''Transition State from OP20 to OP30'''

    def run(self):
        M1.move_robot((600, 360, 0))
        M2.move_robot((600, 470, 0))
        A1.move_robot(Station3.pos)
        sleep(STATE_SLEEP)

    def next(self):
        return ShopFloor.op30


class TransitionToOP40(State):
    '''Transition State from OP30 to OP40'''

    def run(self):
        M1.move_robot((375, 245, 0))
        M2.move_robot((375, 345, 0))
        A1.move_robot(Station4.pos)
        sleep(STATE_SLEEP)

    def next(self):
        return ShopFloor.op40


class TransitionToOP50(State):
    '''Transition State from OP40 to OP50'''

    def run(self):
        A1.move_robot(Station5.pos)
        sleep(STATE_SLEEP)

    def next(self):
        return ShopFloor.op50


class TransitionToOP60(State):
    '''Transition State from OP50 to OP60'''

    def run(self):
        A1.move_robot(Station6.pos)
        sleep(STATE_SLEEP)

    def next(self):
        return ShopFloor.op60


''' Entity and State Machine initialization. '''
# Instantiate Stations
Station1 = Station((650, 160, 0), 'OP10')
Station2 = Station((370, 530, 0), 'OP20')
Station3 = Station((480, 400, 0), 'OP30')
Station4 = Station((250, 300, 0), 'OP40')
Station5 = Station((250, 200, 0), 'OP50')
Station6 = Station((250, 100, 0), 'OP60')

# Instantiate Static Robots
S1 = StaticRobot((615, 100, 0), 'idle', 'static', "S1", "Static-Robot-001")
S2 = StaticRobot((690, 100, 0), 'idle', 'static', "S2", "Static-Robot-002")
S3 = StaticRobot((685, 415, 0), 'idle', 'static', "S3", "Static-Robot-003")
S4 = StaticRobot((490, 600, 0), 'idle', 'static', "S4", "Static-Robot-004")
S5 = StaticRobot((490, 320, 0), 'idle', 'static', "S5", "Static-Robot-005")
S6 = StaticRobot((490, 270, 0), 'idle', 'static', "S6", "Static-Robot-006")

# Instantiate Mobile Robots
M1 = MobileRobot((450, 590, 0), 'idle', 'mobile', "M1", "Mobile-Robot-001")
M2 = MobileRobot((450, 485, 0), 'idle', 'mobile', "M2", "Mobile-Robot-002")

# Instantiate AGV
A1 = AGV(Station1.pos, 'idle', "agv", "A1", "AGV-001")

# Instantiate Jobs
J1 = Job("Job-001", pending_steps=[Station1.op, Station2.op,
                                   Station3.op, Station4.op, Station5.op, Station6.op])

# Shopfloor Manager
Sm = ShopfloorManager()

# List of entities that need to be reset
ShopFloor.entities = [S1, S2, S3, S4, S5, S6, M1, M2, A1, J1]

# Static variable initialization (State registration):
ShopFloor.idle = Idle()
ShopFloor.op10 = OP10()
ShopFloor.op20 = OP20()
ShopFloor.op30 = OP30()
ShopFloor.op40 = OP40()
ShopFloor.op50 = OP50()
ShopFloor.op60 = OP60()
ShopFloor.transition_to_idle = TransitionToIdle()
ShopFloor.transition_to_op20 = TransitionToOP20()
ShopFloor.transition_to_op30 = TransitionToOP30()
ShopFloor.transition_to_op40 = TransitionToOP40()
ShopFloor.transition_to_op50 = TransitionToOP50()
ShopFloor.transition_to_op60 = TransitionToOP60()
