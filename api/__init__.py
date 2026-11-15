"""HYPERION-MDA workstation API: a composition layer ABOVE the existing lanes.

Nothing in `src/hyperion_mda/` imports this package. This package imports the lanes
read-only and composes them; it never modifies them. See docs/PHASE0-API-UI.md §1.

Not a medical device. Demo thresholds, not clinically validated.
"""

__version__ = "0.2.0"
