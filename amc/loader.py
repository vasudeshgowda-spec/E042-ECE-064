"""CSV loaders. Header names are matched case-insensitively with common aliases."""
import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, List, Tuple

from .models import Command, Contract, Coverage, Customer, Equipment

ALIASES = {
    "customers": {"customer_id": ["customer_id", "id", "customer id", "cust_id"], "name": ["name", "customer_name"]},
    "equipment": {"equipment_id": ["equipment_id", "equip_id", "id", "equipment id"],
                  "customer_id": ["customer_id", "customer", "cust_id"],
                  "name": ["name", "equipment_name", "description"],
                  "list_price": ["list_price", "price", "list price"],
                  "install_date": ["install_date", "installation_date", "installed_on", "installed"]},
    "coverage": {"level": ["level", "coverage", "coverage_level", "name"],
                 "percent": ["percent", "pct", "percentage", "rate", "percent_of_list_price"]},
    "contracts": {"contract_id": ["contract_id", "id", "contract id"],
                  "equipment_id": ["equipment_id", "equip_id", "equipment"],
                  "coverage": ["coverage", "coverage_level", "level"],
                  "start": ["start_date", "start", "start date"], "end": ["end_date", "end", "end date"],
                  "last_annual_value": ["last_annual_value", "last_value", "annual_value", "last annual value", "value"]},
    "commands": {"type": ["command", "type", "action", "cmd"],
                 "contract_id": ["contract_id", "contract", "id"],
                 "date": ["date", "command_date", "effective_date"],
                 "new_coverage": ["new_coverage", "coverage", "level", "target_coverage", "to"]},
}


def parse_date(text: str) -> date:
    text = text.strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d-%b-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"bad date '{text}'")


def parse_money(text: str) -> Decimal:
    try:
        return Decimal(text.replace(",", "").replace("Rs", "").strip())
    except InvalidOperation:
        raise ValueError(f"bad number '{text}'")


def parse_percent(text: str) -> Decimal:
    value = parse_money(text.replace("%", ""))
    return value * 100 if value <= 1 else value


def _rows(path: Path, kind: str):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        headers = {h.strip().lower(): h for h in (reader.fieldnames or [])}
        mapping = {}
        for canon, names in ALIASES[kind].items():
            for n in names:
                if n in headers and headers[n] not in mapping.values():
                    mapping[canon] = headers[n]
                    break
        for lineno, raw in enumerate(reader, start=2):
            yield lineno, {k: (raw.get(v) or "").strip() for k, v in mapping.items()}


def load_all(folder: str) -> Tuple[dict, dict, dict, dict, List[Command], List[str]]:
    base, warnings = Path(folder), []
    customers: Dict[str, Customer] = {}
    equipment: Dict[str, Equipment] = {}
    coverage: Dict[str, Coverage] = {}
    contracts: Dict[str, Contract] = {}
    commands: List[Command] = []

    def bad(file, line, why):
        warnings.append(f"{file} line {line}: {why} - row skipped")

    for ln, r in _rows(base / "customers.csv", "customers"):
        if not r.get("customer_id"):
            bad("customers.csv", ln, "missing customer id"); continue
        customers[r["customer_id"]] = Customer(r["customer_id"], r.get("name", ""))

    levels = []
    for ln, r in _rows(base / "coverage.csv", "coverage"):
        try:
            pct = parse_percent(r["percent"])
            if not (0 < pct <= 100):
                raise ValueError("percent outside 0-100")
            levels.append((pct, r["level"].upper()))
        except (KeyError, ValueError) as e:
            bad("coverage.csv", ln, str(e))
    for rank, (pct, level) in enumerate(sorted(levels), start=1):
        coverage[level] = Coverage(level, pct, rank)

    for ln, r in _rows(base / "equipment.csv", "equipment"):
        try:
            price = parse_money(r["list_price"])
            if price <= 0:
                raise ValueError("list price must be positive")
            if r["customer_id"] not in customers:
                raise ValueError(f"unknown customer {r['customer_id']}")
            equipment[r["equipment_id"]] = Equipment(r["equipment_id"], r["customer_id"], r.get("name", ""),
                                                     price, parse_date(r["install_date"]))
        except (KeyError, ValueError) as e:
            bad("equipment.csv", ln, str(e))

    for ln, r in _rows(base / "contracts.csv", "contracts"):
        try:
            level = r["coverage"].upper()
            start, end = parse_date(r["start"]), parse_date(r["end"])
            if end < start:
                raise ValueError("end date before start date")
            if level not in coverage:
                raise ValueError(f"unknown coverage {level}")
            if r["equipment_id"] not in equipment:
                raise ValueError(f"unknown equipment {r['equipment_id']}")
            contracts[r["contract_id"]] = Contract(r["contract_id"], r["equipment_id"], level, start, end,
                                                   parse_money(r["last_annual_value"]))
        except (KeyError, ValueError) as e:
            bad("contracts.csv", ln, str(e))

    for seq, (ln, r) in enumerate(_rows(base / "commands.csv", "commands")):
        try:
            commands.append(Command(seq, r["type"].upper(), r["contract_id"], parse_date(r["date"]),
                                    (r.get("new_coverage") or "").upper() or None))
        except (KeyError, ValueError) as e:
            bad("commands.csv", ln, str(e))
    return customers, equipment, coverage, contracts, commands, warnings
