'''This file defines survey actions, that can be taken for matched survey patterns'''

from abc import ABCMeta, abstractmethod
import io
import datetime

from oslo_config import cfg
from oslo_log import log as logging


CONF = cfg.CONF
LOG = logging.getLogger(__name__)
supported_actions = ('log_survey', )
_action_mapper = {}


class SurveyAction(object):
    """Base class for actions"""
    __metaclass__ = ABCMeta

    def __init__(self):
        pass

    @abstractmethod
    def execute(self, *args, **kwargs):
        pass

    @abstractmethod
    def __del__(self):
        pass

    @abstractmethod
    def destructor(self):
        pass


class LogSurvey(SurveyAction):
    """Action that logs matched survey patterns"""
    def __init__(self, log_file, log_format):
        self.log_format = log_format
        self.f = None
        self.f = io.open(log_file, 'a+b')

    def destructor(self):
        if self.f is not None:
            self.f.close()

    def __del__(self):
        self.destructor()

    def execute(self, pattern, line, *args, **kwargs):

        s = self.log_format.format(
            time=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            line=line,
            matched_pattern=pattern,
        )
        self.f.write(s)
        self.f.write("\n")
        self.f.flush()


def create_survey_actions(action_names):
    '''Create action, for given a list of valid input action names'''
    global _action_mapper

    for action_name in action_names:
        if action_name == 'log_survey':
            log_survey_obj = LogSurvey(
                CONF.log_survey.log_survey_action_log_file,
                CONF.log_survey.log_survey_action_log_format)
            _action_mapper[action_name] = log_survey_obj
        else:
            LOG.error("action name %s not found. Supported actions: %s" % (
                action_name, supported_actions))


def get_survey_action(action_name):
    """Returns survey action object for input action name or None"""
    return _action_mapper.get(action_name, None)


def destroy_survey_actions():
    for action in _action_mapper.values():
        action.destructor()
    _action_mapper.clear()

