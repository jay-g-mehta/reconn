import mock
import ddt
import copy
import pika

from reconn import test
from reconn import action as reconn_action


@ddt.ddt
class LogSurveyActionTestCase(test.TestCase):

    def setUp(self):
        super(LogSurveyActionTestCase, self).setUp()

    def tearDown(self):
        super(LogSurveyActionTestCase, self).tearDown()

    @ddt.data(
        {'log_file': '/tmp/no_file_exists.txt',
         'log_format':
             '{timestamp} {{ {line} : {matched_pattern} : {name} }}',
         'exp_log_format':
             '{timestamp} {{ {line} : {matched_pattern} : {name} }}'
         },
        {'log_file': '/tmp/no_file_exists.txt',
         'log_format':
             '{timestamp} {{ {line} : {matched_pattern} : {name} }}\\r\\n',
         'exp_log_format':
             '{timestamp} {{ {line} : {matched_pattern} : {name} }}\r\n'
         },)
    @ddt.unpack
    def test_log_survey_init(self, log_file,
                             log_format,
                             exp_log_format):

        log_survey_obj = reconn_action.LogSurvey(log_file, log_format)
        self.assertEqual(exp_log_format, log_survey_obj.log_format)

    @ddt.data({'log_file': '/invalid_path/test_file.txt',
               'log_format':
                   '{timestamp} {{ {line} : {matched_pattern} : {name} }}',
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


@ddt.ddt
class RMQSurveyActionTestCase(test.TestCase):

    def setUp(self):
        super(RMQSurveyActionTestCase, self).setUp()

    def tearDown(self):
        super(RMQSurveyActionTestCase, self).tearDown()

    @mock.patch('pika.BlockingConnection')
    def test_rmq_survey_init(self,
                             mock_pika_BlockingConnection):
        rmq_params = dict(
            username='guest',
            password='guest',
            host='10.22.104.223',
            port=5672,
            virtual_host='/',
            exchange_name='test_exchange',
            queue_name='test_queue',
            routing_key='test',
            rmq_message_format='{{"line":"{line}",'
                               ' "matched_pattern":"{matched_pattern}",'
                               ' "timestamp":"{timestamp}", "uuid":"{uuid}",'
                               ' "request_id":"{request_id}" }}',
            rmq_msg_user_data='uuid:6e64ff56-0611-43c5-badc-8a106209e088, '
                              'request_id:'
                              'req-57ecbc1d-c64a-4421-8518-fe0ec6feb86d'
        )

        mock_connection = mock.Mock(name='mock_connection')
        mock_pika_BlockingConnection.return_value = mock_connection

        mock_channel = mock.Mock(name='mock_channel')
        mock_connection.channel.return_value = mock_channel

        rmq_survey_obj = reconn_action.RMQSurvey(rmq_params)

        mock_connection.add_on_connection_blocked_callback.\
            assert_called_once()
        mock_connection.add_on_connection_unblocked_callback.\
            assert_called_once()
        mock_connection.channel.assert_called_once_with()

        mock_channel.add_on_return_callback.assert_called_once()

        mock_channel.exchange_declare.assert_called_once_with(
            rmq_params['exchange_name'],
            'topic',
            durable=True)
        mock_channel.queue_declare.assert_called_once_with(
            rmq_params['queue_name'],
            durable=True)
        mock_channel.queue_bind.assert_called_once_with(
            rmq_params['queue_name'],
            rmq_params['exchange_name'],
            rmq_params['routing_key'])

        mock_channel.confirm_delivery.assert_called_once_with()

    @mock.patch('pika.BlockingConnection')
    def test_rmq_survey_init_conn_closed(self,
                                         mock_pika_BlockingConnection):
        host_with_no_rmq = '250.0.0.1'
        rmq_params = dict(
            username='valid_user',
            password='valid_pwd',
            host=host_with_no_rmq,
            port=5672,
            virtual_host='/',
        )
        mock_pika_BlockingConnection.side_effect = \
            pika.exceptions.ConnectionClosed
        self.assertRaises(pika.exceptions.ConnectionClosed,
                          reconn_action.RMQSurvey,
                          rmq_params)
        mock_pika_BlockingConnection.channel.assert_not_called()

    @mock.patch('pika.BlockingConnection')
    def test_rmq_survey_init_auth_error(self,
                                        mock_pika_BlockingConnection):
        rmq_params = dict(
            username='invalid_user',
            password='invalid_pwd',
            host='10.22.104.223',
            port=5672,
            virtual_host='/',
        )
        mock_pika_BlockingConnection.side_effect = \
            pika.exceptions.ProbableAuthenticationError
        self.assertRaises(pika.exceptions.ProbableAuthenticationError,
                          reconn_action.RMQSurvey,
                          rmq_params)
        mock_pika_BlockingConnection.channel.assert_not_called()

    @mock.patch('reconn.action.RMQSurvey._setup_rmq_exchange_queue')
    @mock.patch('reconn.action.RMQSurvey._estb_rmq_connection')
    @mock.patch('reconn.action.RMQSurvey.destructor')
    def test_reestb_rmq_conn(self,
                             mock_rmqsurvey_destructor,
                             mock_rmqsurvey_estb_conn,
                             mock_rmqsurvey_setup_exch_queue):
        rmq_params = dict(
            username='guest',
            password='guest',
            host='10.22.104.223',
            port=5672,
            virtual_host='/',
            exchange_name='test_exchange',
            queue_name='test_queue',
            routing_key='test',
            rmq_message_format='{{"line":"{line}",'
                               ' "matched_pattern":"{matched_pattern}",'
                               ' "timestamp":"{timestamp}", "uuid":"{uuid}",'
                               ' "request_id":"{request_id}" }}',
            rmq_msg_user_data='uuid:6e64ff56-0611-43c5-badc-8a106209e088, '
                              'request_id: '
                              'req-57ecbc1d-c64a-4421-8518-fe0ec6feb86d'
        )
        rmq_survey_obj = reconn_action.RMQSurvey(rmq_params)
        mock_rmqsurvey_estb_conn.reset_mock()

        rmq_survey_obj._reestb_rmq_connection()

        mock_rmqsurvey_destructor.assert_called_once_with()
        mock_rmqsurvey_estb_conn.assert_called_once_with()

    @mock.patch('pika.BasicProperties')
    @mock.patch('reconn.action.RMQSurvey._setup_rmq_exchange_queue')
    @mock.patch('reconn.action.RMQSurvey._estb_rmq_connection')
    def test_publish(self,
                     mock_rmqsurvey_estb_conn,
                     mock_rmqsurvey_setup_exch_queue,
                     mock_pika_BasicProperties):
        msg = "{'msg': 'testmsg'}"
        rmq_params = dict(
            exchange_name='test_exchange',
            routing_key='test',
        )

        rmq_survey_obj = reconn_action.RMQSurvey(rmq_params)
        mock_rmq_channel = mock.Mock(name='mock rmq channel')
        rmq_survey_obj._channel = mock_rmq_channel
        mock_properties = mock.Mock(name='mock pika properties obj')
        mock_pika_BasicProperties.return_value = mock_properties

        rmq_survey_obj._publish_msg_to_rmq(msg)

        mock_pika_BasicProperties.assert_called_once_with(
            app_id='reconn',
            content_type='application/json',
            headers={})

        mock_rmq_channel.publish.assert_called_once_with(
            rmq_params['exchange_name'],
            rmq_params['routing_key'],
            msg,
            properties=mock_properties,
            mandatory=True,
            immediate=False
        )

    @mock.patch('pika.BasicProperties')
    @mock.patch('reconn.action.RMQSurvey._setup_rmq_exchange_queue')
    @mock.patch('reconn.action.RMQSurvey._reestb_rmq_connection')
    @mock.patch('reconn.action.RMQSurvey._estb_rmq_connection')
    def test_publish_retry(self,
                           mock_rmqsurvey_estb_conn,
                           mock_rmqsurvey_reestb_conn,
                           mock_rmqsurvey_setup_exch_queue,
                           mock_pika_BasicProperties):
        msg = "{'msg': 'testmsg'}"
        rmq_params = dict(
            exchange_name='test_exchange',
            routing_key='test',
        )

        rmq_survey_obj = reconn_action.RMQSurvey(rmq_params)
        mock_rmq_channel = mock.Mock(name='mock rmq channel')
        rmq_survey_obj._channel = mock_rmq_channel
        mock_properties = mock.Mock(name='mock pika properties obj')
        mock_pika_BasicProperties.return_value = mock_properties
        mock_rmq_channel.publish.side_effect = [
            pika.exceptions.ConnectionClosed, None]

        rmq_survey_obj._publish_msg_to_rmq(msg)

        mock_pika_BasicProperties.assert_called_with(
            app_id='reconn',
            content_type='application/json',
            headers={})
        self.assertEqual(2, mock_pika_BasicProperties.call_count)

        mock_rmq_channel.publish.assert_called_with(
            rmq_params['exchange_name'],
            rmq_params['routing_key'],
            msg,
            properties=mock_properties,
            mandatory=True,
            immediate=False
        )
        self.assertEqual(2, mock_rmq_channel.publish.call_count)

        mock_rmqsurvey_reestb_conn.assert_called_once_with()


class SurveyActionTestCase(test.TestCase):
    _CONF = copy.deepcopy(reconn_action.CONF)

    def setUp(self):
        super(SurveyActionTestCase, self).setUp()
        self._LOG = reconn_action.LOG

    def tearDown(self):
        reconn_action.CONF = copy.deepcopy(self._CONF)
        reconn_action.LOG = self._LOG
        super(SurveyActionTestCase, self).tearDown()

    @mock.patch('reconn.action.LogSurvey')
    @mock.patch('reconn.action.RMQSurvey')
    def test_create_survey_actions(self, mock_RMQSurvey,
                                   mock_LogSurvey):
        CONF = mock.Mock()
        CONF.rmq_survey = {}
        CONF.log_survey.log_survey_action_log_file = ''
        CONF.log_survey.log_survey_action_log_format = ''
        reconn_action.CONF = CONF

        log = mock.Mock()
        reconn_action.LOG = log

        mock_log_survey_obj = mock.Mock()
        mock_LogSurvey.return_value = mock_log_survey_obj

        mock_rmq_survey_obj = mock.Mock()
        mock_RMQSurvey.return_value = mock_rmq_survey_obj

        action_names = ['rmq_survey', 'log_survey', 'unsupported_action_name']
        reconn_action.create_survey_actions(action_names)
        mock_RMQSurvey.assert_called_once_with(CONF.rmq_survey)
        mock_LogSurvey.assert_called_once_with(
            CONF.log_survey.log_survey_action_log_file,
            CONF.log_survey.log_survey_action_log_format)
        error_str = "action name %s not found. Supported actions: %s" % (
            'unsupported_action_name', reconn_action.supported_actions)
        log.error.assert_called_once_with(error_str)

        exp_action_mapper = {'log_survey': mock_log_survey_obj,
                             'rmq_survey': mock_rmq_survey_obj}
        self.assertEqual(exp_action_mapper, reconn_action._action_mapper)
