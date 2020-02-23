import re

from loguru import logger

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event

logger = logger.bind(name='twitterfeed')

# Size of the chunks when fetching a timeline
CHUNK_SIZE = 200

# Maximum number of tweets to fetch no matter how (if there is no
# since_id for example or a too old since_id)
MAX_TWEETS = 1000


class TwitterFeed:
    """Parses a twitter feed

    Example::

      twitterfeed:
        account: <account>
        consumer_key: <consumer_key>
        consumer_secret: <consumer_secret>
        access_token_key: <access_token_key>
        access_token_secret: <access_token_secret>

    By default, the 50 last tweets are fetched corresponding to the option:
      all_entries: yes

    To change that default number:
      tweets: 75

    Beware that Twitter only allows 300 requests during a 15 minutes
    window.

    If you want to process only new tweets:
      all_entries: no

    That option's behaviour is changed if the corresponding task's
    configuration has been changed. In that case, new tweets are
    fetched and if there are no more than `tweets`, older ones are
    fetched to have `tweets` of them in total.
    """

    schema = {
        'type': 'object',
        'properties': {
            'account': {'type': 'string'},
            'consumer_key': {'type': 'string'},
            'consumer_secret': {'type': 'string'},
            'access_token_key': {'type': 'string'},
            'access_token_secret': {'type': 'string'},
            'all_entries': {'type': 'boolean', 'default': True},
            'tweets': {'type': 'number', 'default': 50},
        },
        'required': [
            'account',
            'consumer_key',
            'consumer_secret',
            'access_token_secret',
            'access_token_key',
        ],
        'additionalProperties': False,
    }

    def on_task_start(self, task, config):
        try:
            import twitter  # noqa
        except ImportError:
            raise plugin.PluginError('twitter module required', logger=logger)

    def on_task_input(self, task, config):
        import twitter

        account = config['account']
        logger.debug('Looking at twitter account `{}`', account)

        try:
            self.api = twitter.Api(
                consumer_key=config['consumer_key'],
                consumer_secret=config['consumer_secret'],
                access_token_key=config['access_token_key'],
                access_token_secret=config['access_token_secret'],
            )
        except twitter.TwitterError as ex:
            raise plugin.PluginError(
                'Unable to authenticate to twitter for task %s: %s' % (task.name, ex)
            )

        if config['all_entries']:
            logger.debug(
                'Fetching {} last tweets from {} timeline', config['tweets'], config['account']
            )
            tweets = self.get_tweets(account, number=config['tweets'])
        else:
            # Fetching from where we left off last time
            since_id = task.simple_persistence.get('since_id', None)
            if since_id:
                logger.debug(
                    'Fetching from tweet id {} from {} timeline', since_id, config['account']
                )
                kwargs = {'since_id': since_id}
            else:
                logger.debug('No since_id, fetching last {} tweets', config['tweets'])
                kwargs = {'number': config['tweets']}

            tweets = self.get_tweets(account, **kwargs)
            if task.config_modified and len(tweets) < config['tweets']:
                logger.debug(
                    'Configuration modified; fetching at least {} tweets', config['tweets']
                )
                max_id = tweets[-1].id if tweets else None
                remaining_tweets = config['tweets'] - len(tweets)
                tweets = tweets + self.get_tweets(account, max_id=max_id, number=remaining_tweets)
            if tweets:
                last_tweet = tweets[0]
                logger.debug('New last tweet id: {}', last_tweet.id)
                task.simple_persistence['since_id'] = last_tweet.id

        logger.debug('{} tweets fetched', len(tweets))
        for t in tweets:
            logger.debug('id:{}', t.id)

        return [self.entry_from_tweet(e) for e in tweets]

    def get_tweets(self, account, number=MAX_TWEETS, since_id=None, max_id=None):
        """Fetch tweets from twitter account `account`."""
        import twitter

        all_tweets = []
        while number > 0:
            try:
                tweets = self.api.GetUserTimeline(
                    screen_name=account,
                    include_rts=False,
                    exclude_replies=True,
                    count=min(number, CHUNK_SIZE),
                    since_id=since_id,
                    max_id=max_id,
                )
            except twitter.TwitterError as e:
                raise plugin.PluginError('Unable to fetch timeline %s for %s' % (account, e))

            if not tweets:
                break

            all_tweets += tweets
            number -= len(tweets)
            max_id = tweets[-1].id - 1

        return all_tweets

    def entry_from_tweet(self, tweet):
        new_entry = Entry()
        new_entry['title'] = tweet.text
        urls = re.findall(r'(https?://\S+)', tweet.text)
        new_entry['urls'] = urls
        if urls:
            new_entry['url'] = urls[0]
        return new_entry


@event('plugin.register')
def register_plugin():
    plugin.register(TwitterFeed, 'twitterfeed', api_ver=2)
