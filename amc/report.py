"""Text output: renewal quotations and contract status register."""
from datetime import date
from decimal import Decimal

from .processor import Engine, Result


def money(v: Decimal) -> str:
    return f"{v:,.2f}"


def rs(v: Decimal) -> str:
    return f"Rs {v:,.0f}"


def render_quotations(engine: Engine, res: Result) -> str:
    out = ["=" * 78, "RENEWAL QUOTATIONS", "=" * 78]
    for q in res.quotations:
        eq = engine.equipment[q.equipment_id]
        out += [
            f"Contract {q.contract_id} | Customer {q.customer_id} | {eq.name or eq.equipment_id}",
            f"  Command date        : {q.command_date}",
            f"  New term            : {q.new_start} to {q.new_end}   Coverage: {q.coverage}",
            f"  Base value          : {money(q.base)}" + ("  (incl. 25% age surcharge)" if q.age_surcharge else ""),
            f"  Escalated value     : {money(q.escalated)}",
            f"  Early renewal disc. : {q.early_pct * 100:.0f}%",
            f"  Multi-equipment disc: {q.multi_pct * 100:.0f}%",
            f"  Value after disc.   : {money(q.discounted)}",
        ]
        if q.lapse_months:
            out += [f"  Lapse charge        : {money(q.lapse_charge)}  ({q.lapse_months} month(s) x 2%, capped 20%)",
                    f"  Inspection fee      : {money(q.inspection_fee)}"]
        out += [f"  Amount before GST   : {money(q.pre_gst)}",
                f"  GST 18%             : {money(q.gst)}",
                f"  FINAL PAYABLE       : {rs(q.final)}", "-" * 78]
    if not res.quotations:
        out.append("(no renewals processed)")
    if res.upgrades:
        out += ["", "=" * 78, "UPGRADE CHARGES", "=" * 78]
        for u in res.upgrades:
            out += [f"Contract {u.contract_id} | Customer {u.customer_id} | {u.old_coverage} -> {u.new_coverage} on {u.command_date}",
                    f"  Base difference     : {money(u.new_base - u.old_base)} x {u.remaining_days}/{u.term_days} days",
                    f"  Amount before GST   : {money(u.pre_gst)}",
                    f"  FINAL PAYABLE       : {rs(u.final)}", "-" * 78]
    if res.rejections:
        out += ["", "=" * 78, "REJECTED COMMANDS", "=" * 78]
        out += [f"  #{r.command.seq + 1:<3} {r.command.type:<9} {r.command.contract_id:<8} {r.command.date}  {r.reason}"
                for r in res.rejections]
    return "\n".join(out)


def render_register(engine: Engine, as_of: date) -> str:
    head = f"{'Contract':<10}{'Customer':<10}{'Equipment':<12}{'Coverage':<15}{'Start':<12}{'End':<12}{'Last value':>12}  Status"
    out = ["=" * len(head), f"CONTRACT STATUS REGISTER (as of {as_of})", "=" * len(head), head, "-" * len(head)]
    for c in sorted(engine.contracts.values(), key=lambda x: x.contract_id):
        out.append(f"{c.contract_id:<10}{engine.customer_of(c):<10}{c.equipment_id:<12}{c.coverage:<15}"
                   f"{str(c.start):<12}{str(c.end):<12}{c.last_annual_value:>12,.0f}  {engine.status(c, as_of)}")
    return "\n".join(out)


def render_reminders(engine: Engine, as_of: date) -> str:
    """Stretch goal: ACTIVE contracts ending within 60 days (30-day list is a subset)."""
    out = ["=" * 60, f"RENEWAL REMINDERS (as of {as_of})", "=" * 60]
    found = False
    for c in sorted(engine.contracts.values(), key=lambda x: x.end):
        days = (c.end - as_of).days
        if 0 <= days <= 60 and engine.status(c, as_of).startswith("ACTIVE"):
            tag = "30-day reminder" if days <= 30 else "60-day reminder"
            out.append(f"  {c.contract_id:<8} ends {c.end} ({days:>2} days)  {tag}")
            found = True
    if not found:
        out.append("  (none due)")
    return "\n".join(out)
