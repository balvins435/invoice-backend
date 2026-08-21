from decimal import Decimal

from django.test import SimpleTestCase

from invoice.application.pricing import calculate_invoice_totals


class InvoicePricingTests(SimpleTestCase):
    def test_calculates_subtotal_tax_and_total(self):
        totals = calculate_invoice_totals(
            [{"quantity": 2, "unit_price": "100.00"}, {"quantity": 1, "unit_price": "50.00"}],
            tax_rate="16.00",
        )
        self.assertEqual(totals.subtotal, Decimal("250.00"))
        self.assertEqual(totals.tax_amount, Decimal("40.0000"))
        self.assertEqual(totals.total_amount, Decimal("290.0000"))
