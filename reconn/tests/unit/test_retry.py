import mock

from reconn import test
from reconn import retry as reconn_retry
from reconn import exception as reconn_exception


class RetryActionTestCase(test.TestCase):
    def test_retry_decorator(self):
        mock_decorated_f = mock.Mock()
        mock_decorated_f.side_effect = [reconn_exception.RetryAgain, None]
        decorated_f_args = (1, 2, 'something', {'somekey': 'somevalue'})
        decorated_f_kwargs = {'testkwargs': 'testvalue'}

        reconn_retry.retry()(mock_decorated_f)(*decorated_f_args,
                                               **decorated_f_kwargs)

        mock_decorated_f.assert_called_with(*decorated_f_args,
                                            **decorated_f_kwargs)
        self.assertEqual(2, mock_decorated_f.call_count)

    def test_retry_limits(self):
        retry_limit = 1
        mock_decorated_f = mock.Mock()
        mock_decorated_f.side_effect = [reconn_exception.RetryAgain]
        decorated_f_args = (1, 2, 'something', {'somekey': 'somevalue'})
        decorated_f_kwargs = {'testkwargs': 'testvalue'}

        reconn_retry.retry(retry_limit)(mock_decorated_f)(
            *decorated_f_args,
            **decorated_f_kwargs)

        mock_decorated_f.assert_called_with(*decorated_f_args,
                                            **decorated_f_kwargs)
        self.assertEqual(retry_limit, mock_decorated_f.call_count)
