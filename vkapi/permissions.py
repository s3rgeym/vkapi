import re

FLAG_RE = re.compile('[A-Z]+$')


class Permissions:
    """Права приложения

    Подробнее про права приложения можно прочитать по ссылке
    <https://vk.com/dev/permissions>
    """
    NOTIFY = 1
    FRIENDS = 2
    PHOTOS = 4
    AUDIO = 8
    VIDEO = 16
    DOCS = 131072
    NOTES = 2048
    PAGES = 128
    STATUS = 1024
    OFFERS = 32
    QUESTIONS = 64
    WALL = 8192
    GROUPS = 262144
    MESSAGES = 4096
    EMAIL = 4194304
    NOTIFICATIONS = 524288
    STATS = 1048576
    ADS = 32768
    MARKET = 134217728
    OFFLINE = 65536

    @classmethod
    def all_flags(cls):
        flags = 0
        for flag in cls.to_dict().values():
            flags |= flag
        return flags

    @classmethod
    def all_str(cls):
        return cls.to_str(cls.all_flags())

    @classmethod
    def to_int(cls, s):
        """
        >>> Permissions.to_int('wall,friends,audio')
        8202
        >>> Permissions.to_str(8202)
        'audio,friends,wall'
        """
        items = s.split(',')
        flags = cls.to_dict()
        mask = 0
        for item in items:
            item = item.upper()
            if item in flags:
                mask |= flags[item]
        return mask

    @classmethod
    def to_str(cls, mask):
        """
        >>> mask = Permissions.WALL | Permissions.FRIENDS | Permissions.AUDIO
        >>> Permissions.to_str(mask)
        'audio,friends,wall'
        """
        out = []
        for name, flag in cls.to_dict().items():
            if flag & mask == flag:
                out.append(name.lower())
        return ",".join(sorted(out))

    @classmethod
    def to_dict(cls):
        return {v: getattr(cls, v) for v in dir(cls) if FLAG_RE.match(v)}
