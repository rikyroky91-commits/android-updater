"""Persistenza del database fra un riavvio e l'altro.

IL PROBLEMA. Su Streamlit Cloud il disco è effimero: a ogni riavvio, o
dopo una sospensione per inattività, il file del database sparisce e
l'archivio riparte da zero. Per un tracker che serve a rispondere «cosa è
cambiato dall'ultima volta», perdere lo storico è la cosa peggiore che
possa succedere — ed è successo davvero, con il catalogo tornato a zero
dispositivi da un'apertura all'altra.

LA SCELTA. L'alternativa più ovvia sarebbe passare a un database gestito
(Postgres). È però una riscrittura di tutte le query — 41 segnaposto,
espressioni di data specifiche di SQLite, `INSERT OR REPLACE`,
`AUTOINCREMENT` — su codice che oggi funziona e che 193 test verificano.
Molto lavoro, molte occasioni di rompere qualcosa.

Qui si fa invece una cosa più semplice e reversibile: il database resta
SQLite, esattamente com'è, e il FILE viene sincronizzato su un archivio
esterno. All'avvio si scarica l'ultimo salvataggio, a fine scansione si
ricarica. Nessuna query cambia, nessun test cambia, e se un giorno si
volesse davvero Postgres questa strada non lo impedisce.

BACKEND SUPPORTATI, in ordine di preferenza:
  1. Gist GitHub privato (basta un token, nessun servizio da attivare)
  2. Qualsiasi URL HTTP con PUT/GET (S3, Backblaze, WebDAV…)
  3. Nessuno: l'app funziona lo stesso, ma senza memoria fra i riavvii

Nulla di tutto questo è obbligatorio: senza configurazione il modulo resta
inerte e l'applicazione si comporta come prima.
"""
from __future__ import annotations

import base64
import gzip
import json
import os
import threading
import time
from datetime import datetime, timezone

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

from . import cifratura, config as C
from . import storage
from .util import libera_memoria

_GIST_FILENAME = "tracker-db.sqlite.gz"
_lock = threading.Lock()
_stato = {"ultimo_esito": "non configurato", "ultimo_salvataggio": None,
          "ultimo_ripristino": None, "ultima_operazione": None,
          "ultima_operazione_ok": None, "byte": 0}


def stato() -> dict:
    """Diagnostica leggibile, per la scheda Diagnostica."""
    return dict(_stato)


def _esito(operazione: str, ok: bool | None, messaggio: str) -> None:
    """Memorizza l'esito insieme al tipo di operazione che lo ha prodotto.

    Il ripristino viene tentato automaticamente all'avvio e puo' fallire per
    un motivo temporaneo senza impedire al backup di salvare. La Diagnostica
    deve quindi poterlo distinguere dal fallimento di un salvataggio.
    """
    _stato["ultimo_esito"] = messaggio
    _stato["ultima_operazione"] = operazione
    _stato["ultima_operazione_ok"] = ok


def configurato() -> bool:
    return bool(C.env("BACKUP_GIST_ID") and C.env("BACKUP_GITHUB_TOKEN")) or bool(
        C.env("BACKUP_URL")
    )


def _headers_github() -> dict:
    return {
        "Authorization": f"Bearer {C.env('BACKUP_GITHUB_TOKEN')}",
        "Accept": "application/vnd.github+json",
        "User-Agent": C.USER_AGENT,
    }


# ----------------------------------------------------------------------
# Salvataggio
# ----------------------------------------------------------------------
def _istantanea_coerente(percorso: str) -> bytes:
    """Copia del database sicura da salvare, anche a scritture in corso.

    Leggere `tracker.db` con `open()` NON è sicuro quando il giornale è in
    modalità WAL: le transazioni recenti stanno in `tracker.db-wal` e non
    ancora nel file principale. Una copia grezza cattura quindi un
    database a metà — che al ripristino diventa «database disk image is
    malformed».

    `VACUUM INTO` invece delega a SQLite la produzione di uno snapshot
    coerente, tenendo conto del giornale e delle transazioni in volo. È il
    modo previsto dalla libreria per fare esattamente questo.
    """
    destinazione = percorso + ".snapshot"
    if os.path.exists(destinazione):
        os.remove(destinazione)
    try:
        conn = storage.connect()
        conn.execute("VACUUM INTO ?", (destinazione,))
        with open(destinazione, "rb") as f:
            return f.read()
    except Exception:
        # SQLite troppo vecchio per VACUUM INTO, o snapshot non riuscito:
        # si ripiega sulla copia grezza, che è comunque meglio di nessun
        # backup. Prima però si consolida il giornale nel file principale,
        # così la copia è la più completa possibile.
        try:
            storage.connect().execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception:
            pass
        with open(percorso, "rb") as f:
            return f.read()
    finally:
        if os.path.exists(destinazione):
            os.remove(destinazione)


def _archivio_senza_contenuto() -> bool:
    """True se non c'è proprio niente da salvare.

    Si guardano le tre cose che non si ricostruiscono da sole o che
    costano tempo: gli aggiornamenti raccolti, il parco di test e le
    fotografie di collaudo. Se sono tutte vuote, questo archivio non può
    che essere più povero di quello che sostituirebbe.
    """
    try:
        conn = storage.connect()
        for tabella in ("updates", "watchlist", "test_baseline"):
            if conn.execute(f"SELECT 1 FROM {tabella} LIMIT 1").fetchone():
                return False
    except Exception:
        # Nel dubbio si salva: un salvataggio in più non fa danni, uno in
        # meno può costare lo storico.
        return False
    return True


