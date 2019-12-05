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
    if isinstance(value, datetime.datetime):
        return DateTimeSerializer.serialize(value)
    if isinstance(value, datetime.date):
        return DateSerializer.serialize(value)
    elif isinstance(value, (str, int, float, dict, list)):
        return BuiltinSerializer.serialize(value)
    else:
        raise TypeError('%r is not serializable', value)


class Serializable(ABC):
    _registry = None

    @staticmethod
    def registry():
        if Serializable._registry is None:
            Serializable._registry = {c.serializer_name(): c for c in Serializable.__subclasses__()}
        return Serializable._registry

    @abstractmethod
    def _serialize(self):
        """Return a plain python datatype which is json serializable."""
        pass

    def serialize(self):
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
        return cls.registry()[data['serializer']]._deserialize(
            data['value'], data['version']
        )

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


class BuiltinSerializer(Serializable):
    @classmethod
    def serializer_name(cls):
        return 'builtin'

    def _serialize(self):
        pass

    @classmethod
    def serialize(cls, value):
        if isinstance(value, list):
            value = [serialize(i) for i in value]
        elif isinstance(value, dict):
            value = {k: serialize(v) for k, v in value.items()}
        return {
            'serializer': cls.serializer_name(),
            'version': cls.serializer_version(),
            'value': value,
        }

    @classmethod
    def _deserialize(cls, data, version):
        if isinstance(data, list):
            return [cls.deserialize(i) for i in data]
        if isinstance(data, dict):
            return {k: cls.deserialize(v) for k, v in data.items()}
        return data


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
