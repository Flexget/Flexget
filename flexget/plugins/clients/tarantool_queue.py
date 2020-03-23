from loguru import logger
from flexget.entry import Entry
from flexget.event import event
from flexget import plugin

logger = logger.bind(name='tarantool_queue')

class TarantoolTube:
    def __init__(self, queue, tube_name):
        self._queue = queue
        self._tube_name = tube_name

    def put(self, data):
        return self._queue.call('queue.tube.'+self._tube_name+':put', data)

    def take(self, timeout=None):
        return self._queue.call('queue.tube.'+self._tube_name+':take', timeout)

    def ack(self, task_id):
        return self._queue.call('queue.tube.' + self._tube_name + ':ack', task_id)

class TarantoolQueue:
    def __init__(self, tarantool_module, host, port, user, password):
        self._server = tarantool_module.connect(host, port, user=user, password=password)
        self._tubes = {}

    def tube(self, tube_name):
        if tube_name in self._tubes:
            tube = self._tubes[tube_name]
        else:
            tube = TarantoolTube(self, tube_name)
            self._tubes[tube_name] = tube
        return tube

    def call(self, function, *args):
        return self._server.call(function, *args)

class PluginTarantoolQueueBase:
    schema = {
        'anyOf': [
            {'type': 'boolean'},
            {
                'type': 'object',
                'properties': {
                    'host': {'type': 'string'},
                    'port': {'type': 'integer'},
                    'user': {'type': 'string'},
                    'password': {'type': 'string'},
                    'tube': {'type': 'string'},
                    'enabled': {'type': 'boolean'},
                },
                'additionalProperties': False,
            },
        ]
    }

    def __init__(self):
        self._queue = None
        self._is_prepared = False
        self._config = None
        self._tarantool_module = None

    @property
    def config(self):
        if self._config is None:
            raise plugin.PluginError('Config is not set', logger)
        return self._config

    @config.setter
    def config(self, config):
        self._config = config

    @property
    def queue(self):
        self.prepare()
        if self._queue is None:
            self._queue = TarantoolQueue(self._tarantool_module,
                                         self.config.get('host'),
                                         self.config.get('port'),
                                         self.config.get('user'),
                                         self.config.get('password'))

        return self._queue

    @property
    def tube(self):
        return self.queue.tube(self.config.get('tube'))

    def prepare(self):
        if not self._is_prepared:
            try:
                import tarantool
                self._tarantool_module = tarantool
            except:
                raise plugin.PluginError('tarantool_queue module required.', logger)

            if self.config.get('tube') is None:
                raise plugin.PluginError('Tarantool Queue tube is not defined in config.', logger)

            self._is_prepared = True

class PluginTarantoolQueueInput(PluginTarantoolQueueBase):
    def on_task_input(self, task, config):
        if not config.get('enabled', True):
            return

        self.config = config
        tarantool_entries = self.tube.take(0)
        do_continue = True
        entry_count = 0
        entries = []
        while tarantool_entries is not None and len(tarantool_entries) > 0 and do_continue:
            for tarantool_entry in tarantool_entries:
                entry_id, entry_type, entry_data = tarantool_entry
                entry = Entry.deserialize(entry_data, None)
                entries.append(entry)
                self.tube.ack(entry_id)
                entry_count += 1
                if entry_count > 30:
                    do_continue = False
                else:
                    tarantool_entries = self.tube.take(0)

        return entries


class PluginTarantoolQueueOutput(PluginTarantoolQueueBase):
    def on_task_output(self, task, config):
        if not config.get('enabled', True):
            return
        if not task.accepted:
            return

        self.config = config

        for entry in task.accepted:
            try:
                self.tube.put(Entry.serialize(entry))
            except Exception as e:
                entry.fail(e)

@event('plugin.register')
def register_plugin():
    plugin.register(PluginTarantoolQueueInput, 'tarantool_queue_input', api_ver=2)
    plugin.register(PluginTarantoolQueueOutput, 'tarantool_queue_output', api_ver=2)