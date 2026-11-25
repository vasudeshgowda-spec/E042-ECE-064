from datetime import date
from decimal import Decimal as D

from amc.models import Command, Contract, Coverage, Customer, Equipment
from amc.processor import Engine

COVERAGE = {"BASIC": Coverage("BASIC", D(6), 1), "COMPREHENSIVE": Coverage("COMPREHENSIVE", D(10), 2),
            "PREMIUM": Coverage("PREMIUM", D(14), 3)}


def make_engine(contracts, installs=None, customer="C1", list_price=100000):
    """contracts: list of (contract_id, coverage, start, end, last_value). One equipment per contract."""
    customers = {customer: Customer(customer, "Test Lab"), "C2": Customer("C2", "Other Lab")}
    equipment, cs = {}, {}
    for i, (cid, cov, start, end, last) in enumerate(contracts):
        eid = f"E{i}"
        install = (installs or {}).get(cid, date(2024, 1, 1))
        equipment[eid] = Equipment(eid, customer, f"Instrument {i}", D(list_price), install)
        cs[cid] = Contract(cid, eid, cov, start, end, D(last))
    return Engine(customers, equipment, dict(COVERAGE), cs)


def cmd(seq, kind, cid, d, new=None):
    return Command(seq, kind, cid, d, new)


def one(contract_cov="COMPREHENSIVE", start=date(2026, 1, 1), end=date(2026, 12, 31), last=10000, install=date(2024, 1, 1)):
    return make_engine([("K1", contract_cov, start, end, last)], installs={"K1": install})
