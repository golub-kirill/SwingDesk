"""Cross-cutting infrastructure: config, clock injection, storage, scheduling, run manifests.

Nothing here makes a decision. It is the bottom of the layer chain, so everything may import it and
it may import nothing.
"""

from swingdesk.platform.clock import Clock, FixedClock, SystemClock
from swingdesk.platform.parameters import (
    ParameterRegistry,
    ParameterUnset,
    UnknownParameter,
)

__all__ = [
    "Clock",
    "FixedClock",
    "ParameterRegistry",
    "ParameterUnset",
    "SystemClock",
    "UnknownParameter",
]
