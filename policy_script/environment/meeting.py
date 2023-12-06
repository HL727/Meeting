from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping

from policy_script.environment.base import PolicyScriptBaseEnvironment

if TYPE_CHECKING:
    from customer.models import Customer


class MeetingPolicyScriptEnvironment(PolicyScriptBaseEnvironment):

    _instance: MeetingPolicyScriptEnvironment = None

    @classmethod
    def instance(cls):
        if not cls._instance:
            cls._instance = MeetingPolicyScriptEnvironment()
        return cls._instance

    def get_environment_kwargs(self):
        return {
            **super().get_environment_kwargs(),
        }

    def get_context(self, params: Mapping[str, Any], **context: Any):

        if not context.get('customer'):
            raise ValueError('customer must be provided to MeetingPolicyScript context')

        customer: Customer = context.pop('customer')

        return {
            **super().get_context(params, **context),
            'cluster': customer.get_provider(),
            'customer': customer,
        }
