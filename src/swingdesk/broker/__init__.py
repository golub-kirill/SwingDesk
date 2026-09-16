"""Reading a paper brokerage account, placing orders on it, and raising this system's own stops.

`ADR-0005` places this package and names the venue; `DR-026` records the owner's 2026-08-31 ruling
on the order-placing boundary, `DR-027` what may be submitted, `DR-037` the protection placed
against a held position, and `DR-043` the one amendment: raising the trigger of a stop this system
placed, on an approved move. Nothing here cancels.

**Every write verb comes from the committed policy**, each named for its one job, and gate 39 reads
this package's syntax tree for any verb literal and for a third path to the transport.
"""

from swingdesk.broker.alpaca import (
    AlpacaClient,
    BrokerUnavailable,
    CredentialsMissing,
    SubmissionStopped,
    open_client,
)
from swingdesk.broker.armed import STOPPED, Arming
from swingdesk.broker.armed import read as read_arming
from swingdesk.broker.policy import BrokerPolicy, PolicyRefused, WritePolicy
from swingdesk.broker.policy import load as load_policy
from swingdesk.broker.reconcile import (
    MISMATCH_CODE,
    Agreement,
    Divergence,
    Reconciliation,
    Unprotected,
    ours,
    own_stop,
    reconcile,
    resting_stops,
    restorable,
    uncommitted_exposure,
    unprotected,
    unrecorded_fills,
    withdrawn_stops,
)
from swingdesk.broker.submit import (
    client_order_id,
    entry_order,
    protective_order,
    protective_order_id,
    target_price,
    trading_session,
)

__all__ = [
    "MISMATCH_CODE",
    "STOPPED",
    "Agreement",
    "AlpacaClient",
    "Arming",
    "BrokerPolicy",
    "BrokerUnavailable",
    "CredentialsMissing",
    "Divergence",
    "PolicyRefused",
    "Reconciliation",
    "SubmissionStopped",
    "Unprotected",
    "WritePolicy",
    "client_order_id",
    "entry_order",
    "load_policy",
    "open_client",
    "ours",
    "own_stop",
    "protective_order",
    "protective_order_id",
    "read_arming",
    "reconcile",
    "resting_stops",
    "restorable",
    "target_price",
    "trading_session",
    "uncommitted_exposure",
    "unprotected",
    "unrecorded_fills",
    "withdrawn_stops",
]
