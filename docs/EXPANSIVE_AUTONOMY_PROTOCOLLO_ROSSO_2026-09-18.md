# Analisi EXPANSIVE AUTONOMY — Protocollo Rosso

**Data della misura:** 18 settembre 2026.  
**Repository osservato:** `Rosso-rosso-rosso/protocollo-rosso-bot`.  
**Ramo osservato:** `feat/efficient-routing-cache`.  
**Metodo:** classificazione dei limiti, dual-horizon search, Explore → Prune → Compress e Capability Factory.

## Conclusione esecutiva

Il Protocollo Rosso ha oggi un nucleo locale funzionante, una classificazione epistemica deterministica, persistenza SQLite, un ponte HTTP opzionale verso SDQ-1, cache bounded, identità operativa e memoria append-only locale. Non dispone ancora di una memoria realmente condivisa tra nodi, di un motore multi-agente verificato, di un gate H-001 eseguito né di una pipeline di verifica continua che distingua automaticamente codice canonico, codice candidato e artefatti derivati.

Il blocker più urgente non è la mancanza di “potenza” del modello. È la mancanza di **continuità verificabile end-to-end**. Senza questa base, un modello più forte aumenterebbe soprattutto la quantità di output e il rischio di propagare riferimenti, piani o identità fuori scope.

## Stato misurato

La PR aperta contiene due commit: cache bounded e budget dell’input, seguiti da identità scoped e memoria append-only [1]. I test mirati eseguiti sul ramo passano: 22 test, compilazione Python e controllo `git diff --check`. La suite completa presenta un test UX preesistente fallito perché il testo di aiuto non contiene `/registro`, anche se README, menu e metodo lo dichiarano.

Il codice locale dichiara esplicitamente `agenti: 0` quando usa il nucleo. Il ponte `SDQ1_URL` è opzionale e il repository non contiene un provider LLM verificato come parte del percorso locale. Questa distinzione è corretta e deve rimanere invariata fino a una misura reale.

La memoria attuale è append-only e hash-chained, ma il file è locale. La presenza di `R3_MEMORY_PATH` rende possibile il collegamento futuro a uno storage condiviso autorizzato; non costituisce ancora sincronizzazione multi-nodo.

## Classificazione dei blocker

| Priorità | Blocker | Classe | Stato | Perché è critico |
|---|---|---|---|---|
| P0 | Memoria cross-node non condivisa e senza protocollo di conflitto | `CURRENT_TECH` + `POLICY_AUTHORITY` | Aperto | Il filo tra nodi non è ancora riproducibile; un path condiviso da solo non risolve locking, versioni, permessi e replay. |
| P0 | SDQ-1 multi-agente non dimostrato nel percorso operativo | `EVIDENCE_UNCERTAINTY` | Aperto | Il sistema può essere più veloce, ma non è ancora più potente in senso misurato. |
| P1 | Test H-001 non eseguito | `EVIDENCE_UNCERTAINTY` | Aperto | Non sappiamo se scope gate, provenance e change-set completeness riducano davvero false adoption e riferimenti orfani. |
| P1 | Codice, documentazione e suite UX divergenti su `/registro` | `INTERFACE_PRODUCT` | Aperto | L’utente riceve un contratto incoerente; la suite non rappresenta più l’interfaccia dichiarata. |
| P1 | Nessun CI gate sulla PR | `CURRENT_TECH` | Aperto | La PR è aperta senza check automatici registrati; regressioni possono arrivare a `main`. |
| P2 | Continuità di processo dipendente da long polling e keepalive | `INTERFACE_PRODUCT` + `ECONOMIC_RESOURCE` | Parzialmente gestito | Il bot può dormire o perdere disponibilità se l’infrastruttura non mantiene il processo attivo. |
| P2 | Cache piani solo `LINK-ONLY`, senza retrieval operativo verificato | `CURRENT_TECH` | Parzialmente implementato | La struttura esiste, ma non è ancora collegata a un planner/validator che dimostri guadagno. |

## Dual-horizon search

