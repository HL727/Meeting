from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Dict, Generic, Mapping, Tuple, TypeVar

from django.conf import settings
from django.utils.functional import cached_property
from jinja2.nodes import Template
from jinja2.sandbox import SandboxedEnvironment

from policy_script.environment.filters import (
    PolicyExitResponse,
    PolicyResponse,
    get_globals,
)
from policy_script.environment.template_loader import rewrite_template

if TYPE_CHECKING:
    from policy_script.models import PolicyScript  # noqa


TS = TypeVar('TS', bound='PolicyScript')  # Script type
TP = TypeVar('TP', bound=Mapping[str, Any])  # Input param type
TR = TypeVar('TR', bound=Mapping[str, Any])  # Result type


class PolicyScriptBaseEnvironment(Generic[TS, TP]):
    @cached_property
    def jinja_environment(self):
        return self.get_jinja_environment()

    def get_jinja_environment(self):
        kwargs = self.get_environment_kwargs()
        filters = kwargs.pop('filters', None) or {}
        globals = kwargs.pop('globals', None) or {}

        env = SandboxedEnvironment(
            **kwargs,
        )
        env.filters.update(filters)
        env.globals.update(globals)
        return env

    def get_environment_kwargs(self) -> Dict[str, Any]:
        return self.get_base_environment_kwargs()

    @staticmethod
    def get_base_environment_kwargs() -> Dict[str, Any]:
        from jinja2 import select_autoescape

        return {
            'globals': get_globals(),
            'autoescape': select_autoescape(),
            'line_statement_prefix': '%',
            'extensions': ['jinja2.ext.loopcontrols', 'jinja2.ext.do'],
        }

    def load_template(self, content: str):
        content = rewrite_template(content)
        return self.jinja_environment.from_string(content)

    def get_context(self, params: TP, **context: Any) -> Mapping[str, Any]:
        return {
            'request': params,
            **context,
        }

    def _log_error(self, e: Exception) -> None:
        pass

    def clean_response(self, response: Mapping[str, Any], context: Mapping[str, Any]):
        return response

    def execute(
        self, template: Template, response: TR, context: Mapping[str, Any]
    ) -> Tuple[Mapping[str, Any], bool]:
        def _clean(response: TR):
            return self.clean_response(response, context)

        try:
            rendered = template.render({**context, 'response': response})

            if re.search(r'[A-z]', rendered):
                raise Exception('No response called, but {} was rendered'.format(rendered.strip()))
        except PolicyExitResponse as e:
            return _clean(e.response), False
        except PolicyResponse as e:
            return _clean(e.response), True
        except Exception as e:
            if settings.DEBUG or settings.TEST_MODE:
                raise
            self._log_error(e)

        return response, True
