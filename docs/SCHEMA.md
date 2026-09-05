# Schema Documentation

## Overview

All data is stored as JSONL (JSON Lines) files. Each line is a single JSON object.

---

## Source Entity Schemas

### 1. Merchant (`merchants.jsonl`)

| Field | Type | Description | Example |
|---|---|---|---|
| merchant_id | string | Primary key | MER_000001 |
| merchant_name | string | Business name | ShopEase India Pvt Ltd |
| industry | string | ELECTRONICS, FASHION, GROCERY, BOOKS_AND_MEDIA, HOME_AND_FURNITURE | ELECTRONICS |
| gstin | string | 15-char GST Identification Number | 27AABCS1234E1Z5 |
| state | string | Indian state of registration | Maharashtra |
| city | string | City | Mumbai |
| bank_account_id | string | Internal account reference | ACC_000001 |
| bank_account_number | string | Bank account number | 918020043210001 |
| bank_ifsc | string | IFSC code | UTIB0000001 |
| bank_name | string | Bank name | Axis Bank |
| currency | string | Always INR | INR |
| timezone | string | Always Asia/Kolkata | Asia/Kolkata |
| status | string | ACTIVE | ACTIVE |

### 2. Customer (`customers.jsonl`)

| Field | Type | Description | Example |
|---|---|---|---|
| customer_id | string | Primary key | CUS_000001 |
| merchant_id | string | FK → merchants | MER_000001 |
| name | string | Full name | Aarav Sharma |
| email | string | Email address | aarav.sharma42@gmail.com |
| phone | string | Indian mobile (+91...) | +919876543210 |
| city | string | City | Mumbai |
| state | string | Indian state | Maharashtra |

### 3. Order (`orders.jsonl`)

| Field | Type | Description | Example |
|---|---|---|---|
| order_id | string | Primary key | ORD_000001 |
| merchant_id | string | FK → merchants | MER_000001 |
| customer_id | string | FK → customers | CUS_000042 |
| order_date | string | ISO 8601 with timezone | 2026-08-15T14:30:00+05:30 |
| subtotal | string | Decimal, sum of item prices | 5000.00 |
| discount_rate | string | Decimal, 0-0.30 | 0.10 |
| discount | string | Decimal, subtotal × rate | 500.00 |
| taxable_amount | string | Decimal, subtotal - discount | 4500.00 |
| cgst | string | Decimal, 9% if intra-state | 405.00 |
| sgst | string | Decimal, 9% if intra-state | 405.00 |
| igst | string | Decimal, 18% if inter-state | 0.00 |
| total_tax | string | Decimal, cgst + sgst + igst | 810.00 |
| total_amount | string | Decimal, taxable + tax | 5310.00 |
| currency | string | INR | INR |
| status | string | COMPLETED, CANCELLED, PENDING | COMPLETED |
| seller_state | string | Merchant's state | Maharashtra |
| buyer_state | string | Customer's state | Maharashtra |

### 4. Invoice (`invoices.jsonl`)

| Field | Type | Description | Example |
|---|---|---|---|
| invoice_id | string | Primary key | INV_000001 |
| order_id | string | FK → orders | ORD_000001 |
| merchant_id | string | FK → merchants | MER_000001 |
| customer_id | string | FK → customers | CUS_000042 |
| invoice_number | string | Business format invoice number | INV/2026-27/001/00001 |
| invoice_date | string | ISO 8601 | 2026-08-15T15:00:00+05:30 |
| due_date | string | YYYY-MM-DD | 2026-09-14 |
| subtotal | string | Copied from order | 5000.00 |
| discount | string | Copied from order | 500.00 |
| taxable_amount | string | Copied from order | 4500.00 |
| cgst, sgst, igst | string | Copied from order | 405.00 |
| total_tax | string | Copied from order | 810.00 |
| total_amount | string | Copied from order | 5310.00 |
| currency | string | INR | INR |
| seller_gstin | string | Merchant GSTIN | 27AABCS1234E1Z5 |
| seller_state | string | From order | Maharashtra |
| buyer_state | string | From order | Maharashtra |
| status | string | ISSUED | ISSUED |

### 5. GST Record (`gst_records.jsonl`)

| Field | Type | Description | Example |
|---|---|---|---|
| gst_record_id | string | Primary key | GST_000001 |
| invoice_id | string | FK → invoices | INV_000001 |
| invoice_number | string | Business invoice number | INV/2026-27/001/00001 |
| merchant_id | string | FK → merchants | MER_000001 |
| seller_gstin | string | Seller GSTIN | 27AABCS1234E1Z5 |
| buyer_gstin | string/null | Buyer GSTIN (B2B) or null (B2C) | 29AADCF5678G2Z3 |
| supply_type | string | INTRA_STATE or INTER_STATE | INTRA_STATE |
| taxable_amount | string | From invoice | 4500.00 |
| cgst, sgst, igst | string | From invoice | 405.00 |
| total_tax | string | From invoice | 810.00 |
| total_amount | string | From invoice | 5310.00 |
| filing_period | string | MM-YYYY | 08-2026 |
| return_type | string | GSTR-1 | GSTR-1 |
| status | string | FILED | FILED |

