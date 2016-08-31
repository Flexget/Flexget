from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import base64
import hashlib
import io
import logging
import datetime
import os

from sqlalchemy import Column, Integer, String, DateTime, Unicode

from flexget import db_schema, plugin
from flexget.event import event
from flexget.utils.sqlalchemy_utils import table_columns, table_add_column
from flexget.utils.template import render_from_entry, get_template, RenderError

log = logging.getLogger('make_rss')
Base = db_schema.versioned_base('make_rss', 0)

rss2gen = True
try:
    import PyRSS2Gen
except ImportError:
    rss2gen = False


@db_schema.upgrade('make_rss')
def upgrade(ver, session):
    if ver is None:
        columns = table_columns('make_rss', session)
        if 'rsslink' not in columns:
            log.info('Adding rsslink column to table make_rss.')
            table_add_column('make_rss', 'rsslink', String, session)
        ver = 0
    return ver


class RSSEntry(Base):
    __tablename__ = 'make_rss'

    id = Column(Integer, primary_key=True)
    title = Column(Unicode)
    description = Column(Unicode)
    link = Column(String)
    rsslink = Column(String)
    file = Column(Unicode)
    published = Column(DateTime, default=datetime.datetime.utcnow)


class OutputRSS(object):
    """
    Write RSS containing succeeded (downloaded) entries.

    Example::

      make_rss: ~/public_html/flexget.rss

    You may write into same file in multiple tasks.

    Example::

      my-task-A:
        make_rss: ~/public_html/series.rss
        .
        .
      my-task-B:
        make_rss: ~/public_html/series.rss
        .
        .

    With this example file series.rss would contain succeeded
    entries from both tasks.

    **Number of days / items**

    By default output contains items from last 7 days. You can specify
    different perioid, number of items or both. Value -1 means unlimited.

    Example::

      make_rss:
        file: ~/public_html/series.rss
        days: 2
        items: 10

    Generate RSS that will containing last two days and no more than 10 items.

    Example 2::

      make_rss:
        file: ~/public_html/series.rss
        days: -1
        items: 50

    Generate RSS that will contain last 50 items, regardless of dates.

    RSS location link:

    You can specify the url location of the rss file.

    Example::

      make_rss:
        file: ~/public_html/series.rss
        rsslink: http://my.server.net/series.rss

    **RSS link**

    You can specify what field from entry is used as a link in generated rss feed.

    Example::

      make_rss:
        file: ~/public_html/series.rss
        link:
          - imdb_url

    List should contain a list of fields in order of preference.
    Note that the url field is always used as last possible fallback
    even without explicitly adding it into the list.

    Default list: imdb_url, input_url, url
    """

    schema = {
        'oneOf': [
            {'type': 'string'},  # TODO: path / file
            {
                'type': 'object',
                'properties': {
                    'file': {'type': 'string'},
                    'days': {'type': 'integer'},
                    'items': {'type': 'integer'},
                    'history': {'type': 'boolean'},
                    'rsslink': {'type': 'string'},
                    'encoding': {'type': 'string'},  # TODO: only valid choices
                    'title': {'type': 'string'},
                    'template': {'type': 'string'},
                    'link': {'type': 'array', 'items': {'type': 'string'}}
                },
                'required': ['file'],
                'additionalProperties': False
            }
        ]
    }

    def on_task_output(self, task, config):
        # makes this plugin count as output (stops warnings about missing outputs)
        pass

    def prepare_config(self, config):
        if not isinstance(config, dict):
            config = {'file': config}
        config.setdefault('days', 7)
        config.setdefault('items', -1)
        config.setdefault('history', True)
        config.setdefault('encoding', 'iso-8859-1')
        config.setdefault('link', ['imdb_url', 'input_url'])
        config.setdefault('title', '{{title}} (from {{task}})')
        config.setdefault('template', 'default')
        # add url as last resort
        config['link'].append('url')
        return config

    def on_task_exit(self, task, config):
        """Store finished / downloaded entries at exit"""
        if not rss2gen:
            raise plugin.PluginWarning('plugin make_rss requires PyRSS2Gen library.')
        config = self.prepare_config(config)

        # when history is disabled, remove everything from backlog on every run (a bit hackish, rarely useful)
        if not config['history']:
            log.debug('disabling history')
            for item in task.session.query(RSSEntry).filter(RSSEntry.file == config['file']).all():
                task.session.delete(item)

        # save entries into db for RSS generation
        for entry in task.accepted:
            rss = RSSEntry()
            try:
                rss.title = entry.render(config['title'])
            except RenderError as e:
                log.error('Error rendering jinja title for `%s` falling back to entry title: %s' % (entry['title'], e))
                rss.title = entry['title']
            for field in config['link']:
                if field in entry:
                    rss.link = entry[field]
                    break

            try:
                template = get_template(config['template'], 'rss')
            except ValueError as e:
                raise plugin.PluginError('Invalid template specified: %s' % e)
            try:
                rss.description = render_from_entry(template, entry)
            except RenderError as e:
                log.error('Error while rendering entry %s, falling back to plain title: %s' % (entry, e))
                rss.description = entry['title'] + ' - (Render Error)'
            rss.file = config['file']

            # TODO: check if this exists and suggest disabling history if it does since it shouldn't happen normally ...
            log.debug('Saving %s into rss database' % entry['title'])
            task.session.add(rss)

        if not rss2gen:
            return
        # don't generate rss when learning
        if task.options.learn:
            return

        db_items = task.session.query(RSSEntry).filter(RSSEntry.file == config['file']). \
            order_by(RSSEntry.published.desc()).all()

        # make items
        rss_items = []
        for db_item in db_items:
            add = True
            if config['items'] != -1:
                if len(rss_items) > config['items']:
                    add = False
            if config['days'] != -1:
                if datetime.datetime.today() - datetime.timedelta(days=config['days']) > db_item.published:
                    add = False
            if add:
                # add into generated feed
                hasher = hashlib.sha1()
                hasher.update(db_item.title.encode('utf8'))
                hasher.update(db_item.description.encode('utf8'))
                hasher.update(db_item.link.encode('utf8'))
                guid = base64.urlsafe_b64encode(hasher.digest()).decode('ascii')
                guid = PyRSS2Gen.Guid(guid, isPermaLink=False)

                gen = {'title': db_item.title,
                       'description': db_item.description,
                       'link': db_item.link,
                       'pubDate': db_item.published,
                       'guid': guid}
                log.trace('Adding %s into rss %s' % (gen['title'], config['file']))
                rss_items.append(PyRSS2Gen.RSSItem(**gen))
            else:
                # no longer needed
                task.session.delete(db_item)

        # make rss
        rss = PyRSS2Gen.RSS2(title='FlexGet',
                             link=config.get('rsslink', 'http://flexget.com'),
                             description='FlexGet generated RSS feed',
                             lastBuildDate=datetime.datetime.utcnow(),
                             items=rss_items)

        # don't run with --test
        if task.options.test:
            log.info('Would write rss file with %d entries.', len(rss_items))
            return

        # write rss
        fn = os.path.expanduser(config['file'])
        with io.open(fn, 'wb') as file:
            try:
                log.verbose('Writing output rss to %s' % fn)
                rss.write_xml(file, encoding=config['encoding'])
            except LookupError:
                log.critical('Unknown encoding %s' % config['encoding'])
                return
            except IOError:
                # TODO: plugins cannot raise PluginWarnings in terminate event ..
                log.critical('Unable to write %s' % fn)
                return


@event('plugin.register')
def register_plugin():
    plugin.register(OutputRSS, 'make_rss', api_ver=2)
