"""Command-file driven AMC engine.
Usage:  python main.py --data data [--as-of YYYY-MM-DD] [--out output.txt] [--reminders]"""
import argparse
import sys

from amc.loader import load_all, parse_date
from amc.processor import Engine
from amc.report import render_quotations, render_register, render_reminders


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="AMC Renewal and Escalation Engine")
    ap.add_argument("--data", default="data", help="folder with customers/equipment/coverage/contracts/commands CSVs")
    ap.add_argument("--as-of", help="date for the status register (default: last command date)")
    ap.add_argument("--out", help="also write the report to this file")
    ap.add_argument("--reminders", action="store_true", help="append the 60/30-day renewal reminder list (stretch goal)")
    args = ap.parse_args(argv)

    customers, equipment, coverage, contracts, commands, warnings = load_all(args.data)
    engine = Engine(customers, equipment, coverage, contracts)
    result = engine.process(commands)
    if args.as_of:
        as_of = parse_date(args.as_of)
    elif commands:
        as_of = max(c.date for c in commands)
    else:
        as_of = max(c.end for c in contracts.values())

    parts = []
    if warnings:
        parts.append("LOAD WARNINGS\n" + "\n".join("  " + w for w in warnings))
    parts += [render_quotations(engine, result), render_register(engine, as_of)]
    if args.reminders:
        parts.append(render_reminders(engine, as_of))
    text = "\n\n".join(parts) + "\n"
    print(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
