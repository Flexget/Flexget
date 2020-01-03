from loguru import logger

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='spy_headers')


class PluginSpyHeaders:
    """
        Logs all headers sent in http requests. Useful for resolving issues.

        WARNING: At the moment this modifies requests somehow!
    """

    schema = {'type': 'boolean'}

    @staticmethod
    def log_requests_headers(response, **kwargs):
        logger.info('Request : {}', response.request.url)
        logger.info('Response : {} ({})', response.status_code, response.reason)
        logger.info('-- Headers: --------------------------')
        for header, value in response.request.headers.items():
            logger.info('{}: {}', header, value)
        logger.info('--------------------------------------')
        return response

    def on_task_start(self, task, config):
        if not config:
            return
        # Add our hook to the requests session
        task.requests.hooks['response'].append(self.log_requests_headers)

    def on_task_exit(self, task, config):
        """Task exiting, remove additions"""
        if not config:
            return
        task.requests.hooks['response'].remove(self.log_requests_headers)

    # remove also on abort
    on_task_abort = on_task_exit


@event('plugin.register')
def register_plugin():
    plugin.register(PluginSpyHeaders, 'spy_headers', api_ver=2)
