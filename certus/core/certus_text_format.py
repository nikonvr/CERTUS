"""Short text formats with no Qt, shared by the computation modules and the interface (A8b / D26)."""


def format_count_kmg(val: object) -> str:
    """Format a counter value as a short K/M/G string.

    Used by the stats display of METAL and STRAT applications
    (``update_stats_display``). Returns plain ``str(val)`` for values
    under 1000.
    """

    try:
        v = float(val)
    except (TypeError, ValueError):
        return str(val)
    if v >= 1e9:
        return f"{v / 1e9:.1f}G"
    if v >= 1e6:
        return f"{v / 1e6:.1f}M"
    if v >= 1e3:
        return f"{v / 1e3:.1f}K"
    # Preserve integer rendering when possible
    return str(int(v)) if v == int(v) else f"{v:g}"
