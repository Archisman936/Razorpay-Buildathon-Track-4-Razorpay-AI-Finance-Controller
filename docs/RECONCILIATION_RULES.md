# Reconciliation Rules Specification

## Overview

This document defines how the reconciliation engine should match, classify, and handle financial records across the 12 source entities.

---

## 1. Reconciliation Pairs

The engine performs matching across these entity pairs:

| # | Pair Type | Source | Target | Match Logic |
|---|---|---|---|---|
| 1 | ORDER_PAYMENT | Order | Payment | order_id exact match, amount match |
| 2 | ORDER_INVOICE | Order | Invoice | order_id exact match, amount match |
| 3 | PAYMENT_FEE | Payment | Fee | payment_id exact match |
| 4 | PAYMENT_REFUND | Payment | Refund | payment_id exact match |
| 5 | PAYMENT_SETTLEMENT | Payment | Settlement | via settlement_payments linkage |
| 6 | SETTLEMENT_BANK | Settlement | Bank Record | UTR match, amount match, description fuzzy match |
| 7 | INVOICE_GST | Invoice | GST Record | invoice_id exact match, tax amounts match |
| 8 | EVENT_BOOKS | Any event | Book Entry | reference_id match, amount match, debit=credit balance |
| 9 | SETTLEMENT_ADJUSTMENT | Settlement | Adjustment | settlement_id exact match |

---

## 2. Matching Tiers

### Tier 1: Deterministic (Rule-Based)

Applied first. If these match, no ML needed.

| Rule | Fields | Tolerance | Result |
|---|---|---|---|
| Exact ID match | order_id, payment_id, settlement_id, invoice_id | None | MATCH |
| Exact UTR match | utr | None | MATCH |
| Exact gateway_reference | gateway_reference | None | MATCH |
| Exact amount + same date | amount, date | amount=exact, date=same day | MATCH |

### Tier 2: Fuzzy (Feature-Based)

Applied to records not matched in Tier 1.

| Feature | Method | Threshold |
|---|---|---|
| ID similarity | Levenshtein / normalized edit distance | > 0.8 |
| Description similarity | TF-IDF cosine, RapidFuzz | > 0.7 |
| Amount difference | abs(a - b) / max(a, b) | < 0.05 (5%) |
| Date difference | abs(date_a - date_b) in days | ≤ 3 days |
| Reference similarity | Fuzzy string match on UTR/ref | > 0.75 |

### Tier 3: ML Model

Applied to ambiguous candidates from Tier 2.

- Input: feature vector from Tier 2
- Output: match probability
- Threshold: > 0.85 for auto-match, 0.50-0.85 for human review, < 0.50 for non-match

---

## 3. Exception Classification

When records don't match or match with discrepancies, classify the exception:

| Exception Class | Description | Severity | Auto-Resolvable? |
|---|---|---|---|
| FORMAT_MISMATCH | ID format differs (ORD_001 vs ORD-001) | LOW | Yes |
| DESCRIPTION_MISMATCH | Bank narration doesn't match expected | LOW | Yes |
| TIMING_DIFFERENCE | Date differs by 1-3 days | LOW | Yes |
| AMOUNT_DISCREPANCY__FEE_ADJUSTMENT | Amount differs due to fee calculation | MEDIUM | Sometimes |
| AMOUNT_DISCREPANCY__PARTIAL_SETTLEMENT | Partial settlement amount | HIGH | No |
| AMOUNT_DISCREPANCY__TAX_MISMATCH | Tax calculation difference | MEDIUM | Sometimes |
| AMOUNT_DISCREPANCY__ROUNDING | Rounding difference (< ₹1) | LOW | Yes |
| AMOUNT_DISCREPANCY__UNKNOWN | Unexplained amount difference | HIGH | No |
| MISSING_RECORD | Expected counterpart not found | HIGH | No |
| DUPLICATE | Same event recorded twice | MEDIUM | Sometimes |
| WRONG_REFERENCE | Cross-reference points to wrong entity | HIGH | No |

---

## 4. Amount Tolerance Rules

| Context | Tolerance | Rule |
|---|---|---|
| Order ↔ Payment | Exact match | payment.amount == order.total_amount |
| Order ↔ Invoice | Exact match | invoice.total_amount == order.total_amount |
| Settlement ↔ Bank | ±2% or ±₹100 | For fee/adjustment discrepancies |
| Invoice ↔ GST | Exact match | Tax components must match exactly |
| Rounding | ±₹1 | Auto-resolve if within threshold |

---

## 5. Date Tolerance Rules

| Context | Tolerance | Notes |
|---|---|---|
| Order → Payment | Same day | Payment within minutes of order |
| Order → Invoice | 0-1 day | Invoice generated shortly after order |
| Settlement → Bank | 0-2 days | Bank credit may lag settlement |
| Invoice → Books | 0-1 day | Booking may be next business day |
| Settlement → Bank → Books | 0-3 days | End-to-end may span 3 days |

---

## 6. Settlement Arithmetic Rules

```
net_settlement = gross_payments
                 - total_fees
                 - total_fee_tax
                 - total_refunds
                 + total_adjustments
```

If `bank_record.amount ≠ settlement.net_amount`:
1. Check if difference = any pending adjustment amount
2. Check if difference = any fee calculation difference
3. Check if difference < ₹1 (rounding)
4. Otherwise: flag as AMOUNT_DISCREPANCY__UNKNOWN

---

## 7. Double-Entry Validation Rules

For each merchant, across all book entries:

```
SUM(debits) == SUM(credits)
```

For each financial event, the entry pair must balance:

| Event | Debit Account | Credit Account |
|---|---|---|
| Sale | Accounts Receivable | Revenue + GST Payable |
| Payment | Gateway Receivable | Accounts Receivable |
| Fee | Processing Fee + Fee GST | Gateway Receivable |
| Refund | Refund Expense | Gateway Receivable |
| Settlement | Bank Account | Gateway Receivable |

---

## 8. Duplicate Detection Rules

A record is a potential duplicate if:
1. Same entity type
2. Same merchant
3. Amount matches exactly
4. Date within 1 day
5. ID contains `_DUP` suffix OR high string similarity (>0.9) with another record

Action: Flag the newer record as DUPLICATE, keep the older one.

---

## 9. Many-to-One Matching Rules

These scenarios require special handling:

| Scenario | Rule |
|---|---|
| N payments → 1 settlement | Sum of allocated amounts must = gross settlement |
| 1 payment → partial refund | Refund amount < payment amount |
| 1 payment → multiple adjustments | Sum of adjustments tracked separately |
| 1 invoice → multiple ledger entries | All entries must reference same invoice_id |
| 1 settlement → multiple bank records | Should not happen normally; flag if found |

---

## 10. Reconciliation Status Flow

```
UNMATCHED
    ↓
CANDIDATE_FOUND (Tier 2 candidate identified)
    ↓
┌─────────────────────────────────┐
│  Tier 1: Deterministic Match?   │
│  Yes → MATCHED_EXACT            │
│  No  → Continue                 │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│  Tier 2: Fuzzy Match Score?     │
│  > 0.85 → MATCHED_FUZZY        │
│  0.50-0.85 → REVIEW_REQUIRED   │
│  < 0.50 → EXCEPTION            │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│  Exception Classification       │
│  → Assign exception_class       │
│  → Set severity                 │
│  → Auto-resolve or escalate     │
└─────────────────────────────────┘
```
