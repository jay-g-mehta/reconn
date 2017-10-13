import os
import sys
import io
import time
import threading

import watchdog
import watchdog.events
import watchdog.observers

from oslo_log import log as logging

from reconn import conf as reconn_conf
from reconn import utils as reconn_utils
from reconn import timeout as reconn_timeout
from reconn import action as reconn_action


CONF = reconn_conf.CONF
LOG = logging.getLogger(__name__)

file_lock = threading.Lock()
survey_pattern_re_objs = None
end_reconn = False
last_line = ''
target_file_exists = False


class FileEventHandler(watchdog.events.FileSystemEventHandler):
    '''Define handlers for any filesystem events for a  given file'''
    def __init__(self, file_path, file_obj):
        self._file_path = file_path
        self._file = file_obj
        super(FileEventHandler, self).__init__()

    def _event_on_file_path(self, event):
        if event.src_path == self._file_path:
            return True
        else:
            return False

    def on_any_event(self, event):
        LOG.info("Event type:%s is_directory:%s src_path:%s",
                 event.event_type,
                 event.is_directory,
                 event.src_path)

    def on_deleted(self, event):
        global target_file_exists
        if self._event_on_file_path(event):
            target_file_exists = False
            LOG.info("RECONN on target_file is deleted. "
                     "Event type:%s is_directory:%s src_path:%s",
                     event.event_type,
                     event.is_directory,
                     event.src_path)
            # NOTE(jay): observer can be stopped now safely.
            # observer thread periodically checks if it has to stop
            # and the below is a safe ask to observer to exit
            LOG.info("Stopping observer thread. Thread %s %s exiting",
                     threading.current_thread().ident,
                     threading.current_thread().name)
            threading.current_thread().stop()

    def on_modified(self, event):
        # LOG.debug("%s %s" % (threading.current_thread().ident,
        #           threading.current_thread().name))

        # NOTE(jay):
        # Any processing on any handler function blocks
        # delivery/invoking of other handler function
        # time.sleep(5)

        if self._event_on_file_path(event):
            if reconn_timeout.ReconnTimeout.is_timed_out() is True:
                # NOTE(jay): observer can be stopped now safely.
                # observer thread periodically checks if it has to stop
                # and the below is a safe ask to observer to exit
                LOG.info("Timeout!!! Stopping observer thread. "
                         "Thread %s %s exiting",
                         threading.current_thread().ident,
                         threading.current_thread().name)
                threading.current_thread().stop()
            else:
                lock_reconn_file(self._file)


def register_notification(file_path, file_obj):
    '''Register callback for event on a file
    descriptor'''

    observer = watchdog.observers.Observer()
    event_handler = FileEventHandler(file_path, file_obj)
    observer.schedule(event_handler, path=os.path.dirname(file_path),
                      recursive=False)

    return observer


def act_on_pattern(survey_grp_name, matched_pattern, line):
    if matched_pattern is None:
        return
    action_name = reconn_utils.get_survey_success_action_name(matched_pattern)
    survey_action = reconn_action.get_survey_action(action_name)
    survey_action.execute(survey_grp_name, matched_pattern, line)


def reconn_file(f):
    global end_reconn
    global survey_pattern_re_objs
    global last_line

    eof = False
    while(not eof and
              not end_reconn and
              not reconn_timeout.ReconnTimeout.is_timed_out()):
        line = f.readline()

        if line == '':
            eof = True
            continue

        if last_line != '':
            line = last_line + line
            last_line = ''

        if line[-1] != '\n':
            # readline returned due to EOF
            # Because pattern is matched on each line, buffer
            # read contents till \n is read
            last_line = line
        else:
            # readline returned due to \n
            survey_grp_name, matched_pattern = reconn_utils.search_patterns(
                survey_pattern_re_objs, line)
            act_on_pattern(survey_grp_name, matched_pattern, line)
            if reconn_utils.is_pattern_to_end_reconn(matched_pattern):
                # End Reconn pattern matched
                end_reconn = True
                #print line.rstrip('\n')
                return

        #print line.rstrip('\n')

    # Reconn last line for patterns:
    if (end_reconn is False and
            reconn_timeout.ReconnTimeout.is_timed_out() is False and
            eof is True and
            last_line != ''):

        survey_grp_name, matched_pattern = reconn_utils.search_patterns(
            survey_pattern_re_objs, last_line)
        act_on_pattern(survey_grp_name, matched_pattern, last_line)
        if matched_pattern is not None:
            # Some pattern matched. No longer to carry last_line's content.
            last_line = ''

        if reconn_utils.is_pattern_to_end_reconn(matched_pattern):
            # End Reconn pattern matched
            end_reconn = True


def lock_reconn_file(f):
    '''Lock before reading file, avoid race between
    main thread and event handler.
    Main thread requires reading of file so that it reads existing
    content to avoid a situation of no more events on file.'''
    file_lock.acquire()
    reconn_file(f)
    file_lock.release()


def reconn_forever(console_file, observer):
    global end_reconn

    observer.start()
    # Wait for observer thread to start. Don't want to miss any events
    time.sleep(2)
    LOG.debug("observer id:%s, is_alive %s, is_daemon: %s",
              observer.ident,
              observer.is_alive(),
              observer.isDaemon())
    reconn_utils.log_native_threads()

    # Case: when log file has all data in it and no more writes will happen,
    # so main thread has to reconn once.
    lock_reconn_file(console_file)

    # Allow ctrl+c to work:
    try:
        while True:
            time.sleep(1)
            # reconn_utils.log_native_threads()

            if (end_reconn is True or
                    reconn_timeout.ReconnTimeout.is_timed_out() is True or
                    target_file_exists is False):
                break
    except KeyboardInterrupt:
        terminate_reconn(observer, console_file)
        return

    terminate_reconn(observer, console_file)


def register_reconn():
    reconn_utils.register_reconn_opts()


def init_reconn(argv):
    global survey_pattern_re_objs

    reconn_utils.suppress_imported_modules_logging()

    reconn_utils.oslo_logger_config_setup(argv)

    reconn_utils.register_configured_reconn_survey_groups()

    survey_pattern_re_objs = reconn_utils.create_re_objs()

    success_action_names = reconn_utils.register_reconn_survey_action_groups()

    reconn_action.create_survey_actions(success_action_names)


def terminate_reconn(observer, file):
    '''Reconn closure activities executed here.
    Called when timeout or end reconn pattern matched or target file deleted.
    Discontinue any more reconn on files.'''
    LOG.info("Terminating RECONN. Safe clean up in progress.")
    if observer.is_alive():
        observer.stop()
    observer.join()
    reconn_utils.log_native_threads()
    file.close()
    reconn_action.destroy_survey_actions()


def begin_reconn():
    global target_file_exists
    LOG.info("Reconn target file: %s", CONF.target_file)
    try:
        console_file = io.open(CONF.target_file, 'rb')
    except (IOError, TypeError) as e:
        LOG.error("Failed to open console log file. Error: %s", e)
        LOG.info("Exiting")
        sys.exit(1)
    except Exception as e:
        LOG.error("Failed to open console log file. Error: %s", e)
        LOG.info("Exiting")
        sys.exit(1)
    target_file_exists = True
    observer = register_notification(CONF.target_file, console_file)

    # Set program terminate time out
    reconn_timeout.ReconnTimeout.set_timeout(CONF.timeout * 60)

    reconn_forever(console_file, observer)
    LOG.info('RECONN exiting')


def main():
    '''Invoked when running reconn directly'''
    register_reconn()
    init_reconn(sys.argv[1:])
    begin_reconn()


if __name__ == '__main__':
    main()
