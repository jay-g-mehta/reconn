import sys
import re

from reconn import version

from oslo_config import cfg
from oslo_log import log as logging


CONF = cfg.CONF
LOG = logging.getLogger(__name__)


def oslo_logger_config_setup():
    '''Register oslo logger opts.
    Initialize oslo config CONF
    '''

    logging.register_options(CONF)

    CONF(sys.argv[1:], project='reconn',
         version=version.version_string())
    logging.setup(CONF, "reconn")


def register_reconn_opts():
    '''Register reconn opts'''

    reconn_opts = [
        cfg.StrOpt('console_path',
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

    _register_reconn_survey_opts(reconn_opt_group)

    CONF.register_cli_opts(reconn_opts)


def _register_reconn_survey_opts(reconn_opt_group):
    '''Register reconn survey opts'''
    reconn_survey_opts = [
        cfg.StrOpt('survey_group',
                   default=None,
                   help='Survey pattern groups name'),
    ]

    reconn_opt_group = cfg.OptGroup(name='reconn',
                                    title='RECONN opts group')

    CONF.register_opts(reconn_survey_opts, group=reconn_opt_group)


def register_reconn_survey_patterns(survey_pattern_group):
    '''Dynamically register each survey pattern'''
    reconn_survey_pattern_opts = [
        cfg.StrOpt('pattern',
                   default=None,
                   help=''),
        cfg.StrOpt('success',
                   default=None,
                   help=''),
        cfg.StrOpt('failure',
                   default=None,
                   help=''),
    ]

    reconn_survey_opt_group = cfg.OptGroup(name=survey_pattern_group,
                                           title='RECONN survey pattern:' +
                                                 survey_pattern_group)

    CONF.register_opts(reconn_survey_pattern_opts, group=reconn_survey_opt_group)


def get_reconn_survey_groups():
    group_list = CONF.reconn.survey_group.split(",")
    for i in range(len(group_list)):
        group_list[i] = group_list[i].strip(" ")
    return group_list


def create_re_objs():
    '''Create python re pattern obj for each survey pattern'''
    re_objs = []
    for survey_group_name in get_reconn_survey_groups():
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
            LOG.info("Matched %s in line: %s" % (re_obj.pattern, line))
            return re_obj.pattern
    return None


def search_end_reconn_pattern(line):
    '''Search end reconn pattern in line'''
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
