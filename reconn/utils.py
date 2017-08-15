import sys

from reconn import version

from oslo_config import cfg
from oslo_log import log as logging


CONF = cfg.CONF


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
                        'boot up stage'), ]

    reconn_opt_group = cfg.OptGroup(name='reconn',
                                    title='RECONN opts group')

    CONF.register_group(reconn_opt_group)
    CONF.register_opts(reconn_opts, group=reconn_opt_group)

    CONF.register_cli_opts(reconn_opts)

