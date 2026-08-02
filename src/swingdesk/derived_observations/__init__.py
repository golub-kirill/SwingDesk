"""Deterministic calculations and classifiers over source facts.

Pure functions. No I/O, no clock, no journal - this is the purity boundary (ARCHITECTURE 3), and
CI greps this package for wall-clock calls.
"""

from swingdesk.derived_observations import atr

__all__ = ["atr"]
