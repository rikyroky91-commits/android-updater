# L'account amministratore del parco di test

Come funziona e come attivarlo. Stato al 16/08/2026: il codice è in
produzione (commit `84cc964`), `/parco` rimanda già al login, e
`/diagnostica` dice «non configurato» — mancano solo le variabili
d'ambiente su Render.

## Come funziona, prima dei passi

### L'amministratore non si registra: nasce dalle variabili d'ambiente

Non c'è nessuna pagina «crea il primo amministratore», ed è una scelta,
non una dimenticanza: una pagina del genere è aperta a chiunque arrivi
per primo. L'account nasce invece **all'avvio del sito**, letto da tre
variabili impostate su Render:

| Variabile | Cos'è |
|---|---|
| `ADMIN_USERNAME` | il nome con cui farai login |
| `ADMIN_PASSWORD` | la password, almeno 10 caratteri |
| `ADMIN_EMAIL` | solo scritta nella scheda dell'account, **non** serve per accedere e **non** è dove arrivano le richieste |

Servono tutte e tre: se ne manca una, non nasce nessun amministratore e
il parco di test resta inaccessibile. È voluto — meglio un parco chiuso
che un amministratore con credenziali indovinabili.

L'email a cui arrivano le richieste di accesso è un'altra:
`ADMIN_APPROVAL_EMAIL`, che di suo vale già
`Riccardo.cucurullo91@gmail.com` e non va impostata se quella va bene.

### Nasce una volta sola, e questo ha due facce

Il controllo all'avvio è: «esiste già un utente con il flag
amministratore?». Se sì, **non tocca niente** — non ricrea l'account,
non riscrive la password. Serve a non farti tornare alla password
iniziale ogni volta che il piano gratuito si riavvia.

Il rovescio: se il database viene perso e ricreato senza
amministratore, l'account **rinasce con la `ADMIN_PASSWORD` che c'è su
Render in quel momento**. Su Render il disco è effimero e la persistenza
vera è il salvataggio su Gist ogni 30 minuti, quindi succede.

Conseguenza pratica, la cosa più facile da sbagliare:

> Se cambi la password da `/account/password`, **cambia anche
> `ADMIN_PASSWORD` su Render** allo stesso valore. Altrimenti un
> riavvio nel momento sbagliato ti riporta alla password vecchia,
> e tu proverai quella nuova senza capire perché non entra.

Tienile allineate e la domanda non si pone mai.

### Cosa protegge il login, e cosa no

Dietro login c'è **solo** `/parco` (la pagina e le tre azioni: aggiungi,
togli, segna test). Ricerca, dispositivi, aggiornamenti, catalogo,
diagnostica restano pubblici: renderli privati avrebbe tolto lo scopo
del progetto, che è sapere se è uscito un aggiornamento anche senza
avere un account.

Chi non è collegato e apre `/parco` finisce su
`/login?next=/parco`, e dopo il login torna dove voleva andare.

### Le altre persone

Chi vuole un account lo chiede da `/registrati`. L'account nasce subito
ma resta **in attesa**: non entra da nessuna parte finché non lo approvi
tu. Due modi, equivalenti:

* **Dal link nell'email** che arriva a `ADMIN_APPROVAL_EMAIL` — apre una
  pagina con Approva/Rifiuta **senza chiedere il login**, così puoi
  deciderlo dal telefono. Il link vale una volta sola e scade dopo 7
  giorni.
* **Da `/admin/richieste`**, collegato come amministratore. Questa via
  funziona sempre, anche se l'email non parte perché SMTP non è
  configurato. L'email è una comodità, non l'unico canale.

Un rifiuto ha effetto immediato anche su una sessione già aperta: lo
stato dell'account si rilegge dal database a ogni pagina.

### I numeri che ti serviranno

| Cosa | Valore | Si cambia con |
|---|---|---|
| Lunghezza minima password | 10 caratteri | — |
| Tentativi sbagliati prima del blocco | 5 | `LOGIN_MAX_TENTATIVI` |
| Durata del blocco | 15 minuti | `LOGIN_BLOCCO_MINUTI` |
| Durata di una sessione | 12 ore | `SESSIONE_DURATA_ORE` |
| Scadenza del link di approvazione | 7 giorni | `RICHIESTA_ACCESSO_SCADENZA_GIORNI` |

