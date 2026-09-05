# Data Generation Specification

## Overview

This document specifies how synthetic financial data is generated for the Track 4 AI Finance Controller.

## Principle

```
Clean Financial World → Ground Truth → Corruption → Noisy Source Data
```

**Never** start by randomly inserting records. Every child entity is derived from its parent.

## Business Scenario

| Parameter | Value |
|---|---|
| Business type | Indian e-commerce merchants |
| Country | India |
| Currency | INR |
| Period | August 2026 |
| Payment methods | UPI, CARD, NETBANKING, WALLET |
| Tax regime | GST (CGST/SGST intra-state, IGST inter-state) |

## Generation Order (Dependency DAG)

```
Merchant (root)
   │
   ├── Customer
   │
   └── Order
        │
        ├── Invoice
        │     └── GST Record
        │
        └── Payment
              ├── Fee
              ├── Refund
              └── Settlement
                     └── Bank Record

Order / Payment / Settlement / Bank / Invoice
                    ↓
                Book Entries (double-entry)

Settlement → Adjustment
```

Each entity is generated **only after** its parents exist. No entity is created independently.

## Target Counts (Development Scale)

| Entity | Target | Actual |
|---|---|---|
| Merchants | 5 | 5 |
| Customers | 500 | 500 |
| Orders | 2,000 | 2,000 |
| Invoices | ~1,800 | 1,726 (from completed orders) |
| GST Records | ~1,800 | 1,726 (from invoices) |
| Payments | 2,000 | 2,000 |
| Fees | 2,000 | 2,000 |
| Refunds | ~150 | 155 |
| Settlements | ~200 | 173 |
| Bank Records | ~2,200 | 547 (settlement credits + noise) |
| Books/Ledger | 4,000+ | 12,276 |
| Adjustments | ~50 | 50 |

## ID Format

All entities use stable IDs: `{PREFIX}_{NNNNNN}`

| Entity | Prefix | Example |
|---|---|---|
| Merchant | MER | MER_000001 |
| Customer | CUS | CUS_000001 |
| Order | ORD | ORD_000001 |
| Invoice | INV | INV_000001 |
| Payment | PAY | PAY_000001 |
| Fee | FEE | FEE_000001 |
| Refund | REF | REF_000001 |
| Settlement | STL | STL_000001 |
| Bank Record | BNK | BNK_000001 |
| Book Entry | LED | LED_000001 |
| GST Record | GST | GST_000001 |
| Adjustment | ADJ | ADJ_000001 |

External identifiers: `gateway_reference`, `invoice_number`, `UTR`, `bank_reference`

## Order Status Distribution

| Status | Probability | Gets Invoice? | Gets Payment? |
|---|---|---|---|
| COMPLETED | 85% | Yes | Yes (CAPTURED) |
| CANCELLED | 10% | No | Yes (FAILED) |
| PENDING | 5% | No | Yes (PENDING) |

## Payment Method Distribution

| Method | Probability | Fee Rate |
|---|---|---|
| UPI | 45% | 0.00% (RBI mandate) |
| CARD | 30% | 1.80% |
| NETBANKING | 15% | 1.50% |
| WALLET | 10% | 2.00% |

## Refund Distribution

- ~9% of captured payments get refunded
- 50% FULL, 35% PARTIAL, 15% REVERSAL

## Settlement Grouping

- 5-20 payments per settlement
- Grouped by merchant
- Sorted by payment date
- Settlement date = last payment date + 1-3 days

## Corruption Types Applied

| Type | Rate | Description |
|---|---|---|
| ID Noise | 15% | Format variations (dash, slash, no separator, lowercase) |
| Description Noise | 30% | Bank narration variations |
| Date Noise | 20% | ±1-3 day shifts |
| Amount Noise | 8% | Small discrepancies with tracked causes |
| Missing Records | 2-5% | Records removed per entity type |
| Duplicates | 3% | Duplicate records with slight variations |
| Wrong References | 5% | Cross-references swapped |

## Reproducibility

- Global seed: 42
- All generators use `random.seed(42)` for deterministic output
- Full pipeline: `python scripts/generate_all.py`
