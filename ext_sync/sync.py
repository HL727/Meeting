from django.utils.timezone import now
import logging
import json

logger = logging.getLogger(__name__)


class Syncer:

    def __init__(self, valid, existing, options=None):

        self.valid = valid
        self.existing = existing
        self.options = options or {}

    def get_comp(self, obj):
        raise NotImplementedError()

    def add(self, obj):
        raise NotImplementedError()

    def remove(self, obj):
        raise NotImplementedError()

    def get_removed(self, valid, existing):
        'get removed items, and extend data from last sync for existing items'

        remove = []

        # delete removed
        for e in existing:

            comp = self.get_comp(e)

            match = [r for r in valid if self.get_comp(r) == comp]

            if not match:
                remove.append(e)
            else:
                match[0].update(e)
                for m in match[1:]:
                    m['removed'] = True
                    remove.append(m)

        return remove

    def sync(self):

        valid = self.valid
        existing = self.existing

        remove = self.get_removed(valid, existing)

        removed = set()

        for r in remove:
            if r['id'] in removed or not r['id']:
                continue

            if r['id'] in (v['id'] for v in valid if not v.get('removed')):  # duplicate id, still valid
                continue

            try:
                if not self.remove(r) and r.get('error_count') < 3:
                    valid.append(r)
            except Exception as e:
                r['error'] = str(e)
                valid.append(r)
            removed.add(r['id'])

        result = []
        # add missing
        for r in valid:
            if r.get('removed') or r['id'] in removed:
                continue

            if not r['id']:
                try:
                    data = self.add(r)
                except Exception as e:
                    r['error'] = str(e)
                else:
                    r['id'] = data['id']
                    r['created'] = str(now())
                    r.pop('error', None)
                    r.pop('error_count', None)
            result.append(r)

        return result


class SeeviaSyncer(Syncer):

    def get_comp(self, obj):

        return (obj['name'], obj['uri'])

    def add(self, obj):

        opt = self.options
        api, base_dir = opt['api'], opt['base_dir']

        logger.debug('Add seevia object {}'.format(json.dumps(obj)))
        data = api.create_entry(base_dir, name=obj['name'], uri=obj['uri'])
        return data

    def remove(self, obj):
        try:
            self.options['api'].delete_entry(obj['id'])
        except Exception as e:
            obj['error'] = str(e)
            obj['error_count'] = obj.get('error_count', 0) + 1
            logger.info('Remove seevia object failed {}'.format(json.dumps(obj)))

            return False
        else:
            logger.debug('Added seevia object failed {}'.format(json.dumps(obj)))


class LdapSyncer(Syncer):

    def get_comp(self, obj):

        return (obj['name'], obj['uri'])

    def add(self, obj):

        opt = self.options
        api, ou = opt['api'], opt['ou']

        cn = obj['uri'].replace('@', '_').replace('.', '_')

        api.add_user(ou, cn, obj['name'], email=obj['uri'])
        logger.debug('Added ldap object {}'.format(json.dumps(obj)))

        return {'id': cn}

    def remove(self, obj):

        opt = self.options
        api, ou = opt['api'], opt['ou']

        try:
            api.delete_user(ou, obj['id'])
        except Exception as e:
            obj['error'] = str(e)
            obj['error_count'] = obj.get('error_count', 0) + 1
            logger.debug('Remove ldap object failed {}'.format(json.dumps(obj)))

            return False
        else:
            logger.debug('Removed ldap object {}'.format(json.dumps(obj)))

