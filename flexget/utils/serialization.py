from abc import ABC, abstractmethod, abstractclassmethod

from flexget.utils import json


class Serializable(ABC):
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

    @abstractclassmethod
    def _deserialize(cls, data, version):
        """Returns an instance of this class, recreated from the serialized form."""
        pass

    @classmethod
    def deserialize(cls, data):
        registry = serializer_registry()
        return registry[data['serializer']]._deserialize(data['value'], data['version'])

    @classmethod
    def serializer_name(cls):
        return cls.__name__

    @classmethod
    def serializer_version(self):
        return 1

    def dumps(self):
        return json.dumps(self.sereialize())

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
        return {
            'serializer': cls.serializer_name(),
            'version': cls.serializer_version(),
            'value': value,
        }

    @classmethod
    def _deserialize(cls, data, version):
        return data


def serializer_registry():
    return {c.serializer_name(): c for c in Serializable.__subclasses__()}
