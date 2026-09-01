"""Reading a brokerage account. Never writing to one.

`ADR-0005` places this package and names the venue; `DR-026` records the owner's 2026-08-31 ruling
on the order-placing boundary and what remains closed. The package exists so that the fill record
this system reasons over is the venue's own rather than one the owner retyped.

**Nothing here executes**, and gate 39 makes that structural rather than a promise: the committed
policy lists `GET` as the only permitted method, and the gate reads this package's syntax tree for
any HTTP write verb.
"""

from swingdesk.broker.alpaca import (
    AlpacaClient,
    BrokerUnavailable,
    CredentialsMissing,
    open_client,
)
from swingdesk.broker.policy import BrokerPolicy, PolicyRefused
from swingdesk.broker.policy import load as load_policy
from swingdesk.broker.reconcile import (
    MISMATCH_CODE,
    Agreement,
    Divergence,
    Reconciliation,
    reconcile,
    unrecorded_fills,
)

__all__ = [
    "MISMATCH_CODE",
    "Agreement",
    "AlpacaClient",
    "BrokerPolicy",
    "BrokerUnavailable",
    "CredentialsMissing",
    "Divergence",
    "PolicyRefused",
    "Reconciliation",
    "load_policy",
    "open_client",
    "reconcile",
    "unrecorded_fills",
]
