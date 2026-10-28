"""Cost, effort, lock-in and timeline model."""
import calendar
from dataclasses import dataclass, field
from datetime import date

from .pricing import DATA_ACT_FULL_DATE, FREE_GB, PROVIDER_NAMES, WAIVER, list_price

DAYS_BY_LOCKIN = {1: 0.5, 2: 2.0, 3: 5.0}
EFFORT_SPREAD = (0.6, 1.6)
NOTICE_MONTHS = 2
TRANSITION_DAYS = 30
RETRIEVAL_DAYS = 30


def add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, m + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


@dataclass
class ProviderEgress:
    provider: str
    gb: float
    list_cost: float
    per_tb_list: float
    waiver: str


@dataclass
class Timeline:
    notice: date
    latest_start: date
    transition_end: date
    retrieval_end: date
    full_ban: date
    start_after_ban: bool
    earliest_notice_for_ban: date


@dataclass
class Plan:
    services: list = field(default_factory=list)
    egress: list = field(default_factory=list)
    sized: bool = False
    effort_days: tuple = (0.0, 0.0)
    effort_cost: tuple = (0.0, 0.0)
    parallel_cost: float = 0.0
    commitment: float = 0.0
    lockin_score: int = 0
    lockin_label: str = ""
    timeline: Timeline | None = None
    day_rate: float = 0.0


def parse_date(text: str) -> date:
    return date.fromisoformat(text)


def build_timeline(notice: date) -> Timeline:
    latest_start = add_months(notice, NOTICE_MONTHS)
    full = parse_date(DATA_ACT_FULL_DATE)
    transition_end = date.fromordinal(latest_start.toordinal() + TRANSITION_DAYS)
    retrieval_end = date.fromordinal(transition_end.toordinal() + RETRIEVAL_DAYS)
    return Timeline(notice, latest_start, transition_end, retrieval_end, full,
                    latest_start >= full, add_months(full, -NOTICE_MONTHS))


def assign_sizes(findings, sizes):
    """Return {service_key: GB}. A service key wins over its category; a category is split evenly."""
    out = {}
    for key, f in findings.items():
        if key in sizes:
            out[key] = sizes[key]
    for category, gb in sizes.items():
        members = [k for k, f in findings.items() if f.service.data == category and k not in sizes]
        for k in members:
            out[k] = gb / len(members)
    return out


def lockin_label(score: int) -> str:
    return "low" if score < 35 else "medium" if score < 65 else "high"


def make_plan(result, sizes=None, monthly_bill=0.0, parallel_months=1.0,
              commitment=0.0, day_rate=400.0, notice: date | None = None) -> Plan:
    sizes = sizes or {}
    plan = Plan(day_rate=day_rate, commitment=commitment)
    plan.services = sorted(result.findings.values(), key=lambda f: (-f.service.lockin, f.service_key))
    by_service = assign_sizes(result.findings, sizes)
    plan.sized = bool(by_service)

    per_provider = {}
    for key, gb in by_service.items():
        prov = result.findings[key].service.provider
        per_provider[prov] = per_provider.get(prov, 0.0) + gb
    for prov in sorted(result.providers):
        gb = per_provider.get(prov, 0.0)
        plan.egress.append(ProviderEgress(prov, gb, list_price(prov, gb), list_price(prov, 1024 + FREE_GB[prov]), WAIVER[prov]))

    base = 0.0
    for f in plan.services:
        base += DAYS_BY_LOCKIN[f.service.lockin] * (1 + 0.25 * (max(f.resources, 1) - 1))
    plan.effort_days = (round(base * EFFORT_SPREAD[0], 1), round(base * EFFORT_SPREAD[1], 1))
    plan.effort_cost = (round(plan.effort_days[0] * day_rate), round(plan.effort_days[1] * day_rate))
    plan.parallel_cost = round(monthly_bill * parallel_months, 2)

    if plan.services:
        plan.lockin_score = round(100 * sum((f.service.lockin - 1) / 2 for f in plan.services) / len(plan.services))
    plan.lockin_label = lockin_label(plan.lockin_score)
    plan.timeline = build_timeline(notice) if notice else None
    return plan


def provider_name(p):
    return PROVIDER_NAMES[p]
