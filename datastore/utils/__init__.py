from functools import wraps
from typing import Iterator, Dict, Tuple, Any, Callable, TypeVar


def bulk_iter(provider, model, id_field, server_objects, server_id_field='id', batch_size=50) \
              -> Iterator[Tuple[Dict, Any]]:
    """Iter server objects and try to find existing objects"""
    def _iter(batch):
        ids = [obj[server_id_field] for obj in batch if obj.get(server_id_field)]
        existing = {getattr(m, id_field): m for m in model.objects.filter(provider=provider, **{id_field + '__in': ids})}
        for obj in batch:
            yield obj, existing.get(obj.get(server_id_field))

    def _chunk():
        batch = []
        for o in server_objects:
            batch.append(o)
            if len(batch) >= batch_size:
                yield from _iter(batch)
                batch = []

        if batch:
            yield from _iter(batch)

    yield from _chunk()


C = TypeVar('C', bound=Callable)


def sync_method(fn: C) -> C:
    @wraps(fn)
    def inner(api, *args, **kwargs):
        _allow_cached_values = api.allow_cached_values
        _is_syncing = api.is_syncing
        api.allow_cached_values = False
        api.is_syncing = True
        try:
            return fn(api, *args, **kwargs)
        finally:
            api.allow_cached_values = _allow_cached_values
            api.is_syncing = _is_syncing
    return inner
