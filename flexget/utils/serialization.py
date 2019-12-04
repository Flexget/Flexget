from abc import ABC, abstractmethod

from flexget.utils import json


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
        return {
            'serializer': cls.serializer_name(),
            'version': cls.serializer_version(),
            'value': value,
        }

    @classmethod
    def _deserialize(cls, data, version):
        return data
