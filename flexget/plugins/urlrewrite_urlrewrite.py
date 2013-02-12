from __future__ import unicode_literals, division, absolute_import
import re
import logging
from flexget.plugin import register_plugin

log = logging.getLogger('urlrewrite')


class UrlRewrite(object):
    """
    Generic configurable urlrewriter.

    Example::

      urlrewrite:
        demonoid:
          regexp: http://www\.demonoid\.com/files/details/
          format: http://www.demonoid.com/files/download/HTTP/
    """

    resolves = {}

    # built-in resolves

#    resolves = yaml.safe_load("""
#    tvsubtitles:
#      match: http://www.tvsubtitles.net/subtitle-
#      replace: http://www.tvsubtitles.net/download-
#    """
#    )

    def validator(self):
        from flexget import validator
        root = validator.factory('dict')
        config = root.accept_any_key('dict')
        config.accept('regexp', key='regexp', required=True)
        config.accept('text', key='format', required=True)
        return root

    def on_task_start(self, task):
        for name, config in task.config.get('urlrewrite', {}).iteritems():
            match = re.compile(config['regexp'])
            format = config['format']
            self.resolves[name] = {'regexp_compiled': match, 'format': format, 'regexp': config['regexp']}
            log.debug('Added rewrite %s' % name)

    def url_rewritable(self, task, entry):
        log.trace('running url_rewritable')
        log.trace(self.resolves)
        for name, config in self.resolves.iteritems():
            regexp = config['regexp_compiled']
            log.trace('testing %s' % config['regexp'])
            if regexp.search(entry['url']):
                return True
        return False

    def url_rewrite(self, task, entry):
        for name, config in self.resolves.iteritems():
            regexp = config['regexp_compiled']
            format = config['format']
            if regexp.search(entry['url']):
                log.debug('Regexp resolving %s with %s' % (entry['url'], name))

                # run the regexp
                entry['url'] = regexp.sub(format, entry['url'])

                if regexp.match(entry['url']):
                    entry.fail('urlrewriting')
                    task.purge()
                    from flexget.plugins.plugin_urlrewriting import UrlRewritingError
                    raise UrlRewritingError('Regexp %s result should NOT continue to match!' % name)
                return

register_plugin(UrlRewrite, 'urlrewrite', groups=['urlrewriter'])
