from typing import Dict, List, Optional, Union

from typing_extensions import TypedDict


class ConfigurationDict(TypedDict):

    key: List[str]
    value: Optional[str]


class CommandDictRequired(TypedDict):

    command: List[str]
    arguments: Dict[str, Union[str, List[str]]]


class CommandDict(CommandDictRequired, total=False):
    body: Optional[str]


class XAPIParseDict(TypedDict):
    commands: List[CommandDict]
    configuration: List[ConfigurationDict]
