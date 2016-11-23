from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import re
from collections import defaultdict
from datetime import datetime

from flexget import options
from flexget.entry import Entry
from flexget.event import event
from flexget.manager import Session
from flexget.options import ParseExtrasAction, get_parser
from flexget.plugins.generic.archive import ArchiveEntry, ArchiveSource, get_source, get_tag, search
from flexget.terminal import TerminalTable, TerminalTableError, table_parser, console
from flexget.utils.tools import strip_html

log = logging.getLogger('archive_cli')


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
        log.verbose('Checking archive size ...')
        count = session.query(ArchiveEntry).count()
        log.verbose('Found %i items to migrate, this can be aborted with CTRL-C safely.' % count)

        # consolidate old data
        from progressbar import ProgressBar, Percentage, Bar, ETA

        widgets = ['Process - ', ETA(), ' ', Percentage(), ' ', Bar(left='[', right=']')]
        bar = ProgressBar(widgets=widgets, maxval=count).start()

        # id's for duplicates
        duplicates = []

        for index, orig in enumerate(session.query(ArchiveEntry).yield_per(5)):
            bar.update(index)

            # item already processed
            if orig.id in duplicates:
                continue

            # item already migrated
            if orig.sources:
                log.info('Database looks like it has already been consolidated, '
                         'item %s has already sources ...' % orig.title)
                session.rollback()
                return

            # add legacy task to the sources list
            orig.sources.append(get_source(orig.task, session))
            # remove task, deprecated .. well, let's still keep it ..
            # orig.task = None

            for dupe in session.query(ArchiveEntry). \
                    filter(ArchiveEntry.id != orig.id). \
                    filter(ArchiveEntry.title == orig.title). \
                    filter(ArchiveEntry.url == orig.url).all():
                orig.sources.append(get_source(dupe.task, session))
                duplicates.append(dupe.id)

        if duplicates:
            log.info('Consolidated %i items, removing duplicates ...' % len(duplicates))
            for id in duplicates:
                session.query(ArchiveEntry).filter(ArchiveEntry.id == id).delete()
        session.commit()
        log.info('Completed! This does NOT need to be ran again.')
    except KeyboardInterrupt:
        session.rollback()
        log.critical('Aborted, no changes saved')
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
        source = session.query(ArchiveSource).filter(ArchiveSource.name == source_name).first()
        if not source:
            log.critical('Source `%s` does not exists' % source_name)
            srcs = ', '.join([s.name for s in session.query(ArchiveSource).order_by(ArchiveSource.name)])
            if srcs:
                log.info('Known sources: %s' % srcs)
            return

        # construct tags list
        tags = []
        for tag_name in tag_names:
            tags.append(get_tag(tag_name, session))

        # tag 'em
        log.verbose('Please wait while adding tags %s ...' % (', '.join(tag_names)))
        for a in session.query(ArchiveEntry). \
                filter(ArchiveEntry.sources.any(name=source_name)).yield_per(5):
            a.tags.extend(tags)
    finally:
        session.commit()
        session.close()


def cli_search(options):
    search_term = ' '.join(options.keywords)
    tags = options.tags
    sources = options.sources
    query = re.sub(r'[ \(\)]+', ' ', search_term).strip()

    table_data = []
    with Session() as session:
        for archived_entry in search(session, query, tags=tags, sources=sources):
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

    try:
        table = TerminalTable(options.table_type, table_data, wrap_columns=[1])
        table.table.inner_heading_row_border = False
        console(table.output)
    except TerminalTableError as e:
        console('ERROR: %s' % str(e))


def cli_inject(manager, options):
    log.debug('Finding inject content')
    inject_entries = defaultdict(list)
    with Session() as session:
        for id in options.ids:
            archive_entry = session.query(ArchiveEntry).get(id)

            # not found
            if not archive_entry:
                log.critical('There\'s no archived item with ID `%s`' % id)
                continue

            # find if there is no longer any task within sources
            if not any(source.name in manager.tasks for source in archive_entry.sources):
                log.error('None of sources (%s) exists anymore, cannot inject `%s` from archive!' %
                          (', '.join([s.name for s in archive_entry.sources]), archive_entry.title))
                continue

            inject_entry = Entry(archive_entry.title, archive_entry.url)
            if archive_entry.description:
                inject_entry['description'] = archive_entry.description
            if options.immortal:
                log.debug('Injecting as immortal')
                inject_entry['immortal'] = True
            inject_entry['accepted_by'] = 'archive inject'
            inject_entry.accept('injected')

            # update list of tasks to be injected
            for source in archive_entry.sources:
                inject_entries[source.name].append(inject_entry)

    for task_name in inject_entries:
        for inject_entry in inject_entries[task_name]:
            log.info('Injecting from archive `%s` into `%s`' % (inject_entry['title'], task_name))

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
    archive_parser = options.register_command('archive', do_cli, help='Search and manipulate the archive database')
    archive_parser.add_subparsers(title='Actions', metavar='<action>', dest='archive_action')
    # Default usage shows the positional arguments after the optional ones, override usage to fix it
    search_parser = archive_parser.add_subparser('search', help='Search from the archive',
                                                 usage='%(prog)s [-h] <keyword> [<keyword> ...] [optional arguments]',
                                                 parents=[table_parser])
    search_parser.add_argument('keywords', metavar='<keyword>', nargs='+', help='Keyword(s) to search for')
    search_parser.add_argument('--tags', metavar='TAG', nargs='+', default=[], help='Tag(s) to search within')
    search_parser.add_argument('--sources', metavar='SOURCE', nargs='+', default=[], help='Source(s) to search within')
    inject_parser = archive_parser.add_subparser('inject', help='Inject entries from the archive back into tasks')
    inject_parser.add_argument('ids', nargs='+', type=int, metavar='ID', help='Archive ID of an item to inject')
    inject_parser.add_argument('--immortal', action='store_true', help='Injected entries will not be able to be '
                                                                       'rejected by any plugins')
    exec_group = inject_parser.add_argument_group('execute arguments')
    exec_group.add_argument('execute_options', action=ParseExtrasAction, parser=get_parser('execute'))
    tag_parser = archive_parser.add_subparser('tag-source', help='Tag all archived entries within a given source')
    tag_parser.add_argument('source', metavar='<source>', help='The source whose entries you would like to tag')
    tag_parser.add_argument('tags', nargs='+', metavar='<tag>',
                            help='The tag(s) you would like to apply to the entries')
    archive_parser.add_subparser('consolidate', help='Migrate old archive data to new model, may take a long time')
