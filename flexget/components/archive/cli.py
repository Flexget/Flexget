import re
from collections import defaultdict
from datetime import datetime

from loguru import logger
from rich.progress import track

import flexget.components.archive.db
from flexget import options
from flexget.entry import Entry
from flexget.event import event
from flexget.manager import Session
from flexget.options import ParseExtrasAction, get_parser
from flexget.terminal import TerminalTable, console, table_parser
from flexget.utils.tools import strip_html

logger = logger.bind(name='archive_cli')


def do_cli(manager, options):
    action = options.archive_action

    if action == 'tag-source':
        tag_source(options.source, tag_names=options.tags)
    elif action == 'consolidate':
        consolidate()
    elif action == 'search':
        cli_search(options)
    elif action == 'inject':
        cli_inject(manager, options)


def consolidate():
    """
    Converts previous archive data model to new one.
    """

    session = Session()
    try:
        logger.verbose('Checking archive size ...')
        count = session.query(flexget.components.archive.db.ArchiveEntry).count()
        logger.verbose('Found {} items to migrate, this can be aborted with CTRL-C safely.', count)

        # consolidate old data
        # id's for duplicates
        duplicates = []

        for orig in track(
            session.query(flexget.components.archive.db.ArchiveEntry).yield_per(5),
            total=count,
            description='Processing...',
        ):
            # item already processed
            if orig.id in duplicates:
                continue

            # item already migrated
            if orig.sources:
                logger.info(
                    'Database looks like it has already been consolidated, item {} has already sources ...',
                    orig.title,
                )
                session.rollback()
                return

            # add legacy task to the sources list
            orig.sources.append(flexget.components.archive.db.get_source(orig.task, session))
            # remove task, deprecated .. well, let's still keep it ..
            # orig.task = None

            for dupe in (
                session.query(flexget.components.archive.db.ArchiveEntry)
                .filter(flexget.components.archive.db.ArchiveEntry.id != orig.id)
                .filter(flexget.components.archive.db.ArchiveEntry.title == orig.title)
                .filter(flexget.components.archive.db.ArchiveEntry.url == orig.url)
                .all()
            ):
                orig.sources.append(flexget.components.archive.db.get_source(dupe.task, session))
                duplicates.append(dupe.id)

        if duplicates:
            logger.info('Consolidated {} items, removing duplicates ...', len(duplicates))
            for id in duplicates:
                session.query(flexget.components.archive.db.ArchiveEntry).filter(
                    flexget.components.archive.db.ArchiveEntry.id == id
                ).delete()
        session.commit()
        logger.info('Completed! This does NOT need to be ran again.')
    except KeyboardInterrupt:
        session.rollback()
        logger.critical('Aborted, no changes saved')
    finally:
        session.close()


def tag_source(source_name, tag_names=None):
    """
    Tags all archived entries within a source with supplied tags

    :param string source_name: Source name
    :param list tag_names: List of tag names to add
    """

    if not tag_names or tag_names is None:
        return

    session = Session()
    try:
        # check that source exists
        source = (
            session.query(flexget.components.archive.db.ArchiveSource)
            .filter(flexget.components.archive.db.ArchiveSource.name == source_name)
            .first()
        )
        if not source:
            logger.critical('Source `{}` does not exists', source_name)
            srcs = ', '.join(
                [
                    s.name
                    for s in session.query(flexget.components.archive.db.ArchiveSource).order_by(
                        flexget.components.archive.db.ArchiveSource.name
                    )
                ]
            )
            if srcs:
                logger.info('Known sources: {}', srcs)
            return

        # construct tags list
        tags = []
        for tag_name in tag_names:
            tags.append(flexget.components.archive.db.get_tag(tag_name, session))

        # tag 'em
        logger.verbose('Please wait while adding tags {} ...', ', '.join(tag_names))
        for a in (
            session.query(flexget.components.archive.db.ArchiveEntry)
            .filter(flexget.components.archive.db.ArchiveEntry.sources.any(name=source_name))
            .yield_per(5)
        ):
            a.tags.extend(tags)
    finally:
        session.commit()
        session.close()


