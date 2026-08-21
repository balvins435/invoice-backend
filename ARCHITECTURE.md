# Backend Architecture

The backend is a modular Django monolith. Each app owns one business capability,
with dependencies flowing inward from HTTP adapters to application use cases and
then to domain persistence and infrastructure adapters.

```text
invoice/
|-- application/
|   |-- pricing.py       # Pure pricing policy
|   `-- services.py      # Transactional commands/use cases
|-- selectors.py         # Owner-scoped reads and query composition
|-- views.py             # Thin HTTP transport adapter
|-- serializers.py       # API validation and mapping
|-- models.py            # Persistence models
|-- email_utils.py       # Email infrastructure adapter
|-- utils.py             # PDF infrastructure adapter
`-- permissions.py       # Authorization adapter
```

Views translate HTTP requests. Serializers validate API data. Application services
own workflows and transaction boundaries. Selectors own optimized reads. Pure
calculations remain framework-independent. This pattern can be adopted app-by-app
without changing REST routes, database tables, or client contracts.