### P0-A — Memoria condivisa con provenance

**Current-tech path.** Mantenere l’hash-chain locale come fonte append-only e aggiungere un adapter esplicito verso uno storage autorizzato. Ogni evento deve includere `source_project`, `source_node`, `permission_scope`, versione dello schema, autore, timestamp, confidence, evidenze e relazioni. Il nodo deve rifiutare eventi con scope non ammesso, catena rotta o versione incompatibile.

**Capability-horizon path.** Costruire un **Memory Fabric Router** che riceva pacchetti firmati logicamente, verifichi provenienza e scope, deduplichi per hash, rilevi conflitti e proponga `LINK-ONLY`, `ADAPT` o `REJECT`. Non deve adottare automaticamente materiale cross-project.

**First prototype.** Due nodi simulati, uno storage condiviso temporaneo e 100 eventi: 80 validi, 10 duplicati, 5 con scope incompatibile, 5 con catena rotta.

**Falsification test.** Il prototipo fallisce se accetta un evento fuori scope, perde la provenienza, duplica un hash o non produce un rollback riproducibile.

**Expected gain.** Continuità tra nodi senza trasformare la memoria in una fonte unica non auditabile.

### P0-B — Motore potente ma parsimonioso

**Current-tech path.** Conservare il routing in cascata: regole/cache locali, modello piccolo per estrazione e classificazione, modello medio per casi ambigui, modello forte solo per ragionamento e verifica. Ogni risultato deve usare schema strutturato, budget massimo, confidence e fallback.

**Capability-horizon path.** Costruire un **Evidence-Aware Planner** che riusi piani verificati, separi intent statico da contesto dinamico e chieda al modello forte soltanto la parte non risolta. La ricerca sull’Agentic Plan Caching indica che riuso e adattamento di piani possono ridurre costo e latenza, ma il risultato deve essere replicato sul workload R3 prima di diventare un claim [2].

**First prototype.** Dataset di 50 richieste R3 sintetiche e annotate. Confrontare baseline full-model, cascade e plan-cache con stesso criterio di correttezza.

**Falsification test.** Scartare la capacità se il costo diminuisce ma aumentano adozioni errate, riferimenti orfani o risposte non attribuibili.

**Expected gain.** Meno token e latenza senza ridurre auditabilità.

### P1-A — H-001 e gate di adozione

**Current-tech path.** Eseguire H-001 in sandbox su due workstream: artefatto presente nel source ma assente nel target e file nuovo nel target. Misurare baseline contro metodo con scope gate, preflight, diff completeness, provenance e rollback.

**Capability-horizon path.** Costruire un **Candidate Patch Verifier** che produca un report strutturato e non modifichi repository. La decisione di merge deve restare separata e autorizzata dal proprietario del progetto.

**Criterio di successo.** Zero adozioni canoniche automatiche di riferimenti estranei, 100% dei change-type inclusi nel perimetro dichiarato, provenance ricostruibile e rollback riuscito.

**Falsification test.** Se il verifier assume oggetti inesistenti o non vede file nuovi, il metodo è respinto e ridotto a `LINK-ONLY`.

### P1-B — Contratto prodotto e CI

**Current-tech path.** Allineare `/registro` tra handler, menu, README, help e test. Aggiungere CI per installazione dipendenze, suite completa, compileall e diff check.

**Capability-horizon path.** Introdurre un **Contract Linter** che confronti comandi dichiarati in README/menu/Telegram con gli handler registrati e apra una failure precisa quando divergono.

**First prototype.** Estrarre automaticamente i comandi da `main.py`, `menu_rrr.py`, `texts.py`, README e test; confrontare gli insiemi.

**Falsification test.** Il linter deve rilevare `/registro` nel momento in cui è dichiarato ma non esposto nella help o non coperto dal test.

## Explore → Prune → Compress

