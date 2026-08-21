from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Mapping


@dataclass(frozen=True)
class InvoiceTotals:
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal


def calculate_invoice_totals(items: Iterable[Mapping], tax_rate) -> InvoiceTotals:
    subtotal = sum(
        (Decimal(str(item["quantity"])) * Decimal(str(item["unit_price"])) for item in items),
        Decimal("0.00"),
    )
    tax_amount = (subtotal * Decimal(str(tax_rate))) / Decimal("100")
    return InvoiceTotals(subtotal, tax_amount, subtotal + tax_amount)


def calculate_item_total(item: Mapping) -> Decimal:
    return Decimal(str(item["quantity"])) * Decimal(str(item["unit_price"]))
