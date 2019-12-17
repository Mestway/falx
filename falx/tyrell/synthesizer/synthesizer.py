from abc import ABC, abstractmethod
from typing import Any

from falx.tyrell.decider.bidirection_pruning import ConstraintInterpreter

from falx.tyrell.interpreter import InterpreterError
from falx.tyrell.enumerator import Enumerator
from falx.tyrell.decider import Decider
from falx.tyrell.dsl import Node
from falx.tyrell.logger import get_logger

import time

logger = get_logger('tyrell.synthesizer')


class Synthesizer(ABC):

    _enumerator: Enumerator
    _decider: Decider

    def __init__(self, enumerator: Enumerator, decider: Decider, 
                 solution_limit, time_limit_sec):
        """ Initialize the synthesizer
            enumerator: the enumerator for traverse the sapce
            decider: decision procedure for pruning the search space
            solution_limit: the stop criteria of the synthesizer, 
                if solution_limit=k: the synthesizer terminates when it find >= k solution
            time_limit: the synthesizer will terminate *at least* at this time limit 
                (it terminates at the the smallest time above this time time), no guarentee to terminate right at time_limit
        """
        self._enumerator = enumerator
        self._decider = decider
        self.solution_limit = solution_limit
        self.time_limit_sec = time_limit_sec

    @property
    def enumerator(self):
        return self._enumerator

    @property
    def decider(self):
        return self._decider

    def synthesize(self, oracle_decider=None):
        '''
        A convenient method to enumerate ASTs until the result passes the analysis.
        Args:
            oracle_decider: a oracle function that decides whether a consistent solution is the correct solution
        Returns:
            solutions: the synthesized program, or `None` if the synthesis failed.
            consistent_solution_visited: the number of consistent solutions visited
        '''
        # stores all solutions to the result list
        solutions = []

        start_time = time.time()

        # the numeber of solutions visited that are consistent with the input-output spec
        consistent_solution_visited = 0
        
        # this records the number of attempts tried by the enumerator
        num_attempts = 0

        prog = self._enumerator.next()
        while prog is not None:
            num_attempts += 1
            logger.debug('Enumerator generated: {}'.format(prog))
            try:
                res = self._decider.analyze(prog)
                if res.is_ok():
                    logger.debug('Program accepted after {} attempts'.format(num_attempts))

                    # we have visited a consistent example 
                    consistent_solution_visited += 1

                    if oracle_decider is not None:
                        interp_outputs = [ConstraintInterpreter(self._decider.interpreter, example.input).interpret(prog)
                                            for example in self._decider.examples]
                        if oracle_decider(interp_outputs[0]) == False:
                            # the oracle decider thinks that the solution is incorrect
                            self._enumerator.update()
                            prog = self._enumerator.next()
                            continue

                    # in this case we find a real solution
                    solutions.append(prog)

                    if len(solutions) >= self.solution_limit or (time.time() - start_time > self.time_limit_sec):
                        # stop search because we have already find sufficient solutions or we have run out of time
                        logger.info('# candidates before getting the correct solution: {}'.format(consistent_solution_visited))
                        print('# candidates before getting the correct solution: {}'.format(consistent_solution_visited))
                        return solutions
                    else:
                        #block the current program to search for the next
                        self._enumerator.update()
                        prog = self._enumerator.next()
                else:
                    info = res.why()
                    logger.debug('Program rejected. Reason: {}'.format(info))
                    self._enumerator.update(info)
                    prog = self._enumerator.next()
            except InterpreterError as e:
                info = self._decider.analyze_interpreter_error(e)
                logger.debug('Interpreter failed. Reason: {}'.format(info))
                self._enumerator.update(info)
                prog = self._enumerator.next()
        logger.debug(
            'Enumerator is exhausted after {} attempts'.format(num_attempts))
        return None if len(solutions) == 0 else solutions
