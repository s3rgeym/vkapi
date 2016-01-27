class AttrDict(dict):
    """Словарь ключи которого одновременно являются его аттрибутами"""
    def __getattr__(self, attr):
        try:
            return self[attr]
        except KeyError:
            msg = "{!r} object has no attribute {!r}".format(
                self.__class__.__name__, attr)
            raise AttributeError(msg)

    def __setattr__(self, attr, value):
        self[attr] = value

    def __delattr__(self, attr):
        try:
            del self[attr]
        except KeyError:
            raise AttributeError(attr)