def _istantanea_illeggibile(dati: bytes, percorso: str) -> str | None:
    """None se questi byte sono un database leggibile, altrimenti il motivo.

    Il controllo passa da un file temporaneo perché SQLite legge da disco:
    è un costo trascurabile rispetto al caricamento in rete che segue, e
    l'alternativa è scoprire il guasto solo al ripristino, cioè quando i
    dati locali non ci sono più.
    """
    if not dati:
        return "istantanea vuota"
    prova = percorso + ".verifica"
    try:
        with open(prova, "wb") as f:
            f.write(dati)
        return storage.integrita_file(prova)
    except OSError as exc:
        return f"verifica non riuscita: {exc}"
    finally:
        try:
            os.remove(prova)
        except OSError:
            pass


def istantanea_compressa() -> tuple[bytes | None, str]:
    """`(gzip del database, errore)` — per lo scaricamento da parte
    dell'amministratore (`web/account.py::scarica_backup`).

    Riusa `_istantanea_coerente`, la stessa che prepara il salvataggio
    esterno: quella funzione esiste perche' copiare un file SQLite mentre
    qualcuno ci scrive dentro produce un archivio corrotto in modo
    silenzioso. Rifarla qui a modo proprio sarebbe il solito secondo
    percorso che risponde diversamente dal primo.

    NON cifra: vedi il docstring della rotta per il perche'.
    """
    percorso = C.DB_PATH
    if not os.path.exists(percorso):
        return None, "database non ancora creato"
    try:
        grezzo = _istantanea_coerente(percorso)
    except Exception as exc:
        return None, f"lettura del database non riuscita: {exc}"
    return gzip.compress(grezzo, compresslevel=6), ""



# ======================================================================
# UN BACKUP NON SOVRASCRIVE MAI UNA COPIA PIENA CON UNA VUOTA
# ======================================================================
# Il 07/09/2026 l'utente segnala che il parco di test e' sparito:
# «settimane fa era pieno di roba, come si e' perso tutto?». La catena
# che porta li' e' questa, e il pezzo grave e' l'ultimo:
#
#   1. il contenitore riparte — su Render `/tmp` si azzera a ogni deploy,
#      a ogni riavvio per memoria, a ogni risveglio dopo il sonno;
#   2. l'avvio prova `ripristina()`, che e' l'unica cosa che rimette i
#      dati al loro posto;
#   3. se quel ripristino NON riesce — chiave scaduta, GitHub
#      irraggiungibile, archivio danneggiato — l'app parte VUOTA, e
#      questa parte e' sempre stata visibile in Diagnostica;
#   4. mezz'ora dopo il salvataggio periodico carica nel Gist il database
#      vuoto, e da quel momento la copia buona non e' piu' l'ultima.
#
# Il passo 4 e' il difetto, e non e' un caso limite: e' il funzionamento
# normale applicato a una situazione anormale. Un archivio di sicurezza
# che sostituisce da solo una copia piena con una vuota non e' un
# archivio di sicurezza — e nessuno se ne accorge, perche' ogni singolo
# salvataggio «riesce».
#
# LA GUARDIA SI MISURA SU QUELLO CHE C'E' NEL GIST, NON SU UN RICORDO
# LOCALE. Ricordare qui quanto pesava l'ultimo salvataggio buono sarebbe
# inutile: quel ricordo vive nello stesso database che si e' appena
# azzerato. L'unico riferimento che sopravvive alla cancellazione e'
# l'archivio remoto stesso.
#: Sotto questa frazione del salvataggio precedente, il nuovo non parte.
#: Meta' e' larga di proposito: la potatura degli aggiornamenti vecchi fa
#: rimpicciolire l'archivio per motivi legittimi, e una guardia che
#: scatta sul rumore verrebbe disattivata dopo il secondo falso allarme.
FRAZIONE_MINIMA_SALVATAGGIO = 0.5
#: Sotto questa dimensione il confronto non si fa: un archivio remoto
#: minuscolo e' un primo salvataggio, non una copia da proteggere.
_BYTE_MINIMI_PER_CONFRONTO = 32 * 1024


def _dimensione_remota() -> tuple[int, str]:
    """Quanto pesa il salvataggio che c'e' adesso nel Gist, in byte.

    `0` quando non c'e' niente da proteggere: nessun Gist configurato,
    primo salvataggio, o GitHub che non risponde. In tutti quei casi la
    guardia si fa da parte — bloccare un salvataggio perche' non si e'
    riusciti a leggere il precedente vorrebbe dire smettere di salvare
    proprio quando la rete e' incerta.
    """
    if not C.env("BACKUP_GIST_ID") or requests is None:
        return 0, ""
    try:
        risposta = requests.get(
            f"https://api.github.com/gists/{C.env('BACKUP_GIST_ID')}",
            headers=_headers_github(), timeout=C.HTTP_TIMEOUT,
        )
    except Exception as exc:
        return 0, f"dimensione precedente non leggibile ({type(exc).__name__})"
    if risposta.status_code != 200:
        return 0, f"dimensione precedente non leggibile (HTTP {risposta.status_code})"
    try:
        file_gist = (risposta.json().get("files") or {}).get(_GIST_FILENAME) or {}
        return int(file_gist.get("size") or 0), ""
    except (ValueError, TypeError, AttributeError):
        return 0, "dimensione precedente non leggibile (risposta inattesa)"


