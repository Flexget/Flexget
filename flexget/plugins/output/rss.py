import base64
import datetime
import hashlib
import os

from loguru import logger
from sqlalchemy import Column, DateTime, Integer, String, Unicode

from flexget import db_schema, plugin
from flexget.event import event
from flexget.utils.sqlalchemy_utils import table_add_column, table_columns
from flexget.utils.template import RenderError, get_template, render_from_entry

logger = logger.bind(name='make_rss')
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
            logger.info('Adding rsslink column to table make_rss.')
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
    enc_length = Column(Integer)
    enc_type = Column(String)


class OutputRSS:
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

    RSS feed properties:

    You can specify the URL, title, and description to include in tthe header
    of the RSS feed.

    Example::

      make_rss:
        file: ~/public_html/series.rss
        rsslink: http://my.server.net/series.rss
        rsstitle: The Flexget RSS Feed
        rssdesc: Episodes about Flexget.

    **RSS item title and link**

    You can specify the title and link for each item in the RSS feed.

    The item title can be any pattern that references fields in the input entry.

    The item link can be created from one of a list of fields in the input
    entry, in order of preference. The fields should be enumerated in a list.
    Note that the url field is always used as last possible fallback even
    without explicitly adding it into the list.

    Default field list for item URL: imdb_url, input_url, url

    Example::

      make_rss:
        file: ~/public_html/series.rss
        title: '{{title}} (from {{task}})'
        link:
          - imdb_url

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
                    'timestamp': {'type': 'boolean'},
                    'rsslink': {'type': 'string'},
                    'rsstitle': {'type': 'string'},
                    'rssdesc': {'type': 'string'},
                    'encoding': {'type': 'string'},  # TODO: only valid choices
                    'title': {'type': 'string'},
                    'template': {'type': 'string'},
                    'link': {'type': 'array', 'items': {'type': 'string'}},
                },
                'required': ['file'],
                'additionalProperties': False,
            },
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
        config.setdefault('encoding', 'UTF-8')
        config.setdefault('timestamp', False)
        config.setdefault('link', ['imdb_url', 'input_url'])
        config.setdefault('title', '{{title}} (from {{task}})')
        config.setdefault('template', 'rss')
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
            logger.debug('disabling history')
            for item in task.session.query(RSSEntry).filter(RSSEntry.file == config['file']).all():
                task.session.delete(item)

        # save entries into db for RSS generation
        for entry in task.accepted:
            rss = RSSEntry()
            try:
                rss.title = entry.render(config['title'])
            except RenderError as e:
                logger.error(
                    'Error rendering jinja title for `{}` falling back to entry title: {}',
                    entry['title'],
                    e,
                )
                rss.title = entry['title']
            for field in config['link']:
                if entry.get(field) is not None:
                    rss.link = entry[field]
                    break

            try:
                template = get_template(config['template'], scope='task')
            except ValueError as e:
                raise plugin.PluginError('Invalid template specified: %s' % e)
            try:
                rss.description = render_from_entry(template, entry)
            except RenderError as e:
                logger.error(
                    'Error while rendering entry {}, falling back to plain title: {}', entry, e
                )
                rss.description = entry['title'] + ' - (Render Error)'
            rss.file = config['file']
            if 'rss_pubdate' in entry:
                rss.published = entry['rss_pubdate']

            rss.enc_length = entry['size'] if 'size' in entry else None
            rss.enc_type = entry['type'] if 'type' in entry else None

            # TODO: check if this exists and suggest disabling history if it does since it shouldn't happen normally ...
            logger.debug('Saving {} into rss database', entry['title'])
            task.session.add(rss)

        if not rss2gen:
            return
        # don't generate rss when learning
        if task.options.learn:
            return

        db_items = (
            task.session.query(RSSEntry)
            .filter(RSSEntry.file == config['file'])
            .order_by(RSSEntry.published.desc())
            .all()
        )

        # make items
        rss_items = []
        for db_item in db_items:
            add = True
            if config['items'] != -1:
                if len(rss_items) > config['items']:
                    add = False
            if config['days'] != -1:
                if (
                    datetime.datetime.today() - datetime.timedelta(days=config['days'])
                    > db_item.published
                ):
                    add = False
            if add:
                # add into generated feed
                hasher = hashlib.sha1()
                hasher.update(db_item.title.encode('utf8'))
                hasher.update(db_item.description.encode('utf8'))
                hasher.update(db_item.link.encode('utf8'))
                guid = base64.urlsafe_b64encode(hasher.digest()).decode('ascii')
                guid = PyRSS2Gen.Guid(guid, isPermaLink=False)

                gen = {
                    'title': db_item.title,
                    'description': db_item.description,
                    'link': db_item.link,
                    'pubDate': db_item.published,
                    'guid': guid,
                }
                if db_item.enc_length is not None and db_item.enc_type is not None:
                    gen['enclosure'] = PyRSS2Gen.Enclosure(
                        db_item.link, db_item.enc_length, db_item.enc_type
                    )
                logger.trace('Adding {} into rss {}', gen['title'], config['file'])
                rss_items.append(PyRSS2Gen.RSSItem(**gen))
            else:
                # no longer needed
                task.session.delete(db_item)

        # make rss
        rss = PyRSS2Gen.RSS2(
            title=config.get('rsstitle', 'FlexGet'),
            link=config.get('rsslink', 'http://flexget.com'),
            description=config.get('rssdesc', 'FlexGet generated RSS feed'),
            lastBuildDate=datetime.datetime.utcnow() if config['timestamp'] else None,
            items=rss_items,
        )

        # don't run with --test
        if task.options.test:
            logger.info('Would write rss file with {} entries.', len(rss_items))
            return

        # write rss
        fn = os.path.expanduser(config['file'])
        with open(fn, 'wb') as file:
            try:
                logger.verbose('Writing output rss to {}', fn)
                rss.write_xml(file, encoding=config['encoding'])
            except LookupError:
                logger.critical('Unknown encoding {}', config['encoding'])
                return
            except OSError:
                # TODO: plugins cannot raise PluginWarnings in terminate event ..
                logger.critical('Unable to write {}', fn)
                return


@event('plugin.register')
def register_plugin():
    plugin.register(OutputRSS, 'make_rss', api_ver=2)
