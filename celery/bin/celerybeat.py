#!/usr/bin/env python
"""celerybeat

.. program:: celerybeat

.. cmdoption:: -f, --logfile

    Path to log file. If no logfile is specified, ``stderr`` is used.

.. cmdoption:: -l, --loglevel

    Logging level, choose between ``DEBUG``, ``INFO``, ``WARNING``,
    ``ERROR``, ``CRITICAL``, or ``FATAL``.

.. cmdoption:: -p, --pidfile

    Path to pidfile.

.. cmdoption:: -d, --detach, --daemon

    Run in the background as a daemon.

.. cmdoption:: -u, --uid

    User-id to run ``celerybeat`` as when in daemon mode.

.. cmdoption:: -g, --gid

    Group-id to run ``celerybeat`` as when in daemon mode.

.. cmdoption:: --umask

    umask of the process when in daemon mode.

.. cmdoption:: --workdir

    Directory to change to when in daemon mode.

.. cmdoption:: --chroot

    Change root directory to this path when in daemon mode.

"""
import os
import sys
from celery.loaders import current_loader
from celery.loaders import settings
from celery import __version__
from celery.log import emergency_error
from celery import conf
from celery import platform
from celery.beat import ClockService
import traceback
import optparse


STARTUP_INFO_FMT = """
Configuration ->
    * Broker -> amqp://%(vhost)s@%(host)s:%(port)s
    * Exchange -> %(exchange)s (%(exchange_type)s)
    * Consumer -> Queue:%(consumer_queue)s Routing:%(consumer_rkey)s
""".strip()

OPTION_LIST = (
    optparse.make_option('-f', '--logfile', default=conf.DAEMON_LOG_FILE,
            action="store", dest="logfile",
            help="Path to log file."),
    optparse.make_option('-l', '--loglevel', default=conf.DAEMON_LOG_LEVEL,
            action="store", dest="loglevel",
            help="Choose between DEBUG/INFO/WARNING/ERROR/CRITICAL/FATAL."),
    optparse.make_option('-p', '--pidfile', default=conf.DAEMON_PID_FILE,
            action="store", dest="pidfile",
            help="Path to pidfile."),
    optparse.make_option('-d', '--detach', '--daemon', default=False,
            action="store_true", dest="detach",
            help="Run in the background as a daemon."),
    optparse.make_option('-u', '--uid', default=None,
            action="store", dest="uid",
            help="User-id to run celerybeat as when in daemon mode."),
    optparse.make_option('-g', '--gid', default=None,
            action="store", dest="gid",
            help="Group-id to run celerybeat as when in daemon mode."),
    optparse.make_option('--umask', default=0,
            action="store", type="int", dest="umask",
            help="umask of the process when in daemon mode."),
    optparse.make_option('--workdir', default=None,
            action="store", dest="working_directory",
            help="Directory to change to when in daemon mode."),
    optparse.make_option('--chroot', default=None,
            action="store", dest="chroot",
            help="Change root directory to this path when in daemon mode."),
    )


def run_clockserver(detach=False, loglevel=conf.DAEMON_LOG_LEVEL,
        logfile=conf.DAEMON_LOG_FILE, pidfile=conf.DAEMON_PID_FILE,
        umask=0, uid=None, gid=None, working_directory=None, chroot=None,
        **kwargs):
    """Starts the celerybeat clock server."""

    print("Celery Beat %s is starting." % __version__)

    # Setup logging
    if not isinstance(loglevel, int):
        loglevel = conf.LOG_LEVELS[loglevel.upper()]
    if not detach:
        logfile = None # log to stderr when not running in the background.

    # Dump configuration to screen so we have some basic information
    # when users sends e-mails.
    print(STARTUP_INFO_FMT % {
            "vhost": getattr(settings, "AMQP_VHOST", "(default)"),
            "host": getattr(settings, "AMQP_SERVER", "(default)"),
            "port": getattr(settings, "AMQP_PORT", "(default)"),
            "exchange": conf.AMQP_EXCHANGE,
            "exchange_type": conf.AMQP_EXCHANGE_TYPE,
            "consumer_queue": conf.AMQP_CONSUMER_QUEUE,
            "consumer_rkey": conf.AMQP_CONSUMER_ROUTING_KEY,
            "publisher_rkey": conf.AMQP_PUBLISHER_ROUTING_KEY,
            "loglevel": loglevel,
            "pidfile": pidfile,
    })

    print("Celery Beat has started.")
    if detach:
        from celery.log import setup_logger, redirect_stdouts_to_logger
        context = platform.create_daemon_context(logfile, pidfile,
                                        chroot_directory=chroot,
                                        working_directory=working_directory,
                                        umask=umask,
                                        uid=uid,
                                        gid=gid)
        context.open()
        logger = setup_logger(loglevel, logfile)
        redirect_stdouts_to_logger(logger, loglevel)

    # Run the worker init handler.
    # (Usually imports task modules and such.)
    current_loader.on_worker_init()

    def _run_clock():
        clockservice = ClockService(loglevel=loglevel,
                                    logfile=logfile,
                                    is_detached=detach)

        try:
            clockservice.start()
        except Exception, e:
            emergency_error(logfile,
                    "celerybeat raised exception %s: %s\n%s" % (
                            e.__class__, e, traceback.format_exc()))

    try:
        _run_clock()
    except:
        if detach:
            context.close()
        raise


def parse_options(arguments):
    """Parse the available options to ``celeryd``."""
    parser = optparse.OptionParser(option_list=OPTION_LIST)
    options, values = parser.parse_args(arguments)
    return options


if __name__ == "__main__":
    options = parse_options(sys.argv[1:])
    run_clockserver(**vars(options))
