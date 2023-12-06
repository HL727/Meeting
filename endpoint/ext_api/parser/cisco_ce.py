import dataclasses
from collections import OrderedDict, defaultdict
from typing import Any, DefaultDict, Dict, Generic, Iterator, List, Optional
from typing import OrderedDict as TOrderedDict
from typing import Sequence, Set, Tuple, TypeVar, Union
from xml.etree.ElementTree import Element

from django.utils.datastructures import MultiValueDict

from endpoint.ext_api.parser.types import (
    BaseParser,
    Command,
    ParsedCommandTuple,
    ParsedConfigurationTuple,
    ParsedStatusTuple,
    PathTuple,
    Setting,
    ValueSpace,
    ValueSpaceDict,
)


def get_tag(node):
    "remove namespace if included"

    tag = str(node.tag)
    if tag.startswith('{'):
        tag = tag.split('}', 1)[-1]
    return tag


T = TypeVar('T', ParsedConfigurationTuple, ParsedStatusTuple, ParsedCommandTuple)
PathDefaultDict = DefaultDict[PathTuple, List[T]]


class NestedXMLResult(Generic[T]):

    def __init__(self, data: Sequence[T]):
        self.data = data
        self._cached_keys: Optional[PathDefaultDict[T]] = None
        self._cached_keys_with_items: Optional[PathDefaultDict[T]] = None
        self._duplicated_keys = set()

    def _groupdict(self, lst):
        result = defaultdict(list)
        for k, v in lst:
            result[k].append(v)
        return MultiValueDict(result)

    @property
    def _nested_keys(self) -> PathDefaultDict[T]:
        if self._cached_keys is not None:
            return self._cached_keys

        keys_with_items: PathDefaultDict[T] = defaultdict(list)
        all_keys: PathDefaultDict[T] = defaultdict(list)
        duplicated_keys: Set[PathTuple] = set()

        def _iter(lst: Sequence[T]):
            for item in lst:
                path = item.meta.get('path', ())
                if path:
                    all_keys[path].append(item)
                    if item.item:
                        keys_with_items[path].append(item)
                _iter(item.children)
                path_without_index = tuple(x.split('[', 1)[0] for x in path)
                if path != path_without_index:
                    duplicated_keys.add(path_without_index)
                    all_keys[path_without_index].append(item)

        _iter(self.data)
        self._cached_keys = all_keys
        self._cached_keys_with_items = keys_with_items

        return all_keys

    @property
    def all_keys(self) -> PathDefaultDict[T]:
        if not self._cached_keys_with_items:
            list(self._nested_keys)
        return self._cached_keys_with_items

    def findall(self, path: str):

        parts = tuple(path.lstrip('./').rstrip('/').replace('.', '/').split('/'))

        if self.data is None:
            raise ValueError('Result not loaded')

        return self._nested_keys.get(parts, [])

    def find(self, path: str) -> Optional[T]:
        all = self.findall(path)
        return all[0] if all else None

    def _get_text_value(self, node: T) -> str:
        raise NotImplementedError()

    def findtext(self, path: str, default='') -> str:

        result = self.find(path)
        if result is None:
            return default
        return self._get_text_value(result)

    def findtextall(self, path: str) -> List[str]:

        result = self.findall(path)
        return [self._get_text_value(r) for r in result]

    def textdict(self, path: str) -> MultiValueDict:

        parent = self.find(path)
        if not parent:
            return MultiValueDict()
        return self._groupdict(
            (child.title, self._get_text_value(child)) for child in parent.children
        )

    def textdictall(self, path: str) -> List[Dict[str, str]]:

        all = self.findall(path)
        return [
            self._groupdict((child.title, self._get_text_value(child)) for child in parent.children)
            for parent in all
        ]

    def get(self, key, default=None) -> Optional[str]:
        return self.findtext(key, default)

    def __getitem__(self, key: str) -> str:
        try:
            return self.findtextall(key)[0]
        except IndexError:
            raise KeyError(key)

    def __iter__(self) -> Iterator[Tuple[str, T]]:
        return (('.'.join(k), v[0].item) for k, v in self.all_keys.items())

    def tuple_items(self) -> List[Tuple]:
        def _iter(lst: Sequence[T]):
            for item in lst:
                c = item.children
                try:
                    item.children = list(_iter(item.children)) if item.children else []
                    res = dataclasses.astuple(item)
                    item.children = c
                    yield res
                finally:
                    item.children = c

        return list(_iter(self.data))


class NestedConfigurationXMLResult(NestedXMLResult[ParsedConfigurationTuple]):
    def _get_text_value(self, node: ParsedConfigurationTuple) -> str:
        return node.item.value


class NestedStatusXMLResult(NestedXMLResult[ParsedStatusTuple]):
    def _get_text_value(self, node: ParsedStatusTuple) -> str:
        return node.item


class NestedCommandsXMLResult(NestedXMLResult[ParsedCommandTuple]):
    def _get_text_value(self, node: ParsedCommandTuple) -> str:
        raise NotImplementedError()


