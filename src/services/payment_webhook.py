"""Apply payment webhook events to caller-managed payment state."""


def process_payment_webhook(payment: dict, event: dict) -> dict:
    transitions = {
        ("pending", "payment.authorized"): "authorized",
        ("pending", "payment.failed"): "failed",
        ("authorized", "payment.captured"): "paid",
        ("authorized", "payment.cancelled"): "cancelled",
        ("paid", "payment.refunded"): "refunded",
    }
    event_id = event.get("id")
    if not isinstance(event_id, str) or not event_id.strip():
        raise ValueError("A nonempty webhook event ID is required.")
    if not payment.get("id") or event.get("payment_id") != payment["id"]:
        raise ValueError("The webhook must reference this payment.")
    processed = list(payment.get("processed_events", []))
    if event_id in processed:
        return dict(payment)
    current = payment.get("status", "pending")
    target = transitions.get((current, event.get("type")))
    if target is None:
        raise ValueError("Unsupported payment state transition.")
    if target in {"paid", "refunded"}:
        amount = event.get("amount_cents")
        if type(amount) is not int or amount <= 0:
            raise ValueError("A positive integer amount in cents is required.")
        if amount != payment.get("amount_cents"):
            raise ValueError("Only full payment captures and refunds are supported.")
        if event.get("currency") != payment.get("currency"):
            raise ValueError("The payment currency must match.")
    updated = dict(payment)
    updated["status"] = target
    updated["processed_events"] = processed + [event_id]
    updated["last_event_id"] = event_id
    updated["history"] = list(payment.get("history", [])) + [
        {"event_id": event_id, "from": current, "to": target}
    ]
    return updated
