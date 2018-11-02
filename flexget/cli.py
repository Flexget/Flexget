import os
import random
import string

import click

from flexget import logger
from flexget.entry import Entry
from flexget.event import fire_event
from flexget.manager import Manager, DEFAULT_OPTIONS
from flexget.terminal import console
from flexget.utils.tools import (
    get_latest_flexget_version_number,
    get_current_flexget_version,
)


class AliasedGroup(click.Group):
    def get_command(self, ctx, cmd_name):
        """Allows unambigouous partial matches."""
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv
        matches = [x for x in self.list_commands(ctx) if x.startswith(cmd_name)]
        if not matches:
            return None
        elif len(matches) == 1:
            return click.Group.get_command(self, ctx, matches[0])
        ctx.fail("Too many matches: %s" % ", ".join(sorted(matches)))

    def parse_core_options(self, args=None):
        """
        Returns known core options without validating anything. Works before plugins are loaded.
        """
        if args is None:
            args = click.get_os_args()
        with self.make_context(
            "flexget",
            args,
            ignore_unknown_options=True,
            help_option_names=[],
            resilient_parsing=True,
        ) as ctx:
            return {k: v for k, v in ctx.params.items() if v is not None}


def inject_callback(ctx, param, value):
    return [
        Entry(
            **{
                "title": title,
                "url": "http://localhost/inject/{}".format(
                    "".join(random.sample(string.ascii_letters + string.digits, 30))
                ),
            }
        )
        for title in value
    ]


