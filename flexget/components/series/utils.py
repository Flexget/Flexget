TRANSLATE_MAP = {ord("&"): " and "}
for char in "'\\":
    TRANSLATE_MAP[ord(char)] = ""
for char in "_./-,[]():":
    TRANSLATE_MAP[ord(char)] = " "


def normalize_series_name(name):
    """Return a normalized version of the series name."""
    name = name.lower()
    name = name.replace("&amp;", " and ")
    name = name.translate(TRANSLATE_MAP)  # Replaced some symbols with spaces
    return " ".join(name.split())