class ConfigurationParser(BaseParser):

    def __init__(self, root, valuespace):
        super().__init__()
        self.root = root
        self.valuespace = valuespace

    def parse(self) -> NestedConfigurationXMLResult:
        self.result = self._iter(self.root)
        return NestedConfigurationXMLResult(self.result)

    def _iter(self, node: Element, path=()) -> List[ParsedConfigurationTuple]:
        '''
        [
            ('title', {'option':''}, child_tree, setting),
        ]
        setting.path = Audio > Microphone > [0] ->
        '''

        result: List[ParsedConfigurationTuple] = []

        count_tag = ''
        count = 0

        for section in node:

            cur_tag = get_tag(section)

            if count_tag == cur_tag:
                count += 1
            else:
                count_tag, count = cur_tag, 0

            items = []
            setting = None

            if section.get('maxOccurrence'):
                cur_path = path + ('{}[{}]'.format(cur_tag, section.get('item')),)
            else:
                cur_path = path + (cur_tag,)

            if section.get('valueSpaceRef'):
                limitations = self.get_limitations(
                    section.get('valueSpaceRef').replace('/Valuespace/', '')
                )
                setting = Setting(cur_path, section.text, limitations)
            else:

                items = self._iter(section, path=cur_path)

            result.append(
                ParsedConfigurationTuple(
                    cur_tag,
                    {'index': count, 'multiple': section.get('maxOccurrence'), 'path': cur_path},
                    items,
                    setting,
                )
            )

        return result

    def get_limitations(self, valuespace_ref):
        return self.valuespace.get(valuespace_ref) or {}


class CommandParser(BaseParser):

    def __init__(self, root, valuespace=None):
        super().__init__()
        self.root = root
        self.valuespace = valuespace

    def parse(self) -> NestedCommandsXMLResult:
        self.result = self._iter(self.root)
        return NestedCommandsXMLResult(self.result)

    def _iter(self, node: Element, path=()) -> List[ParsedCommandTuple]:
        '''
        [
            ('title', {'option':''}, child_tree, command),
        ]
        '''

        result: List[ParsedCommandTuple] = []

        for section in node:

            cur_tag = get_tag(section)

            items = []
            command = None

            if section.get('command') == 'True':
                command = Command(path + (cur_tag,),
                                  self._iter_arguments(section),
                                  section.get('multiline') == 'True'
                                  )
            else:
                items = self._iter(section, path=path + (cur_tag,))

            result.append(ParsedCommandTuple(cur_tag, {'path': path + (cur_tag,)}, items, command))

        return result

    def _iter_arguments(self, node: Element):
        result: TOrderedDict[str, Any] = OrderedDict()
        for section in node:
            cur_tag = get_tag(section)
            result[cur_tag] = {
                'default': section.get('default'),
                'multiple': section.get('multiple'),
                'required': section.get('required') == 'True',
                'limitations': self.get_limitations(section)
            }

        return result

    def get_limitations(self, section: Element):
        valuespace_ref = section.get('valueSpaceRef', '').replace('/Valuespace/', '')
        if not self.valuespace:
            return ValueSpaceParser(section).parse().get(valuespace_ref) or {}
        return self.valuespace.get(valuespace_ref) or {}


class ValueSpaceParser(BaseParser):

    def __init__(self, root):
        super().__init__()
        self.root = root

    def parse(self) -> ValueSpaceDict:
        self.result = self._iter(self.root)
        return self.result

    def _iter(self, node: Element = None, path=()) -> ValueSpaceDict:
        '''
        {
            'key': value,,
        '''
        result: ValueSpaceDict = OrderedDict()
        for section in node:

            cur_tag = get_tag(section)
            type = section.get('type')
            limitations: Dict[str, Union[str, int, List[str]]] = {}

            if type == 'Integer':
                limitations = {
                    'max': int(section.findtext('./Max') or 0),
                    'min': int(section.findtext('./Min') or 0),
                    'step': int(section.findtext('./Step') or 0),
                }
            elif type == 'String':
                limitations = {
                    'max_length': int(section.findtext('./MaxLength') or 0),
                    'min_length': int(section.findtext('./MinLength') or 0),
                }
            elif type == 'Literal':
                limitations = {
                    'choices': [str(v.text or '') for v in section],
                }

            result[cur_tag] = ValueSpace(path + (cur_tag,), type=section.get('type'), limitations=limitations)

        return result


class StatusParser(BaseParser):

    def __init__(self, root):
        super().__init__()
        self.root = root

    def _nest_duplicates(self, lst: List[ParsedStatusTuple]):
        result = []

        duplicates = {r.title for r in lst if r.meta.get('index', 0) > 0}

        for r in lst:
            if r.title not in duplicates:
                result.append(r)
            elif r.meta['index'] == 0:
                children = [i for i in lst if i.title == r.title]
                result.append(ParsedStatusTuple(r.title, {'path': r.meta['path']}, children, ''))
            else:
                continue
        return result

    def parse(self) -> NestedStatusXMLResult:
        items = self._iter(self.root)

        self.result = self._nest_duplicates(items)
        return NestedStatusXMLResult(self.result)

    def _iter(self, node: Element, path=()) -> List[ParsedStatusTuple]:
        '''
        [
            ('title', {'option':''}, child_tree, value),
        ]
        '''

        result = []

        count_tag = ''
        count = 0

        for section in node:

            cur_tag = get_tag(section)

            if count_tag == cur_tag:
                count += 1
            else:
                count_tag, count = cur_tag, 0

            items = []
            value = None

            if section.get('item'):
                cur_path = path + ('{}[{}]'.format(cur_tag, section.get('item')),)
            else:
                cur_path = path + (cur_tag,)

            if len(section):
                items = self._iter(section, path=cur_path)
            else:
                value = section.text or ''

            cur = ParsedStatusTuple(cur_tag, {'index': count, 'path': cur_path}, items, value)
            if section.get('item'):
                cur.meta['item'] = section.get('item')

            result.append(cur)

        return result