Nessuna regola su maiuscole o simboli: la lunghezza è la difesa che
conta contro un attacco offline, e le regole di complessità spingono
verso password prevedibili («Password1!»). Il blocco vale anche per
l'amministratore: cinque errori e aspetti un quarto d'ora.

## I passi

### 1. Prepara la chiave di firma delle sessioni

`SESSION_SECRET` firma i cookie di sessione. Senza, il sito ne genera
una a caso a ogni avvio: funziona, ma sei disconnesso a ogni riavvio del
piano gratuito — cioè spesso.

Generane una **tua**, da terminale:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Non usare la stringa che trovi scritta in
`guida-configurazione-render.md`: è passata da una conversazione. Una
generata adesso sul tuo computer no.

### 2. Imposta le variabili su Render

[dashboard.render.com](https://dashboard.render.com) → il servizio
`mobile-update-tracker` → scheda **Environment** → **Add Environment
Variable**, una alla volta:

| Nome | Valore |
|---|---|
| `ADMIN_USERNAME` | quello che vuoi, es. `riccardo` |
| `ADMIN_EMAIL` | la tua email |
| `ADMIN_PASSWORD` | una password tua, almeno 10 caratteri, non usata altrove |
| `SESSION_SECRET` | la stringa generata al passo 1 |

Poi **Save Changes** in fondo alla pagina. Render riavvia da solo, 1-2
minuti.

Una nota sullo username: scegline uno che **non** avresti usato per
registrarti come utente normale. Se quel nome risulta già preso da un
account non amministratore, l'account admin non viene creato — e la
diagnostica te lo dice a chiare lettere invece di far finta di niente.

### 3. Controlla che sia arrivato, prima di provare a entrare

Apri `https://android-updater.onrender.com/diagnostica` e cerca nella
tabella «Cataloghi» la riga **Amministratore parco di test**. Dice cosa
è successo all'ultimo avvio:

| Cosa leggi | Cosa significa | Cosa fare |
|---|---|---|
| `creato (riccardo)` | tutto a posto, l'account esiste | vai al passo 4 |
| `già presente` | l'account c'era già da un avvio precedente | vai al passo 4 |
| `non configurato (...)` | manca almeno una delle tre variabili | ricontrolla di aver premuto Save Changes e che il deploy sia finito |
| `ADMIN_PASSWORD non valida: ...` | la password non rispetta il minimo | mettine una di almeno 10 caratteri, senza spazi ai bordi |
| `ADMIN_USERNAME «x» è già di un account non amministratore` | quel nome è di un utente normale | scegli un altro `ADMIN_USERNAME` |
| `non riuscito: ...` | guasto imprevisto | il testo dell'errore è lì; il resto del sito funziona lo stesso |

Questa riga esiste apposta per rispondere senza dover prima provare a
fare login, cioè senza dover indovinare se il problema è la password o
la configurazione.

### 4. Entra

`https://android-updater.onrender.com/login`, con `ADMIN_USERNAME` e
`ADMIN_PASSWORD`. Finisci su `/parco`, ora protetto.

In testata compare il tuo nome, con accanto **richieste** (solo per
l'amministratore), **password** e **Esci**.

### 5. Facoltativo: l'email delle richieste

Senza, tutto funziona: le richieste restano visibili su
`/admin/richieste`. Se la vuoi davvero, aggiungi su Render:

| Nome | Valore |
|---|---|
| `SMTP_USERNAME` | un indirizzo Gmail |
| `SMTP_PASSWORD` | una **password per le app** di quell'account |

La password per le app si genera su
[myaccount.google.com](https://myaccount.google.com) → Sicurezza →
Verifica in due passaggi → Password per le app. **Non** è la password
normale dell'account Google, e Gmail rifiuta quella normale.

Questo pezzo non è mai stato provato contro un server SMTP vero (le
sessioni che l'hanno scritto non avevano accesso di rete a Gmail): il
primo test vero è qui.

### 6. Prova il giro completo

1. Da un altro browser, o in incognito, vai su `/registrati` e crea un
   account di prova.
2. Se hai fatto il passo 5, dovrebbe arrivarti l'email con il link.
3. In ogni caso, da amministratore vai su `/admin/richieste`: la
   richiesta è lì.
4. Approvala, e verifica che quell'account entri in `/parco`
   dall'altro browser.

Se salti questa prova, il primo collaudo dell'approvazione sarà con una
persona vera che aspetta.

## Se qualcosa non torna

**«Nome utente o password non corretti» ma sei sicuro della password.**
Guarda `/diagnostica`: se dice `creato (...)` a un avvio recente, la
password in vigore è quella che c'è ora in `ADMIN_PASSWORD` su Render,
non quella che hai cambiato da `/account/password`. È il caso descritto
sopra.

**«Troppi tentativi non riusciti».** Cinque errori bloccano l'account
per 15 minuti, e vale anche con la password giusta. Aspetta.

**Ti disconnette da solo di continuo.** Manca `SESSION_SECRET`: la
chiave di firma cambia a ogni riavvio e i cookie di prima non valgono
più.

**Hai perso una password.** Vedi la sezione qui sotto: dal 16/08/2026 ci
sono tre vie, una per ogni situazione.

## Recuperare una password

### Se a perderla è una persona qualsiasi

Due strade, e la seconda funziona sempre:

1. **Da sola, con l'email** — va su `/password-dimenticata`, scrive il
   proprio indirizzo e riceve un link che vale una volta sola e scade
   dopo 2 ore. **Richiede SMTP configurato** (passo 5 sopra): senza, la
   pagina risponde normalmente ma non parte niente. Il modulo dice la
   stessa cosa anche quando l'indirizzo non corrisponde a nessuno — di
   proposito: distinguere i due casi lo trasformerebbe in un modo per
   scoprire chi ha un account qui dentro.
2. **Gliela generi tu** — da `/admin/utenti` (in testata: **account**)
   c'è un pulsante «Genera link di recupero» accanto a ogni persona. Il
   link **compare a schermo**, non parte per email: lo copi e glielo dai
   come preferisci. È la via che funziona anche senza SMTP, cioè quella
   che ti serve oggi.

In entrambi i casi, chi usa il link sceglie una password nuova e viene
anche **sbloccato** se si era chiuso fuori a forza di tentativi
sbagliati — altrimenti sarebbe un recupero che non fa recuperare niente.
Le sessioni aperte altrove con la password vecchia smettono di valere:
è quello che si vuole, se il motivo del recupero è il sospetto che
qualcun altro sia entrato.

Un link nuovo annulla quello di prima: due link vivi insieme vorrebbero
dire che il più vecchio, magari in una casella che quella persona non
controlla più, apre ancora l'account.

### Se a perderla sei tu

Qui non c'è nessuno che possa generarti un link — sei tu che li generi —
e l'email non serve, perché non è mai stata verificata e quindi non
dimostra chi sei. Resta una prova d'identità più forte di un'email: **chi
può scrivere nelle variabili d'ambiente di Render controlla già il
servizio**.

Su Render, scheda Environment:

1. Cambia `ADMIN_PASSWORD` con la password nuova che vuoi.
2. Aggiungi `ADMIN_PASSWORD_RESET` con valore `true`.
3. Save Changes, e aspetta il riavvio.
4. Su `/diagnostica`, la riga «Amministratore parco di test» deve dire
   `password di «godadmin» reimpostata da ADMIN_PASSWORD_RESET`.
5. Entra con la password nuova.
6. **Togli `ADMIN_PASSWORD_RESET`.** Lasciata accesa, ogni riavvio
   riporterebbe la password a quella della variabile, cancellando ogni
   cambio fatto da `/account/password`. La diagnostica te lo ricorda
   nella riga stessa, finché non la togli.

Serve l'azione esplicita a due tempi proprio per questo: senza la
variabile, un riavvio non tocca mai la password: è il comportamento
normale, e va difeso.
