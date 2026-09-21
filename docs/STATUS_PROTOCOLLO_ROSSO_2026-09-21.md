# Stato aggiornato — Protocollo Rosso / R³∞

**Data di rilevazione:** 2026-09-21 07:12 UTC  
**Repository:** `Rosso-rosso-rosso/protocollo-rosso-bot`  
**Ramo:** `feat/efficient-routing-cache`  
**HEAD:** `f1d3738735a59ef2a6f8e298d37e3e2fdbb4a5e7`  
**PR:** #1, aperta; nessun merge in `main`.

## Verifica corrente

La suite locale è composta da **51 test superati**. Il CI remoto della PR è verde: i due check `protocollo-ci/test` risultano `SUCCESS`, senza failure o job pending.

## Capability principale

Il Persistent Node Registry è normalizzato come **CAP-R3-004**. La provenienza storica è preservata: CAP-R3-002 rimane associata all’Evidence-Aware Planner nei riferimenti precedenti e non viene riscritta.

`FabricNode` usa l’interfaccia `NodeRegistryStore` e supporta `InMemoryNodeRegistry` e `PostgreSQLNodeRegistry`. Il registry include identità Ed25519, scope, capability, idempotenza, conflitto verificabile per chiavi diverse, rotazione, revoca esplicita e protezione contro più chiavi `ACTIVE` per lo stesso nodo.

## PostgreSQL

Sono presenti schema, adapter, transazioni e indice univoco parziale:

```sql
UNIQUE (node_id) WHERE status='ACTIVE'
```

Il test PostgreSQL reale **non è stato eseguito** perché nel sandbox non sono disponibili `postgres`, `psql` o `docker`. Non viene quindi dichiarata un’integrazione end-to-end PostgreSQL.

## Blocker reali

1. Eseguire test su un server PostgreSQL reale con almeno due processi/nodi concorrenti.
2. Verificare restart recovery, durability, conflict rate e rollback sul backend reale.
3. Collegare una gestione persistente delle chiavi e della revoca, senza esportare private key.
4. Decidere una destinazione autorizzata per l’eventuale deploy distribuito.

## Vincoli operativi

Il fabric Internet non è attivo. Non sono state aperte porte pubbliche, acquistati servizi o installate credenziali di produzione. `r3-memory.jsonl` è memoria runtime locale e resta non versionata.
