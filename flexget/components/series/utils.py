from __future__ import unicode_literals


TRANSLATE_MAP = {ord(u'&'): u' and '}
for char in u'\'\\':
    TRANSLATE_MAP[ord(char)] = u''
for char in u'_./-,[]():':
    TRANSLATE_MAP[ord(char)] = u' '


def normalize_series_name(name):
    """Returns a normalized version of the series name."""
    name = name.lower()
    name = name.replace('&amp;', ' and ')
    name = name.translate(TRANSLATE_MAP)  # Replaced some symbols with spaces
    name = u' '.join(name.split())
    return name
