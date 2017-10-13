import threading
import re
import logging as py_logging

from oslo_config import cfg
from oslo_log import log as logging

from reconn import version
from reconn import action as reconn_action
from reconn import conf as reconn_conf


CONF = reconn_conf.CONF
LOG = logging.getLogger(__name__)

_default_action_message_format = '{{"name": "{name}", "line":"{line}", ' \
                                 '"matched_pattern":"{matched_pattern}", ' \
                                 '"timestamp":"{timestamp}" }}'


def suppress_imported_modules_logging():
    py_logging.getLogger('pika').setLevel(py_logging.INFO)
    py_logging.getLogger('pika').propagate = False

    py_logging.getLogger('watchdog').setLevel(py_logging.INFO)
    py_logging.getLogger('watchdog').propagate = False


def oslo_logger_config_setup(argv):
    '''
    Initialize oslo config CONF
    '''
    CONF(argv, project='reconn',
         version=version.version_string())
    logging.setup(CONF, "reconn")


def register_reconn_opts():
    '''Register oslo logger opts & cli opts
     and reconn default opts & cli opts
    '''

    global _default_action_message_format
    _default_message_format_help = "Default format of message for all survey " \
                                   "action group. Message will be composed " \
                                   "of this format on matched pattern. " \
                                   "Variables within {} will be substituted " \
                                   "with its value. These variables should " \
                                   "be part of msg_user_data option. Fields " \
                                   "{timestamp}, {line} and {matched_pattern} " \
                                   "are computed. Field {name} is substituted " \
                                   "by the value defined for parameter name " \
                                   "of matching survey config group. " \
                                   "Rest all characters will be sent as it is in message. " \
                                   "Logging { or } requires escape by doubling " \
                                   "{{, }}. Defaults to :" + _default_action_message_format

    logging.register_options(CONF)

    reconn_opts = [
        cfg.StrOpt('target_file',
                   required=True,
                   default=None,
                   help='Absolute file path of console.log '
                        'of a VM instance, RECONN is supposed '
                        'to stream read and look out for VM '
                        'boot up stage'),

        cfg.IntOpt('timeout',
                   default=20,
                   help='terminate reconn after timeout minutes. '
                        'Defaults to 20 minutes'),

        cfg.StrOpt('survey_action_message_format',
                   default=_default_action_message_format,
                   help=_default_message_format_help),

        cfg.DictOpt('msg_user_data',
                    default={},
                    help="User data is a set of key:value pairs, where the "
                         "key is looked up in survey_action_message_format "
                         "string within {} and it is substituted with the "
                         "value. This helps in forming "
                         "custom message to be sent to RMQ"),

        cfg.StrOpt('end_reconn',
                   default=None,
                   help='A [CONFIG] group name that defines a '
                        'parameter called "pattern" which is an '
                        'regular expression that will be looked '
                        'out in file. On encountering end reconn '
                        'pattern, reconn will be stopped'),

        cfg.StrOpt('survey_group',
                   required=True,
                   default=None,
                   help='Survey pattern groups name'),
    ]

    CONF.register_opts(reconn_opts)

    CONF.register_cli_opts(reconn_opts[:-2])


def _register_survey_opts(survey_pattern_group):
    '''Dynamically register a survey config group and its opts'''
    reconn_survey_pattern_opts = [
        cfg.StrOpt('pattern',
                   default=None,
                   required=True,
                   help='Pattern to match'),
        cfg.StrOpt('name',
                   default=survey_pattern_group,
                   help='Alternate name to survey config group. Defaults '
                        'to config group name.'),
        cfg.StrOpt('success',
                   default='log_survey',
                   choices=reconn_action.supported_actions,
                   help='Action when pattern matches'),
        cfg.StrOpt('failure',
                   default=None,
                   help=''),
    ]

    reconn_survey_opt_group = cfg.OptGroup(name=survey_pattern_group,
                                           title='RECONN survey pattern:' +
                                                 survey_pattern_group)
    CONF.register_group(reconn_survey_opt_group)
    CONF.register_opts(reconn_survey_pattern_opts,
                       group=reconn_survey_opt_group)


def register_configured_reconn_survey_groups():
    '''Dynamically register all configured survey config group and its opts'''
    survey_pattern_groups = _get_reconn_survey_groups()
    if survey_pattern_groups == []:
        LOG.error("survey_group not configured. Configure survey_group "
                  "to perform reconn on target file.")
        raise ValueError

    for survey_pattern_group in survey_pattern_groups:
        _register_survey_opts(survey_pattern_group)
        LOG.debug("Registered pattern: %s", survey_pattern_group)


def _register_log_survey_action_group_opts():
    '''Register log_survey action config group and opts'''
    log_survey_action_opts = [
        cfg.StrOpt('log_survey_action_log_format',
                   default=CONF.survey_action_message_format,
                   help='Format to log matched pattern. Supported replacement '
                        'fields are {name}, {timestamp}, {line} '
                        'and {matched_pattern}. '
                        'Rest all characters will be sent to log file as is.'
                        'Logging "{" or "}" requires escape by doubling '
                        '{{, }}. Defaults to :' + CONF.survey_action_message_format),
        cfg.StrOpt('log_survey_action_log_file',
                   default='/var/log/reconn/reconn_survey.log',
                   help='File to log message for pattern match'),
    ]

    log_survey_action_opt_group = cfg.OptGroup(name='log_survey',
                                               title='RECONN LogSurvey action group')
    CONF.register_group(log_survey_action_opt_group)
    CONF.register_opts(log_survey_action_opts,
                       group=log_survey_action_opt_group)


