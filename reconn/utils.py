import re

from oslo_config import cfg
from oslo_log import log as logging

from reconn import version
from reconn import action as reconn_action


CONF = cfg.CONF
LOG = logging.getLogger(__name__)


def oslo_logger_config_setup(argv):
    '''Register oslo logger opts.
    Initialize oslo config CONF
    '''

    logging.register_options(CONF)
    CONF(argv, project='reconn',
         version=version.version_string())
    logging.setup(CONF, "reconn")


def register_reconn_opts():
    '''Register reconn opts'''
    reconn_opts = [
        cfg.StrOpt('target_file',
                   default=None,
                   help='Absolute file path of console.log '
                        'of a VM instance, RECONN is supposed '
                        'to stream read and look out for VM '
                        'boot up stage'),

        cfg.IntOpt('timeout',
                   default=20,
                   help='terminate reconn after timeout minutes. '
                        'Defaults to 20 minutes'),

        cfg.StrOpt('end_reconn',
                   default=None,
                   help='A [CONFIG] group name that defines a '
                        'parameter called "pattern" which is an '
                        'regular expression that will be looked '
                        'out in file. On encountering end reconn '
                        'pattern, reconn will be stopped'),
    ]

    reconn_opt_group = cfg.OptGroup(name='reconn',
                                    title='RECONN opts group')

    CONF.register_group(reconn_opt_group)
    CONF.register_opts(reconn_opts, group=reconn_opt_group)

    _register_reconn_opt_survey_group(reconn_opt_group)

    CONF.register_cli_opts(reconn_opts)


def _register_reconn_opt_survey_group(reconn_opt_group):
    """Register reconn option 'survey_group'"""
    reconn_survey_opts = [
        cfg.StrOpt('survey_group',
                   default=None,
                   help='Survey pattern groups name'),
    ]

    reconn_opt_group = cfg.OptGroup(name='reconn',
                                    title='RECONN opts group')

    CONF.register_opts(reconn_survey_opts, group=reconn_opt_group)


def _register_survey_opts(survey_pattern_group):
    '''Dynamically register a survey config group and its opts'''
    reconn_survey_pattern_opts = [
        cfg.StrOpt('pattern',
                   default=None,
                   help=''),
        cfg.StrOpt('success',
                   default='log_survey',
                   choices=reconn_action.supported_actions,
                   help='Action when pattern match'),
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
    for survey_pattern_group in _get_reconn_survey_groups():
        _register_survey_opts(survey_pattern_group)
        LOG.debug("Registered pattern: %s", survey_pattern_group)


def _register_log_survey_action_group_opts():
    '''Register log_survey action config group and opts'''
    log_survey_action_opts = [
        cfg.StrOpt('log_survey_action_log_format',
                   default='{time} {{ {line} : {matched_pattern} }}\n',
                   help='defaults to %(time)d {%(line)s: %(matched_pattern)s}'),
        cfg.StrOpt('log_survey_action_log_file',
                   default='/var/log/reconn/reconn_survey.log',
                   help='File to log message for pattern match'),
    ]

    log_survey_action_opt_group = cfg.OptGroup(name='log_survey',
                                               title='RECONN LogSurvey action group')
    CONF.register_group(log_survey_action_opt_group)
    CONF.register_opts(log_survey_action_opts,
                       group=log_survey_action_opt_group)


def register_reconn_survey_action_groups():
    '''Register survey action group and its opts'''
    success_actions = _get_all_configured_success_actions()
    for success_action in success_actions:
        if success_action == 'log_survey':
            _register_log_survey_action_group_opts()

    return success_actions


def _get_reconn_survey_groups():
    '''Get list of names of configured survey groups'''
    group_list = CONF.reconn.survey_group.split(",")
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
        re_objs.append(re.compile(CONF.get(survey_group_name).pattern))

    return re_objs


def search_patterns(re_objs, line):
    '''Returns first matched pattern in line or None'''
    for re_obj in re_objs:
        match_obj = re_obj.search(line)
        if match_obj is None:
            # pattern not in line
            pass
        else:
            # pattern in line
            s = "Matched %s in line: %s" % (re_obj.pattern, line)
            LOG.debug(s)
            return re_obj.pattern
    return None


def search_end_reconn_pattern(line):
    '''Search and return end reconn pattern in line or None'''
    reconn_end_group_name = CONF.reconn.end_reconn
    end_reconn_pattern = CONF.get(reconn_end_group_name).pattern
    if re.search(end_reconn_pattern, line) is None:
        return None
    else:
        LOG.info("Matched End Reconn pattern: %s in line: %s" % (
                 end_reconn_pattern, line))
        return end_reconn_pattern


def is_pattern_to_end_reconn(pattern):
    '''Match pattern with end reconn group's pattern'''
    reconn_end_group_name = CONF.reconn.end_reconn
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
