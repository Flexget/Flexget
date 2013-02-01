import logging
from flexget.plugin import register_plugin

log = logging.getLogger('nzbget')


class OutputNzbget(object):
    """
    Example::

      nzbget:
        url: http://nzbget:12345@localhost:6789/xmlrpc
        category: movies
        priority: 0
        top: False
    """

    def validator(self):
        from flexget import validator
        config = validator.factory('dict')

        config.accept('text', key='url', required=True)
        config.accept('text', key='category')
        config.accept('integer', key='priority')
        config.accept('boolean', key='top')
        return config

    def get_params(self, config):
        params = {}

        params['url'] = config['url']
        params['category'] = config.get("category", "")
        params['priority'] = config.get("priority", 0)
        params['top'] = config.get("top", False)

        return params

    def on_task_output(self, task, config):
        from xmlrpclib import ServerProxy

        params = self.get_params(config)

        server = ServerProxy(params["url"])

        for entry in task.accepted:
            if task.manager.options.test:
                log.info('Would add into nzbget: %s' % entry['title'])
                continue

            # allow overriding the category
            if 'category' in entry:
                params['category'] = entry['category']

            try:
                server.appendurl(entry["title"], params["category"], params["priority"], params["top"], entry["url"])
                log.info("Added `%s` to nzbget" % entry["title"])
            except:
                log.critical("rpc call to nzbget failed")
                entry.fail("could not call appendurl via RPC")

register_plugin(OutputNzbget, 'nzbget', api_ver=2)
