from reconn.scout import init_reconn, begin_reconn


def start_reconn(config_file='/etc/reconn/reconn.conf',
                 log_file='/var/log/reconn/reconn.log'):
    '''Function to be invoked when using
    reconn as importable package'''
    sys_argv = "--config-file=%s --log-file %s" % (config_file, log_file)
    init_reconn(sys_argv.split(" "))
    begin_reconn()

__all__ = ['start_reconn']
