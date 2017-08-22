import os
import sys
import io
import time
import threading

import watchdog
import watchdog.events
import watchdog.observers

from oslo_config import cfg
from oslo_log import log as logging

from reconn import utils as reconn_utils
from reconn import timeout as reconn_timeout


CONF = cfg.CONF
LOG = logging.getLogger(__name__)

file_lock = threading.Lock()
survey_pattern_re_objs = None
end_reconn = False


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
        LOG.info("Event type:%s is_directory:%s src_path:%s" % (
                 event.event_type,
                 event.is_directory,
                 event.src_path))
        # LOG.debug("%s %s" % (threading.current_thread().ident,
        #           threading.current_thread().name))

    def on_modified(self, event):
        # LOG.debug("%s %s" % (threading.current_thread().ident,
        #           threading.current_thread().name))

        # NOTE(jay):
        # Any processing on any handler function blocks
        # delivery/invoking of other handler function
        # time.sleep(5)

        if self._event_on_file_path(event):
            if reconn_timeout.ReconnTimeout.is_timed_out() is False:
                # Allow main thread to gain control & terminate.
                # TODO(jay): If possible, stop observer here.
                time.sleep(1)

            lock_reconn_file(self._file)


def register_notification(file_path, file_obj):
    '''Register callback for event on a file
    descriptor'''

    observer = watchdog.observers.Observer()
    event_handler = FileEventHandler(file_path, file_obj)
    observer.schedule(event_handler, path=os.path.dirname(file_path),
                      recursive=False)

    return observer


last_line = ''


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
            matched_pattern = reconn_utils.search_patterns(survey_pattern_re_objs,
                                                           line)
            if reconn_utils.is_pattern_to_end_reconn(matched_pattern):
                # End Reconn pattern matched
                end_reconn = True
                print line
                return

        print line

    # Reconn last line for patterns:
    if (end_reconn is False and
            reconn_timeout.ReconnTimeout.is_timed_out() is False and
            eof is True and
            last_line != ''):

        matched_pattern = reconn_utils.search_patterns(survey_pattern_re_objs,
                                                       last_line)
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

    # Case: when log file has all data in it and no more writes will happen,
    # so main thread has to reconn once.
    lock_reconn_file(console_file)

    # Allow ctrl+c to work:
    try:
        while True:
            time.sleep(1)

            if (end_reconn is True or
                    reconn_timeout.ReconnTimeout.is_timed_out() is True):
                terminate_reconn(observer, console_file)
    except KeyboardInterrupt:
        terminate_reconn(observer, console_file)

    # Allow observer thread to run forever and so this process
    observer.join()


def init_reconn(argv):
    global survey_pattern_re_objs

    reconn_utils.register_reconn_opts()
    reconn_utils.oslo_logger_config_setup(argv)

    for survey_pattern_group in reconn_utils.get_reconn_survey_groups():
        reconn_utils.register_reconn_survey_patterns(survey_pattern_group)

    survey_pattern_re_objs = reconn_utils.create_re_objs()


def terminate_reconn(observer, console_file):
    '''Reconn closure activities executed here.
    Called when timeout or end reconn pattern matched.
    Discontinue any more reconn on files.'''
    observer.stop()
    observer.join()
    console_file.close()
    sys.exit(0)


def begin_reconn():
    LOG.info("console_path: %s", CONF.reconn.console_path)
    try:
        console_file = io.open(CONF.reconn.console_path, 'rt', newline='\n')
    except (IOError, TypeError) as e:
        LOG.error("Failed to open console log file. Error: %s", e)
        LOG.info("Exiting")
        exit(1)
    except Exception as e:
        LOG.error("Failed to open console log file. Error: %s", e)
        LOG.info("Exiting")
        exit(1)

    observer = register_notification(CONF.reconn.console_path, console_file)

    # Set program terminate time out
    reconn_timeout.ReconnTimeout.set_timeout(CONF.reconn.timeout * 60)

    reconn_forever(console_file, observer)


def main():
    '''Invoked when running reconn directly'''
    init_reconn(sys.argv[1:])
    begin_reconn()


if __name__ == '__main__':
    main()
