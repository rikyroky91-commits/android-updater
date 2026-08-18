"""La rete è staccata per tutta la suite, e i due cataloghi grossi arrivano
da fixture registrate dalle fonti vere.

## Il difetto che questo file chiude

`tests/test_niente_rete.py` verifica che UNA ricerca non esca in rete, e lo
fa bene: blocca il socket e guarda. Ma era un'isola. Tutto il resto della
suite girava con la rete aperta, e ci si appoggiava senza dirlo: il
17/08/2026 il database TAC ha risposto `HTTP 429` e sono diventati rossi
test che nessuno aveva toccato — `TestRicercaPerImei`, che non riconosceva
più un IMEI valido, e `TestPrimaLEuropa`, che non trovava più le varianti
regionali. Su un albero pulito, senza una riga cambiata.

Un test che cambia esito perché un server di terzi ha avuto una brutta
giornata non sta misurando questo codice: sta misurando la connessione. E
lo fa nel modo peggiore, perché quando è verde nessuno se ne accorge.

Qui la rete è spenta per tutti, sempre, e un tentativo di uscire dice
esattamente chi stava per contattare chi. Non è un elenco di agganci da
tenere aggiornato — quello invecchierebbe alla prima fonte aggiunta — è il
socket.

## Perché due cataloghi hanno una fixture e gli altri no

Con la rete spenta ogni fonte degrada a «non raggiungibile», ed è lo stato
che quasi tutti i test vogliono: le fonti firmware sono già sostituite da
doppi nei singoli file. Due però non sono fonti, sono ANAGRAFICHE, e senza
di loro metà della suite non collauda più quello che dice di collaudare:

* **i codici modello** (`core/modelcodes.py`): senza, `SM-A546B` non è più
  un Galaxy A54 e sette test cambiano esito — misurati, non temuti;
* **i TAC** (`core/imeicheck.py`): senza, nessun IMEI si riconosce e la
  pagina che i test leggono non ha più niente da dire.

Le fixture sono righe VERE, registrate dalle fonti vere
(`scripts/registra_fixture_cataloghi.py`), nel formato vero — BOM e UTF-16
compresi, che è dove `modelcodes` ha già sbagliato due volte in silenzio.
Un CSV inventato a mano collauderebbe l'immaginazione di chi l'ha scritto.

Un terzo catalogo registrato — quello Xiaomi, con le sue varianti
regionali — NON sta qui: lo usa una classe sola (`TestPrimaLEuropa` in
`tests/test_nome_e_codice.py`), e un catalogo che serve a un file solo si
installa in quel file, come già fanno le altre fonti.

## Quello che il blocco NON fa

Ferma le connessioni, non la risoluzione dei nomi: un `getaddrinfo` esce
ancora (è il motivo per cui nel riepilogo compaiono indirizzi IP e non
solo nomi). Non cambia l'esito di nessun test — senza DNS il download
fallisce comunque, e da lì in poi il percorso è lo stesso — ma vale la
pena saperlo prima di leggere quell'elenco come «tutto fermo».

## L'interruttore

    TEST_CON_RETE=1 pytest tests/

Serve al registratore delle fixture e a chi vuole confrontare il
comportamento con le fonti vive. Non serve alla suite: se un test passa
solo così, è quel test a essere da sistemare.
"""
from __future__ import annotations

import gzip
import os
import socket
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import imeicheck, modelcodes, sources  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
CON_RETE = os.environ.get("TEST_CON_RETE") == "1"

# Chi il blocco ha visto passare, per il riepilogo di fine sessione. Non è
# una lista di colpevoli: molte fonti tentano di uscire apposta, per
# collaudare come degradano. È il modo per accorgersi quando ne compare
# una nuova che nessuno ha sostituito.
TENTATIVI: dict[str, int] = {}

_LOCALI = {"127.0.0.1", "::1", "localhost"}


def _blocca_la_rete() -> None:
    """Ogni connessione in uscita viene annotata e respinta.

    Si intercettano entrambe le porte d'ingresso — `socket.create_connection`
    (la via di `requests`/`urllib3`) e `socket.socket.connect` (quella di
    `urllib.request` e di chiunque scenda più in basso) — perché nel
    progetto convivono i due client: `core/aer_catalog.py` e
    `core/oppo_official.py` usano `urllib`, tutto il resto `requests`.

    Il loopback resta aperto: non è rete di terzi, ed è il pavimento su cui
    poggiano il client di prova di FastAPI e i thread del worker.
    """
    vero_create = socket.create_connection
    vero_connect = socket.socket.connect

    def annota(indirizzo) -> str:
        try:
            return f"{indirizzo[0]}:{indirizzo[1]}"
        except Exception:  # socket unix o indirizzo di forma inattesa
            return str(indirizzo)

    def locale(indirizzo) -> bool:
        try:
            return indirizzo[0] in _LOCALI
        except Exception:
            return False

    def create_connection(address, *args, **kwargs):
        if locale(address):
            return vero_create(address, *args, **kwargs)
        dove = annota(address)
        TENTATIVI[dove] = TENTATIVI.get(dove, 0) + 1
        raise OSError(f"un test ha provato a scaricare da {dove}")

    def connect(self, address, *args, **kwargs):
        if locale(address):
            return vero_connect(self, address, *args, **kwargs)
        dove = annota(address)
        TENTATIVI[dove] = TENTATIVI.get(dove, 0) + 1
        raise OSError(f"un test ha provato a scaricare da {dove}")

    socket.create_connection = create_connection
    socket.socket.connect = connect


