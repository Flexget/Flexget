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
        return self._queue.call('queue.tube.{0}:put'.format(self._tube_name), data)

    def take(self, timeout=None):
        entries = self._queue.call('queue.tube.{0}:take'.format(self._tube_name), timeout)
        if entries is None:
            entries = []
        return entries

    def ack(self, task_id):
        return self._queue.call('queue.tube.{0}:ack'.format(self._tube_name), task_id)


class TarantoolQueue:
    def __init__(self, tarantool_module, host, port, user, password):
        self._server = tarantool_module.connect(host, port, user=user, password=password)
        self._tubes = {}

    def get_tube(self, tube_name):
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
                    'chunk_size': {'type': 'integer', 'default': 30}
                },
                'required': ['host', 'port', 'user', 'password', 'tube'],
                'additionalProperties': False,
            },
        ]
    }

    def get_queue(self, tarantool_module, config):
        queue = TarantoolQueue(tarantool_module,
                               config.get('host'),
                               config.get('port'),
                               config.get('user'),
                               config.get('password'))

        return queue

    def get_tube_of_queue(self, tarantool_module, config):
        return self.get_queue(tarantool_module, config).get_tube(config.get('tube'))

    @staticmethod
    def get_tarantool_module():
        try:
            import tarantool
        except:
            raise plugin.PluginError('tarantool_queue module required.', logger)
        return tarantool


class PluginTarantoolQueueInput(PluginTarantoolQueueBase):
    def on_task_input(self, task, config):
        tarantool_module = self.get_tarantool_module()
        tube = self.get_tube_of_queue(tarantool_module, config)
        tarantool_entries = tube.take(0)
        do_continue = True
        entry_count = 0
        entries = []
        while tarantool_entries and do_continue:
            for tarantool_entry in tarantool_entries:
                entry_id, entry_type, entry_data = tarantool_entry
                entry = Entry.deserialize(entry_data, None)
                entries.append(entry)
                tube.ack(entry_id)
                entry_count += 1
            if entry_count > config['chunk_size']:
                do_continue = False
            else:
                tarantool_entries = tube.take(0)

        return entries


class PluginTarantoolQueueOutput(PluginTarantoolQueueBase):
    def on_task_output(self, task, config):
        if not task.accepted:
            return

        tarantool_module = self.get_tarantool_module()
        tube = self.get_tube_of_queue(tarantool_module, config)
        for entry in task.accepted:
            try:
                tube.put(Entry.serialize(entry))
            except Exception as e:
                entry.fail(e)


@event('plugin.register')
def register_plugin():
    plugin.register(PluginTarantoolQueueInput, 'from_tarantool', api_ver=2)
    plugin.register(PluginTarantoolQueueOutput, 'tarantool', api_ver=2)
