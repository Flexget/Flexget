import click

from flexget.utils.tools import get_latest_flexget_version_number, get_current_flexget_version


class AliasedGroup(click.Group):
    def resolve_command(self, ctx, args):
        """Click's 'ignore_unknown_options' doesn't really work  with Groups. This fixes that."""
        if args and ctx.ignore_unknown_options:
            for i in range(len(args)):
                # Look for an argument that appears to be an option name
                if not click.parser.split_opt(args[i])[0]:
                    unknown_opts, args = args[:i], args[i:]
                    ctx.args.extend(unknown_opts)
                    break
        return click.Group.resolve_command(self, ctx, args)

    def get_command(self, ctx, cmd_name):
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv
        matches = [x for x in self.list_commands(ctx)
                   if x.startswith(cmd_name)]
        if not matches:
            return None
        elif len(matches) == 1:
            # Update default map with shortened command name
            if ctx.default_map and matches[0] in ctx.default_map:
                ctx.default_map[cmd_name] = ctx.default_map[matches[0]]
            return click.Group.get_command(self, ctx, matches[0])
        ctx.fail('Too many matches: %s' % ', '.join(sorted(matches)))


def version_callback(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return
    current = get_current_flexget_version()
    latest = get_latest_flexget_version_number()

    # Print the version number
    click.echo('%s' % get_current_flexget_version())
    # Check for latest version from server
    if latest:
        if current == latest:
            click.echo('You are on the latest release.')
        else:
            click.echo('Latest release: %s' % latest)
    else:
        click.echo('Error getting latest version number from https://pypi.python.org/pypi/FlexGet')
    ctx.exit()


def debug_callback(ctx, param, value):
    if value:
        ctx.default_map['loglevel'] = 'debug'
    return value


def debug_trace_callback(ctx, param, value):
    if value:
        ctx.default_map['loglevel'] = 'trace'
        ctx.default_map['debug'] = True
    return value


def cron_callback(ctx, param, value):
    if value:
        ctx.default_map['loglevel'] = 'info'
    return value


@click.group("flexget", cls=AliasedGroup, context_settings={'default_map': {}, 'ignore_unknown_options': True, 'allow_extra_args': True})
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
    "--test",
    is_flag=True,
    default=False,
    help="Verbose what would happen on normal execution.",
)
@click.option(
    "-c",
    "--config",
    default="config.yml",
    help="Specify configuration file.",
    show_default=True
)
@click.option(
    "--logfile",
    "-l",
    default="flexget.log",
    help="Specify a custom logfile name/location.  [default: flexget.log in the config directory]",
)
@click.option(
    "--loglevel",
    "-L",
    help="Set the verbosity of the logger.",
    type=click.Choice(
        ["none", "critical", "error", "warning", "info", "verbose", "debug", "trace"]
    ),
    default="verbose",
)
@click.option('--bugreport', 'debug_tb', is_flag=True,
              help='Use this option to create a detailed bug report, '
                                 'note that the output might contain PRIVATE data, so edit that out')
# click.option('--profile', metavar='OUTFILE', nargs='?', const='flexget.profile',
#                             help='Use the python profiler for this run to debug performance issues.'),
@click.option('--debug', is_flag=True, callback=debug_callback, hidden=True)
@click.option('--debug-trace', is_flag=True, callback=debug_trace_callback, hidden=True)
@click.option('--debug-sql', is_flag=True, hidden=True)
@click.option('--experimental', is_flag=True, hidden=True)
@click.option('--ipc-port', type=click.IntRange(min=0), hidden=True)
@click.option('--cron', is_flag=True, callback=cron_callback,
                            help='use when executing FlexGet non-interactively: allows background '
                                 'maintenance to run, disables stdout and stderr output, reduces logging level')
@click.pass_context
def run_flexget(ctx, **params):
    click.echo("ran flexget")
    print(params)
    print(ctx.args)


@run_flexget.command()
@click.option('--aoeu', is_flag=True, default=False)
@click.pass_context
def execute(ctx, **params):
    print("ran execute")
    print(params)
    print(ctx.args)


if __name__ == "__main__":
    run_flexget()
