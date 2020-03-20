from flexget import plugin
from flexget.event import EventType, event


class Magnets:
    """Removes magnet urls form the urls list. Rejects entries that have nothing but magnet urls."""

    schema = {'type': 'boolean'}

    @plugin.priority(0)
    def on_task_urlrewrite(self, task, config):
        if config is not False:
            return
        for entry in task.accepted:
            if 'urls' in entry:
                entry['urls'] = [url for url in entry['urls'] if not url.startswith('magnet:')]

            if entry['url'].startswith('magnet:'):
                if entry.get('urls'):
                    entry['url'] = entry['urls'][0]
                else:
                    entry.reject('Magnet urls not allowed.', remember=True)


@event(EventType.plugin__register)
def register_plugin():
    plugin.register(Magnets, 'magnets', api_ver=2)
