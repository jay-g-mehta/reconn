'''This file defines survey actions, that can be taken for matched survey patterns'''

from abc import ABCMeta, abstractmethod
import io

from oslo_log import log as logging


LOG = logging.getLogger(__name__)
supported_actions = ('LogSurvey', )
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
    def __init__(self, log_file):
        # TODO(Jay): accept log format too.
        self.log_format = 'Matched pattern: %s in line: %s \n'
        self.f = None
        self.f = io.open(log_file, 'a')

    def destructor(self):
        if self.f is not None:
            self.f.close()

    def __del__(self):
        self.destructor()

    def execute(self, pattern, line, *args, **kwargs):
        self.f.write(self.log_format % (pattern, line))


def register_survey_actions(action_names):
    '''For a list of valid input action names, register it'''
    global _action_mapper

    for action_name in action_names:
        if action_name == 'LogSurvey':
            # TODO(jay): Accept LogSurvey path from config
            log_survey = LogSurvey('/var/log/reconn/reconn_survey.log')
            _action_mapper[action_name] = log_survey
        else:
            LOG.error("action name %s not found. Supported actions: %s" % (
                action_name, supported_actions))


def get_survey_action(action_name):
    """Returns survey action object for input action name or None"""
    return _action_mapper.get(action_name, None)


def deregister_survey_actions():
    for action in _action_mapper.values():
        action.destructor()
    _action_mapper.clear()