def _register_rmq_survey_action_group_opts():
    '''Register rmq_survey action config group and opts'''
    rmq_survey_action_opts = [
        cfg.StrOpt('username',
                   default='guest',
                   help='username to connect to RMQ server'),
        cfg.StrOpt('password',
                   default='guest',
                   help='password for username to connect to RMQ server'),
        cfg.HostAddressOpt('host',
                           default='127.0.0.1',
                           help='Host address(IP or hostname) where '
                                'RMQ server is running'),
        cfg.PortOpt('port',
                    default=5672,
                    help='port on which RMQ server is listening'),
        cfg.StrOpt('virtual_host',
                   default='/',
                   help='RMQ virtual host'),
        cfg.StrOpt('exchange_name',
                   default='',
                   help='exchange name to create or publish message to'),
        cfg.StrOpt('queue_name',
                   required=True,
                   help='Explicit Queue name where the message gets forwarded to'),
        cfg.StrOpt('routing_key',
                   required=True,
                   help='Routing key that allows message to be '
                        'forwarded to Queue from Exchange'),
        cfg.StrOpt('rmq_message_format',
                   default=CONF.survey_action_message_format,
                   help="Format of message to send to RMQ on matched pattern. "
                        "Variables within {} will be substituted with its value. "
                        "Fields {name}, {timestamp}, {line} and "
                        "{matched_pattern} are computed. "
                        "Rest all characters will be sent as it is in message. "
                        "Logging { or } requires escape by doubling "
                        "{{, }}. Defaults to :" + CONF.survey_action_message_format),
        cfg.DictOpt('rmq_msg_user_data',
                    default={},
                    help="RMQ msg user data is a set of key:value pairs, where "
                         "the key is looked up in rmq_message_format string "
                         "within {} and it is substituted with the value. "
                         "This helps is forming custom message to be sent to "
                         "RMQ. These set of key:value pairs overrides "
                         "key:value pairs from reconn config group's "
                         "msg_user_data"),
    ]

    rmq_survey_action_opt_group = cfg.OptGroup(name='rmq_survey',
                                               title='RECONN RMQSurvey action group')
    CONF.register_group(rmq_survey_action_opt_group)
    CONF.register_opts(rmq_survey_action_opts,
                       group=rmq_survey_action_opt_group)


def register_reconn_survey_action_groups():
    '''Register survey action group and its opts'''
    success_actions = _get_all_configured_success_actions()
    for success_action in success_actions:
        if success_action == 'log_survey':
            _register_log_survey_action_group_opts()
        elif success_action == 'rmq_survey':
            _register_rmq_survey_action_group_opts()
    return success_actions


def _get_reconn_survey_groups():
    '''Get list of names of configured survey groups or
    empty list'''
    if CONF.survey_group is None:
        return []
    group_list = CONF.survey_group.split(",")
    for i in range(len(group_list)):
        group_list[i] = group_list[i].strip(" ")
    return group_list


def _get_all_configured_success_actions():
    '''Returns a list of all unique success action used by all
    survey groups.
    NOTE: This function should be called only after all the
    survey groups and its opts are registered'''
    unique_survey_actions = []
    for survey_pattern_group_name in _get_reconn_survey_groups():
        success_action = CONF.get(survey_pattern_group_name).success.strip()
        if success_action not in unique_survey_actions:
            unique_survey_actions.append(success_action)

    return unique_survey_actions


def create_re_objs():
    '''Create python re pattern obj for each survey pattern'''
    re_objs = []
    for survey_group_name in _get_reconn_survey_groups():
        re_objs.append((CONF.get(survey_group_name).name,
                       re.compile(CONF.get(survey_group_name).pattern)))

    return re_objs


def search_patterns(re_objs, line):
    '''Returns first matched pattern in line and its
     survey pattern group name. On Failure, returns (None,None)'''
    for survey_grp_name, re_obj in re_objs:
        match_obj = re_obj.search(line)
        if match_obj is None:
            # pattern not in line
            pass
        else:
            # pattern in line
            s = "Matched %s in line: %s" % (re_obj.pattern, line)
            LOG.debug(s)
            return survey_grp_name, re_obj.pattern
    return None, None


def search_end_reconn_pattern(line):
    '''Search and return end reconn pattern in line or None'''
    if CONF.end_reconn is None:
        return False
    reconn_end_group_name = CONF.end_reconn
    end_reconn_pattern = CONF.get(reconn_end_group_name).pattern
    if re.search(end_reconn_pattern, line) is None:
        return None
    else:
        LOG.info("Matched End Reconn pattern: %s in line: %s" % (
                 end_reconn_pattern, line))
        return end_reconn_pattern


def is_pattern_to_end_reconn(pattern):
    '''Returns True if pattern matches with end reconn group's pattern.
    Returns False otherwise or if end reconn config group is not defined'''
    if CONF.end_reconn is None:
        return False
    reconn_end_group_name = CONF.end_reconn
    end_reconn_pattern = CONF.get(reconn_end_group_name).pattern
    if end_reconn_pattern == pattern:
        return True
    else:
        return False


def get_survey_success_action_name(pattern):
    '''For a given survey pattern, get its configured success action name.
    None on failure'''

    for survey_group_name in _get_reconn_survey_groups():
        if CONF.get(survey_group_name).pattern == pattern:
            return CONF.get(survey_group_name).success
    return None


def log_native_threads():
    '''Log native threads to log file
    '''
    out = "%d active threads: " % threading.active_count()
    for t in threading.enumerate():
        out = out + "'%s':(id: %s, is_alive %s, isDaemon: %s), " % (
            t.name, t.ident, t.is_alive(), t.isDaemon())

    LOG.debug("%s", out.rstrip(", "))