def _crollo_sospetto(nuovo_byte: int) -> str:
    """Il motivo per cui questo salvataggio NON deve partire, o «».

    Il confronto e' fra byte in base64 da una parte e byte compressi
    dall'altra, quindi non e' esatto: il base64 gonfia di un terzo. E'
    voluto — la soglia lavora sugli ordini di grandezza, e sbagliare
    dalla parte del «non sovrascrivo» e' l'errore giusto da fare.
    """
    remota, nota = _dimensione_remota()
    if nota or remota < _BYTE_MINIMI_PER_CONFRONTO:
        return ""
    # Il contenuto caricato e' base64 del compresso: ~4/3 dei byte.
    stimato = nuovo_byte * 4 // 3
    if stimato >= remota * FRAZIONE_MINIMA_SALVATAGGIO:
        return ""
    return (f"salvataggio ANNULLATO per sicurezza: l'archivio da caricare "
            f"({stimato // 1024} KB) e' molto piu' piccolo di quello gia' "
            f"presente ({remota // 1024} KB). Di solito vuol dire che "
            f"l'applicazione e' ripartita senza i suoi dati e sta per "
            f"sovrascrivere la copia buona con una vuota. Controlla in "
            f"Diagnostica se il ripristino all'avvio e' riuscito; se il "
            f"contenuto attuale e' giusto e la riduzione voluta, usa "
            f"«Salva adesso» che passa oltre questo controllo")


