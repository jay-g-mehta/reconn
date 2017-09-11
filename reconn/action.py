'''This file defines survey actions, that can be taken for matched survey patterns'''

from abc import ABCMeta, abstractmethod
import io
import codecs
import datetime
import pika
import json
import six

if six.PY2:
    import Queue as native_queue
else:
    import queue as native_queue

from oslo_log import log as logging

from reconn import conf as reconn_conf


CONF = reconn_conf.CONF
LOG = logging.getLogger(__name__)
supported_actions = ('log_survey', 'rmq_survey')
_action_mapper = {}


class SurveyAction(object):
    """Base class for actions"""
    __metaclass__ = ABCMeta

    def __init__(self):
        pass

    @abstractmethod
    def execute(self, *args, **kwargs):
        pass

    @abstractmethod
    def __del__(self):
        self.destructor()

    @abstractmethod
    def destructor(self):
        pass


class LogSurvey(SurveyAction):
    """Action that logs matched survey patterns"""
    def __init__(self, log_file, log_format):
        self.log_format = codecs.decode(log_format, 'unicode_escape')
        self.f = None
        self.f = io.open(log_file, 'ab',)

    def destructor(self):
        if self.f is not None:
            self.f.close()

    def __del__(self):
        self.destructor()

    def execute(self, pattern, line, *args, **kwargs):
        s = self.log_format.format(
            timestamp=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'),
            line=line,
            matched_pattern=pattern,
        )
        self.f.write(s)
        self.f.flush()


