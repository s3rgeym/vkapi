def parse_hash(s):
    import urllib.parse
    return dict(urllib.parse.parse_qsl(s))