def salva(forza: bool = False) -> tuple[bool, str]:
    """Carica il database sull'archivio esterno.

    Il file viene compresso: un database di qualche megabyte scende a
    poche centinaia di kilobyte, il che conta perché i Gist hanno un
    limite di dimensione e la banda non è gratuita.
    """
    if not configurato():
        messaggio = "nessun archivio configurato"
        _esito("salvataggio", False, messaggio)
        return False, messaggio
    if requests is None:  # pragma: no cover
        messaggio = "libreria 'requests' non disponibile"
        _esito("salvataggio", False, messaggio)
        return False, messaggio

    percorso = C.DB_PATH
    if not os.path.exists(percorso):
        messaggio = "database non ancora creato"
        _esito("salvataggio", False, messaggio)
        return False, messaggio

    with _lock:
        try:
            grezzo = _istantanea_coerente(percorso)
        except Exception as exc:
            messaggio = f"lettura del database non riuscita: {exc}"
            _esito("salvataggio", False, messaggio)
            return False, messaggio

        # UN ARCHIVIO VUOTO NON SI CARICA MAI SOPRA UNO PIENO.
        #
        # Da quando l'archivio si ripara da solo, un file illeggibile
        # diventa un file VALIDO e VUOTO — che è la cosa giusta da fare in
        # locale, e la peggiore da caricare: il salvataggio esterno è
        # l'unica copia dello storico, e sostituirlo con il vuoto lo
        # cancella per sempre. È il danno che questo modulo esiste per
        # evitare, arrivato dalla porta di servizio.
        #
        # Un archivio vuoto non ha niente da proteggere, quindi non
        # salvarlo non costa nulla; il primo salvataggio utile avviene
        # dopo la prima scansione, che è comunque a un'ora di distanza.
        if _archivio_senza_contenuto():
            messaggio = ("archivio locale vuoto: salvataggio saltato per non "
                         "sovrascrivere lo storico esterno")
            _esito("salvataggio", False, messaggio)
            return False, messaggio

        # E SI CONTROLLA ANCHE PRIMA DI CARICARE.
        #
        # L'altra metà del giro: un archivio esterno guasto ci finisce
        # perché qualcuno ce lo ha scritto. `_istantanea_coerente` ripiega
        # sulla copia grezza quando `VACUUM INTO` non è disponibile, ed è
        # esattamente la copia che può risultare incoerente. Meglio non
        # salvare, e dirlo, che sostituire un salvataggio buono con uno
        # rotto — perché il salvataggio buono è l'unica copia dello storico.
        guasto = _istantanea_illeggibile(grezzo, percorso)
        if guasto:
            messaggio = (f"istantanea non valida ({guasto}): salvataggio annullato "
                         "per non sovrascrivere l'ultima copia buona")
            _esito("salvataggio", False, messaggio)
            return False, messaggio

        compresso = gzip.compress(grezzo, compresslevel=6)
        # E IL DATABASE IN CHIARO SI LASCIA ANDARE SUBITO.
        #
        # Da qui in poi serve solo `compresso`, ma `grezzo` — il database
        # intero, decine di megabyte — restava in memoria per tutta la
        # durata del caricamento, mentre accanto crescevano la copia
        # base64 e il corpo JSON della richiesta. Tre copie dello stesso
        # archivio nello stesso momento, ogni mezz'ora, su un servizio da
        # 512 MB: è uno dei picchi che portavano al riavvio per memoria
        # esaurita segnalato il 31/08/2026.
        del grezzo

        # SI CIFRA DOPO AVER COMPRESSO, mai prima: il testo cifrato non ha
        # ridondanza da comprimere, quindi l'ordine inverso gonfierebbe il
        # file invece di ridurlo.
        #
        # Se la chiave e' impostata ma qualcosa non va, il salvataggio si
        # FERMA: caricare in chiaro un archivio che qualcuno ha chiesto di
        # cifrare sarebbe il tipo di degrado silenzioso che nessuno nota
        # finche' non conta (vedi core/cifratura.py).
        if cifratura.attiva():
            compresso, errore_cifratura = cifratura.cifra(compresso)
            if compresso is None:
                _esito("salvataggio", False, errore_cifratura)
                return False, errore_cifratura

        _stato["byte"] = len(compresso)

        # L'ULTIMO CONTROLLO PRIMA DI SOVRASCRIVERE. Vedi il commento
        # sopra `FRAZIONE_MINIMA_SALVATAGGIO`: e' il passo 4 della catena
        # che il 07/09/2026 ha fatto sparire il parco di test.
        #
        # `forza` esiste perche' una riduzione puo' essere voluta, e una
        # guardia senza via d'uscita si finisce per toglierla. Ma la via
        # d'uscita e' un gesto esplicito di una persona, non il
        # comportamento automatico di ogni mezz'ora.
        if not forza:
            crollo = _crollo_sospetto(len(compresso))
            if crollo:
                _esito("salvataggio", False, crollo)
                return False, crollo

        if C.env("BACKUP_GIST_ID"):
            ok, messaggio = _salva_su_gist(compresso)
        else:
            ok, messaggio = _salva_su_url(compresso)

        _esito("salvataggio", ok, messaggio)
        if ok:
            _stato["ultimo_salvataggio"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        # E SI RESTITUISCE AL SISTEMA QUELLO CHE QUESTO GIRO HA CONSUMATO.
        #
        # Questa funzione è il momento più affamato di tutta la giornata:
        # il database intero, la sua copia compressa, quella in base64 e il
        # corpo della richiesta esistono tutti nello stesso minuto.
        # Misurato su un archivio di 20 MB: 43,6 MB di picco, e dopo
        # `gc.collect()` erano ancora 43,6 — le arene restano al processo.
        # Ogni mezz'ora, tutta la notte, il pavimento saliva e non
        # riscendeva mai. Vedi `core/util.libera_memoria`.
        _stato["memoria_restituita_mb"] = libera_memoria()
        return ok, messaggio


def _salva_su_gist(dati: bytes) -> tuple[bool, str]:
    # I Gist accettano solo testo: il binario compresso viaggia in base64.
    contenuto = base64.b64encode(dati).decode("ascii")
    if len(contenuto) > 50 * 1024 * 1024:
        return False, f"database troppo grande per un Gist ({len(contenuto) // 1024 // 1024} MB)"
    quanti_kb = len(dati) // 1024
    # PROVATO A COSTRUIRE IL CORPO A MANO, ED È PEGGIO. Sembrava ovvio che
    # preparare il JSON qui — liberando la stringa base64 prima di spedire
    # — costasse meno che lasciarlo fare a `requests` con `json=`.
    # Misurato invece, campionando la memoria ogni 5 ms durante un
    # salvataggio da 19,3 MB:
    #
    #     con `json=` (questo)      +35,6 MB di picco
    #     con `data=` costruito a mano  +74,0 MB
    #
    # `requests` serializza in modo più parsimonioso di così, e il `del`
    # anticipato non recupera quello che il doppio passaggio
    # `dumps` → `encode` costa. La riga resta com'era, e il commento
    # esiste perché qualcuno non rifaccia la stessa prova credendola nuova.
    try:
        risposta = requests.patch(
            f"https://api.github.com/gists/{C.env('BACKUP_GIST_ID')}",
            headers=_headers_github(),
            json={"files": {_GIST_FILENAME: {"content": contenuto}}},
            timeout=C.HTTP_TIMEOUT + 45,
        )
    except Exception as exc:
        return False, f"connessione fallita: {exc}"
    if risposta.status_code != 200:
        return False, f"GitHub ha risposto {risposta.status_code}: {risposta.text[:120]}"
    return True, f"salvato ({quanti_kb} KB compressi)"


def _salva_su_url(dati: bytes) -> tuple[bool, str]:
    try:
        risposta = requests.put(
            C.env("BACKUP_URL"), data=dati,
            headers={"Content-Type": "application/octet-stream",
                     "User-Agent": C.USER_AGENT},
            timeout=C.HTTP_TIMEOUT + 45,
        )
    except Exception as exc:
        return False, f"connessione fallita: {exc}"
    if risposta.status_code not in (200, 201, 204):
        return False, f"l'archivio ha risposto {risposta.status_code}"
    return True, f"salvato ({len(dati) // 1024} KB compressi)"


# ----------------------------------------------------------------------
# Ripristino
# ----------------------------------------------------------------------
def ripristina(solo_se_mancante: bool = True,
               revisione: str = "") -> tuple[bool, str]:
    """Scarica il database dall'archivio esterno.

    `solo_se_mancante` protegge dal caso peggiore: sovrascrivere un
    database locale già popolato con una copia più vecchia. All'avvio il
    file non esiste (disco effimero) e il ripristino è quello che serve;
    in ogni altra situazione si preferisce non toccare nulla.

    `revisione` SERVE QUANDO L'ULTIMA COPIA E' QUELLA SBAGLIATA, ed e' il
    caso che il 07/09/2026 non aveva via d'uscita: il parco di test era
    sparito, il Gist conteneva ormai il salvataggio del database vuoto, e
    il ripristino automatico — che legge solo l'ultima versione e solo se
    l'archivio manca — non poteva fare niente. Le versioni precedenti
    c'erano sempre state (vedi `revisioni`), ma nessuna riga di codice
    sapeva chiederle.

    PRIMA DI SOVRASCRIVERE SI METTE DA PARTE QUELLO CHE C'E'. Un
    ripristino da una revisione sbagliata sarebbe un secondo disastro
    sopra il primo, e senza copia non ci sarebbe modo di tornare indietro.
    """
    if not configurato():
        messaggio = "nessun archivio configurato"
        _esito("ripristino", False, messaggio)
        return False, messaggio
    if requests is None:  # pragma: no cover
        messaggio = "libreria 'requests' non disponibile"
        _esito("ripristino", False, messaggio)
        return False, messaggio

    percorso = C.DB_PATH
    if solo_se_mancante and os.path.exists(percorso) and os.path.getsize(percorso) > 4096:
        messaggio = "database locale già presente: ripristino non necessario"
        _esito("ripristino", None, messaggio)
        return False, messaggio

    with _lock:
        if C.env("BACKUP_GIST_ID"):
            dati, messaggio = _leggi_da_gist(revisione)
        elif revisione:
            messaggio = "le revisioni esistono solo per i Gist"
            _esito("ripristino", False, messaggio)
            return False, messaggio
        else:
            dati, messaggio = _leggi_da_url()

        if dati is None:
            _esito("ripristino", False, messaggio)
            return False, messaggio

        # Un archivio in chiaro torna da qui immutato: i salvataggi fatti
        # prima che la cifratura esistesse devono continuare a
        # ripristinarsi, ed e' l'intestazione a distinguerli.
        dati, errore_cifratura = cifratura.decifra(dati)
        if dati is None:
            _esito("ripristino", False, errore_cifratura)
            return False, errore_cifratura

        try:
            grezzo = gzip.decompress(dati)
        except Exception as exc:
            messaggio = f"archivio scaricato ma non decomprimibile: {exc}"
            _esito("ripristino", False, messaggio)
            return False, messaggio

        # Scrittura atomica: un'interruzione a metà lascerebbe un database
        # corrotto, che è peggio di un database assente.
        temporaneo = percorso + ".tmp"
        try:
            with open(temporaneo, "wb") as f:
                f.write(grezzo)
                f.flush()
                os.fsync(f.fileno())

            # SI CONTROLLA LA COPIA PRIMA DI INSTALLARLA.
            #
            # È la correzione che chiude il giro. Finora il ripristino
            # scriveva qualunque cosa avesse scaricato, e se l'archivio
            # esterno conteneva una copia danneggiata — cosa possibile per
            # ogni salvataggio fatto prima della v39, quando l'istantanea
            # era una copia grezza di un database in modalità WAL — quella
            # copia tornava al suo posto **a ogni avvio**.
            #
            # Il risultato era un guasto che si ripresentava da solo dopo
            # ogni riparazione: si riparava all'avvio, si ripristinava
            # subito dopo il file rotto, e ogni pagina falliva di nuovo.
            # Riavviare a mano non serviva a niente, perché il giro
            # ricominciava identico.
            guasto = storage.integrita_file(temporaneo)
            if guasto:
                messaggio = (
                    f"il salvataggio nell'archivio esterno è danneggiato ({guasto}): "
                    "NON è stato installato. L'archivio locale resta quello che era; "
                    "il prossimo salvataggio sovrascriverà la copia guasta con una buona."
                )
                _esito("ripristino", False, messaggio)
                return False, messaggio

            # PRIMA di sostituire il file: chiudere le connessioni aperte e
            # cancellare i giornali della base dati VECCHIA.
            #
            # È la causa del «database disk image is malformed» che
            # compariva ogni tanto. In modalità WAL, accanto a `tracker.db`
            # vivono `tracker.db-wal` e `tracker.db-shm`, che contengono le
            # transazioni non ancora consolidate. Sostituendo solo il `.db`,
            # quei due file restavano lì — riferiti a un database che non
            # esiste più — e al primo accesso SQLite provava ad applicarli
            # sopra il file nuovo. Il risultato è un'immagine incoerente.
            #
            # Lo stesso vale per le connessioni già aperte: continuavano a
            # puntare al file precedente mentre sotto veniva sostituito.
            storage.reset_state()
            for coda in ("-wal", "-shm", "-journal"):
                giornale = percorso + coda
                if os.path.exists(giornale):
                    os.remove(giornale)

            # QUELLO CHE C'ERA SI METTE DA PARTE, NON SI BUTTA. Un
            # ripristino dalla revisione sbagliata sarebbe un secondo
            # disastro sopra il primo, e senza questa copia non ci sarebbe
            # modo di tornare indietro: il file appena sovrascritto era
            # l'unica cosa rimasta. Costa un raddoppio temporaneo dello
            # spazio e vale ogni byte.
            if os.path.exists(percorso):
                try:
                    os.replace(percorso, percorso + ".prima-del-ripristino")
                except OSError:  # pragma: no cover - meglio proseguire
                    pass

            os.replace(temporaneo, percorso)
        except OSError as exc:
            messaggio = f"scrittura del database non riuscita: {exc}"
            _esito("ripristino", False, messaggio)
            return False, messaggio
        finally:
            if os.path.exists(temporaneo):
                os.remove(temporaneo)

        messaggio = f"ripristinato ({len(grezzo) // 1024} KB)"
        _esito("ripristino", True, messaggio)
        _stato["ultimo_ripristino"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return True, messaggio



# ======================================================================
# LE VERSIONI PRECEDENTI DEL SALVATAGGIO
# ======================================================================
# Il 07/09/2026 l'utente segnala che il parco di test e' vuoto: «settimane
# fa era pieno di roba, come si e' perso tutto?». L'archivio vive in
# `/tmp` su Render e sopravvive solo grazie a questo backup; se un
# ripristino all'avvio non riesce, l'app riparte vuota e il salvataggio
# periodico — che gira ogni mezz'ora — scrive nel Gist il database VUOTO,
# seppellendo la copia buona.
#
# Seppellendo, non cancellando: `_salva_su_gist` fa una `PATCH`, e GitHub
# conserva la storia completa di un Gist. Ogni salvataggio e' una
# revisione, e quelle di settimane fa ci sono ancora tutte. Mancava solo
# una riga di codice che sapesse chiederle — il ripristino automatico
# legge l'ultima versione, che in questo scenario e' proprio quella
# sbagliata.
def revisioni(quante: int = 30) -> tuple[list[dict], str]:
    """`([{sha, quando, byte, chi}], errore)` — la storia del Gist.

    Dalla piu' recente. I byte sono quelli del file base64 dentro il
    Gist, non del database: servono a RICONOSCERE la revisione giusta, ed
    e' esattamente il salto di dimensione a tradire il salvataggio del
    database vuoto.
    """
    if not C.env("BACKUP_GIST_ID"):
        return [], "le revisioni esistono solo per i Gist"
    if requests is None:  # pragma: no cover
        return [], "libreria 'requests' non disponibile"
    try:
        risposta = requests.get(
            f"https://api.github.com/gists/{C.env('BACKUP_GIST_ID')}",
            headers=_headers_github(), timeout=C.HTTP_TIMEOUT + 30,
        )
    except Exception as exc:
        return [], f"connessione fallita: {exc}"
    if risposta.status_code != 200:
        return [], f"GitHub ha risposto {risposta.status_code}"
    try:
        storia = risposta.json().get("history") or []
    except ValueError:
        return [], "risposta di GitHub in forma inattesa"

    elenco = []
    for voce in storia[:max(1, quante)]:
        cambi = voce.get("change_status") or {}
        elenco.append({
            "sha": str(voce.get("version") or ""),
            "quando": str(voce.get("committed_at") or ""),
            "byte": int(cambi.get("additions") or 0),
            "chi": ((voce.get("user") or {}) or {}).get("login") or "",
        })
    return [v for v in elenco if v["sha"]], ""


def _leggi_da_gist(revisione: str = "") -> tuple[bytes | None, str]:
    """Il salvataggio dal Gist; con `revisione`, quella versione precisa.

    OGNI SALVATAGGIO E' UNA REVISIONE, e questa e' la cosa che ha reso
    recuperabile il disastro del 07/09/2026. `_salva_su_gist` fa una
    `PATCH`, e GitHub conserva la storia completa: la copia buona di
    settimane fa non e' stata cancellata dai salvataggi successivi, e'
    solo finita sotto. Senza questo parametro l'unica cosa leggibile era
    l'ultima versione — cioe' proprio quella vuota.
    """
    indirizzo = f"https://api.github.com/gists/{C.env('BACKUP_GIST_ID')}"
    if revisione:
        indirizzo += f"/{revisione}"
    try:
        risposta = requests.get(
            indirizzo,
            headers=_headers_github(), timeout=C.HTTP_TIMEOUT + 30,
        )
    except Exception as exc:
        return None, f"connessione fallita: {exc}"
    if risposta.status_code != 200:
        return None, f"GitHub ha risposto {risposta.status_code}"
    try:
        file_gist = risposta.json()["files"].get(_GIST_FILENAME)
    except (ValueError, KeyError, AttributeError):
        return None, "risposta di GitHub in forma inattesa"
    if not file_gist:
        return None, "nessun salvataggio presente nel Gist"

    contenuto = file_gist.get("content")
    # I Gist grandi arrivano troncati: in quel caso il contenuto va preso
    # dal raw_url, altrimenti si scriverebbe un database incompleto.
    if file_gist.get("truncated") and file_gist.get("raw_url"):
        try:
            grezzo = requests.get(file_gist["raw_url"], timeout=C.HTTP_TIMEOUT + 45)
            contenuto = grezzo.text if grezzo.status_code == 200 else contenuto
        except Exception:
            pass
    if not contenuto:
        return None, "salvataggio vuoto"
    try:
        return base64.b64decode(contenuto), "ok"
    except Exception as exc:
        return None, f"contenuto non decodificabile: {exc}"


def _leggi_da_url() -> tuple[bytes | None, str]:
    try:
        risposta = requests.get(C.env("BACKUP_URL"), timeout=C.HTTP_TIMEOUT + 45)
    except Exception as exc:
        return None, f"connessione fallita: {exc}"
    if risposta.status_code == 404:
        return None, "nessun salvataggio presente"
    if risposta.status_code != 200:
        return None, f"l'archivio ha risposto {risposta.status_code}"
    return risposta.content, "ok"


# ----------------------------------------------------------------------
# Salvataggio periodico
# ----------------------------------------------------------------------
# None = non si è ancora salvato in questa esecuzione. Va distinto da 0.0:
# con un contatore azzerato il primo salvataggio verrebbe scambiato per
# «appena fatto» e saltato, e il primissimo dopo l'avvio non avverrebbe mai.
_ultimo_tentativo: float | None = None


def salva_se_serve(intervallo_minuti: int | None = None) -> None:
    """Salva, ma non più spesso del necessario.

    Chiamata a fine di ogni scansione: senza un intervallo minimo si
    caricherebbe l'intero database a ogni giro, sprecando banda e
    consumando il limite di chiamate dell'archivio.
    """
    global _ultimo_tentativo
    if not configurato():
        return
    minuti = intervallo_minuti if intervallo_minuti is not None else C.BACKUP_EVERY_MINUTES
    if _ultimo_tentativo is not None and (time.monotonic() - _ultimo_tentativo) < minuti * 60:
        return
    _ultimo_tentativo = time.monotonic()
    salva()


# ----------------------------------------------------------------------
# Salvataggio subito dopo una modifica fatta da una persona
# ----------------------------------------------------------------------
# PERCHÉ NON «A OGNI CLICK», che era la richiesta letterale. Ogni
# salvataggio ricarica l'INTERO database: oggi 5,7 MB compressi, che in
# base64 diventano circa 7,6 MB per invio (vedi `_salva_su_gist`). Un
# invio per click significherebbe spedirli di nuovo per ogni nota
# scritta, ogni allegato, ogni «Segna test» — su un piano gratuito da
# 512 MB, con la scansione che gira in sottofondo, è proprio il peso che
# la richiesta voleva evitare.
#
# Quello che serviva davvero è che una modifica non possa restare fuori
# dal salvataggio per mezz'ora. Qui una modifica ALZA UNA BANDIERINA, e
# un thread la raccoglie entro `RITARDO_SALVATAGGIO` secondi: dieci
# modifiche di fila diventano un invio solo invece di dieci, e la più
# vecchia ha comunque aspettato meno di un minuto.
#
# La scansione NON alza la bandierina: scrive in continuazione e
# terrebbe il salvataggio sempre acceso. Per lei resta
# `salva_se_serve()` con il suo intervallo di mezz'ora, che è il ritmo
# giusto per dati che si riscaricano da soli.
RITARDO_SALVATAGGIO = 60

_da_salvare = threading.Event()
_fermare = threading.Event()
_thread_salvataggio: threading.Thread | None = None


def segna_modificato() -> None:
    """Da chiamare dopo una modifica fatta da una persona (una nota, un
    allegato, un test segnato, un account approvato). Non salva: dice che
    c'è qualcosa da salvare, e torna subito — chi ha cliccato non deve
    aspettare un invio di rete per vedere la propria pagina."""
    _da_salvare.set()


def _ciclo_salvataggio() -> None:
    while not _fermare.is_set():
        # Aspetta una modifica; se non arriva niente, si sveglia comunque
        # ogni tanto per accorgersi di `_fermare` senza restare appesa.
        if not _da_salvare.wait(timeout=5):
            continue
        # Una modifica c'è. Si concede la finestra di raggruppamento
        # PRIMA di salvare: è quella che unisce una raffica di click in un
        # invio solo. Se nel frattempo arriva l'ordine di fermarsi, si
        # salva subito invece di aspettare la fine della finestra.
        _fermare.wait(timeout=RITARDO_SALVATAGGIO)
        _da_salvare.clear()
        try:
            salva()
        except Exception:  # pragma: no cover - un guasto di rete non ferma il thread
            pass


def avvia_salvataggio_continuo() -> str:
    """Accende il thread. Il testo torna in STATO_AVVIO, come gli altri
    passi dell'avvio."""
    global _thread_salvataggio
    if not configurato():
        return "non attivo: nessun archivio configurato"
    if _thread_salvataggio and _thread_salvataggio.is_alive():
        return "già attivo"
    _fermare.clear()
    _thread_salvataggio = threading.Thread(
        target=_ciclo_salvataggio, name="salvataggio-continuo", daemon=True)
    _thread_salvataggio.start()
    return f"attivo (salva entro {RITARDO_SALVATAGGIO}s da una modifica)"


def ferma_salvataggio_continuo(attesa: float = 30.0) -> None:
    """All'arresto del servizio: sveglia il thread, che salva subito se
    ha una modifica in sospeso invece di portarsela via. Render manda un
    SIGTERM prima di spegnere, quindi questa finestra esiste davvero."""
    _fermare.set()
    if _thread_salvataggio and _thread_salvataggio.is_alive():
        _thread_salvataggio.join(timeout=attesa)


# ----------------------------------------------------------------------
# Preparazione assistita
# ----------------------------------------------------------------------
def verifica_token(token: str) -> tuple[bool, str]:
    """Controlla che il token esista e abbia il permesso giusto.

    Vale la pena farlo prima di tentare qualsiasi altra cosa: un token
    senza il permesso «gist» produrrebbe un errore molto più avanti, e
    molto più difficile da ricondurre alla causa.
    """
    if requests is None:  # pragma: no cover
        return False, "libreria 'requests' non disponibile"
    token = (token or "").strip()
    if not token:
        return False, "nessun token indicato"
    try:
        risposta = requests.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {token}",
                     "Accept": "application/vnd.github+json",
                     "User-Agent": C.USER_AGENT},
            timeout=C.HTTP_TIMEOUT,
        )
    except Exception as exc:
        return False, f"connessione a GitHub fallita: {exc}"
    if risposta.status_code == 401:
        return False, "token non valido o scaduto"
    if risposta.status_code != 200:
        return False, f"GitHub ha risposto {risposta.status_code}"

    # I token classici dichiarano i permessi in un'intestazione; quelli
    # «fine-grained» no, quindi l'assenza non è di per sé un errore.
    ambiti = risposta.headers.get("x-oauth-scopes", "")
    if ambiti and "gist" not in ambiti:
        return False, (
            f"il token non ha il permesso «gist» (permessi attuali: {ambiti or 'nessuno'})"
        )
    try:
        utente = risposta.json().get("login", "")
    except ValueError:
        utente = ""
    return True, f"token valido{f' (utente {utente})' if utente else ''}"


