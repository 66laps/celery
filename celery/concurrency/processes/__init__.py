"""

Process Pools.

"""
import sys
import traceback

from celery import log
from celery.datastructures import ExceptionInfo
from celery.utils.functional import partial

from celery.concurrency.processes.pool import Pool, RUN


class TaskPool(object):
    """Process Pool for processing tasks in parallel.

    :param processes: see :attr:`processes`.
    :param logger: see :attr:`logger`.


    .. attribute:: limit

        The number of processes that can run simultaneously.

    .. attribute:: logger

        The logger used for debugging.

    """
    Pool = Pool

    def __init__(self, processes=None, putlocks=True, logger=None, **options):
        self.processes = processes
        self.putlocks = putlocks
        self.logger = logger or log.get_default_logger()
        self.options = options
        self._pool = None

    def start(self):
        """Run the task pool.

        Will pre-fork all workers so they're ready to accept tasks.

        """
        self._pool = self.Pool(processes=self.processes, **self.options)

    def stop(self):
        """Gracefully stop the pool."""
        if self._pool is not None and self._pool._state == RUN:
            self._pool.close()
            self._pool.join()
            self._pool = None

    def terminate(self):
        """Force terminate the pool."""
        if self._pool is not None:
            self._pool.terminate()
            self._pool = None

    def apply_async(self, target, args=None, kwargs=None, callbacks=None,
            errbacks=None, accept_callback=None, timeout_callback=None,
            **compat):
        """Equivalent of the :func:`apply` built-in function.

        All `callbacks` and `errbacks` should complete immediately since
        otherwise the thread which handles the result will get blocked.

        """
        args = args or []
        kwargs = kwargs or {}
        callbacks = callbacks or []
        errbacks = errbacks or []

        on_ready = partial(self.on_ready, callbacks, errbacks)
        on_worker_error = partial(self.on_worker_error, errbacks)

        self.logger.debug("TaskPool: Apply %s (args:%s kwargs:%s)" % (
            target, args, kwargs))

        return self._pool.apply_async(target, args, kwargs,
                                      callback=on_ready,
                                      accept_callback=accept_callback,
                                      timeout_callback=timeout_callback,
                                      error_callback=on_worker_error,
                                      waitforslot=self.putlocks)

    def grow(self, n=1):
        return self._pool.grow(n)

    def shrink(self, n=1):
        return self._pool.shrink(n)

    def on_worker_error(self, errbacks, exc):
        einfo = ExceptionInfo((exc.__class__, exc, None))
        [errback(einfo) for errback in errbacks]

    def on_ready(self, callbacks, errbacks, ret_value):
        """What to do when a worker task is ready and its return value has
        been collected."""

        if isinstance(ret_value, ExceptionInfo):
            if isinstance(ret_value.exception, (
                    SystemExit, KeyboardInterrupt)):
                raise ret_value.exception
            [self.safe_apply_callback(errback, ret_value)
                    for errback in errbacks]
        else:
            [self.safe_apply_callback(callback, ret_value)
                    for callback in callbacks]

    def safe_apply_callback(self, fun, *args):
        try:
            fun(*args)
        except:
            self.logger.error("Pool callback raised exception: %s" % (
                traceback.format_exc(), ),
                exc_info=sys.exc_info())

    @property
    def info(self):
        return {"max-concurrency": self.processes,
                "processes": [p.pid for p in self._pool._pool],
                "max-tasks-per-child": self._pool._maxtasksperchild,
                "put-guarded-by-semaphore": self.putlocks,
                "timeouts": (self._pool.soft_timeout, self._pool.timeout)}
