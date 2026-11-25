from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from . import pricing

D = Decimal


@dataclass(frozen=True)
class Customer:
    customer_id: str
    name: str


@dataclass(frozen=True)
class Equipment:
    equipment_id: str
    customer_id: str
    name: str
    list_price: Decimal
    install_date: date


@dataclass(frozen=True)
class Coverage:
    level: str
    percent: Decimal
    rank: int


@dataclass
class Contract:
    contract_id: str
    equipment_id: str
    coverage: str
    start: date
    end: date
    last_annual_value: Decimal
    status: str = "ACTIVE"          # ACTIVE or LAPSED (explicit LAPSE command)
    pending_coverage: Optional[str] = None


@dataclass(frozen=True)
class Command:
    seq: int
    type: str
    contract_id: str
    date: date
    new_coverage: Optional[str] = None


@dataclass
class Quotation:
    """One renewal. multi_pct is filled in by the second pass (BR-09)."""
    seq: int
    contract_id: str
    customer_id: str
    equipment_id: str
    command_date: date
    coverage: str
    new_start: date
    new_end: date
    base: Decimal
    age_surcharge: bool
    escalated: Decimal
    early_pct: Decimal
    lapse_months: int
    lapse_pct: Decimal
    inspection_fee: Decimal
    multi_pct: Decimal = D(0)

    @property
    def discounted(self) -> Decimal:
        return self.escalated * (1 - self.early_pct) * (1 - self.multi_pct)

    @property
    def lapse_charge(self) -> Decimal:
        return self.escalated * self.lapse_pct

    @property
    def pre_gst(self) -> Decimal:
        return self.discounted + self.lapse_charge + self.inspection_fee

    @property
    def gst(self) -> Decimal:
        return self.pre_gst * pricing.GST

    @property
    def final(self) -> Decimal:
        return pricing.gst_round(self.pre_gst)


@dataclass
class UpgradeCharge:
    seq: int
    contract_id: str
    customer_id: str
    command_date: date
    old_coverage: str
    new_coverage: str
    old_base: Decimal
    new_base: Decimal
    remaining_days: int
    term_days: int

    @property
    def pre_gst(self) -> Decimal:
        return pricing.upgrade_pre_gst(self.old_base, self.new_base, self.remaining_days, self.term_days)

    @property
    def final(self) -> Decimal:
        return pricing.gst_round(self.pre_gst)


@dataclass(frozen=True)
class Rejection:
    command: Command
    reason: str
