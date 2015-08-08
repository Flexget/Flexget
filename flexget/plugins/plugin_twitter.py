from __future__ import print_function
import logging

from flexget import options
from flexget import plugin
from flexget.event import event
from flexget.utils.template import RenderError

try:
    import tweepy
except ImportError:
    tweepy = None

log = logging.getLogger('twitter')


def dependency_check():
    if not tweepy:
        raise plugin.DependencyError(issued_by='twitter', missing='tweepy',
                                     message='twitter plugin requires the tweepy Python module.')


class OutputTwitter:
    """Outputs accepted entries to Twitter

    Example::

      twitter:
        template: 'Flexget: {{ title }} accepted'
        consumer_key: <consumer_key>
        consumer_secret: <consumer_secret>
        access_key: <access_key>
        access_secret: <access_secret>

    Beware that Twitter only allows 300 requests during a 15 minutes
    window.

    The template option accepts the usual template format.
    """

    schema = {
        'type': 'object',
        'properties': {
            'active': {'type': 'boolean', 'default': True},
            'template': {'type': 'string', 'default': 'Flexget: {{ title }} accepted'},
            'consumer_key': {'type': 'string'},
            'consumer_secret': {'type': 'string'},
            'access_key': {'type': 'string'},
            'access_secret': {'type': 'string'}
        },
        'required': ['consumer_key', 'consumer_secret', 'access_key', 'access_secret'],
        'additionalProperties': False
    }

    def on_task_output(self, task, config):

        dependency_check()

        auth = tweepy.OAuthHandler(config['consumer_key'], config['consumer_secret'])
        auth.set_access_token(config['access_key'], config['access_secret'])
        api = tweepy.API(auth)

        for entry in task.accepted:
            try:
                content = entry.render(config['template'])
            except RenderError, e:
                log.error('Error rendering message: %s' % e)
                return

            if task.manager.options.test:
                log.info('Would update twitter with: %s' % content)
                continue
            try:
                api.update_status(status=content)
            except Exception, e:
                log.warning('Unable to post tweet: %s' % e)
            log.debug('Posted tweet: %s' % content)


def twitter_auth(manager, cmd_options):
    """
    Authenticates with the Twitter API and produces a config snippet to use with the Twitter output plugin
    """
    dependency_check()

    if cmd_options.queue_action == 'auth':
        print("Please input your Consumer key/secret for your registered application.")
        print("")
        consumer_key = raw_input('Consumer Key: ').strip()
        consumer_secret = raw_input('Consumer Secret: ').strip()
        print("Attempting to authenticate...")
        auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
        auth_url = auth.get_authorization_url()

        print("Open the following URL in a browser to authenticate Flexget to access your Twitter account:")
        print(auth_url)
        print("Once completed, please provide the PIN code that Twitter returned")
        verifier = raw_input('PIN: ').strip()
        auth.get_access_token(verifier)
        print("Add the following to your config.yml, either under your tasks or global as required")
        print("")
        print("twitter:")
        print(" consumer_key: %s" % consumer_key)
        print(" consumer_secret: %s" % consumer_secret)
        print(" access_key: %s" % auth.access_token)
        print(" access_secret: %s" % auth.access_token_secret)
        return


@event('plugin.register')
def plugin_register():
    plugin.register(OutputTwitter, 'twitter', api_ver=2)


@event('options.register')
def register_options():
    parser = options.register_command('twitter', twitter_auth, help='validate configuration file and print errors')
    subparsers = parser.add_subparsers(title='actions', metavar='<action>', dest='queue_action')
    subparsers.add_parser('auth', help='authenticate against the Twitter API')