def version_callback(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return
    current = get_current_flexget_version()
    latest = get_latest_flexget_version_number()

    # Print the version number
    console("%s" % get_current_flexget_version())
    # Check for latest version from server
    if latest:
        if current == latest:
            console("You are on the latest release.")
        else:
            console("Latest release: %s" % latest)
    else:
        console(
            "Error getting latest version number from https://pypi.python.org/pypi/FlexGet"
        )
    ctx.exit()


def debug_callback(ctx, param, value):
    if value:
        ctx.default_map["loglevel"] = "debug"
    return value


def debug_trace_callback(ctx, param, value):
    if value:
        ctx.default_map["loglevel"] = "trace"
        ctx.default_map["debug"] = True
    return value


def cron_callback(ctx, param, value):
    if value:
        ctx.default_map["loglevel"] = "info"
    return value


pass_manager = click.make_pass_decorator(Manager)


@click.group(
    "flexget", cls=AliasedGroup, context_settings={"default_map": DEFAULT_OPTIONS}
)
@click.option(
    "-V",
    "--version",
    is_flag=True,
    callback=version_callback,
    expose_value=False,
    is_eager=True,
    help="Print FlexGet version and exit.",
)
@click.option(
    "--test", is_flag=True, help="Verbose what would happen on normal execution."
)
@click.option("-c", "--config", help="Specify configuration file.", show_default=True)
@click.option(
    "--logfile",
    "-l",
    help="Specify a custom logfile name/location.  [default: flexget.log in the config directory]",
)
@click.option(
    "--loglevel",
    "-L",
    help="Set the verbosity of the logger.",
    type=click.Choice(
        ["none", "critical", "error", "warning", "info", "verbose", "debug", "trace"]
    ),
)
@click.option(
    "--cron",
    is_flag=True,
    callback=cron_callback,
    help="use when executing FlexGet non-interactively: allows background "
    "maintenance to run, disables stdout and stderr output, reduces logging level",
)
@click.option("--ipc-port", type=click.IntRange(min=0), hidden=True)
@click.option(
    "--bugreport",
    "debug_tb",
    is_flag=True,
    help="Use this option to create a detailed bug report, "
    "note that the output might contain PRIVATE data, so edit that out",
)
# TODO: make this a plugin?
@click.option(
    "--profile",
    "do_profile",
    is_flag=True,
    help="Use the python profiler for this run to debug performance issues.",
)
@click.option("--debug", is_flag=True, callback=debug_callback, hidden=True)
@click.option("--debug-trace", is_flag=True, callback=debug_trace_callback, hidden=True)
@click.option("--debug-sql", is_flag=True, hidden=True)
@click.option("--experimental", is_flag=True, hidden=True)
@pass_manager
def run_flexget(manager, **params):
    # manager gets initialized with options before plugins are loaded. Update options with fully parsed versions now
    # TODO: is this the right answer? What about when it's an IPC run and manager already has inited options?
    manager.options.update(params)


@run_flexget.command("execute", help="execute tasks now")
@click.option(
    "--tasks",
    "--task",
    metavar="TASK",
    multiple=True,
    help='run only specified task(s), optionally using glob patterns ("tv-*"). '
    "matching is case-insensitive",
)
@click.option(
    "--learn",
    is_flag=True,
    help="matches are not downloaded but will be skipped in the future",
)
@click.option(
    "--disable-phase", "--disable-phases", "disable_phases", multiple=True, hidden=True
)
@click.option("--inject", multiple=True, callback=inject_callback, hidden=True)
# Plugins should respect these flags where appropriate
@click.option("--retry", is_flag=True, hidden=True)
@click.option(
    "--no-cache",
    "nocache",
    is_flag=True,
    help="disable caches. works only in plugins that have explicit support",
)
@pass_manager
@click.pass_context
def execute(ctx, manager, **params):
    # Execute uses a few parameters defined at the root of the parser
    if ctx.parent:
        parent_keys = ['debug', 'cron', 'test', 'loglevel']
        for key in parent_keys:
            if key in ctx.parent.params:
                params[key] = ctx.parent.params[key]
    manager.execute_command(options=params)


@run_flexget.group(
    "daemon",
    help="run continuously, executing tasks according to schedules defined in config",
)
@click.pass_context
def daemon(ctx, **params):
    # TODO: set loglevel to info?
    pass


@daemon.command("start", help="start the daemon")
@click.option(
    "-d",
    "--daemonize",
    is_flag=True,
    help="causes process to daemonize after starting " "(not available on Windows)",
)
@click.option(
    "--autoreload-config",
    is_flag=True,
    help="automatically reload the config from disk if the daemon detects any changes",
)
@pass_manager
def daemon_start(manager, daemonize, autoreload_config):
    console("daemon_start")
    manager.run_daemon(daemonize=daemonize, autoreload_config=autoreload_config)


@daemon.command("stop", help="shutdown the running daemon")
@click.option(
    "--wait",
    is_flag=True,
    help="wait for all queued tasks to finish before stopping daemon",
)
@pass_manager
def daemon_stop(manager, wait):
    if not manager.is_daemon:
        console("There does not appear to be a daemon running.", err=True)
        return
    tasks = (
        "all queued tasks (if any) have"
        if wait
        else "currently running task (if any) has"
    )
    console(
        "Daemon shutdown requested. Shutdown will commence when %s finished executing."
        % tasks
    )
    manager.shutdown(wait)


@daemon.command("status", help="check if a daemon is running")
@pass_manager
def daemon_status(manager, **params):
    if manager.is_daemon:
        console("Daemon running. (PID: %s)" % os.getpid())


@daemon.command(
    "reload-config", help="causes a running daemon to reload the config from disk"
)
@pass_manager
def daemon_reload(manager, **params):
    if not manager.is_daemon:
        console("There does not appear to be a daemon running.", err=True)
        return
    console("Reloading config from disk.")
    try:
        manager.load_config()
    except ValueError as e:
        console("Error loading config: %s" % e.args[0])
    else:
        console("Config successfully reloaded from disk.")


def main():
    from flexget.manager import Manager

    logger.initialize()
    args = click.get_os_args()
    try:
        params = run_flexget.parse_core_options(args)
    except click.exceptions.Exit as e:
        # -V can end us up here
        return
    manager = Manager(params)
    if manager.run_ipc_command(args):
        return
    with manager.acquire_lock():
        manager.initialize()
        fire_event("options.register")
        run_flexget(args, obj=manager)
