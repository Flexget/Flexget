import datetime
from abc import ABC, abstractmethod
from typing import Any, Optional, Type

import yaml
from loguru import logger

from flexget.utils import json

DATE_FMT = '%Y-%m-%d'
DATETIME_FMT = '%Y-%m-%dT%H:%M:%SZ'


logger = logger.bind(name='utils.serialization')


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
    """Dump an object to JSON text using the serialization system."""
    serialized = serialize(value)
    try:
        return json.dumps(serialized)
    except TypeError as exc:
        raise TypeError('Error during dumping {}. Instance: {!r}'.format(exc, serialized)) from exc


def loads(value: str) -> Any:
    """Restore an object from JSON text created by `dumps`"""
    return deserialize(json.loads(value))


def yaml_dump(data, *args, **kwargs):
    """Dump an object to YAML text using the serialization system."""
    data = serialize(data)
    kwargs['Dumper'] = FGDumper
    return yaml.dump(data, *args, **kwargs)


def yaml_load(stream):
    """Restore an object from YAML text created by `yaml_dump`"""
    return yaml.load(stream, Loader=FGLoader)


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


# Dates and DateTimes are not always symmetric using strftime and strptime :eyeroll:
# See:
# https://bugs.python.org/issue13305
# https://github.com/Flexget/Flexget/issues/2818
# https://github.com/Flexget/Flexget/issues/3304


class DateTimeSerializer(Serializer):
    @classmethod
    def serializer_handles(cls, value):
        return isinstance(value, datetime.datetime)

    @classmethod
    def serialize(cls, value: datetime.datetime):
        result = value.strftime(DATETIME_FMT)
        # See note above
        year, rest = result.split('-', maxsplit=1)
        if len(year) != 4:
            result = f'{value.year:04}-{rest}'
        return result

    @classmethod
    def deserialize(cls, data: str, version: int) -> datetime.datetime:
        try:
            return datetime.datetime.strptime(data, DATETIME_FMT)
        except ValueError:
            logger.error(f'Error deserializing datetime `{data}`')
            return datetime.datetime.min


class DateSerializer(Serializer):
    @classmethod
    def serializer_handles(cls, value):
        return isinstance(value, datetime.date) and not isinstance(value, datetime.datetime)

    @classmethod
    def serialize(cls, value: datetime.date):
        result = value.strftime(DATE_FMT)
        # See note above
        year, rest = result.split('-', maxsplit=1)
        if len(year) != 4:
            result = f'{value.year:04}-{rest}'
        return result

    @classmethod
    def deserialize(cls, data: str, version: int) -> datetime.date:
        try:
            return datetime.datetime.strptime(data, DATE_FMT).date()
        except ValueError:
            logger.error(f'Error deserializing date `{data}`')
            return datetime.date.min


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


def _yaml_representer(dumper, data):
    if isinstance(data, dict) and all(k in data for k in ('value', 'serializer', 'version')):
        tag = f"!{data['serializer']}.v{data['version']}"
        if isinstance(data['value'], dict):
            return dumper.represent_mapping(tag, data['value'])
        elif isinstance(data['value'], list):
            return dumper.represent_sequence(tag, data['value'])
        else:
            return dumper.represent_scalar(tag, data['value'])
    return dumper.represent_dict(data)


def _yaml_constructor(loader, node):
    serializer, version = node.tag.split('.v')
    serializer = serializer.lstrip('!')
    version = int(version)
    if node.id == 'mapping':
        value = loader.construct_mapping(node, deep=True)
    elif node.id == 'sequence':
        value = loader.construct_sequence(node, deep=True)
    else:
        value = loader.construct_scalar(node)
    return _deserializer_for(serializer).deserialize(value, version)


class FGDumper(yaml.SafeDumper):
    pass


FGDumper.add_representer(dict, _yaml_representer)


class FGLoader(yaml.SafeLoader):
    def __init__(self, stream):
        for s in Serializer.__subclasses__():
            name = s.serializer_name()
            for v in range(1, s.serializer_version() + 1):
                self.add_constructor(f"!{name}.v{v}", _yaml_constructor)
        super().__init__(stream)
