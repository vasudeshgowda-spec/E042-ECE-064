# Decision Log — E042-ECE-064

Where the problem statement is silent or ambiguous we chose one reading, wrote it down here and covered it with a test.
Rule IDs (BR-xx) match the design document.

| ID | Question | Decision | Why | Test |
|---|---|---|---|---|
| D-01 | Language | Python 3.10+, standard library only | Short, readable, `Decimal` for exact money; nothing to install | all |
| D-02 | Money type | `decimal.Decimal` everywhere; no float | Avoids 0.1+0.2 errors that would change a rounded rupee | BR10 tests |
| D-03 | Rounding | Round half-up to whole rupees, once, after GST | Statement says "rounded at the end"; half-up, not banker's | `test_BR10_rounds_half_up_not_bankers` |
| D-04 | Order of calculation | base, age surcharge, escalation floor, early discount, multi discount, lapse charge, inspection fee, GST, round | Follows rule numbering; discounts reduce the escalated value, lapse charge and fee are added after | full-pipeline tests |
| D-05 | "Older than 8 years" (BR-02) | Strictly older: install date + 8 years is before the new term start. Exactly 8 or turning 8 during the term: no surcharge | Statement says "older than ... at the new term start" | `test_BR02_*edge*` |
| D-06 | Early-renewal thresholds (BR-04) | Inclusive: 30 days = 5%, 60 days = 8%; 8% replaces 5% (never both); on the end date itself 0% | "30 or more" / "60 or more" | `test_BR04_*` |
| D-07 | Lapsed months (BR-05) | Smallest m such that end date + m calendar months >= renewal date | Implements "part month counts as full" with real calendar months, month-end clamped | `test_BR05_*` |
| D-08 | Inspection fee (BR-06) | Only when lapse is more than 6 months (m >= 7); exactly 6 months: none | "a lapse over 6 months" | `test_BR06_*` |
| D-09 | What is stored as "last annual value" after renewal | The escalated value (before discounts, lapse charge, fee and GST) | A one-off discount must not permanently lower next year's price. Floor then protects against under-pricing after a downgrade | `test_BR03_renewal_updates_last_annual_value` |
| D-10 | Combining early and multi-equipment discounts | Sequential multiplication: V x (1 - early) x (1 - multi) | A 3% discount on an already-discounted value is the usual reading of "off each of those renewals" | `test_BR09_*` |
| D-11 | Lapse charge base | Percentage of the escalated value V ("the new value"), before discounts | Early discount cannot co-occur with a lapse; multi discount is a separate promotional discount | `test_BR05_BR06_lapse_7_months...` |
| D-12 | Term dates after renewal | On-time: starts the day after the old end, runs 1 year (inclusive). Lapsed: starts on the renewal date | "reinstates the contract from the renewal date" | `test_BR05_BR06_*` |
| D-13 | UPGRADE pro-rating (BR-07) | (new base - old base) x remaining days / term days; both counts inclusive of the end date, so an UPGRADE on the last day charges 1 day. GST applied; coverage changes immediately; any pending downgrade cancelled | Last-day upgrade must still be chargeable and non-zero | `test_BR07_*` |
| D-14 | Bases used for UPGRADE | Both bases use the current term's start date for the age surcharge | Consistent with the term being priced | `test_BR07_*` |
| D-15 | DOWNGRADE (BR-08) | Stored as pending, no money now; applied at the next RENEW including a reinstating one; the escalation floor still uses previous value x 1.05, so price cannot drop | The viva question on under-pricing after a downgrade | `test_BR03_BR08_*` |
| D-16 | Multi-equipment (BR-09) | Count valid RENEW commands per customer per calendar month of the command date; at 5 or more, every renewal that month gets 3%, including the earlier ones. Implemented as a second pass after all commands are processed | The 5th arriving on the 31st must retroactively discount the first four | `test_BR09_*` |
| D-17 | Do lapse renewals count toward BR-09? | Yes, any valid RENEW | Statement says "renewing 5 or more contracts" | covered by counting rule |
| D-18 | LAPSE command | Marks the contract LAPSED; a later RENEW reinstates it with lapse charge. Status is also derived as LAPSED when the as-of date is past the end date with no renewal | Needed for "track contract status over time" | `test_BR11_*` |
| D-19 | Command ordering | Stable sort by date, ties keep file order | Commands may arrive unordered; dates drive every rule | `test_VR07_*` |
| D-20 | Duplicate RENEW | A RENEW dated before the current term start is rejected, which catches a second renewal of the same cycle | A contract renewed early already has a future start date | `test_VR06_*` |
| D-21 | Invalid commands | Rejected with a reason, listed in `REJECTED COMMANDS`, processing continues | Bad input must not stop the batch | `test_VR01..VR06` |
| D-22 | Input headers | Case-insensitive with aliases; bad rows skipped with a warning | Official file layout is not fixed by the statement | loader |

## Open points to re-verify against the official sample outputs
D-09, D-10, D-11 are the ones most likely to change numbers. If the visible expected output disagrees, only
`amc/pricing.py` / `amc/processor.py::_renew` need to change; the tests then show exactly which rules moved.
