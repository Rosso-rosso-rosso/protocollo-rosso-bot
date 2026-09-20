# R³∞ Capability Registry

## CAP-R3-004 — Persistent Node Registry

**Status:** hardened candidate on `feat/efficient-routing-cache`.

Il registry persistente gestisce identità di nodo, chiavi Ed25519, scope autorizzati, capability, rotazione, revoca, conflitti e idempotenza. `FabricNode` dipende dall’interfaccia `NodeRegistryStore` e può usare `InMemoryNodeRegistry` oppure `PostgreSQLNodeRegistry`.

La normalizzazione preserva lo storico: il report precedente `docs/EXPANSIVE_AUTONOMY_PROTOCOLLO_ROSSO_2026-09-18.md` usava `CAP-R3-002` per l’**Evidence-Aware Planner**. Quel riferimento storico non viene riscritto; da questo punto `CAP-R3-002` resta riservato all’Evidence-Aware Planner e il Persistent Node Registry è `CAP-R3-004`.

Il PostgreSQL end-to-end non è dichiarato integrato: l’adapter e lo schema sono presenti, ma nel sandbox non è disponibile un server PostgreSQL.
