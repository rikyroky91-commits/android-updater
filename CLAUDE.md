# Istruzioni per chi lavora su questo repository

Prima di cominciare leggi `PASSAGGIO-CONSEGNE.md`: è il documento di consegna unico per Mobile Update Tracker e Page Brawl (stato, regole, build, deploy, problemi noti).

**Regola fissa:** ogni giro di lavoro che cambia codice, configurazione, versioni, deploy o stato dei rami aggiorna `PASSAGGIO-CONSEGNE.md` nello stesso commit, seguendo la sezione 9 di quel file (data e commit in cima, riga nel registro, tabelle di stato, problemi noti). Se qualcosa non è stato verificato, scrivilo.

Promemoria rapidi (il dettaglio è nel documento):
- mai committare `tracker.db` o altri `.db`, né segreti;
- i test non toccano la rete (`tests/conftest.py`); suite Python e Node verdi prima del push;
- il gioco si modifica solo in `web/static/ring.js` / `lingue.js`, poi `python3 estensione/costruisci.py` e, per l'app, `python3 android/costruisci.py`;
- `DATA_LOGIC_VERSION` in `core/config.py` si alza quando cambia l'interpretazione di una fonte;
- un push su `main` pubblica il sito su Oracle.
