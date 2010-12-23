import logging
from flexget.plugin import register_plugin, priority, PluginError

log = logging.getLogger('format_field')


class FormatField(object):
    """Uses a jinja2 template string to set a field in Entry"""

    def on_feed_start(self, feed):
        """Checks that jinja2 is available"""
        try:
            from jinja2 import Template
        except ImportError, e:
            raise PluginError('format_field plugin requires the jinja2 module. ImportError: %s' % e, log)

    def validator(self):
        from flexget.validator import DictValidator
        root = DictValidator()
        root.accept_any_key('text')
        return root

    # Run after other plugins have populated entry fields
    @priority(0)
    def on_feed_filter(self, feed):
        from jinja2 import Template
        config = feed.config.get('format_field')
        for entry in feed.entries:
            for field, template_string in config.iteritems():
                template = Template(template_string)
                result = template.render(entry)
                entry[field] = result

register_plugin(FormatField, 'format_field')
