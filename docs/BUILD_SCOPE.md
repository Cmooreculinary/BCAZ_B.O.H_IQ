# BCAz B.O.H Global IQ — Recovered Build Scope

## Recovery status

This branch reconstructs the locally completed BCAz B.O.H Global IQ beta originally recorded as commit `ab75f0d` on `feature/bcaz-boh-global-iq`. The source was rebuilt from the preserved implementation transcript, its 13-test API contract, and the canonical build specification.

## Verified vertical slices

1. **Foundation** — tenant isolation, signed authentication, role enforcement, explicit CORS, request IDs, structured errors, audit events, idempotency, and optimistic concurrency.
2. **Universal records** — tenant-scoped list, read, create, and update behavior across approved operational domains.
3. **Procurement** — purchase-order records, approval boundary, and source-linked procure-to-pay timeline.
4. **Dock receiving** — receiving exception records and idempotent inventory-ledger posting on completion.
5. **Accounts payable** — invoice capture, duplicate candidate detection, and three-way match exceptions.
6. **Inventory** — immutable-source movement records plus actual, theoretical, and variance calculations.
7. **Recipes and production** — production batches, recipe economics, menu simulation, and allergen-liability language.
8. **Operator command** — ranked exception cards, ownership actions, tasks, and evidence-backed Global IQ answers.
9. **Continuity** — installable PWA shell and an IndexedDB operation queue for later synchronization.

## Verification gates

- Backend contract: 13 tests
- Frontend component tests
- TypeScript production compilation
- Vite production bundle
- Python syntax compilation
- No wildcard CORS configuration
- No committed secrets
- No prohibited generator references

## Boundaries

- Live payments are not enabled.
- Global IQ uses stored, cited operational evidence; it does not fabricate unsupported answers.
- MongoDB transactions require a production replica set and are outside local in-memory test coverage.
- Allergen data never guarantees safety and must be checked against current supplier labels, preparation methods, and cross-contact controls.
- Six-month and twelve-month capability materials remain planning scenarios, not launch-ready claims.
