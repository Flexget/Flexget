import datetime
from abc import ABC, abstractmethod
from typing import Any, Optional, Type

from flexget.utils import json

DATE_FMT = '%Y-%m-%d'
ISO8601_FMT = '%Y-%m-%dT%H:%M:%SZ'


def serialize(value: Any) -> Any:
    """Convert an object to JSON serializable format.

    :param value: Object to serialize.
    :return: JSON serializable representation of this object.
    """
    s = _serializer_for(value)
    if s:
        return {
            'serializer': s.serializer_name(),
            'version': s.serializer_version(),
            'value': s.serialize(value),
        }
    if isinstance(value, list):
        return [serialize(v) for v in value]
    if isinstance(value, dict):
        return {k: serialize(v) for k, v in value.items()}
    if isinstance(value, (str, int, float, type(None))):
        return value
    raise TypeError(f'`{value!r}` of type {type(value)!r} is not serializable')


def deserialize(value: Any) -> Any:
    """Restore an object stored with this serialization system to its original format.

    :param value: Serialized representation of the object.
    :return: Deserialized object.
    """
    if isinstance(value, dict):
        if all(key in value for key in ('serializer', 'version', 'value')):
            return _deserializer_for(value['serializer']).deserialize(
                value['value'], value['version']
            )
        return {k: deserialize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [deserialize(v) for v in value]
    return value


def dumps(value: Any) -> str:
    """Dump an object to text using the serialization system."""
    serialized = serialize(value)
    try:
        return json.dumps(serialized)
    except TypeError as exc:
        raise TypeError('Error during dumping {}. Instance: {!r}'.format(exc, serialized)) from exc


def loads(value: str) -> Any:
    """Restore an object from JSON text created by `dumps`"""
    return deserialize(json.loads(value))


class Serializer(ABC):
    """
    Any data types that should be serializable should subclass this, and implement the `serialize` and `deserialize`
    methods. This is important for data that is stored in `Entry` fields so that it can be stored to the database.
    """

    @classmethod
    def serializer_name(cls) -> str:
        """
        Name of the serializer defaults to class name.
        This can be overridden in subclass implementations if desired.
        """
        return cls.__name__

    @classmethod
    def serializer_version(cls) -> int:
        """
        If the format of serialization changes, this number should be incremented.
        The `deserialize` method of this class should continue to handle the old versions as well as the
        current version.
        """
        return 1

    @classmethod
    def serializer_handles(cls, value: Any) -> bool:
        """Return True if this serializer can handle `value`."""
        return isinstance(value, cls)

    @classmethod
    @abstractmethod
    def serialize(cls, value: Any) -> Any:
        """This method should be implemented to return a plain python datatype which is json serializable."""

    @classmethod
    @abstractmethod
    def deserialize(cls, data: Any, version: int) -> Any:
        """Returns an instance of the original class, recreated from the serialized form."""


class DateTimeSerializer(Serializer):
    @classmethod
    def serializer_handles(cls, value):
        return isinstance(value, datetime.datetime)

    @classmethod
    def serialize(cls, value: datetime.datetime):
        return value.strftime(ISO8601_FMT)

    @classmethod
    def deserialize(cls, data: str, version: int) -> datetime.datetime:
        return datetime.datetime.strptime(data, ISO8601_FMT)


class DateSerializer(Serializer):
    @classmethod
    def serializer_handles(cls, value):
        return isinstance(value, datetime.date) and not isinstance(value, datetime.datetime)

    @classmethod
    def serialize(cls, value: datetime.date):
        return value.strftime(DATE_FMT)

    @classmethod
    def deserialize(cls, data: str, version: int) -> datetime.date:
        return datetime.datetime.strptime(data, DATE_FMT).date()


class SetSerializer(Serializer):
    @classmethod
    def serializer_handles(cls, value):
        return isinstance(value, set)

    @classmethod
    def serialize(cls, value: set) -> list:
        return serialize(list(value))

    @classmethod
    def deserialize(cls, data: list, version: int) -> set:
        return set(deserialize(data))


class TupleSerializer(Serializer):
    @classmethod
    def serializer_handles(cls, value):
        return isinstance(value, tuple)

    @classmethod
    def serialize(cls, value: tuple) -> list:
        return serialize(list(value))

    @classmethod
    def deserialize(cls, data: list, version: int) -> tuple:
        return tuple(deserialize(data))  # type: ignore


def _serializer_for(value) -> Optional[Type[Serializer]]:
    for s in Serializer.__subclasses__():
        if s.serializer_handles(value):
            return s
    return None


def _deserializer_for(serializer_name: str) -> Type[Serializer]:
    for s in Serializer.__subclasses__():
        if serializer_name == s.serializer_name():
            return s
    raise ValueError(f'No deserializer for {serializer_name}')