def crea_archivio(token: str) -> tuple[bool, str, str | None]:
    """Crea da zero il Gist privato dove conservare l'archivio.

    Ritorna `(riuscito, messaggio, id_del_gist)`. Serve a togliere di mezzo
    i passaggi manuali: senza questo bisognerebbe creare il Gist a mano,
    copiarne l'identificativo dall'indirizzo e incollarlo altrove — tre
    occasioni di sbagliare per un'operazione che si fa una volta sola.
    """
    if requests is None:  # pragma: no cover
        return False, "libreria 'requests' non disponibile", None
    ok, messaggio = verifica_token(token)
    if not ok:
        return False, messaggio, None

    try:
        risposta = requests.post(
            "https://api.github.com/gists",
            headers={"Authorization": f"Bearer {token.strip()}",
                     "Accept": "application/vnd.github+json",
                     "User-Agent": C.USER_AGENT},
            json={
                "description": "Mobile Update Tracker — archivio (non modificare a mano)",
                "public": False,
                "files": {_GIST_FILENAME: {"content": "in attesa del primo salvataggio"}},
            },
            timeout=C.HTTP_TIMEOUT + 15,
        )
    except Exception as exc:
        return False, f"connessione a GitHub fallita: {exc}", None
    if risposta.status_code != 201:
        return False, f"GitHub ha risposto {risposta.status_code}: {risposta.text[:120]}", None
    try:
        identificativo = risposta.json()["id"]
    except (ValueError, KeyError):
        return False, "risposta di GitHub in forma inattesa", None
    return True, "archivio creato", identificativo


