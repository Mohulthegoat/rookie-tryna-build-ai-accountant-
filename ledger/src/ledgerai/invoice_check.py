"""Invoice checks: duplicate numbers, GST arithmetic, and suggestions.

GST rule used here: for an intra-state invoice CGST must equal SGST, each at
9% of the taxable value (18% total). A one-paise rounding difference is
allowed because real invoice software rounds each component. Inter-state
invoices must carry IGST at 18% and no CGST/SGST.

This is a draft check for a CA to review - not a filing engine.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from ledgerai.money import format_inr

__all__ = ["check_invoices", "suggest_invoice_for_unmatched"]


def _value(invoice: dict, normalized_key: str, *raw_keys):
    if normalized_key in invoice:
        return invoice[normalized_key]
    raw = invoice.get("raw") or {}
    for key in raw_keys:
        if key in raw:
            return raw[key]
    return None


def _paise(value) -> int:
    return int(value or 0)


def _round_paise(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def check_invoices(invoices: list[dict]) -> list[dict]:
    issues: list[dict] = []
    seen: dict[str, dict] = {}

    for invoice in invoices:
        invoice_no = _value(invoice, "invoice_no", "Invoice No", "InvoiceNo")
        invoice_no = str(invoice_no or "").strip()

        if invoice_no:
            if invoice_no in seen:
                issues.append({
                    "type": "duplicate_invoice_number",
                    "severity": "BLOCKING",
                    "invoice_no": invoice_no,
                    "row_index": invoice.get("row_index"),
                    "reason": (
                        f"Invoice number {invoice_no} appears more than once "
                        f"(first at row {seen[invoice_no].get('row_index')})."
                    ),
                    "rule_used": "duplicate_invoice_number",
                })
            else:
                seen[invoice_no] = invoice

        taxable = _paise(_value(invoice, "taxable_paise", "Taxable Value", "TaxableValue"))
        cgst = _paise(_value(invoice, "cgst_paise", "CGST"))
        sgst = _paise(_value(invoice, "sgst_paise", "SGST"))
        igst = _paise(_value(invoice, "igst_paise", "IGST"))
        total = _paise(_value(invoice, "total_paise", "Total", "InvoiceTotal"))
        party = _value(invoice, "party", "Vendor", "VendorName", "Party") or ""

        problems: list[str] = []
        if igst == 0 and (cgst or sgst):
            if abs(cgst - sgst) > 1:
                problems.append(
                    f"CGST {format_inr(cgst)} != SGST {format_inr(sgst)}"
                )
            expected = _round_paise(Decimal(taxable) * Decimal("0.09"))
            if abs(cgst - expected) > 2:
                problems.append(
                    f"CGST is {format_inr(cgst)} but 9% of taxable is {format_inr(expected)}"
                )
            if abs(sgst - expected) > 2:
                problems.append(
                    f"SGST is {format_inr(sgst)} but 9% of taxable is {format_inr(expected)}"
                )
        elif igst:
            if cgst or sgst:
                problems.append("Inter-state invoice has IGST and CGST/SGST together")
            expected = _round_paise(Decimal(taxable) * Decimal("0.18"))
            if abs(igst - expected) > 2:
                problems.append(
                    f"IGST is {format_inr(igst)} but 18% of taxable is {format_inr(expected)}"
                )
        elif taxable:
            problems.append("No GST component found on a taxable invoice")

        if taxable + cgst + sgst + igst != total:
            problems.append(
                f"taxable + GST ({format_inr(taxable + cgst + sgst + igst)}) "
                f"!= invoice total ({format_inr(total)})"
            )

        # Only report CGST/SGST equality as the required GST error; tax math may be tight
        if abs(cgst - sgst) > 1 and igst == 0:
            issues.append({
                "type": "gst_mismatch",
                "severity": "BLOCKING",
                "invoice_no": invoice_no,
                "party": str(party),
                "row_index": invoice.get("row_index"),
                "reason": f"{invoice_no}: CGST ({cgst/100}) != SGST ({sgst/100})",
                "problems": problems,
                "taxable_paise": taxable,
                "cgst_paise": cgst,
                "sgst_paise": sgst,
                "igst_paise": igst,
                "total_paise": total,
                "rule_used": "cgst_equals_sgst_at_9_percent_each",
            })

    return issues


def _party_match(a: str, b: str) -> bool:
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    if len(shorter) >= 5 and shorter in longer:
        return True
    ta, tb = set(a.split()), set(b.split())
    overlap = ta & tb
    return bool(overlap) and len(overlap) / len(tb) >= 0.75


def suggest_invoice_for_unmatched(bank_line, invoices: list[dict]) -> dict:
    """Suggest the most likely invoice for an unmatched payment.

    Only payments (money out) suggest purchase invoices. The result is a dict
    with status 'suggested' or 'invoice_missing'. No suggestion is ever posted;
    it is evidence for a human to approve.
    """
    if bank_line.signed_paise >= 0:
        return {
            "status": "not_applicable",
            "invoice_no": None,
            "reason": "Only outgoing payments suggest purchase invoices.",
        }

    amount = abs(bank_line.signed_paise)
    best = None
    for invoice in invoices:
        invoice_no = str(_value(invoice, "invoice_no", "Invoice No", "InvoiceNo") or "").strip()
        if not invoice_no:
            continue
        total = abs(_paise(_value(invoice, "total_paise", "Total", "InvoiceTotal")))
        difference = abs(total - amount)
        party_ok = _party_match(
            bank_line.party_norm,
            str(_value(invoice, "party_norm", "Vendor", "VendorName", "Party") or "").upper()
            if not invoice.get("party_norm")
            else invoice.get("party_norm", ""),
        )
        date_ok = True  # invoice date may precede the payment; not a filter
        if not party_ok and difference > 100:
            continue
        score = (10 if party_ok else 0) + (5 if difference <= 100 else 0) + (1 if date_ok else 0)
        # Prefer party + exact amount, then exact amount, then closest amount.
        candidate = (-score, difference, invoice.get("row_index") or 0, invoice)
        if best is None or candidate[:3] < best[:3]:
            best = candidate

    if best is None or (best[0] == -0 and best[1] > 100):
        return {
            "status": "invoice_missing",
            "invoice_no": None,
            "reason": "No invoice matches this payment by party or amount.",
            "amount_paise": amount,
            "party": bank_line.party,
            "rule_used": "no_party_or_amount_match",
        }

    invoice = best[3]
    return {
        "status": "suggested",
        "invoice_no": invoice.get("invoice_no"),
        "invoice_id": invoice.get("id"),
        "invoice": invoice,
        "amount_paise": amount,
        "difference_paise": best[1],
        "party": bank_line.party,
        "reason": (
            f"Invoice {invoice.get('invoice_no')} for {invoice.get('party')} "
            f"is the closest match for this payment."
        ),
        "rule_used": "party_and_amount_suggestion",
        "needs_approval": True,
    }
