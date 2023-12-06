import json
from typing import Dict, OrderedDict, Union

from django.utils.encoding import force_text

from .cisco_ce import NestedConfigurationXMLResult
from .poly_x import PolyBaseParser


class PolyTrioRunningConfigurationValueParser(PolyBaseParser):
    """Parse values from runningConfig"""

    def parse(self) -> Dict[str, str]:
        self.result = self._iter(json.loads(force_text(self.root)))
        return self.result

    def _iter(self, parent: Dict[str, Union[str, dict]], parent_path="", target=None):

        result = target or OrderedDict()

        for k, v in parent.items():
            if parent_path == "":
                path = k
            else:
                path = parent_path + "." + k
            if isinstance(v, dict):
                result = OrderedDict({**result, **self._iter(v, parent_path=path, target=result)})
            else:
                result[path] = v

        return result

class PolyTrioStatusValueParser(PolyBaseParser):
    """Parse values from status"""

    def parse(self) -> Dict[str, str]:
        self.result = self._iter(json.loads(force_text(self.root)))
        return self.result

    def _iter(self, parent: Dict[str, Union[str, dict]], parent_path="", target=None):

        result = target or OrderedDict()

        for k, v in parent.items():
            if parent_path == "":
                path = k
            else:
                path = parent_path + "." + k
            if isinstance(v, dict):
                result = OrderedDict({**result, **self._iter(v, parent_path=path, target=result)})
            else:
                result[path] = v

        return result
