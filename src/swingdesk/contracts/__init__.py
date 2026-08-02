"""Records that cross a bounded-context boundary.

One canonical definition each (docs/contracts/README.md). Every record is frozen: records are
values, and immutability at the boundary supports the append-only rules in the journal and the
point-in-time store.

Money is Decimal, never float (DETERMINISM_SPEC 3.3). Fact-bearing records carry knowledge_time
(POINT_IN_TIME_SPEC 2).
"""

from swingdesk.contracts.market import Bar, BarSeries, Interval, Series
from swingdesk.contracts.observation import Observation, ObservationSeries
from swingdesk.contracts.reference import Exchange, ExchangeSession, Instrument
from swingdesk.contracts.run import RunManifest

__all__ = [
    "Bar",
    "BarSeries",
    "Exchange",
    "ExchangeSession",
    "Instrument",
    "Interval",
    "Observation",
    "ObservationSeries",
    "RunManifest",
    "Series",
]
