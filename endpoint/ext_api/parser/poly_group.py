import json
from typing import Dict, OrderedDict

from django.utils.encoding import force_text

from .poly_x import PolyBaseParser


class PolyGroupConfigurationValueParser(PolyBaseParser):
    """Parse exported configurationProfile"""

    def parse(self) -> Dict[str, str]:
        self.result = self._iter(force_text(self.root))
        return self.result

    def _iter(self, parent: str):

        if parent.startswith('{'):
            return json.loads(parent)

        result = OrderedDict[str, str]()
        for line in force_text(parent).split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                result[key] = value

        return result
