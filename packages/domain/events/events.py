"""
Immutable payment event — foundation for event sourcing.

All state in RAPID is derived by replaying events in chronological order.
Events are never mutated or deleted.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class PaymentEvent:
    """
    Immutable event record.

    Source of truth for payment state. The full timeline of events
    for a payment can be replayed to reconstruct state at any point.

    Attributes:
        event_id:   Unique identifier (from DB row ID or Razorpay event ID).
        payment_id: The payment this event belongs to.
        event_type: What happened (e.g., webhook_received, state_changed).
        timestamp:  When the event occurred (not when it was received).
        data:       Event-specific payload.
    """

    event_id: str
    payment_id: str
    event_type: str
    timestamp: datetime
    data: dict[str, Any]

    def __lt__(self, other: "PaymentEvent") -> bool:
        """Events are ordered by timestamp for chronological replay."""
        return self.timestamp < other.timestamp

    def __str__(self) -> str:
        return (
            f"PaymentEvent("
            f"id={self.event_id}, "
            f"payment={self.payment_id}, "
            f"type={self.event_type}, "
            f"ts={self.timestamp.isoformat()}"
            f")"
        )
