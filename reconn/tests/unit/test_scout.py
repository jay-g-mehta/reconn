import mock
import ddt

from reconn import test
from reconn import scout as reconn_scout


@ddt.ddt
class FileEventHandlerTestCase(test.TestCase):

    @ddt.data({'event_src_path': '/tmp/test_path/test_file.txt',
               'event_is_dir': False,
               'exp_reconn': True,
               },
              {'event_src_path': '/tmp/test_path/',
               'event_is_dir': True,
               'exp_reconn': False,
               },
              {'event_src_path': '/tmp/test_path/some_other_file.txt',
               'event_is_dir': False,
               'exp_reconn': False,
               }
              )
    @ddt.unpack
    @mock.patch('time.sleep')
    @mock.patch('watchdog.events.FileSystemEventHandler')
    @mock.patch('reconn.timeout.ReconnTimeout.is_timed_out')
    @mock.patch('reconn.scout.lock_reconn_file')
    def test_file_event_handler(self,
                                mock_reconn_lock_reconn_file,
                                mock_reconn_timeout_is_timed_out,
                                mock_watchdog_fseventhandler,
                                mock_time_sleep,
                                event_src_path, event_is_dir,
                                exp_reconn):
        file_path = '/tmp/test_path/test_file.txt'
        file_obj = mock.Mock()

        mock_reconn_timeout_is_timed_out.return_value = False
        event = mock.Mock()
        event.src_path = event_src_path
        event.is_directory = event_is_dir
        event.event_type = 'modified'

        event_handler = reconn_scout.FileEventHandler(file_path, file_obj)
        event_handler.on_modified(event)

        if exp_reconn:
            mock_reconn_lock_reconn_file.assert_called_once_with(file_obj)
        else:
            mock_reconn_lock_reconn_file.assert_not_called()

    @mock.patch('reconn.scout.FileEventHandler')
    @mock.patch('watchdog.observers.Observer')
    def test_register_notification(self,
                                   mock_watchdog_observer,
                                   mock_reconn_fileeventhandler):
        file_path = '/tmp/test_path/test_file.txt'
        file_obj = mock.Mock()

        mock_watchdog_observer_obj = mock.Mock(
            name='mock_watchdog_observer_obj')
        mock_watchdog_observer.return_value = mock_watchdog_observer_obj

        mock_event_handler = mock.Mock()
        mock_reconn_fileeventhandler.return_value = mock_event_handler

        reconn_scout.register_notification(file_path, file_obj)

        mock_watchdog_observer_obj.schedule.assert_called_once_with(
            mock_event_handler,
            path='/tmp/test_path',
            recursive=False)
        mock_reconn_fileeventhandler.assert_called_once_with(
            file_path, file_obj)


