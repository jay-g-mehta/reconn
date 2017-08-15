import os
import io
import time
import threading

import watchdog
import watchdog.events
import watchdog.observers

from oslo_config import cfg
from oslo_log import log as logging

from reconn import utils as reconn_utils


CONF = cfg.CONF
LOG = logging.getLogger(__name__)

file_lock = threading.Lock()

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
        #LOG.debug("%s %s", threading.current_thread().ident,
        #          threading.current_thread().name)

    def on_modified(self, event):
        #LOG.debug("%s %s", threading.current_thread().ident,
        #          threading.current_thread().name)

        # NOTE(jay):
        # Any processing on any handler function blocks
        # delivery/invoking of other handler function
        #time.sleep(5)

        if self._event_on_file_path(event):
            lock_read_file(self._file)


def register_notification(file_path, file_obj):
    '''Register callback for event on a file
    descriptor'''

    observer = watchdog.observers.Observer()
    #LOG.info(observer)
    #LOG.info(dir(observer))
    event_handler = FileEventHandler(file_path, file_obj)
    observer.schedule(event_handler, path=os.path.dirname(file_path),
                      recursive=False)

    return observer


def read_file(f):
    eof = False
    read_size_at_once = 4096
    while not eof:
        read_bytes = f.read(read_size_at_once)
        if read_bytes is None:
            # f was in non blocking mode, no bytes available.
            LOG.debug(" f was in non blocking mode, no bytes available.")
            break
        elif len(read_bytes) == 0:
            eof = True
            return 0

        print read_bytes
    return 1


def lock_read_file(f):
    '''Lock before reading file, avoid race between
    main thread and event handler.
    Main thread requires reading of file so that it reads existing
    content to avoid a situation of no more events on file.'''
    file_lock.acquire()
    read_file(f)
    file_lock.release()


def read_forever(console_file, observer):
    observer.start()

    # Wait for observer thread to start. Don't want to miss any events
    time.sleep(2)

    lock_read_file(console_file)

    # Allow ctrl+c to work:
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    # Allow observer thread to run forever and so this process
    observer.join()


def init_reconn():
    reconn_utils.register_reconn_opts()
    reconn_utils.oslo_logger_config_setup()


def main():
    init_reconn()
    LOG.info("console_path: %s", CONF.reconn.console_path)
    try:
        console_file = io.open(CONF.reconn.console_path, 'rb')
    except (IOError, TypeError) as e:
        LOG.error("Failed to open console log file. Error: %s", e)
        LOG.info("Exiting")
        exit(1)
    except Exception as e:
        LOG.error("Failed to open console log file. Error: %s", e)
        LOG.info("Exiting")
        exit(1)

    observer = register_notification(CONF.reconn.console_path, console_file)

    read_forever(console_file, observer)

    console_file.close()



if __name__ == '__main__':
    main()