### 6. Payment (`payments.jsonl`)

| Field | Type | Description | Example |
|---|---|---|---|
| payment_id | string | Primary key | PAY_000001 |
| order_id | string | FK → orders | ORD_000001 |
| merchant_id | string | FK → merchants | MER_000001 |
| customer_id | string | FK → customers | CUS_000042 |
| amount | string | = order.total_amount | 5310.00 |
| currency | string | INR | INR |
| payment_method | string | UPI, CARD, NETBANKING, WALLET | UPI |
| status | string | CAPTURED, FAILED, PENDING | CAPTURED |
| gateway | string | Always RAZORPAY | RAZORPAY |
| gateway_reference | string | Razorpay payment ID | pay_AbCdEfGhIjKlMn |
| utr | string/null | UTR for captured payments | HDFC1234567890123 |
| payment_date | string | ISO 8601 | 2026-08-15T14:35:00+05:30 |
| captured_at | string/null | Capture timestamp | 2026-08-15T14:35:00+05:30 |
| card_network | string | (CARD only) VISA, MASTERCARD, RUPAY, AMEX | VISA |
| card_last4 | string | (CARD only) Last 4 digits | 4242 |
| card_type | string | (CARD only) DEBIT, CREDIT | CREDIT |
| upi_app | string | (UPI only) GPAY, PHONEPE, etc. | GPAY |
| upi_id | string | (UPI only) UPI address | user1234@oksbi |
| wallet_provider | string | (WALLET only) | PAYTM |
| bank_name | string | (NETBANKING only) | HDFC |

### 7. Fee (`fees.jsonl`)

| Field | Type | Description | Example |
|---|---|---|---|
| fee_id | string | Primary key | FEE_000001 |
| payment_id | string | FK → payments | PAY_000001 |
| merchant_id | string | FK → merchants | MER_000001 |
| fee_type | string | PLATFORM_FEE, PROCESSING_FEE, GATEWAY_FEE | PROCESSING_FEE |
| fee_amount | string | Calculated from fee_rules.yaml | 95.58 |
| tax_amount | string | 18% GST on fee | 17.20 |
| total_fee | string | fee_amount + tax_amount | 112.78 |
| currency | string | INR | INR |
| payment_method | string | From payment | CARD |

### 8. Refund (`refunds.jsonl`)

| Field | Type | Description | Example |
|---|---|---|---|
| refund_id | string | Primary key | REF_000001 |
| payment_id | string | FK → payments | PAY_000123 |
| order_id | string | FK → orders | ORD_000123 |
| merchant_id | string | FK → merchants | MER_000001 |
| refund_amount | string | FULL=payment amt, PARTIAL=fraction | 2655.00 |
| refund_type | string | FULL, PARTIAL, REVERSAL | PARTIAL |
| reason | string | Refund reason | Wrong item delivered |
| status | string | PROCESSED | PROCESSED |
| refund_date | string | ISO 8601 | 2026-08-20T10:00:00+05:30 |
| currency | string | INR | INR |

### 9. Settlement (`settlements.jsonl`)

| Field | Type | Description | Example |
|---|---|---|---|
| settlement_id | string | Primary key | STL_000001 |
| merchant_id | string | FK → merchants | MER_000001 |
| settlement_date | string | ISO 8601 | 2026-08-18T12:00:00+05:30 |
| gross_amount | string | Sum of payment amounts | 53100.00 |
| total_fees | string | Sum of fee_amounts | 955.80 |
| total_fee_tax | string | Sum of fee tax_amounts | 172.04 |
| total_refunds | string | Sum of refund amounts | 5310.00 |
| total_adjustments | string | Sum of adjustment amounts | 0.00 |
| net_amount | string | gross - fees - fee_tax - refunds + adj | 46662.16 |
| currency | string | INR | INR |
| utr | string | Settlement UTR | UTIB1234567890123 |
| status | string | SETTLED | SETTLED |
| payment_count | int | Number of payments in settlement | 10 |

### 10. Settlement-Payment Link (`settlement_payments.jsonl`)

| Field | Type | Description | Example |
|---|---|---|---|
| settlement_id | string | FK → settlements | STL_000001 |
| payment_id | string | FK → payments | PAY_000001 |
| allocated_amount | string | Payment amount allocated | 5310.00 |

### 11. Bank Record (`bank_records.jsonl`)

