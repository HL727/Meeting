import re
from collections import defaultdict
from datetime import timedelta, datetime
from typing import Sequence, Dict, TypeVar, Callable, List, Optional, Type, Tuple, Any

from django.db import models, transaction
from django.utils.timezone import now


def _get_or_create(qs_or_model, *, defaults=None, **filters):
    if isinstance(qs_or_model, type) and issubclass(qs_or_model, models.Model):
        qs = qs_or_model.objects
    else:
        qs = qs_or_model
    obj, created = qs.select_for_update().get_or_create(**filters, defaults=defaults or {})
    return obj, created


@transaction.atomic
def maybe_update_or_create(qs_or_model, *, defaults=None, **filters):

    obj, created = _get_or_create(qs_or_model, defaults=defaults, **filters)
    if not created:
        maybe_update(obj, defaults)

    return obj, created


@transaction.atomic
def partial_update_or_create(qs_or_model, *, defaults=None, **filters):

    obj, created = _get_or_create(qs_or_model, defaults=defaults, **filters)

    if not created:
        partial_update(obj, defaults)

    return obj, created


def maybe_update(obj, *default_arg, **kwargs):
    "save object if changed. pass either values in first argument dict, or as **kwargs"

    changed = update_changed_fields(obj, *default_arg, **kwargs)
    if changed:
        obj.save()
    return changed


def partial_update(obj, *default_arg, **kwargs):
    "save only changed fields. pass either values in first argument dict, or as **kwargs"

    changed = update_changed_fields(obj, *default_arg, **kwargs)
    if changed:
        obj.save(update_fields=list(changed))
    return changed


def update_changed_fields(obj, *default_arg, **kwargs):
    if default_arg:
        assert len(default_arg) == 1 and not kwargs
        kwargs = default_arg[0]

    changed = get_changed_fields(obj, **kwargs)
    for k in changed:
        setattr(obj, k, kwargs[k])

    return changed


def get_changed_fields(obj, *default_arg, **kwargs):

    if default_arg:
        assert len(default_arg) == 1 and not kwargs
        kwargs = default_arg[0]

    class Undef:
        pass

    changed = set()
    for k, v in kwargs.items():
        if isinstance(v, models.Model) and hasattr(obj, k + '_id'):
            if v.pk != getattr(obj, k + '_id', Undef):
                changed.add(k)
        elif getattr(obj, k, Undef) != v:
            changed.add(k)

    return list(changed)


def prettify_xml(xml):
    from defusedxml.minidom import parseString
    try:
        doc = parseString(xml)
    except Exception:
        return xml
    xml = doc.toprettyxml(indent='  ')
    text_content_re = re.compile(r'>\n\s+([^<>\s].*?)\n\s+</', re.DOTALL)
    return text_content_re.sub(r'>\g<1></', xml)


class SyncBatcher:
    """
    Batch multiple updates. Group updates that only change time field into single operation
    """

    min_now_change: Optional[datetime] = None
    update_queue: Dict[Type[models.Model], List[Tuple[models.Model, Dict[str, Any]]]]
    only_time_update_queue: Dict[Type[models.Model], List[models.Model]]

    def __init__(self, size=50, time_update_fields: Sequence = None, max_time_drift=10, defaults=None):
        self.max_size = size
        self.cur_size = 0

        self.update_queue = defaultdict(list)
        self.only_time_update_queue = defaultdict(list)

        self.time_update_fields = time_update_fields if time_update_fields else ()
        self.defaults = defaults or {}

        self.only_time_update_set = set(time_update_fields) | set(defaults.keys()) if time_update_fields else set()
        self.max_time_drift = timedelta(seconds=max_time_drift)

        from threading import Lock
        self.lock = Lock()

    def partial_update(self, obj, changes: Dict):

        all_changes = {**self.defaults, **changes}

        changed = update_changed_fields(obj, all_changes)
        if not changed:
            return changed

        if not len(set(changed) - self.only_time_update_set):  # only time + default fields changed
            self.only_time_update_queue[obj.__class__].append(obj)
            if not self.min_now_change:
                self.min_now_change = now()
        else:
            self.update_queue[obj.__class__].append((obj, changes))

        self.cur_size += 1

        if self.cur_size >= self.max_size:
            self.commit()
        elif self.min_now_change and self.min_now_change < now() - self.max_time_drift:
            self.commit()

    def partial_update_or_create(self, qs_or_model, *, defaults: Dict, **filters):
        with transaction.atomic():
            obj, created = _get_or_create(qs_or_model, defaults=defaults, **filters)

        if not created:
            self.partial_update(obj, defaults)

        return obj, created

    def replace_queues(self):
        self.lock.acquire(blocking=True)

        only_time_update_queue, update_queue = self.update_queue, self.only_time_update_queue

        self.update_queue = defaultdict(list)
        self.only_time_update_queue = defaultdict(list)

        self.min_now_change = None
        self.cur_size = 0

        self.lock.release()
        return only_time_update_queue, update_queue

    def commit(self):

        update_queue, only_time_update_queue = self.replace_queues()

        if only_time_update_queue:
            self.update_only_time_objects(only_time_update_queue)
        if update_queue:
            self.update_objects(update_queue)

    def update_only_time_objects(self, queue):
        time_update = {f: now() for f in self.time_update_fields}
        for model, objects in queue.items():
            model.objects.filter(pk__in=[obj.pk for obj in objects]).update(**time_update,
                                                                            **self.defaults)
    def update_objects(self, queue):
        with transaction.atomic():
            for _model, objects in queue.items():
                for obj, changes in objects:
                    obj.save(update_fields=changes)

    def __del__(self):
        if self.cur_size:
            try:
                self.commit()
            except BaseException:
                self.commit()
                raise

            raise ValueError('Queue not empty when destroyed. Make sure to call .commit()')
        try:
            super().__del__()
        except AttributeError:
            pass


TD = TypeVar('TD')  # input item
TR = TypeVar('TR')  # key type


def get_multidict(it: Sequence[TD], key: Callable[[TD], TR]) -> Dict[TR, List[TD]]:
    """
    Group items using key from callable key(item)
    """
    result = defaultdict(list)
    for item in it:
        result[key(item)].append(item)
    return dict(result)
