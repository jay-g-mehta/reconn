from reconn import exception as reconn_exception

from oslo_log import log as logging


LOG = logging.getLogger(__name__)


def retry(count=3):
    """decorator that repeatedly calls a decorated function
    as long as the decorated function raises RetryAgain exception
    and limited by count times max.
    """
    def wrapper(f):
        def retry_f(*args, **kwargs):
            retry_count = count
            LOG.debug("Retry %s max %d times", f, count)
            while retry_count > 0:
                retry_count = retry_count - 1
                try:
                    f(*args, **kwargs)
                except reconn_exception.RetryAgain as ra:
                    LOG.info("Retrying %s ... (%d)", f, retry_count)
                    continue
                break
        return retry_f
    return wrapper
