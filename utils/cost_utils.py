"""Cost utilities (spec §5): currency formatting, per-person math, budget normalization."""
from __future__ import annotations


def inr(amount: float | None) -> str:
    """₹ formatting with Indian digit grouping: 1234567 → ₹12,34,567."""
    if amount is None:
        return "—"
    a = round(float(amount))
    neg = a < 0
    s = str(abs(a))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join(groups + [tail])
    return ("-" if neg else "") + f"₹{s}"


def per_person(total: float | None, passengers: int) -> float | None:
    if total is None:
        return None
    return round(total / max(1, passengers), 2)


def normalize_budget(budget: float | None, budget_type: str, passengers: int) -> float | None:
    """Convert a per-person budget into the total budget for the party."""
    if budget is None:
        return None
    if budget_type == "per_person":
        return budget * max(1, passengers)
    return budget


def parse_rupee_amount(text: str) -> float | None:
    """'₹6000', 'rs 5,500', 'budget 6k', 'budget is 3000' → float."""
    import re
    t = (text or "").lower().replace(",", "")
    m = re.search(r"(?:₹|rs\.?|rupees?\s*)\s*(\d+(?:\.\d+)?)\s*(k)?", t)
    if not m:
        m = re.search(r"(\d+(?:\.\d+)?)\s*(k)?\s*(?:₹|rs|rupees|budget)", t)
    if not m:
        # 'budget (is|of|around)? 3000' — amount AFTER the word budget
        m = re.search(r"budget(?:\s+is|\s+of|\s+around)?\s*(\d+(?:\.\d+)?)\s*(k)?", t)
    if not m:
        return None
    val = float(m.group(1))
    if m.group(2):
        val *= 1000
    return val
