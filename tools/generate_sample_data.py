"""Generate our own sample dataset (the official files arrive in Week 2). Deterministic: seed 42.
Run from the repo root:  python tools/generate_sample_data.py"""
import csv
import os
import random
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from amc.dates import add_months, add_years, term_end_for  # noqa: E402

random.seed(42)
OUT = "data"
os.makedirs(OUT, exist_ok=True)
PCT = {"BASIC": 6, "COMPREHENSIVE": 10, "PREMIUM": 14}


def write(name, header, rows):
    with open(f"{OUT}/{name}", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


customers = [(f"C{i:02d}", f"{n}") for i, n in enumerate(
    ["Atria Institute Labs", "BMS Engineering Lab", "RV College Physics Lab", "Bosch Test Centre", "IISc Materials Lab",
     "PES University Labs", "Texas Instruments Lab", "NIT Electronics Lab", "Siemens Service Lab", "DRDO Test Facility"], start=1)]
write("customers.csv", ["customer_id", "name"], customers)
write("coverage.csv", ["level", "percent"], [(k, v) for k, v in PCT.items()])

kinds = ["Oscilloscope", "Spectrum Analyser", "Function Generator", "Power Supply", "Logic Analyser", "Multimeter",
         "Soldering Station", "Network Analyser", "Signal Generator", "Environmental Chamber"]
contracts, equipment, commands = [], [], []
multi_group = [0, 10, 20, 30, 40]                         # all owned by C01 (index % 10 == 0)
others = [i for i in range(60) if i not in multi_group]
random.shuffle(others)
role = {}
for i, kind in enumerate(["UP"] * 4 + ["LAPSE"] * 6 + ["E60", "E30", "AGE8", "AGEOVER"] + ["DOWN"] * 3 + ["TWOCYCLE"] * 7):
    role[others[i]] = kind
for i in multi_group:
    role[i] = "MULTI"

lapse_months = iter([1, 2, 3, 5, 6, 8])
multi_dates = iter([date(2026, 5, d) for d in (4, 11, 19, 26, 31)])
up_targets = iter(["PREMIUM", "PREMIUM", "COMPREHENSIVE", "PREMIUM"])
n_up = 0

for i in range(60):
    cid, eid = f"K{i+1:03d}", f"E{i+1:03d}"
    cust = customers[i % 10][0]
    r = role.get(i, "SIMPLE")
    price = random.choice(range(50000, 800001, 25000))
    cov = random.choice(list(PCT))
    start = date(2025, 1, 1) + timedelta(days=random.randint(0, 364))
    if r == "MULTI":
        start = date(2025, 7, 1) + timedelta(days=multi_group.index(i) * 20)
    if r == "UP":
        cov = "BASIC" if n_up != 2 else "BASIC"
    if r == "DOWN":
        cov = "PREMIUM"
    end = term_end_for(start)
    new_start = end + timedelta(days=1)
    install = date(2025, 1, 1) - timedelta(days=random.randint(200, 3000))
    if r == "AGE8":
        install = add_years(new_start, -8) + timedelta(days=90)         # turns 8 inside the new term
    if r == "AGEOVER":
        cov, install = "PREMIUM", add_years(new_start, -9)               # older than 8 at term start
    last = round(price * PCT[cov] / 100 * random.uniform(0.97, 1.08))
    contracts.append((cid, eid, cov, start, end, last))
    equipment.append((eid, cust, f"{random.choice(kinds)} {i+1}", price, install))

    if r == "UP":
        n_up += 1
        d = end if n_up == 1 else start + timedelta(days=random.randint(30, 300))   # first one: last day of term
        commands.append(("UPGRADE", cid, d, next(up_targets)))
    elif r == "LAPSE":
        m = next(lapse_months)
        d = add_months(end, m)
        if m == 3:
            d = add_months(end, 2) + timedelta(days=10)                  # part month -> 3
        commands.append(("RENEW", cid, d, ""))
    elif r == "E60":
        commands.append(("RENEW", cid, end - timedelta(days=60), ""))
    elif r == "E30":
        commands.append(("RENEW", cid, end - timedelta(days=30), ""))
    elif r == "DOWN":
        commands.append(("DOWNGRADE", cid, start + timedelta(days=random.randint(20, 150)), "BASIC"))
        commands.append(("RENEW", cid, end - timedelta(days=random.randint(0, 45)), ""))
    elif r == "MULTI":
        commands.append(("RENEW", cid, next(multi_dates), ""))
    elif r == "TWOCYCLE":
        first = end - timedelta(days=random.randint(0, 90))
        commands.append(("RENEW", cid, first, ""))
        commands.append(("RENEW", cid, term_end_for(new_start) - timedelta(days=random.randint(5, 80)), ""))
    else:
        commands.append(("RENEW", cid, end - timedelta(days=random.randint(0, 100)), ""))

# a couple of deliberately invalid commands to exercise validation
commands.append(("UPGRADE", "K001", date(2026, 6, 15), "BASIC"))
commands.append(("RENEW", "K999", date(2026, 6, 15), ""))
commands.append(("LAPSE", contracts[11][0], contracts[11][4] + timedelta(days=20), ""))

random.shuffle(commands)
write("equipment.csv", ["equipment_id", "customer_id", "name", "list_price", "install_date"], equipment)
write("contracts.csv", ["contract_id", "equipment_id", "coverage", "start_date", "end_date", "last_annual_value"], contracts)
write("commands.csv", ["command", "contract_id", "date", "new_coverage"], commands)
print(f"customers={len(customers)} equipment={len(equipment)} contracts={len(contracts)} commands={len(commands)}")