@ddt.ddt
class ReconnTestCase(test.TestCase):

    @mock.patch('reconn.scout.reconn_file')
    def test_lock_reconn_file(self, mock_reconn_file):
        file_obj = mock.Mock()

        mock_file_lock = mock.Mock()
        _reconn_file_lock = reconn_scout.file_lock
        reconn_scout.file_lock = mock_file_lock

        reconn_scout.lock_reconn_file(file_obj)

        mock_file_lock.acquire.assert_called_once_with()
        mock_reconn_file.assert_called_once_with(file_obj)
        mock_file_lock.release.assert_called_once_with()

        reconn_scout.file_lock = _reconn_file_lock

    @mock.patch('time.sleep')
    @mock.patch('reconn.timeout.ReconnTimeout.is_timed_out')
    @mock.patch('reconn.scout.lock_reconn_file')
    def test_reconn_forever_when_end_reconn(self,
                                            mock_lock_reconn_file,
                                            mock_reconn_timeout_is_timed_out,
                                            mock_time_sleep):
        mock_watchdog_observer_obj = mock.Mock(
            name='mock_watchdog_observer_obj')
        file_obj = mock.Mock()

        _end_reconn = reconn_scout.end_reconn
        reconn_scout.end_reconn = True

        mock_reconn_timeout_is_timed_out.return_value(False)
        reconn_scout.reconn_forever(file_obj, mock_watchdog_observer_obj)

        mock_watchdog_observer_obj.start.assert_called_once_with()
        mock_lock_reconn_file.assert_called_once_with(file_obj)
        mock_watchdog_observer_obj.stop.assert_called_once_with()
        mock_watchdog_observer_obj.join.assert_called_once_with()
        file_obj.close.assert_called_once_with()

        reconn_scout.end_reconn = _end_reconn

    @mock.patch('time.sleep')
    @mock.patch('reconn.timeout.ReconnTimeout.is_timed_out')
    @mock.patch('reconn.scout.lock_reconn_file')
    def test_reconn_forever_when_reconn_timeout(self,
                                                mock_lock_reconn_file,
                                                mock_reconn_timeout_is_timed_out,
                                                mock_time_sleep):
        mock_watchdog_observer_obj = mock.Mock(
            name='mock_watchdog_observer_obj')
        file_obj = mock.Mock()

        _end_reconn = reconn_scout.end_reconn
        reconn_scout.end_reconn = False

        mock_reconn_timeout_is_timed_out.return_value=True

        reconn_scout.reconn_forever(file_obj, mock_watchdog_observer_obj)

        mock_watchdog_observer_obj.start.assert_called_once_with()
        mock_lock_reconn_file.assert_called_once_with(file_obj)
        mock_watchdog_observer_obj.stop.assert_called_once_with()
        mock_watchdog_observer_obj.join.assert_called_once_with()
        file_obj.close.assert_called_once_with()

        reconn_scout.end_reconn = _end_reconn

    @ddt.data({'readline_side_effect': [''],
               'exp_readline_count': 1,
               'search_pattern_side_effect': [(None, None)],
               'exp_search_pattern_count': 0,
               'end_reconn_val': False
               },
              {'readline_side_effect': ['line 1', ''],
               'exp_readline_count': 2,
               'search_pattern_side_effect': [(None, None)],
               'exp_search_pattern_count': 1,
               'end_reconn_val': False
               },
              {'readline_side_effect': ['line 1', ''],
               'exp_readline_count': 2,
               'search_pattern_side_effect': [('test_survey_grp', 'line')],
               'exp_search_pattern_count': 1,
               'end_reconn_val': False
               },
              {'readline_side_effect': ['line with end reconn \n', 'line not read'],
               'exp_readline_count': 1,
               'search_pattern_side_effect': [('test_end_survey_grp', 'end')],
               'exp_search_pattern_count': 1,
               'end_reconn_val': True
               },
              )
    @ddt.unpack
    @mock.patch('reconn.timeout.ReconnTimeout.is_timed_out')
    @mock.patch('reconn.utils.is_pattern_to_end_reconn')
    @mock.patch('reconn.utils.search_patterns')
    @mock.patch('reconn.scout.act_on_pattern')
    def test_reconn_file(self,
                         mock_reconn_act_on_pattern,
                         mock_reconn_search_patterns,
                         mock_reconn_is_pattern_to_end_reconn,
                         mock_reconn_timeout_is_timed_out,
                         readline_side_effect,
                         exp_readline_count,
                         search_pattern_side_effect,
                         exp_search_pattern_count,
                         end_reconn_val):
        file_obj = mock.Mock()

        mock_reconn_is_pattern_to_end_reconn.return_value = end_reconn_val
        mock_reconn_timeout_is_timed_out.return_value = False
        file_obj.readline.side_effect = readline_side_effect
        mock_reconn_search_patterns.side_effect = search_pattern_side_effect

        reconn_scout.reconn_file(file_obj)

        self.assertEqual(exp_readline_count,
                         file_obj.readline.call_count)
        self.assertEqual(exp_search_pattern_count,
                         mock_reconn_act_on_pattern.call_count)
        self.assertEqual(exp_search_pattern_count,
                         mock_reconn_search_patterns.call_count)

