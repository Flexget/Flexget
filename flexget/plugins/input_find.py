import logging
from flexget.plugin import register_plugin

log = logging.getLogger('find')


class InputFind(object):
    """
        Uses local path content as an input, recurses through directories and creates entries for files that match mask.

        You can specify either the mask key, in shell file matching format, (see python fnmatch module,) or regexp key.

        Example:

        find:
          path: /storage/movies/
          mask: *.avi
          
        Example:

        find:
          path:
            - /storage/movies/
            - /storage/tv/
          regexp: .*\.(avi|mkv)$
    """

    def validator(self):
        from flexget import validator
        root = validator.factory('dict')
        root.accept('path', key='path', required=True)
        root.accept('list', key='path').accept('path')
        root.accept('text', key='mask')
        root.accept('regexp', key='regexp')
        root.accept('boolean', key='recursive')
        return root

    def prepare_config(self, config):
        from fnmatch import translate
        # If only a single path is passed turn it into a 1 element list
        if isinstance(config['path'], basestring):
            config['path'] = [config['path']]
        config.setdefault('recursive', False)
        # If mask was specified, turn it in to a regexp
        if config.get('mask'):
            config['regexp'] = translate(config['mask'])
        # If no mask or regexp specified, accept all files
        if not config.get('regexp'):
            config['regexp'] = '.'

    def on_feed_input(self, feed, config):
        from flexget.feed import Entry
        import os
        import re
        self.prepare_config(config)
        entries = []
        match = re.compile(config['regexp'], re.IGNORECASE).match
        for path in config['path']:
            # unicode causes problems in here (#989)
            for item in os.walk(str(path)):
                for name in item[2]:
                    # If mask fails continue
                    if match(name) is None:
                        continue
                    e = Entry()
                    try:
                        e['title'] = unicode(name)
                    except UnicodeDecodeError:
                        # TODO: if we hadn't casted path to str this would not be a problem
                        # how to support everything?
                        log.warning('Filename `%s` in `%s` encoding broken?' % (repr(name)[1:-1], item[0]))
                        continue
                    filepath = os.path.join(item[0], name)
                    e['location'] = filepath
                    # Windows paths need an extra / prepended to them for url
                    if not filepath.startswith('/'):
                        filepath = '/' + filepath
                    e['url'] = 'file://%s' % (filepath)
                    entries.append(e)
                # If we are not searching recursively, break after first (base) directory
                if not config['recursive']:
                    break
        return entries

register_plugin(InputFind, 'find', api_ver=2)
