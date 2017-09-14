import mock
import ddt
import copy
import logging as py_logging

from reconn import test
from reconn import utils as reconn_utils


@ddt.ddt
class ReconnUtilTestCase(test.TestCase):
    _CONF = copy.deepcopy(reconn_utils.CONF)

    def setUp(self):
        super(ReconnUtilTestCase, self).setUp()

    def tearDown(self):
        reconn_utils.CONF = copy.deepcopy(self._CONF)
        super(ReconnUtilTestCase, self).tearDown()

    def test_suppress_imp_modules_logging(self):
        suppressed_log_level = py_logging.INFO
        pika_log = reconn_utils.py_logging.getLogger('pika')
        watchdog_log = reconn_utils.py_logging.getLogger('watchdog')
        reconn_utils.suppress_imported_modules_logging()
        self.assertEqual(suppressed_log_level, pika_log.level)
        self.assertEqual(suppressed_log_level, watchdog_log.level)

    @mock.patch('reconn.utils.logging.register_options')
    def test_reconn_opts_registration(self, oslo_log_register_options):
        CONF = reconn_utils.CONF
        reconn_utils.register_reconn_opts()
        valid_reconn_opts = ['target_file', 'timeout',
                             'survey_action_message_format',
                             'msg_user_data', 'end_reconn',
                             'survey_group']
        for opt in valid_reconn_opts:
            self.assertIn(opt, CONF)

        oslo_log_register_options.assert_called_once_with(CONF)

    def test_configured_reconn_survey_groups_opts_registration(self):
        CONF = reconn_utils.CONF
        reconn_utils.register_reconn_opts()
        CONF.survey_group = 'test_survey_group'
        reconn_utils.register_configured_reconn_survey_groups()
        valid_survey_group_opts = ['pattern', 'name', 'success', 'failure']
        for opt in CONF.test_survey_group:
            self.assertIn(opt, valid_survey_group_opts)

    def test_reconn_opt_survey_group_is_none(self):
        reconn_utils.register_reconn_opts()
        self.assertRaises(ValueError,
                          reconn_utils.register_configured_reconn_survey_groups)

    def test_default_survey_action(self):
        CONF = reconn_utils.CONF
        reconn_utils.register_reconn_opts()
        CONF.survey_group = 'test_survey_group'
        reconn_utils.register_configured_reconn_survey_groups()
        self.assertEqual('log_survey', CONF.test_survey_group.success)

    def test_default_survey_action_in_supported_actions(self):
        CONF = reconn_utils.CONF
        reconn_utils.register_reconn_opts()
        CONF.survey_group = 'test_survey_group'
        reconn_utils.register_configured_reconn_survey_groups()
        self.assertIn(CONF.test_survey_group.success,
                      reconn_utils.reconn_action.supported_actions)

    def test_log_survey_action_opts_registration(self):
        CONF = reconn_utils.CONF
        reconn_utils.register_reconn_opts()
        CONF.survey_group = 'test_survey_group'
        reconn_utils.register_configured_reconn_survey_groups()
        CONF.test_survey_group.success = 'log_survey'

        valid_log_survey_action_opts = ['log_survey_action_log_format',
                                        'log_survey_action_log_file']
        reconn_utils.register_reconn_survey_action_groups()
        for opt in CONF.log_survey:
            self.assertIn(opt, valid_log_survey_action_opts)

    def test_rmq_survey_action_opts_registration(self):
        CONF = reconn_utils.CONF
        reconn_utils.register_reconn_opts()
        CONF.survey_group = 'test_survey_group'
        reconn_utils.register_configured_reconn_survey_groups()
        CONF.test_survey_group.success = 'rmq_survey'

        valid_rmq_survey_action_opts = ['username',
                                        'password',
                                        'host',
                                        'port',
                                        'virtual_host',
                                        'exchange_name',
                                        'queue_name',
                                        'routing_key',
                                        'rmq_message_format',
                                        'rmq_msg_user_data']
        reconn_utils.register_reconn_survey_action_groups()
        for opt in CONF.rmq_survey:
            self.assertIn(opt, valid_rmq_survey_action_opts)

    def test_re_patterns_obj_creation(self):
        CONF = reconn_utils.CONF
        reconn_utils.register_reconn_opts()
        CONF.survey_group = 'test_survey_group1, test_survey_group2'
        reconn_utils.register_configured_reconn_survey_groups()
        CONF.test_survey_group1.pattern = 'pattern1'
        CONF.test_survey_group2.pattern = 'pattern2'
        re_objs = reconn_utils.create_re_objs()
        self.assertEqual(2, len(re_objs))
        for survey_grp_name, re_obj in re_objs:
            self.assertIn(survey_grp_name, ['test_survey_group1',
                                            'test_survey_group2'])
            if survey_grp_name == 'test_survey_group1':
                self.assertEqual('pattern1', re_obj.pattern)
            else:
                self.assertEqual('pattern2', re_obj.pattern)

    @ddt.data({'line': 'Line with matching pattern',
               'exp_return': ('test_survey_group', 'matching pattern')},
              {'line': 'Line without matching any pattern', 'exp_return': (None, None)})
    @ddt.unpack
    def test_search_patterns(self, line, exp_return):
        CONF = reconn_utils.CONF
        reconn_utils.register_reconn_opts()
        CONF.survey_group = 'test_survey_group'
        reconn_utils.register_configured_reconn_survey_groups()
        CONF.test_survey_group.pattern = 'matching pattern'
        re_objs = reconn_utils.create_re_objs()

        ret_value = reconn_utils.search_patterns(re_objs, line)
        self.assertEqual(exp_return, ret_value)



    @ddt.data({'line': 'Matching reconn end pattern', 'exp_return': 'end pattern'},
              {'line': 'No end reconn pattern', 'exp_return': None})
    @ddt.unpack
    def test_search_end_reconn_pattern(self, line, exp_return):
        CONF = reconn_utils.CONF
        reconn_utils.register_reconn_opts()
        CONF.survey_group = 'test_survey_group, end_reconn_survey_group'
        CONF.end_reconn = 'end_reconn_survey_group'
        reconn_utils.register_configured_reconn_survey_groups()
        CONF.end_reconn_survey_group.pattern = 'end pattern'

        ret_value = reconn_utils.search_end_reconn_pattern(line)
        self.assertEqual(exp_return, ret_value)

    @ddt.data({'pattern': 'pattern1', 'exp_return': False},
              {'pattern': 'end pattern', 'exp_return': True})
    @ddt.unpack
    def test_is_pattern_to_end_reconn(self, pattern, exp_return):
        CONF = reconn_utils.CONF
        reconn_utils.register_reconn_opts()
        CONF.survey_group = 'test_survey_group, end_reconn_survey_group'
        CONF.end_reconn = 'end_reconn_survey_group'
        reconn_utils.register_configured_reconn_survey_groups()
        CONF.end_reconn_survey_group.pattern = 'end pattern'

        ret_val = reconn_utils.is_pattern_to_end_reconn(pattern)
        self.assertEqual(exp_return, ret_val)

    @ddt.data({'pattern': 'pattern1', 'exp_return': False})
    @ddt.unpack
    def test_is_pattern_to_end_reconn_when_end_reconn_is_none(self,
                                                              pattern,
                                                              exp_return):
        """test is_pattern_to_end_reconn when end_reconn is None"""
        CONF = reconn_utils.CONF
        reconn_utils.register_reconn_opts()
        CONF.survey_group = 'test_survey_group'
        CONF.end_reconn = None
        reconn_utils.register_configured_reconn_survey_groups()

        ret_val = reconn_utils.is_pattern_to_end_reconn(pattern)
        self.assertEqual(exp_return, ret_val)

    @ddt.data({'pattern': 'pattern1', 'exp_act_name': 'log_survey'},
              {'pattern': 'patternxyz', 'exp_act_name': None})
    @ddt.unpack
    def test_get_survey_success_action_name(self, pattern, exp_act_name):
        CONF = reconn_utils.CONF
        reconn_utils.register_reconn_opts()
        CONF.survey_group = 'test_survey_group1, test_survey_group2'
        reconn_utils.register_configured_reconn_survey_groups()
        CONF.test_survey_group1.pattern = 'pattern1'
        CONF.test_survey_group2.pattern = 'pattern2'
        CONF.test_survey_group1.success = 'log_survey'
        CONF.test_survey_group2.success = 'rmq_survey'
        ret_action_name = reconn_utils.get_survey_success_action_name(pattern)
        self.assertEqual(exp_act_name, ret_action_name)
