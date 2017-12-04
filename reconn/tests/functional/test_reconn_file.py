import os
import time
import io
import json

from reconn import test
import reconn


class ReconnTestCase(test.TestCase):
    def setUp(self):
        super(ReconnTestCase, self).setUp()

    def test_reconn_log_patterns(self):

        reconn.setup_reconn()
        prefix_path = os.getcwd()
        target_file = prefix_path + \
            '/reconn/tests/functional/sample_files/console.log'
        exp_pattern = ['login:', 'Starting network',
                       'initramfs:', 'rc.sysinit']
        config_file = prefix_path + \
            '/reconn/tests/functional/sample_files/reconn_log_survey.conf'
        reconn_log_file = '/tmp/' + self.id() + '_' + str(time.time) +\
                          '_reconn.log'
        # As defined in the config file
        survey_log_file = '/tmp/reconn_functional_test_reconn_survey.log'

        reconn.start_reconn(target_file,
                            config_file=config_file,
                            log_file=reconn_log_file)

        # Verify
        with io.open(survey_log_file, 'rt') as f:
            while True:
                line = f.readline()
                if line == '':
                    break
                self.assertIn(json.loads(line)["pattern"], exp_pattern)

        # clean up
        os.remove(survey_log_file)
        os.remove(reconn_log_file)
