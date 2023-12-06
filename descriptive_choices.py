
class DescriptiveChoices:

    def __init__(self, items):
        self.items = items

        # key => id
        self.id_map = {x[1]: x[0] for x in items}

        # key / id => id
        self.item_map = {x[0]: x[0] for x in items}  # id map
        self.item_map.update((x[1], x[0]) for x in items)  # name map. overwrite

        # id => key
        self.key_map = {x[0]: x[1] for x in items}  # id map

        # key / id => title
        self.title_map = {x[0]: x[2] for x in items}  # id map
        self.title_map.update((x[1], x[2]) for x in items)  # name map. overwrite

        # key / id => info
        info_map = {}
        for x in items:
            if len(x) > 3:
                info_map[x[0]] = x[3]
                info_map[x[1]] = x[3]

        self.info_map = info_map

    def __getattr__(self, key):
        try:
            return self.item_map[key]
        except KeyError:
            raise AttributeError()

    def __getitem__(self, key):
        return self.item_map.get(key)

    def get_title(self, key):
        return str(self.title_map.get(key))

    def get_info(self, key):
        return str(self.info_map[key])

    def get_key(self, value):
        return str(self.key_map[value])

    def title_for(self, attr_name):
        @property
        def inner(obj_self):
            return self.get_title(getattr(obj_self, attr_name))
        return inner

    def info_for(self, attr_name):
        @property
        def inner(obj_self):
            return self.get_info(getattr(obj_self, attr_name))
        return inner

    def key_for(self, attr_name):
        @property
        def inner(obj_self):
            return self.get_key(getattr(obj_self, attr_name))
        return inner

    def __iter__(self):
        return iter((x[0], x[2]) for x in self.items)