class RMQSurvey(object):
    """Action that publish messages to RMQ for matched survey patterns"""
    _exchange_type = 'topic'

    def __init__(self, rmq_params):
        self._username = rmq_params.get('username')
        self._password = rmq_params.get('password')
        self._host = rmq_params.get('host', '127.0.0.1')
        self._port = rmq_params.get('port', 5672)
        self._virtual_host = rmq_params.get('virtual_host', '/')
        self._connection = None
        self._channel = None
        self._exchange_name = rmq_params.get('exchange_name')
        self._queue_name = rmq_params.get('queue_name')
        self._routing_key = rmq_params.get('routing_key')
        self._blocked_connection_timeout = 5
        self._flag_rmq_blocked = False
        # Lets create an indefinite queue. It's safe as this
        # is just a temporary msg holder, used in a rare cases
        # when RMQ server is blocked because of low resource
        self.q = native_queue.Queue(-1)
        self._estb_rmq_connection()

    def destructor(self):
        if self._channel is not None and \
                not self._channel.is_closed and \
                not self._channel.is_closing:
            self._channel.close()
            LOG.debug("RMQ channel closed")

        if self._connection is not None and \
                not self._connection.is_closed and \
                not self._connection.is_closing:
            self._connection.close()
            LOG.debug("RMQ connection closed")

    def __del__(self):
        self.destructor()

    def _construct_msg(self, pattern, line):
        '''Construct msg to be publish in RMQ.
        Msg will be a string formed from json dumped msg obj'''
        msg_format = CONF.rmq_survey.rmq_message_format
        msg = {}
        msg.update(CONF.msg_user_data)
        msg.update(CONF.rmq_survey.rmq_msg_user_data)
        msg.update(
            {'line': line,
             'matched_pattern': pattern,
             'timestamp':
                 datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
             })

        try:
            msg = msg_format.format(**msg)
        except KeyError as e:
            LOG.exception("%s", e)
            LOG.exception("rmq_message_format or rmq_msg_user_data incorrect. "
                          "Key not found while composing message for RMQ. "
                          "Verify configuration")

        # TODO(jay): Validate json schema in the message.
        # Like property names in the message should be double quoted
        # and not single quote.

        # Handling control characters like \r \n.
        tmp_json_obj = json.loads(msg, strict=False)
        msg = json.dumps(tmp_json_obj, ensure_ascii=False)
        return msg

    def _publish_msg_to_rmq(self, msg):
        hdrs = {}
        properties = pika.BasicProperties(app_id='reconn',
                                          content_type='application/json',
                                          headers=hdrs)

        try:
            # set immediate=False, become independent of consumer exists
            # set mandatory=True, if msg cannot be routed to queue, we can get
            # exception and act to re-create queue and re-bind again or
            # verify routing_key, if necessary.
            self._channel.publish(self._exchange_name,
                                  self._routing_key,
                                  msg,
                                  properties=properties,
                                  mandatory=True,
                                  immediate=False)
        except pika.exceptions.UnroutableError as unroutable_excp:
            LOG.exception("%s" % unroutable_excp)
            (return_msg, ) = unroutable_excp.messages
            # return_msg is of type:
            # pika.adapters.blocking_connection.ReturnedMessage

            LOG.exception("%s", return_msg.method)
            # <Basic.Return(['exchange=test_exchange', 'reply_code=312',
            #   'reply_text=NO_ROUTE', 'routing_key=some_key'])>
        except pika.exceptions.NackError as nack_excp:
            LOG.exception("%s" % nack_excp)
        except pika.exceptions.ChannelClosed as channel_closed_excp:
            LOG.exception("%s" % channel_closed_excp)
        except pika.exceptions.ConnectionClosed as connection_closed_excp:
            LOG.exception("%s" % connection_closed_excp)

    def execute(self, pattern, line, *args, **kwargs):
        """Publish message"""
        if self._channel is None or not self._channel.is_open:
            LOG.error("Channel is None or not open. Not publishing message"
                      "pattern: %s, line: %s" % (pattern, line))
            # TODO(jay): try to re-estb connection and publish

        msg = self._construct_msg(pattern, line)
        if self._flag_rmq_blocked is True:
            # Note(jay): Race condition here.
            # A call back to _connection_unblocked_callback
            # might have unset  _flag_rmq_blocked. One msg
            # will be queued and not flushed until next msg
            # is published or flush is invoked
            self._queue_msg(msg)
        else:
            self._flush_queued_msgs()
            self._publish_msg_to_rmq(msg)

    def _queue_msg(self, msg):
        """Queue the msg for RMQ for later dispatch"""
        try:
            self.q.put_nowait(msg)
        except native_queue.Full:
            # This will not happen as our queue in indefinite.
            # But better be safe
            LOG.exception("Failed to queue msg for later dispatch to RMQ."
                          "Reason: Queue is full. Msg: %s", str(msg))

    def _flush_queued_msgs(self):
        """Flush all queued msgs to RMQ server"""
        while not self.q.empty():
            try:
                msg = self.q.get_nowait()
                self._publish_msg_to_rmq(msg)
            except native_queue.Empty as e:
                break

    def _connection_blocked_callback(self, method):
        """Callback when RMQ has sent Connection.Blocked frame indicating
         that RabbitMQ is low on resources.
         Voluntarily suspend publishing, until connection is unblocked
         """
        LOG.exception("RMQ server is low on resource. Halting publishing until RMQ"
                      "acknowledges healthy, and unblocked")
        self._flag_rmq_blocked = True

    def _connection_unblocked_callback(self, method):
        """Callback when RMQ has sent a Connection.Unblocked frame.
          It's okay to resume publishing."""
        LOG.info("RMQ server is unblocked, healthy, out of low resource."
                 "Resuming message publishing")
        self._flag_rmq_blocked = False

    def _msg_rejected_callback(self, channel, method, properties, body):
        """Broker rejected message and returned Basic.Return.
        Broker returns an undeliverable message for msg that was published with
        the "immediate" flag set, or an unroutable message for msg that was
        published with the "mandatory" flag set.
        """
        LOG.error("RMQ server rejected and returned msg: %s %s %s %s " % (
                  channel, method, properties, body))

    def _estb_rmq_connection(self):
        credentials = pika.credentials.PlainCredentials(self._username, self._password)
        parameters = pika.ConnectionParameters(
            host=self._host,
            port=self._port,
            virtual_host=self._virtual_host,
            credentials=credentials,
            blocked_connection_timeout=self._blocked_connection_timeout,
        )
        self._connection = pika.BlockingConnection(parameters=parameters)
        LOG.info("RMQ Connection with broker established at %s:%s" % (
            self._host, self._port))

        self._connection.add_on_connection_blocked_callback(
            self._connection_blocked_callback)
        self._connection.add_on_connection_unblocked_callback(
            self._connection_unblocked_callback)

        self._channel = self._connection.channel()
        LOG.info("RMQ Channel created")

        # Register call back for msg rejected by server
        self._channel.add_on_return_callback(self._msg_rejected_callback)

        # setup exchange
        try:
            self._channel.exchange_declare(self._exchange_name,
                                           self._exchange_type)
        except pika.exceptions.ChannelClosed as channel_closed_excp:
            # Raised when the exchange is already declared and no permission
            # to redeclare it. Like declaring default exchange of some topic
            # type.
            LOG.exception("%s" % channel_closed_excp)
            raise
        LOG.info("RMQ Exchange %s of type %s created" %
                 (self._exchange_name, self._exchange_type))

        self._channel.queue_declare(self._queue_name)
        LOG.info("RMQ Queue %s created", self._queue_name)

        # Bind queue with Exchange using routing key
        self._channel.queue_bind(self._queue_name,
                                 self._exchange_name, self._routing_key)

        LOG.info("RMQ Queue %s binding with Exchange %s done" %
                 (self._queue_name, self._exchange_name))

        # enable RMQ confirm mode, publish confirms
        self._channel.confirm_delivery()


def create_survey_actions(action_names):
    '''Create action, for given a list of valid input action names'''
    global _action_mapper

    for action_name in action_names:
        if action_name == 'log_survey':
            log_survey_obj = LogSurvey(
                CONF.log_survey.log_survey_action_log_file,
                CONF.log_survey.log_survey_action_log_format)
            _action_mapper[action_name] = log_survey_obj
        elif action_name == 'rmq_survey':
            rmq_params = CONF.rmq_survey
            rmq_survey_obj = RMQSurvey(rmq_params)
            _action_mapper[action_name] = rmq_survey_obj
        else:
            LOG.error("action name %s not found. Supported actions: %s" %
                      (action_name, supported_actions))


def get_survey_action(action_name):
    """Returns survey action object for input action name or None"""
    return _action_mapper.get(action_name, None)


def destroy_survey_actions():
    for action in _action_mapper.values():
        action.destructor()
    _action_mapper.clear()

