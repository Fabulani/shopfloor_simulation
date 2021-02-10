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

    def __init__(self, initialState):
        ''' Set and run the initial State. '''
        self.currentState = initialState
        self.currentState.run()

    def runAll(self):
        ''' Run States indefinitly, according to the rules set inside its `next` methods. '''
        while True:
            self.currentState = self.currentState.next()
            self.currentState.run()
