from pipeline.config import CORRIDOR_IMPACT_MAP, _CORRIDOR_NO_MATCH

def apply_corridor_impact(text):
    """
    Scan *text* (title or article body) against CORRIDOR_IMPACT_MAP and return
    the impact dict for the FIRST matching entry, following the same scan
    pattern as _get_impact() applied to IMPACT_MAP.

    Returns a dict: {"buffer_layer": str, "corridor": str, "severity": int}
    Returns _CORRIDOR_NO_MATCH (all-none) if nothing matches.
    """
    t = str(text).lower()
    for keywords, impact in CORRIDOR_IMPACT_MAP:
        if any(kw in t for kw in keywords):
            return impact
    return _CORRIDOR_NO_MATCH