def prova_completa(gist_id: str, token: str) -> tuple[bool, str]:
    """Salva e rilegge un dato di prova, per confermare che tutto funzioni.

    Verificare la configurazione con una scrittura vera è l'unico modo per
    sapere che funzionerà davvero quando servirà: un errore di permessi si
    scoprirebbe altrimenti solo al primo riavvio, cioè quando i dati sono
    già andati persi.
    """
    if requests is None:  # pragma: no cover
        return False, "libreria 'requests' non disponibile"
    prova = f"prova-{datetime.now(timezone.utc).isoformat(timespec='seconds')}"
    intestazioni = {
        "Authorization": f"Bearer {(token or '').strip()}",
        "Accept": "application/vnd.github+json",
        "User-Agent": C.USER_AGENT,
    }
    try:
        scrittura = requests.patch(
            f"https://api.github.com/gists/{(gist_id or '').strip()}",
            headers=intestazioni,
            json={"files": {"prova-scrittura.txt": {"content": prova}}},
            timeout=C.HTTP_TIMEOUT + 15,
        )
    except Exception as exc:
        return False, f"scrittura non riuscita: {exc}"
    if scrittura.status_code != 200:
        return False, (
            f"scrittura non riuscita ({scrittura.status_code}): "
            "controlla che l'identificativo dell'archivio sia corretto e che il "
            "token abbia il permesso «gist»"
        )

    try:
        lettura = requests.get(
            f"https://api.github.com/gists/{(gist_id or '').strip()}",
            headers=intestazioni, timeout=C.HTTP_TIMEOUT,
        )
        riletto = lettura.json()["files"]["prova-scrittura.txt"]["content"]
    except Exception as exc:
        return False, f"rilettura non riuscita: {exc}"
    if riletto.strip() != prova:
        return False, "il dato riletto non corrisponde a quello scritto"
    return True, "scrittura e rilettura riuscite: l'archivio è pronto"
