from dataclasses import dataclass
from typing import Any, List, Optional, OrderedDict, Tuple, TypeVar, Sequence

from typing_extensions import Protocol, TypedDict


class DictValue:

    def __getitem__(self, key):
        return self.as_dict()[key]

    def __repr__(self):
        return str(self.as_dict())

    def __iter__(self):
        return iter(self.as_dict().items())

    def as_dict(self) -> dict:
        raise NotImplementedError()


class Setting(DictValue):
    def __init__(self, path, value, limitations=None, name=None):

        self.path = path
        self.name = path[-1] if name is None else name
        self.value = value
        self.limitations = limitations

    def as_dict(self):
        return {
            'path': self.path,
            'name': self.name,
            'value': self.value,
            'is_setting': True,
            'limitations': self.limitations,
        }


class Command(DictValue):
    def __init__(self, path, arguments, body=False):

        self.path = path
        self.name = path[-1]
        self.arguments = arguments
        self.body = body

    def as_dict(self):
        return {
            'path': self.path,
            'name': self.name,
            'is_command': True,
            'arguments': self.arguments,
            'body': self.body,
        }

    def __repr__(self):
        return str(self.as_dict())


class ValueSpace(DictValue):
    def __init__(self, path, type, limitations):

        self.path = path
        if limitations.get('choices') == ['On', 'Off']:
            self.type = 'Toggle'
        else:
            self.type = type
        self.limitations = limitations

    def as_dict(self):
        return {
            'path': self.path,
            'type': self.type,
            'limitations': self.limitations,
        }

    def __repr__(self):
        return str(self.as_dict())


C = TypeVar('C')
IT = TypeVar('IT')

PathTuple = Tuple[str, ...]


class PathMeta(TypedDict):
    path: PathTuple


class ParsedItemTuple(Protocol):
    title: str
    meta: PathMeta
    item: Any

    def __getitem__(self, s: int):
        ...


class ConfigurationOptionalMeta(TypedDict, total=False):

    parents: Sequence[str]
    multiple: Optional[int]


class ConfigurationMeta(ConfigurationOptionalMeta, PathMeta):
    index: int


@dataclass
class ParsedConfigurationTuple:
    title: str
    meta: ConfigurationMeta
    children: List['ParsedConfigurationTuple']
    item: Optional[Setting]


@dataclass
class ParsedCommandTuple:
    title: str
    meta: PathMeta
    children: List['ParsedCommandTuple']
    item: Optional[Command]


class StatusMetaOpt(PathMeta, total=False):
    item: str


class StatusMeta(StatusMetaOpt):
    index: int


@dataclass
class ParsedStatusTuple:
    title: str
    meta: StatusMeta
    children: List['ParsedStatusTuple']
    item: str


ValueSpaceDict = OrderedDict[str, ValueSpace]


class BaseParser:
    def __init__(self):
        self.result = None
