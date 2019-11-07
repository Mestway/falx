from abc import ABC, abstractmethod
from typing import Any

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

    def __init__(self, enumerator: Enumerator, decider: Decider):
        self._enumerator = enumerator
        self._decider = decider

    @property
    def enumerator(self):
        return self._enumerator

    @property
    def decider(self):
        return self._decider

    def synthesize(self):
        '''
        A convenient method to enumerate ASTs until the result passes the analysis.
        Returns the synthesized program, or `None` if the synthesis failed.
        '''
        # stores all solutions to the result list
        solutions = []

        start_time = time.time()

        num_attempts = 0
        prog = self._enumerator.next()
        while prog is not None:
            num_attempts += 1
            logger.debug('Enumerator generated: {}'.format(prog))
            try:
                res = self._decider.analyze(prog)
                if res.is_ok():
                    logger.debug(
                        'Program accepted after {} attempts'.format(num_attempts))
                    solutions.append(prog)
                    if len(solutions) > 5 or (time.time() - start_time > 5.):
                        return solutions
                    else:
                        #block the current example
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
