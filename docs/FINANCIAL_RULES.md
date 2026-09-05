# Financial Rules — Track 4

## 1. Order Calculations

```
subtotal = sum(item_prices)
discount = subtotal × discount_rate
taxable_amount = subtotal - discount
```

## 2. Tax Calculations (GST)

Indian GST rules:
- **Intra-state** (same state): CGST (9%) + SGST (9%) = 18%
- **Inter-state** (different state): IGST (18%)

```
IF seller_state == buyer_state:
    CGST = taxable_amount × 0.09
    SGST = taxable_amount × 0.09
    IGST = 0
ELSE:
    CGST = 0
    SGST = 0
    IGST = taxable_amount × 0.18

total_tax = CGST + SGST + IGST
```

## 3. Invoice Calculations

```
invoice_amount = taxable_amount + total_tax
invoice_amount = order.total_amount  (must match)
```

## 4. Payment Calculations

For normal successful payments:
```
payment.amount = order.total_amount
```

## 5. Fee Calculations

Fees vary by payment method:

| Method      | Fee Rate | Fee Tax (GST on fee) |
|-------------|----------|----------------------|
| UPI         | 0.00%    | 18% of fee           |
| CARD        | 1.80%    | 18% of fee           |
| NETBANKING  | 1.50%    | 18% of fee           |
| WALLET      | 2.00%    | 18% of fee           |

```
base_fee = payment_amount × fee_rate
fee_tax = base_fee × 0.18
total_fee = base_fee + fee_tax
```

Note: UPI has 0% MDR in India (as per RBI), but we keep the structure for consistency.

## 6. Refund Calculations

```
FULL refund:    refund_amount = payment_amount
PARTIAL refund: refund_amount = payment_amount × random(0.1, 0.9)
REVERSAL:       refund_amount = payment_amount (chargeback)
```

## 7. Settlement Calculations

Multiple payments are grouped into one settlement:

```
gross_amount = sum(payment.amount for payment in settlement_payments)
total_fees = sum(fee.fee_amount for fee in settlement_fees)
total_fee_tax = sum(fee.tax_amount for fee in settlement_fees)
total_refunds = sum(refund.amount for refund in settlement_refunds)
total_adjustments = sum(adj.amount for adj in settlement_adjustments)

net_settlement = gross_amount - total_fees - total_fee_tax - total_refunds + total_adjustments
```

## 8. Bank Record Rules

For settlement-related bank credits:
```
bank_credit_amount = settlement.net_amount
```

For non-settlement transactions (noise):
- Supplier payments, rent, salary, utilities — random realistic amounts.

## 9. Double-Entry Accounting Rules

**Fundamental rule**: For every transaction, total debits = total credits.

### Entry patterns:

**Sale/Order placed:**
```
Debit   Accounts Receivable     order.total_amount
Credit  Revenue                 order.taxable_amount
Credit  GST Payable             order.total_tax
```

**Payment received:**
```
Debit   Gateway Receivable      payment.amount
Credit  Accounts Receivable     payment.amount
```

**Fee charged:**
```
Debit   Payment Processing Fee  fee.fee_amount
Debit   Fee GST (Input Credit)  fee.tax_amount
Credit  Gateway Receivable      fee.fee_amount + fee.tax_amount
```

**Refund processed:**
```
Debit   Refund Expense          refund.amount
Credit  Gateway Receivable      refund.amount
```

**Settlement received:**
```
Debit   Bank Account            settlement.net_amount
Credit  Gateway Receivable      settlement.net_amount
```

**Adjustment:**
```
IF positive (credit to merchant):
    Debit   Gateway Receivable      adj.amount
    Credit  Adjustment Income       adj.amount
IF negative (debit to merchant):
    Debit   Adjustment Expense      adj.amount
    Credit  Gateway Receivable      adj.amount
```

## 10. Validation Invariants

These must hold for clean data:

1. `∀ order: order.total_amount = order.taxable_amount + order.total_tax`
2. `∀ invoice: invoice.total_amount = invoice.order.total_amount`
3. `∀ payment (success): payment.amount = payment.order.total_amount`
4. `∀ fee: fee.tax_amount = fee.fee_amount × 0.18`
5. `∀ settlement: settlement.net_amount = gross - fees - fee_tax - refunds + adjustments`
6. `∀ bank_record (settlement): bank_record.amount = settlement.net_amount`
7. `∀ gst_record: gst_record.total_tax = gst_record.cgst + gst_record.sgst + gst_record.igst`
8. `∀ merchant: sum(debits) = sum(credits) for all book entries`
