from reconn.scout import register_reconn, init_reconn, begin_reconn


__all__ = ['start_reconn', 'setup_reconn']


def setup_reconn():
    register_reconn()


def start_reconn(target_file,
                 config_file='/etc/reconn/reconn.conf',
                 log_file='/var/log/reconn/reconn.log',
                 survey_action_message_format=None,
                 user_data=None,
                 ):
    '''Function to be invoked when using
    reconn as importable package'''
    args_dict = {
        '--target_file': target_file,
        '--config-file': config_file,
        '--log-file': log_file,
    }
    if survey_action_message_format is not None:
        args_dict['--survey_action_message_format'] = survey_action_message_format
    if user_data is not None:
        args_dict['--msg_user_data'] = user_data

    sys_argv = ['{0}={1}'.format(k, v) for k, v in args_dict.items()]
    init_reconn(sys_argv)
    begin_reconn()
