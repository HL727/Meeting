from __future__ import annotations

from typing import Any, Mapping

from policy_script.environment.base import PolicyScriptBaseEnvironment


class ClusterPolicyScriptEnvironment(PolicyScriptBaseEnvironment):

    _instance: ClusterPolicyScriptEnvironment = None

    @classmethod
    def instance(cls):
        if not cls._instance:
            cls._instance = ClusterPolicyScriptEnvironment()
        return cls._instance

    def get_environment_kwargs(self):
        return {
            **super().get_environment_kwargs(),
        }

    def clean_response(self, response: Mapping[str, Any], context: Mapping[str, Any]):
        from policy.response import clean_pexip_response

        return clean_pexip_response(response, context)

    def get_context(self, params: Mapping[str, Any], **context: Any):
        if 'cluster' not in context:
            raise KeyError('cluster must be included in ClusterPolicy context')

        return {
            **super().get_context(params, **context),
        }
