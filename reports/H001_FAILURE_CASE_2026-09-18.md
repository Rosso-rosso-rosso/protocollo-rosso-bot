# H-001 — Failure case

La baseline copia una regola presente solo nel source (`foreign_rule.txt`) nel target e non copre il file nuovo `new_relevant_file.txt`.

Il metodo H rifiuta l’adozione canonica, registra source/destination/scope, include i change type e verifica che il target non cambi; quindi il rollback è riproducibile.