| Field | Type | Description | Example |
|---|---|---|---|
| bank_record_id | string | Primary key | BNK_000001 |
| merchant_id | string | FK → merchants | MER_000001 |
| account_id | string | Internal account ref | ACC_000001 |
| account_number | string | Bank account number | 918020043210001 |
| bank_name | string | Bank name | Axis Bank |
| transaction_date | string | YYYY-MM-DD | 2026-08-19 |
| value_date | string | YYYY-MM-DD | 2026-08-19 |
| amount | string | Transaction amount | 46662.16 |
| currency | string | INR | INR |
| transaction_type | string | CREDIT or DEBIT | CREDIT |
| reference | string | UTR or ref code | UTIB1234567890123 |
| description | string | Bank narration | RAZORPAY SETTLEMENT STL_000001 |
| settlement_id | string/null | FK → settlements (null for noise) | STL_000001 |
| balance_after | string | Running balance | 1546662.16 |
| category | string | SETTLEMENT, SUPPLIER_PAYMENT, RENT, SALARY, etc. | SETTLEMENT |

### 12. Book/Ledger Entry (`books.jsonl`)

| Field | Type | Description | Example |
|---|---|---|---|
| entry_id | string | Primary key | LED_000001 |
| merchant_id | string | FK → merchants | MER_000001 |
| entry_date | string | YYYY-MM-DD | 2026-08-15 |
| account_code | string | Chart of accounts code | 1200 |
| account_name | string | Account name | Accounts Receivable |
| debit | string | Debit amount (0.00 if credit) | 5310.00 |
| credit | string | Credit amount (0.00 if debit) | 0.00 |
| reference_type | string | ORDER, PAYMENT, FEE, REFUND, SETTLEMENT | ORDER |
| reference_id | string | FK → referenced entity | ORD_000001 |
| description | string | Entry description | Sale - ORD_000001 |
| entry_type | string | SALE, PAYMENT, FEE, REFUND, SETTLEMENT, TAX | SALE |

### 13. Adjustment (`adjustments.jsonl`)

| Field | Type | Description | Example |
|---|---|---|---|
| adjustment_id | string | Primary key | ADJ_000001 |
| settlement_id | string | FK → settlements | STL_000001 |
| merchant_id | string | FK → merchants | MER_000001 |
| adjustment_type | string | SETTLEMENT_ADJUSTMENT, ROUNDING, CHARGEBACK, REVERSAL, MANUAL_ADJUSTMENT | CHARGEBACK |
| amount | string | Signed decimal (negative=debit) | -5000.00 |
| direction | string | CREDIT or DEBIT | DEBIT |
| reason | string | Reason text | Fraud-related chargeback |
| adjustment_date | string | ISO 8601 | 2026-08-20T10:00:00+05:30 |
| currency | string | INR | INR |
| status | string | APPLIED | APPLIED |

---

## Ground Truth Schemas

### Event Links (`event_links.jsonl`)

| Field | Type | Description |
|---|---|---|
| source_type | string | Entity type (invoice, payment, etc.) |
| source_id | string | Entity ID |
| target_type | string | Related entity type |
| target_id | string | Related entity ID |
| relationship | string | DERIVED_FROM, PAYS_FOR, CHARGED_ON, REFUNDS, SETTLES, CORRESPONDS_TO, TAX_FOR, RECORDS, ADJUSTS |
| expected_status | string | MATCH |

### Reconciliation Truth (`reconciliation_truth.jsonl`)

| Field | Type | Description |
|---|---|---|
| pair_type | string | ORDER_INVOICE, ORDER_PAYMENT, SETTLEMENT_BANK, INVOICE_GST |
| source_type | string | Source entity type |
| source_id | string | Source entity ID |
| target_type | string | Target entity type |
| target_id | string | Target entity ID |
| expected_result | string | MATCH |
| match_fields | list | Fields to compare |

### Exception Truth (`exception_truth.jsonl`)

| Field | Type | Description |
|---|---|---|
| case_id | string | Exception case ID (EXC_000001) |
| exception_class | string | Classification label |
| exception_subclass | string/null | Sub-classification for amount issues |
| severity | string | LOW, MEDIUM, HIGH |
| resolution_hint | string | Suggested resolution |
| requires_manual_review | bool | Whether human review is needed |
| corruption_type | string | Original corruption type |
| affected_entity_id | string | The corrupted entity's ID |
| affected_field | string | Which field was corrupted |
| original_value | string | Clean value |
| corrupted_value | string | Noisy value |

---

## Chart of Accounts

| Code | Name | Type |
|---|---|---|
| 1100 | Bank Account | Asset |
| 1200 | Accounts Receivable | Asset |
| 1210 | Gateway Receivable | Asset |
| 1300 | GST Input Credit (Fees) | Asset |
| 2100 | GST Payable | Liability |
| 2101 | CGST Payable | Liability |
| 2102 | SGST Payable | Liability |
| 2103 | IGST Payable | Liability |
| 4000 | Revenue | Income |
| 4100 | Adjustment Income | Income |
| 5100 | Payment Processing Fee | Expense |
| 5200 | Refund Expense | Expense |
| 5300 | Adjustment Expense | Expense |