def cli_search(options):
    search_term = ' '.join(options.keywords)
    tags = options.tags
    sources = options.sources
    query = re.sub(r'[ \(\)\:]+', ' ', search_term).strip()

    table_data = []
    with Session() as session:
        for archived_entry in flexget.components.archive.db.search(
            session, query, tags=tags, sources=sources
        ):
            days_ago = (datetime.now() - archived_entry.added).days
            source_names = ', '.join([s.name for s in archived_entry.sources])
            tag_names = ', '.join([t.name for t in archived_entry.tags])

            table_data.append(['ID', str(archived_entry.id)])
            table_data.append(['Title', archived_entry.title])
            table_data.append(['Added', str(days_ago) + ' days ago'])
            table_data.append(['URL', archived_entry.url])
            table_data.append(['Source(s)', source_names or 'N/A'])
            table_data.append(['Tag(s)', tag_names or 'N/A'])
            if archived_entry.description:
                table_data.append(['Description', strip_html(archived_entry.description)])
            table_data.append([])
    if not table_data:
        console('No results found for search')
        return
    table = TerminalTable('Field', 'Value', table_type=options.table_type)
    for row in table_data:
        table.add_row(*row)
    console(table)


def cli_inject(manager, options):
    logger.debug('Finding inject content')
    inject_entries = defaultdict(list)
    with Session() as session:
        for id in options.ids:
            archive_entry = session.query(flexget.components.archive.db.ArchiveEntry).get(id)

            # not found
            if not archive_entry:
                logger.critical("There's no archived item with ID `{}`", id)
                continue

            # find if there is no longer any task within sources
            if not any(source.name in manager.tasks for source in archive_entry.sources):
                logger.error(
                    'None of sources ({}) exists anymore, cannot inject `{}` from archive!',
                    ', '.join([s.name for s in archive_entry.sources]),
                    archive_entry.title,
                )
                continue

            inject_entry = Entry(archive_entry.title, archive_entry.url)
            if archive_entry.description:
                inject_entry['description'] = archive_entry.description
            if options.immortal:
                logger.debug('Injecting as immortal')
                inject_entry['immortal'] = True
            inject_entry['accepted_by'] = 'archive inject'
            inject_entry.accept('injected')

            # update list of tasks to be injected
            for source in archive_entry.sources:
                inject_entries[source.name].append(inject_entry)

    for task_name in inject_entries:
        for inject_entry in inject_entries[task_name]:
            logger.info('Injecting from archive `{}` into `{}`', inject_entry['title'], task_name)

    for index, task_name in enumerate(inject_entries):
        options.inject = inject_entries[task_name]
        options.tasks = [task_name]
        # TODO: This is a bit hacky, consider a better way
        if index == len(inject_entries) - 1:
            # We use execute_command on the last item, rather than regular execute, to start FlexGet running.
            break
        manager.execute(options)
    manager.execute_command(options)


@event('options.register')
def register_parser_arguments():
    archive_parser = options.register_command(
        'archive', do_cli, help='Search and manipulate the archive database'
    )
    archive_parser.add_subparsers(title='Actions', metavar='<action>', dest='archive_action')
    # Default usage shows the positional arguments after the optional ones, override usage to fix it
    search_parser = archive_parser.add_subparser(
        'search',
        help='Search from the archive',
        usage='%(prog)s [-h] <keyword> [<keyword> ...] [optional arguments]',
        parents=[table_parser],
    )
    search_parser.add_argument(
        'keywords', metavar='<keyword>', nargs='+', help='Keyword(s) to search for'
    )
    search_parser.add_argument(
        '--tags', metavar='TAG', nargs='+', default=[], help='Tag(s) to search within'
    )
    search_parser.add_argument(
        '--sources', metavar='SOURCE', nargs='+', default=[], help='Source(s) to search within'
    )
    inject_parser = archive_parser.add_subparser(
        'inject', help='Inject entries from the archive back into tasks'
    )
    inject_parser.add_argument(
        'ids', nargs='+', type=int, metavar='ID', help='Archive ID of an item to inject'
    )
    inject_parser.add_argument(
        '--immortal',
        action='store_true',
        help='Injected entries will not be able to be rejected by any plugins',
    )
    exec_group = inject_parser.add_argument_group('execute arguments')
    exec_group.add_argument(
        'execute_options', action=ParseExtrasAction, parser=get_parser('execute')
    )
    tag_parser = archive_parser.add_subparser(
        'tag-source', help='Tag all archived entries within a given source'
    )
    tag_parser.add_argument(
        'source', metavar='<source>', help='The source whose entries you would like to tag'
    )
    tag_parser.add_argument(
        'tags',
        nargs='+',
        metavar='<tag>',
        help='The tag(s) you would like to apply to the entries',
    )
    archive_parser.add_subparser(
        'consolidate', help='Migrate old archive data to new model, may take a long time'
    )