Sono state considerate quattro architetture: memoria condivisa immediata, semantic cache globale, plan cache scoped e planner multi-agente completo. La memoria condivisa immediata è stata scartata perché un file condiviso senza protocollo di conflitto crea race e perdita di provenance. La semantic cache globale è stata scartata come primo passo perché può confondere richieste semanticamente simili ma con scope, versione o contesto diversi. Il planner multi-agente completo è stato rinviato perché manca un benchmark e un provider verificato.

Restano tre capacità prioritarie: **Memory Fabric Router**, **Evidence-Aware Planner** e **Candidate Patch Verifier**. Sono sufficientemente concrete, reversibili e testabili.

## Capability Factory

### `CAP-R3-001` — Memory Fabric Router

- **Current limit:** memoria locale non sincronizzata.
- **Desired capability:** collegare nodi autorizzati preservando hash, scope e provenance.
- **Observable function:** accetta, deduplica, rifiuta o collega un evento con motivo verificabile.
- **Input:** pacchetto evento append-only.
- **Output:** `ACCEPT`, `DUPLICATE`, `REJECT_SCOPE`, `REJECT_CHAIN`, `LINK-ONLY`.
- **Security boundary:** nessun bypass di credenziali o permessi.
- **Horizon:** H0 prototipo locale; H1 storage condiviso autorizzato.
- **Status:** SPECIFIED, non implementato end-to-end.

### `CAP-R3-002` — Evidence-Aware Planner

- **Current limit:** cache piani non collegata a planner e validator.
- **Desired capability:** riusare piani verificati solo quando intent, scope, versione e contesto sono compatibili.
- **Observable function:** produce piano candidato con confidence ed evidenze.
- **Input:** intent, contesto, scope, versione.
- **Output:** piano, evidenze, decisione e fallback.
- **Security boundary:** nessuna adozione automatica cross-project.
- **Horizon:** H0 dataset sintetico; H1 provider LLM verificato.
- **Status:** SCAFFOLD, test comparativo necessario.

### `CAP-R3-003` — Candidate Patch Verifier

- **Current limit:** H-001 non eseguito e nessun gate automatico.
- **Desired capability:** verificare completezza e reversibilità prima di ogni proposta.
- **Observable function:** elenca diff, riferimenti orfani, conflitti, permessi e rollback.
- **Input:** source, target, candidate patch.
- **Output:** report strutturato e decisione proposta.
- **Security boundary:** read-only per default.
- **Horizon:** H0 sandbox; H1 CI e review umana.
- **Status:** SPECIFIED, priorità P1.

## Ordine di esecuzione raccomandato

1. **Correggere il contratto `/registro` e attivare CI.** È il lavoro più piccolo e rimuove una divergenza già osservata.
2. **Eseguire H-001 in sandbox.** Senza questa misura non va ampliata la propagazione cross-project.
3. **Implementare `CAP-R3-001` con due nodi simulati.** Solo dopo il test si valuta uno storage condiviso reale.
4. **Costruire il benchmark per `CAP-R3-002`.** Misurare token, latenza, correttezza, provenance e rollback.
5. **Collegare provider LLM e routing a cascata soltanto dopo la baseline.** La potenza deve essere misurata, non dedotta dal nome del modello.

## Decisione

Il Protocollo Rosso non è bloccato da un limite fisico o logico dimostrato. È bloccato soprattutto da **evidenza incompleta, continuità non condivisa, contratti incoerenti e assenza di gate automatici**. Questi sono blocker di ingegneria e governance, non motivi per concludere che la capacità desiderata sia impossibile.

La priorità non è rendere Raffaello più assertivo. È renderlo più capace di distinguere, collegare e verificare senza perdere l’origine. Una volta misurata questa base, l’espansione verso memoria condivisa, piani riutilizzabili e modelli più forti diventa controllabile.

## References

[1]: https://github.com/Rosso-rosso-rosso/protocollo-rosso-bot/pull/1 "PR #1 — bounded cache, scoped identity and append-only node memory"

[2]: https://arxiv.org/html/2506.14852v2 "Agentic Plan Caching: Test-Time Memory for Fast and Cost-Efficient LLM Agents"
