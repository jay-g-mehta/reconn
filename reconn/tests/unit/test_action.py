import mock
import ddt

from reconn import test
from reconn import action as reconn_action


@ddt.ddt
class LogSurveyActionTestCase(test.TestCase):

    def setUp(self):
        super(LogSurveyActionTestCase, self).setUp()

    def tearDown(self):
        super(LogSurveyActionTestCase, self).tearDown()

    @ddt.data({'log_file': '/tmp/no_file_exists.txt',
               'log_format': '{timestamp} {{ {line} : {matched_pattern} : {name} }}',
               'exp_log_format': '{timestamp} {{ {line} : {matched_pattern} : {name} }}'
               },
              {'log_file': '/tmp/no_file_exists.txt',
               'log_format': '{timestamp} {{ {line} : {matched_pattern} : {name} }}\\r\\n',
               'exp_log_format': '{timestamp} {{ {line} : {matched_pattern} : {name} }}\r\n'
               },
              )
    @ddt.unpack
    def test_log_survey_init(self, log_file,
                             log_format,
                             exp_log_format):

        log_survey_obj = reconn_action.LogSurvey(log_file, log_format)
        self.assertEqual(exp_log_format, log_survey_obj.log_format)

    @ddt.data({'log_file': '/invalid_path/test_file.txt',
               'log_format': '{timestamp} {{ {line} : {matched_pattern} : {name} }}',
               'exp_exception': IOError
               })
    @ddt.unpack
    def test_log_survey_init_exceptions(self, log_file,
                                        log_format,
                                        exp_exception):

        self.assertRaises(exp_exception,
                          reconn_action.LogSurvey,
                          log_file, log_format,
                          )

    @ddt.data({'survey_grp_name': 'test_survey_grp',
               'pattern': 'some pattern',
               'line': 'This is some pattern in line'
               })
    @ddt.unpack
    @mock.patch('io.open')
    def test_log_survey_execute(self,
                                mock_io_open,
                                survey_grp_name, pattern, line):
        mock_BufferedWriter = mock.Mock()
        mock_io_open.return_value = mock_BufferedWriter

        mock_BufferedWriter.write = mock.Mock()
        mock_BufferedWriter.flush = mock.Mock()
        mock_BufferedWriter.close = mock.Mock()

        log_file = '/tmp/no_file_exists.txt'
        log_format = '{timestamp} {{ {line} : {matched_pattern} : {name} }}'

        log_survey_obj = reconn_action.LogSurvey(log_file, log_format)
        log_survey_obj.execute(survey_grp_name, pattern, line)

        mock_BufferedWriter.write.assert_called_once()
