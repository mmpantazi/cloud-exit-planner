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
    "aws": "AWS: waives transfer-out fees for customers who leave. Account in good standing, move finished within 60 days, remaining data and workloads deleted; large moves need a support request for credits.",
    "azure": "Azure: waives internet egress for Azure Storage data when you leave. Tell Microsoft in advance, get approval, cancel all Azure subscriptions; you pay first and request a credit afterwards. Sources disagree on the 60-day window.",
    "gcp": "Google Cloud: waives exit transfer fees. File a formal exit request, finish within 60 days and terminate the agreement; the fee is credited on the final invoice and Google may audit the data movement. Partial exits: ask support.",
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


def apply_overrides(data: dict) -> None:
    """Replace prices from a user file: {"aws": {"free_gb": 100, "tiers": [[10240, 0.09], [null, 0.05]]}}."""
    for provider, spec in data.items():
        if provider not in TIERS:
            raise ValueError(f"unknown provider '{provider}' (use {', '.join(TIERS)})")
        tiers = spec.get("tiers")
        if tiers is not None:
            if not tiers or tiers[-1][0] is not None or any(t[0] is None for t in tiers[:-1]):
                raise ValueError(f"{provider}: tiers must end with one open-ended tier [null, price]")
            bounds = [t[0] for t in tiers[:-1]]
            if bounds != sorted(bounds):
                raise ValueError(f"{provider}: tier limits must be increasing")
            TIERS[provider] = [(None if up is None else float(up), float(rate)) for up, rate in tiers]
        if "free_gb" in spec:
            FREE_GB[provider] = float(spec["free_gb"])
