

import json
from typing import Dict, List, Mapping, Set, Type, TypeVar, Union
from xml.etree.ElementTree import Element

from django.utils.encoding import force_text
from typing_extensions import DefaultDict, OrderedDict

from .cisco_ce import (
    BaseParser,
    NestedConfigurationXMLResult,
    NestedStatusXMLResult,
    NestedXMLResult,
    Setting,
    ValueSpace,
)
from .types import ParsedConfigurationTuple, ParsedStatusTuple, PathTuple, ValueSpaceDict


class PolyBaseParser(BaseParser):

    ns = {
        '': 'http://www.w3.org/2001/XMLSchema',
    }

    type_aliases = {
        'nonNegativeInteger': 'Integer',
        'unsignedInt': 'Integer',
        'string': 'String',
        'boolean': 'Toggle',
        'integer': 'Integer',
    }

    def __init__(self, root):
        super().__init__()
        self.root = root

    def parse(self):
        self.result = self._iter(self.root)
        return NestedXMLResult(self.result)

    def _iter(self, parent: Element):
        raise NotImplementedError()


class PolyXStatusParser(PolyBaseParser):
    def parse(self):
        self.result = self._iter(json.loads(force_text(self.root)))
        return NestedStatusXMLResult(nested_tree_from_path(self.result, ParsedStatusTuple))

    def _iter(self, parent: dict, parent_path=()):

        result = []

        for k, values in parent.items():
            cur_path = parent_path + tuple(k.split('.'))

            if not isinstance(values, (tuple, list)):
                values = [values]

            for i, value in enumerate(values):

                if isinstance(value, dict):
                    children = self._iter(value, cur_path)
                    cur = ParsedStatusTuple(
                        cur_path[-1], {'index': i + 1, 'path': cur_path}, children, None
                    )
                else:
                    cur = ParsedStatusTuple(
                        cur_path[-1], {'index': i + 1, 'path': cur_path}, [], value
                    )

                result.append(cur)

        return result


T = TypeVar('T', ParsedStatusTuple, ParsedConfigurationTuple)


class PolyXConfigurationParser(PolyBaseParser):
    """Parse configuration settings from polycomConfig.xsd"""

    def __init__(
        self,
        root: Element,
        valuespace=None,
        values: Union[NestedConfigurationXMLResult, Mapping[str, str]] = None,
    ):
        self.valuespace = valuespace or {}
        self.values = values or {}
        super().__init__(root)

    def parse(self) -> NestedConfigurationXMLResult:
        items = self._iter(self.root)

        self.result = nested_tree_from_path(items, ParsedConfigurationTuple)
        return NestedConfigurationXMLResult(self.result)

    def _iter(self, parent: Element) -> List[ParsedConfigurationTuple]:

        all_elements = {
            tuple(el.get('name', '').split('.')) for el in parent.findall('.//element', self.ns)
        }

        result: List[ParsedConfigurationTuple] = []
        for attrib in parent.iterfind('./attribute', self.ns):
            name = attrib.get('name', '')
            parts = tuple(name.split('.'))
            value = self.values.get(name)
            if parts[-1].isdigit():
                name, index = parts[-2], int(parts[-1])
            else:
                name, index = parts[-1], 1

            parent_elements = [
                '.'.join(parts[: i + 1]) for i in range(len(parts)) if parts[:i] in all_elements
            ]

            if attrib.get('type', '').startswith('xsd:'):
                type = attrib.get('type', '')[4:]
                limitations = {
                    'type': self.type_aliases.get(type) or type,
                }
            else:
                limitations = self.valuespace.get(attrib.get('type')) or {}

            result.append(
                ParsedConfigurationTuple(
                    name,
                    {'index': index, 'path': parts, 'parents': parent_elements},
                    [],
                    Setting(parts, value, limitations, name=name),
                )
            )

        return result


class PolyXConfigurationValueParser(PolyBaseParser):
    """Parse exported configurationProfile"""

    def parse(self) -> Dict[str, str]:
        self.result = self._iter(self.root)
        return self.result

    def _iter(self, parent: Element):

        result = OrderedDict()
        for node in parent:
            for attrib, value in node.items():
                result[attrib] = value

        return result


class PolyXValueSpaceParser(PolyBaseParser):
    """Parse configuration types from polycomConfig.xsd"""

    def parse(self) -> ValueSpaceDict:
        self.result = self._iter(self.root)
        return self.result

    def _iter(self, parent: Element, path=()) -> ValueSpaceDict:
        """
        { 'key': ValueSpace(...), ... }
        """

        def _get_value(_parent: Element, k: str, default=None):
            target = _parent.find(k, self.ns)
            if target is not None:
                return target.get('value')
            return default

        result: ValueSpaceDict = OrderedDict()
        for child in parent.iterfind('./simpleType', self.ns):
            name = child.get('name')
            limitations = {}
            type = 'String'
            for restriction in child.iterfind('./restriction', self.ns):
                if restriction.get('base', '').startswith('xsd:'):
                    type = restriction.get('base', '')[4:]
                    limitations['choices'] = [
                        e.get('value') for e in restriction.iterfind('./enumeration', self.ns)
                    ] or None
                    limitations['Min'] = _get_value(restriction, 'minInclusive')
                    limitations['Max'] = _get_value(restriction, 'maxInclusive')
            if limitations.get('choices'):
                type = 'Literal'
            elif type in self.type_aliases:
                type = self.type_aliases[type]
            limitations = {k: v for k, v in limitations.items() if v is not None}
            result[name] = ValueSpace(tuple(name.split('.')), type, limitations)
        return result


def nested_tree_from_path(lst: List[T], klass: Type[T]):
    result = []

    tree = DefaultDict[PathTuple, Set](set)
    by_parent = DefaultDict[PathTuple, List[T]](list)

    group_by_number = False

    for r in lst:

        for i in range(len(r.meta['path']) - 1):
            if r.meta['path'][i].isdigit() and i >= 2:
                if group_by_number:  # TODO ever a good idea?
                    cur = r.meta['path'][:i]
                    break
        else:
            cur = r.meta['path'][:-1] or r.meta['path']

        if len(r.meta['path']) == 1 and not r.children:
            cur = ('Misc',)  # Fake parent for top level
            tree.setdefault(cur, set())
        else:
            for i in range(len(cur)):
                tree[cur[: i + 1]].add(cur[: i + 2])
        by_parent[cur].append(r)

    def recurse(parent: PathTuple) -> List[klass]:

        result = []
        nested_children = [c for p in tree.get(parent, []) for c in recurse(p) if p != parent]
        nested_children.extend(c for p in by_parent[parent] for c in p.children)

        settings_children = [s for s in by_parent[parent] if not s.children]

        cur = klass(
            parent[-1].title(), {'path': parent}, [*nested_children, *settings_children], None
        )
        result.append(cur)
        return result

    for key in list(tree.keys()):  # remove self references
        tree[key].discard(key)

    for path in tree.keys():
        if len(path) > 1:
            continue
        result.extend(recurse(path))

    return result
