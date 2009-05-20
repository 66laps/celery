"""celery.backends.base"""
from celery.timer import TimeoutTimer
try:
    import cPickle as pickle
except ImportError:
    import pickle
import sys


def find_nearest_pickleable_exception(exc):
    """With an exception instance, iterate over its super classes (by mro)
    and find the first super exception that is pickleable.
  
    :param exc: An exception instance.
    :rtype: :exc:`Exception`

    """
    for supercls in exc.__class__.mro():
        try:
            superexc = supercls(exc.args)
            pickle.dumps(superexc)
        except:
            pass
        else:
            return superexc
    return exc


class UnpickleableExceptionWrapper(Exception):
    """Wraps unpickleable exceptions.
   
    :param exc_module: see :attr:`exc_module`.

    :param exc_cls_name: see :attr:`exc_cls_name`.
    
    :param exc_args: The arguments for the original exception.

    .. attribute:: exc_module

        The module of the original exception.

    .. attribute:: exc_cls_name

        The name of the original exception class.

    Example

        >>> try:
        ...     something_raising_unpickleable_exc()
        >>> except Exception, e:
        ...     exc = UnpickleableException(e.__class__.__module__,
        ...                                 e.__class__.__name__,
        ...                                 e.args)
        ...     pickle.dumps(exc) # Works fine.

    """

    def __init__(self, exc_module, exc_cls_name, exc_args):
        self.exc_module = exc_module
        self.exc_cls = exc_cls_name
        super(Exception, self).__init__(exc_module, exc_cls_name, exc_args)


class BaseBackend(object):
    """The base backend class. All backends should inherit from this."""

    def store_result(self, task_id, result, status):
        """Store the result and status of a task."""
        raise NotImplementedError(
                "Backends must implement the store_result method")

    def mark_as_done(self, task_id, result):
        """Mark task as successfully executed."""
        return self.store_result(task_id, result, status="DONE")

    def mark_as_failure(self, task_id, exc):
        """Mark task as executed with failure. Stores the execption."""
        return self.store_result(task_id, exc, status="FAILURE")

    def prepare_exception(self, exc):
        exc = find_nearest_pickleable_exception(exc)
        try:
            pickle.dumps(exc)
        except pickle.PickleError:
            excwrapper = UnpickleableExceptionWrapper(
                            exc.__class__.__module__,
                            exc.__class__.__name__,
                            exc.args)
            return excwrapper
        else:
            return exc

    def mark_as_retry(self, task_id, exc):
        """Mark task for retry."""
        return self.store_result(task_id, exc, status="RETRY")

    def get_status(self, task_id):
        """Get the status of a task."""
        raise NotImplementedError(
                "Backends must implement the get_status method")

    def prepare_result(self, result):
        """Prepare result for storage."""
        if result is None:
            return True
        return result

    def get_result(self, task_id):
        """Get the result of a task."""
        raise NotImplementedError(
                "Backends must implement the get_result method")

    def is_done(self, task_id):
        """Returns ``True`` if the task was successfully executed."""
        return self.get_status(task_id) == "DONE"

    def cleanup(self):
        """Backend cleanup. Is run by
        :class:`celery.task.DeleteExpiredTaskMetaTask`."""
        pass

    def wait_for(self, task_id, timeout=None):
        """Wait for task and return its result.

        If the task raises an exception, this exception
        will be re-raised by :func:`wait_for`.

        If ``timeout`` is not ``None``, this raises the
        :class:`celery.timer.TimeoutError` exception if the operation takes
        longer than ``timeout`` seconds.

        """
        timeout_timer = TimeoutTimer(timeout)
        while True:
            status = self.get_status(task_id)
            if status == "DONE":
                return self.get_result(task_id)
            elif status == "FAILURE":
                raise self.get_result(task_id)
            timeout_timer.tick()
