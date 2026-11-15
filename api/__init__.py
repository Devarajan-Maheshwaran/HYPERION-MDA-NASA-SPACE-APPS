"""HYPERION-MDA workstation API: a composition layer ABOVE the existing lanes.

Nothing in `src/hyperion_mda/` imports this package. This package imports the lanes
read-only and composes them; it never modifies them. See docs/API-CONTRACT.md and
docs/FRONTEND-DESIGN.md.

Not a medical device. Demo thresholds, not clinically validated.
"""

__version__ = "0.2.0"
