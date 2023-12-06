import enum
from typing import Any, Dict, List, Literal, Mapping, Tuple

from cacheout import fifo_memoize
from django.core.exceptions import ValidationError
from django.db import models
from jinja2 import Template

from customer.models import Customer
from provider.models.provider import Cluster


class OnResponse(enum.Enum):
    CONTINUE = 'continue'
    BREAK = 'break'


class PolicyScriptType(enum.Enum):

    CLUSTER = 'cluster'
    MEETING = 'meeting'


class PolicyScriptResponseType(enum.Enum):

    SERVICE = 'service'


def validate_template(content: str):
    from policy_script.environment.cluster import ClusterPolicyScriptEnvironment

    try:
        ClusterPolicyScriptEnvironment.instance().load_template(content)
    except Exception as e:
        raise ValidationError(str(e))


class PolicyScript(models.Model):

    OnResponse = OnResponse

    title = models.CharField(max_length=200)

    content = models.TextField(validators=[validate_template])
    priority = models.SmallIntegerField(default=10)
    enabled = models.BooleanField(blank=True, default=True)
    type = models.CharField(
        max_length=255, editable=False, choices=[(t.value, t.name) for t in PolicyScriptType]
    )
    on_response = models.CharField(max_length=255, choices=[(c.value, c.name) for c in OnResponse])

    def __str__(self):
        return self.title


class ClusterPolicyScript(PolicyScript):
    cluster = models.ForeignKey(Cluster, on_delete=models.CASCADE)
    limit_customers = models.BooleanField(default=False)
    customers = models.ManyToManyField(Customer, blank=True)
    service_type = models.CharField(
        max_length=255,
        editable=False,
        choices=[(t.value, t.name) for t in PolicyScriptResponseType],
    )

    type: Literal['cluster']  # type: ignore

    def save(self, *args, **kwargs):
        self.type = 'cluster'
        super().save(*args, **kwargs)

    def get_template(self):
        from policy_script.environment.cluster import ClusterPolicyScriptEnvironment

        return ClusterPolicyScriptEnvironment.instance().load_template(self.content)


class MeetingPolicyScript(PolicyScript):
    limit_customers = models.BooleanField(default=False)
    customers = models.ManyToManyField(Customer, blank=True)

    type: Literal['meeting']  # type: ignore

    def save(self, *args, **kwargs):
        self.type = 'meeting'
        super().save(*args, **kwargs)


@fifo_memoize(100, ttl=10)
def get_cluster_policy_scripts(cluster_id: int) -> List[Tuple[Template, OnResponse]]:

    result = []
    for script in ClusterPolicyScript.objects.filter(cluster=cluster_id):
        cur = script.get_template(), script.on_response
        result.append(cur)
    return result


def get_cluster_policy_response(
    cluster: Cluster,
    params: Mapping[str, Any],
    response: Dict[str, Any],
    **extra_context: Any,
):
    from policy_script.environment.cluster import ClusterPolicyScriptEnvironment

    env = ClusterPolicyScriptEnvironment.instance()
    context = env.get_context(params, cluster=cluster, **extra_context)

    result = None, False

    for template, on_response in get_cluster_policy_scripts(cluster.id):
        new_response, has_response = env.execute(template, response, context)
        if has_response:
            result = new_response, True

            if on_response == OnResponse.BREAK:
                return result

    return result


def clear_cache(sender, **kwargs):

    get_cluster_policy_scripts.cache.clear()


models.signals.post_save.connect(clear_cache, sender=ClusterPolicyScript)
models.signals.post_delete.connect(clear_cache, sender=ClusterPolicyScript)
