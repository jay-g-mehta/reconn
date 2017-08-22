import signal

from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class ReconnTimeout(object):
    '''Only main thread can set SIGALRM alarm for timeout.
    Any thread can monitor timed out, to terminate'''
    reconn_timedout = False

    @staticmethod
    def clear_timeout():
        '''De-register to receive SIGALRM for timeouts'''
        signal.alarm(0)

    @staticmethod
    def set_timeout(timeout):
        '''Register to receive SIGALRM for timeout'''
        signal.signal(signal.SIGALRM, ReconnTimeout.reconn_timeout_handler)
        signal.alarm(timeout)

    @staticmethod
    def reconn_timeout_handler(signum, stack_frame):

        ReconnTimeout.reconn_timedout = True
        ReconnTimeout.clear_timeout()
        LOG.info("Reconn timed out")

    @staticmethod
    def is_timed_out():
        return ReconnTimeout.reconn_timedout