# ======================================================================
# I codici modello, dalle righe vere dei due dataset
# ======================================================================
# SI SOSTITUISCE `_download`, NON L'INDICE. È il punto più in basso che
# esiste: sopra di lui restano veri la cache su archivio, i due parser con
# le loro codifiche, la fusione delle due fonti e `reset_cache()`. Se
# invece si semasse l'indice già pronto, il primo test che chiama
# `reset_cache()` — ce ne sono parecchi — se lo ritroverebbe vuoto, e
# fallirebbe per un motivo che non c'entra con quello che verifica.
def _fixture_codici() -> dict[str, bytes]:
    voci = {}
    for url, nome in ((modelcodes.MOBILEMODELS_URL, "codici_mobilemodels.csv"),
                      (modelcodes.GOOGLE_PLAY_URL, "codici_google_play.csv")):
        with open(os.path.join(FIXTURES, nome), "rb") as f:
            voci[url] = f.read()
    return voci


def _download_codici(url: str, source_key: str) -> bytes | None:
    dati = _CODICI.get(url)
    modelcodes._status[source_key] = (
        f"fixture di test ({len(dati) // 1024} KB)" if dati
        else "fonte non prevista nelle fixture di test")
    return dati


# ======================================================================
# I TAC, dall'istantanea che il repository già si porta dietro
# ======================================================================
# `data/tac_era_android.csv.gz` non è una fixture nuova: è la copia della
# base dati principale che l'app usa in produzione quando la rete non
# risponde, registrata dalla fonte vera da
# `scripts/aggiorna_istantanea_tac.py`. Ha lo stesso formato
# `Brand,TAC,SPECS` del download, quindi restituirla da `_download` fa
# percorrere ai test la strada normale — quella che in produzione si
# imbocca quando la fonte c'è — invece del ripiego.
#
# Le fonti SUPPLEMENTARI (il foglio di calcolo, Osmocom, IMEIDB) restano
# assenti: non ci sono a norma di progetto quando la rete manca, hanno i
# loro parser collaudati a parte, e aggiungerle qui significherebbe far
# dipendere l'ordine delle risposte da tre cataloghi invece che da uno.
def _tac_registrati() -> bytes:
    percorso = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "tac_era_android.csv.gz")
    with gzip.open(percorso, "rb") as f:
        return f.read()


def _download_tac() -> bytes:
    imeicheck._status = f"fixture di test ({len(_TAC) // 1024} KB)"
    return _TAC


if not CON_RETE:
    _blocca_la_rete()
    _CODICI = _fixture_codici()
    _TAC = _tac_registrati()
    modelcodes._download = _download_codici
    imeicheck._download = _download_tac
    imeicheck._scarica_url = lambda url, minimo=10_000: None


@pytest.fixture(autouse=True)
def _niente_thread_del_test_precedente():
    """Nessun riscaldamento in volo quando un test comincia.

    `sources._scalda_fonti` avvia il download dei cataloghi a basso costo
    e non lo aspetta (è la correzione dei dodici secondi, vedi il suo
    docstring): ognuno di quei thread apre la propria connessione SQLite
    quando gli serve. Finché le fonti erano lente il thread finiva molto
    prima che il test dopo creasse il suo database temporaneo; con la rete
    staccata ogni download fallisce subito e l'ordine si inverte — il
    thread si sveglia DENTRO il test successivo, apre il database di
    QUELLO, e su Windows quel file non si può più cancellare. Il test
    falliva in `tearDown` con un `PermissionError`, a intermittenza, per
    colpa del test di prima.

    Aspettare qui costa niente quando non c'è niente da aspettare, e
    toglie di mezzo l'intera categoria. Non copre i thread avviati dal
    test stesso: quelli li aspetta chi li avvia, prima di cancellare il
    proprio database (vedi `TestDiagnosticaFonteDistinta` in
    `tests/test_core.py`).
    """
    sources.attendi_riscaldamenti()
    yield


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Chi ha bussato alla rete, e quante volte.

    Non è un errore di per sé — parecchi test staccano la rete APPOSTA per
    verificare che una fonte caduta produca un messaggio leggibile invece
    di un'eccezione. Serve a vedere quando compare un indirizzo nuovo: è il
    segnale che una fonte è stata aggiunta senza un doppio, e che da quel
    momento qualche test dipenderebbe dalla connessione se il blocco non
    ci fosse.
    """
    if CON_RETE or not TENTATIVI:
        return
    terminalreporter.write_sep("-", "rete bloccata: chi ha provato a uscire")
    for dove, quante in sorted(TENTATIVI.items(), key=lambda v: -v[1]):
        terminalreporter.write_line(f"  {quante:5d}  {dove}")
