"""Command processing: validation, state changes and pricing (BR-01 .. BR-11)."""
from collections import Counter
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from typing import Dict, List

from . import pricing
from .dates import inclusive_days, term_end_for
from .models import (Command, Contract, Coverage, Customer, Equipment, Quotation,
                     Rejection, UpgradeCharge)


@dataclass
class Result:
    quotations: List[Quotation] = field(default_factory=list)
    upgrades: List[UpgradeCharge] = field(default_factory=list)
    rejections: List[Rejection] = field(default_factory=list)
    events: List[str] = field(default_factory=list)


class Engine:
    def __init__(self, customers: Dict[str, Customer], equipment: Dict[str, Equipment],
                 coverage: Dict[str, Coverage], contracts: Dict[str, Contract]):
        self.customers, self.equipment = customers, equipment
        self.coverage, self.contracts = coverage, contracts

    # ---- helpers ----
    def customer_of(self, contract: Contract) -> str:
        return self.equipment[contract.equipment_id].customer_id

    def base_for(self, contract: Contract, level: str, term_start) -> Decimal:
        eq, cov = self.equipment[contract.equipment_id], self.coverage[level]
        return pricing.base_with_age(eq.list_price, cov.percent, eq.install_date, term_start, level)

    def status(self, contract: Contract, as_of) -> str:
        """BR-11: derived status at a given date."""
        if contract.status == "LAPSED" or as_of > contract.end:
            return "LAPSED"
        return "ACTIVE (DOWNGRADE PENDING)" if contract.pending_coverage else "ACTIVE"

    # ---- main entry ----
    def process(self, commands: List[Command]) -> Result:
        res = Result()
        for cmd in sorted(commands, key=lambda c: (c.date, c.seq)):   # VR-07
            contract = self.contracts.get(cmd.contract_id)
            if contract is None:
                res.rejections.append(Rejection(cmd, "unknown contract"))
                continue
            handler = {"RENEW": self._renew, "UPGRADE": self._upgrade,
                       "DOWNGRADE": self._downgrade, "LAPSE": self._lapse}.get(cmd.type)
            if handler is None:
                res.rejections.append(Rejection(cmd, f"unknown command type {cmd.type}"))
                continue
            handler(cmd, contract, res)
        self._apply_multi_equipment(res.quotations)                  # BR-09, second pass
        return res

    # ---- handlers ----
    def _renew(self, cmd, c: Contract, res: Result):
        if cmd.date < c.start:
            res.rejections.append(Rejection(cmd, "RENEW dated before current term start (already renewed or invalid)"))
            return
        level = c.pending_coverage or c.coverage                      # BR-08 applied here
        lapsed = cmd.date > c.end
        if lapsed:
            new_start, months = cmd.date, pricing.lapse_months(c.end, cmd.date)
            early = Decimal(0)
        else:
            new_start, months = c.end + timedelta(days=1), 0
            early = pricing.early_pct((c.end - cmd.date).days)
        new_end = term_end_for(new_start)
        eq = self.equipment[c.equipment_id]
        base = self.base_for(c, level, new_start)
        escalated = pricing.escalate(c.last_annual_value, base)
        q = Quotation(
            seq=cmd.seq, contract_id=c.contract_id, customer_id=eq.customer_id, equipment_id=eq.equipment_id,
            command_date=cmd.date, coverage=level, new_start=new_start, new_end=new_end, base=base,
            age_surcharge=pricing.age_surcharge_applies(eq.install_date, new_start, level),
            escalated=escalated, early_pct=early, lapse_months=months,
            lapse_pct=pricing.lapse_charge_pct(months) if lapsed else Decimal(0),
            inspection_fee=pricing.inspection_fee(months) if lapsed else Decimal(0))
        res.quotations.append(q)
        c.coverage, c.start, c.end = level, new_start, new_end
        c.last_annual_value, c.pending_coverage, c.status = escalated, None, "ACTIVE"   # D-1

    def _upgrade(self, cmd, c: Contract, res: Result):
        if self.status(c, cmd.date).startswith("LAPSED"):
            res.rejections.append(Rejection(cmd, "contract is LAPSED; renew first"))
            return
        if not (c.start <= cmd.date <= c.end):
            res.rejections.append(Rejection(cmd, "UPGRADE dated outside the current term"))
            return
        target = self.coverage.get((cmd.new_coverage or "").upper())
        if target is None:
            res.rejections.append(Rejection(cmd, f"unknown coverage level {cmd.new_coverage}"))
            return
        if target.rank <= self.coverage[c.coverage].rank:
            res.rejections.append(Rejection(cmd, "UPGRADE target is not a higher level"))
            return
        up = UpgradeCharge(
            seq=cmd.seq, contract_id=c.contract_id, customer_id=self.customer_of(c), command_date=cmd.date,
            old_coverage=c.coverage, new_coverage=target.level,
            old_base=self.base_for(c, c.coverage, c.start), new_base=self.base_for(c, target.level, c.start),
            remaining_days=inclusive_days(cmd.date, c.end), term_days=inclusive_days(c.start, c.end))
        res.upgrades.append(up)
        c.coverage, c.pending_coverage = target.level, None

    def _downgrade(self, cmd, c: Contract, res: Result):
        if self.status(c, cmd.date).startswith("LAPSED"):
            res.rejections.append(Rejection(cmd, "contract is LAPSED; renew first"))
            return
        if not (c.start <= cmd.date <= c.end):
            res.rejections.append(Rejection(cmd, "DOWNGRADE dated outside the current term"))
            return
        target = self.coverage.get((cmd.new_coverage or "").upper())
        if target is None:
            res.rejections.append(Rejection(cmd, f"unknown coverage level {cmd.new_coverage}"))
            return
        if target.rank >= self.coverage[c.coverage].rank:
            res.rejections.append(Rejection(cmd, "DOWNGRADE target is not a lower level"))
            return
        c.pending_coverage = target.level                             # BR-08: effective at next renewal
        res.events.append(f"{cmd.date} {c.contract_id}: DOWNGRADE to {target.level} scheduled for next renewal")

    def _lapse(self, cmd, c: Contract, res: Result):
        if c.status == "LAPSED":
            res.rejections.append(Rejection(cmd, "contract already LAPSED"))
            return
        if cmd.date < c.start:
            res.rejections.append(Rejection(cmd, "LAPSE dated before current term start"))
            return
        c.status = "LAPSED"
        res.events.append(f"{cmd.date} {c.contract_id}: marked LAPSED")

    # ---- BR-09 ----
    def _apply_multi_equipment(self, quotes: List[Quotation]):
        counts = Counter((q.customer_id, q.command_date.year, q.command_date.month) for q in quotes)
        for q in quotes:
            if counts[(q.customer_id, q.command_date.year, q.command_date.month)] >= pricing.MULTI_MIN_RENEWALS:
                q.multi_pct = pricing.MULTI_DISCOUNT
