import datetime
from abc import ABC, abstractmethod

from flexget.utils import json

DATE_FMT = '%Y-%m-%d'
ISO8601_FMT = '%Y-%m-%dT%H:%M:%SZ'


def serialize(value):
    """
    Convert an object to JSON serializable format.
    """
    if isinstance(value, Serializable):
        return value.serialize()
    if isinstance(value, (list, tuple)):
        return [serialize(v) for v in value]
    if isinstance(value, dict):
        return {k: serialize(v) for k, v in value.items()}
    if isinstance(value, datetime.datetime):
        return DateTimeSerializer.serialize(value)
    if isinstance(value, datetime.date):
        return DateSerializer.serialize(value)
    if isinstance(value, (str, int, float, type(None))):
        return value
    raise TypeError(f'{value!r} is not serializable')


def deserialize(value):
    if isinstance(value, dict):
        if all(key in value for key in ('serializer', 'version', 'value')):
            return _registry()[value['serializer']].deserialize(value)
        return {k: deserialize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [deserialize(v) for v in value]
    return value


class Serializable(ABC):
    @abstractmethod
    def _serialize(self):
        """This method should be implemented to return a plain python datatype which is json serializable."""
        pass

    def serialize(self):
        """Returns a json serializable form of this class, with all information needed to deserialize."""
        return {
            'serializer': self.serializer_name(),
            'version': self.serializer_version(),
            'value': self._serialize(),
        }

    @classmethod
    @abstractmethod
    def _deserialize(cls, data, version):
        """Returns an instance of this class, recreated from the serialized form."""
        pass

    @classmethod
    def deserialize(cls, data):
        return cls._deserialize(data['value'], data['version'])

    @classmethod
    def serializer_name(cls):
        return cls.__name__

    @classmethod
    def serializer_version(cls):
        return 1

    def dumps(self):
        return json.dumps(self.serialize())

    @classmethod
    def loads(cls, data):
        return cls.deserialize(json.loads(data))


class DateSerializer(Serializable):
    @classmethod
    def serializer_name(cls):
        return 'date'

    def _serialize(self):
        pass

    @classmethod
    def serialize(cls, value):
        return {
            'serializer': cls.serializer_name(),
            'version': cls.serializer_version(),
            'value': value.strftime(DATE_FMT),
        }

    @classmethod
    def _deserialize(cls, data, version):
        return datetime.datetime.strptime(data, DATE_FMT).date()


class DateTimeSerializer(Serializable):
    @classmethod
    def serializer_name(cls):
        return 'datetime'

    def _serialize(self):
        pass

    @classmethod
    def serialize(cls, value):
        return {
            'serializer': cls.serializer_name(),
            'version': cls.serializer_version(),
            'value': value.strftime(ISO8601_FMT),
        }

    @classmethod
    def _deserialize(cls, data, version):
        return datetime.datetime.strptime(data, ISO8601_FMT)


_registry_cache = None


def _registry():
    global _registry_cache
    if _registry_cache is None:
        _registry_cache = {c.serializer_name(): c for c in Serializable.__subclasses__()}
    return _registry_cache
