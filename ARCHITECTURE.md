# Backend Architecture

The backend is a modular Django monolith. Each app owns one business capability,
with dependencies flowing inward from HTTP adapters to application use cases and
then to domain persistence and infrastructure adapters.

```text
<capability>/
|-- application/services.py  # Commands and workflows
|-- selectors.py             # Owner-scoped reads
|-- views.py                 # HTTP adapter
|-- serializers.py           # API validation and mapping
|-- models.py                # Persistence
`-- services/                # External provider adapters
```

Views translate HTTP requests. Serializers validate API data. Application services
own workflows and transaction boundaries. Selectors own optimized reads. Pure
calculations remain framework-independent.

The convention now covers invoices, businesses, expenses, payments, tax,
messaging, reports, users, and AI. Provider integrations remain behind dedicated
adapters for M-Pesa, eTIMS, WhatsApp, email, PDF, and AI services. Existing routes,
database tables, migrations, and client contracts remain unchanged.
