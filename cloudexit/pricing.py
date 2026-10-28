"""Internet egress list prices (USD per GB), read from public pricing pages and price guides.

Prices change and differ per region. They are indicative only, so the report always tells
the reader to confirm them on the provider's own page.
"""
AS_OF = "2026-10"

# (upper bound of tier in GB or None for open-ended, price per GB)
TIERS = {
    "aws": [(10_240, 0.09), (51_200, 0.085), (153_600, 0.07), (None, 0.05)],
    "azure": [(10_240, 0.087), (51_200, 0.083), (153_600, 0.07), (None, 0.05)],
    "gcp": [(1_024, 0.12), (10_240, 0.11), (None, 0.08)],
}
FREE_GB = {"aws": 100, "azure": 100, "gcp": 0}

WAIVER = {
    "aws": "AWS waives transfer-out fees for customers who leave: account in good standing, move finished within 60 days, remaining data deleted; large moves need a support request for credits.",
    "azure": "Azure waives internet egress for customers who leave or move to another provider: request through support, finish within the stated window.",
    "gcp": "Google Cloud waives data transfer fees for customers who leave: request through support, finish within the stated window.",
}
PROVIDER_NAMES = {"aws": "AWS", "azure": "Microsoft Azure", "gcp": "Google Cloud"}
DATA_ACT_FULL_DATE = "2027-01-12"


def list_price(provider: str, gb: float) -> float:
    """Cost in USD of sending gb out once, tiers applied after the monthly free allowance."""
    billable = max(0.0, gb - FREE_GB.get(provider, 0))
    cost, floor = 0.0, 0.0
    for upper, rate in TIERS[provider]:
        if billable <= floor:
            break
        top = billable if upper is None else min(billable, upper)
        cost += (top - floor) * rate
        floor = upper if upper is not None else billable
    return round(cost, 2)
