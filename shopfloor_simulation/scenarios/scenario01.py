import json
from time import sleep
from random import randint
from mpmath import *
from math import sqrt
from shopfloor_simulation.state_machine import State, StateMachine
from shopfloor_simulation.entities import StationaryRobot, MobileRobot, AGV, Station, Job, ShopfloorManager
from shopfloor_simulation.mqtt_utils import ShopfloorPublisher, ShopfloorSubscriber


STATE_SLEEP = 2  # Amount of time to wait between states.


''' State Machine and States setup. '''
# The State Machine is a cycle: Idle -> OP10 -> TransitionToOP20 -> OP20 -> ... -> TransitionToIdle -> Idle
# Note about TransitionToOP10: this State was discarded since all the robots are already positioned correctly in the TransitionToIdle State.
# This means that OP10 can start without having to move Robots around from the previous State (Idle). This is not the case for other OPs.


class Shopfloor(StateMachine):
    def __init__(self):
        # Initial state
        print("[STATE] Idle")
        StateMachine.__init__(self, Shopfloor.idle)

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
        return Shopfloor.op10


class OP10(State):
    def run(self):
        J1.begin_step(Station1.op)
        J1.status = 'underway'
        S1.status = 'busy'
        S2.status = 'busy'
        A1.status = 'busy'

        sleep(STATE_SLEEP)
        J1.complete_step(Station1.op)
        S1.reset()
        S2.reset()

    def next(self):
        return Shopfloor.transition_to_op20


class OP20(State):
    def run(self):
        J1.begin_step(Station2.op)
        S4.status = 'busy'
        M1.status = 'busy'
        M2.status = 'busy'

        sleep(STATE_SLEEP)
        J1.complete_step(Station2.op)
        S4.reset()

    def next(self):
        return Shopfloor.transition_to_op30


class OP30(State):
    def run(self):
        J1.begin_step(Station3.op)
        S3.status = 'busy'

        sleep(STATE_SLEEP)
        J1.complete_step(Station3.op)
        S3.reset()

    def next(self):
        return Shopfloor.transition_to_op40


class OP40(State):
    def run(self):
        J1.begin_step(Station4.op)
        S5.status = 'busy'
        S6.status = 'busy'

        sleep(STATE_SLEEP)
        J1.complete_step(Station4.op)
        S5.reset()
        S6.reset()
        M1.reset()
        M2.reset()

    def next(self):
        return Shopfloor.transition_to_op50


class OP50(State):
    def run(self):
        J1.begin_step(Station5.op)

        sleep(STATE_SLEEP)
        J1.complete_step(Station5.op)

    def next(self):
        return Shopfloor.transition_to_op60


class OP60(State):
    def run(self):
        J1.begin_step(Station6.op)

        sleep(STATE_SLEEP)
        J1.complete_step(Station6.op)
        J1.status = 'completed'

    def next(self):
        return Shopfloor.transition_to_idle


class TransitionToIdle(State):
    '''Transition State from OP60 to Idle'''

    def run(self):
        for entity in Shopfloor.entities:
            entity.reset()
        sleep(5)

    def next(self):
        return Shopfloor.idle


class TransitionToOP20(State):
    '''Transition State from OP10 to OP20'''

    def run(self):
        A1.move_robot((370, 530, 0))
        sleep(STATE_SLEEP)

    def next(self):
        return Shopfloor.op20


class TransitionToOP30(State):
    '''Transition State from OP20 to OP30'''

    def run(self):
        M1.move_robot((600, 360, 0))
        M2.move_robot((600, 470, 0))
        A1.move_robot((480, 400, 0))
        sleep(STATE_SLEEP)

    def next(self):
        return Shopfloor.op30


class TransitionToOP40(State):
    '''Transition State from OP30 to OP40'''

    def run(self):
        M1.move_robot((375, 245, 0))
        M2.move_robot((375, 345, 0))
        A1.move_robot((250, 300, 0))
        sleep(STATE_SLEEP)

    def next(self):
        return Shopfloor.op40


class TransitionToOP50(State):
    '''Transition State from OP40 to OP50'''

    def run(self):
        A1.move_robot((250, 200, 0))
        sleep(STATE_SLEEP)

    def next(self):
        return Shopfloor.op50


class TransitionToOP60(State):
    '''Transition State from OP50 to OP60'''

    def run(self):
        A1.move_robot((250, 100, 0))
        sleep(STATE_SLEEP)

    def next(self):
        return Shopfloor.op60


''' Entity and State Machine initialization. '''
# Instantiate Stations
Station1 = Station("Station-001", "Station1", "stations",
                   "I'm Station 001!", (650, 160, 0), 'OP10')
Station2 = Station("Station-002", "Station2", "stations",
                   "I'm Station 002!", (370, 530, 0), 'OP20')
Station3 = Station("Station-003", "Station3", "stations",
                   "I'm Station 003!", (480, 400, 0), 'OP30')
Station4 = Station("Station-004", "Station4", "stations",
                   "I'm Station 004!", (250, 300, 0), 'OP40')
Station5 = Station("Station-005", "Station5", "stations",
                   "I'm Station 005!", (250, 200, 0), 'OP50')
Station6 = Station("Station-006", "Station6", "stations",
                   "I'm Station 006!", (250, 100, 0), 'OP60')

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
                 initial_position=[450, 590, 0], initial_orientation=[0, 0, 0, 0], current_station=Station3.header)
M2 = MobileRobot("Mobile-Robot-002", "M2", "robots", "I'm Mobile Robot 002!", "mobile",
                 initial_position=[450, 485, 0], initial_orientation=[0, 0, 0, 0], current_station=Station2.header)

# Instantiate AGV  #! initial_position=Station1.pos results in A1.pose["position"]=([650, 160, 0],), no idea why
A1 = AGV("AGV-001", "A1", "robots", "I'm AGV 001!", "agv",
         initial_position=[650, 160, 0], initial_orientation=[0, 0, 0, 0], current_station=Station1.header)

# Instantiate Jobs
J1 = Job("Job-001", pending_steps=[Station1.op, Station2.op,
                                   Station3.op, Station4.op, Station5.op, Station6.op])

# Shopfloor Manager
Sm = ShopfloorManager()

# List of entities that need to be reset
Shopfloor.entities = [S1, S2, S3, S4, S5, S6, M1, M2, A1, J1]

# MQTT Publisher and Subscriber
Shopfloor.publisher = ShopfloorPublisher(
    name="MQTT-P",
    publishing_entities=Shopfloor.entities)
Shopfloor.subscriber = ShopfloorSubscriber(
    name="MQTT-S",
    subscribed_topics=["freeaim/echo/ShopfloorSubscriber"])

# Stationary variable initialization (State registration):
Shopfloor.idle = Idle()
Shopfloor.op10 = OP10()
Shopfloor.op20 = OP20()
Shopfloor.op30 = OP30()
Shopfloor.op40 = OP40()
Shopfloor.op50 = OP50()
Shopfloor.op60 = OP60()
Shopfloor.transition_to_idle = TransitionToIdle()
Shopfloor.transition_to_op20 = TransitionToOP20()
Shopfloor.transition_to_op30 = TransitionToOP30()
Shopfloor.transition_to_op40 = TransitionToOP40()
Shopfloor.transition_to_op50 = TransitionToOP50()
Shopfloor.transition_to_op60 = TransitionToOP60()
