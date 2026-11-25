"""Pure pricing functions, one per business rule. No state, no I/O."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from .dates import add_months, add_years

D = Decimal
AGE_LIMIT_YEARS = 8
AGE_SURCHARGE = D("0.25")
SURCHARGE_LEVELS = frozenset({"COMPREHENSIVE", "PREMIUM"})
ESCALATION = D("1.05")
EARLY_30, EARLY_60 = D("0.05"), D("0.08")
LAPSE_RATE_PER_MONTH, LAPSE_CAP = D("0.02"), D("0.20")
INSPECTION_FEE, INSPECTION_AFTER_MONTHS = D("2000"), 6
MULTI_MIN_RENEWALS, MULTI_DISCOUNT = 5, D("0.03")
GST = D("0.18")


def base_value(list_price: Decimal, percent: Decimal) -> Decimal:
    """BR-01: yearly base = list price x coverage percent."""
    return list_price * percent / D(100)


def age_surcharge_applies(install_date: date, term_start: date, level: str) -> bool:
    """BR-02: strictly older than 8 years at the new term start, COMPREHENSIVE/PREMIUM only."""
    return level.upper() in SURCHARGE_LEVELS and add_years(install_date, AGE_LIMIT_YEARS) < term_start


def base_with_age(list_price, percent, install_date, term_start, level) -> Decimal:
    base = base_value(list_price, percent)
    if age_surcharge_applies(install_date, term_start, level):
        base *= (1 + AGE_SURCHARGE)
    return base


def escalate(previous_value: Decimal, current_base: Decimal) -> Decimal:
    """BR-03: escalation floor = higher of previous x 1.05 and current base."""
    return max(previous_value * ESCALATION, current_base)


def early_pct(days_before_end: int) -> Decimal:
    """BR-04: inclusive thresholds; 60+ -> 8%, 30+ -> 5%, never both."""
    if days_before_end >= 60:
        return EARLY_60
    if days_before_end >= 30:
        return EARLY_30
    return D(0)


def lapse_months(end: date, renewal_date: date) -> int:
    """BR-05: smallest m with end + m calendar months >= renewal date (part month = full)."""
    m = 1
    while add_months(end, m) < renewal_date:
        m += 1
    return m


def lapse_charge_pct(months: int) -> Decimal:
    """BR-05: 2% per lapsed month, capped at 20%."""
    return min(LAPSE_RATE_PER_MONTH * months, LAPSE_CAP)


def inspection_fee(months: int) -> Decimal:
    """BR-06: Rs 2,000 only when the lapse is MORE than 6 months."""
    return INSPECTION_FEE if months > INSPECTION_AFTER_MONTHS else D(0)


def upgrade_pre_gst(old_base: Decimal, new_base: Decimal, remaining_days: int, term_days: int) -> Decimal:
    """BR-07: base difference pro-rated by remaining days of the term."""
    return (new_base - old_base) * D(remaining_days) / D(term_days)


def gst_round(pre_gst: Decimal) -> Decimal:
    """BR-10: GST 18%, rounded half-up to whole rupees, once, at the very end."""
    return (pre_gst * (1 + GST)).quantize(D(1), rounding=ROUND_HALF_UP)
