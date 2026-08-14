"""Il sito: FastAPI più pagine HTML, sopra lo stesso `core` di sempre.

## Cosa cambia rispetto alla versione Streamlit, e cosa no

**Non cambia niente sotto.** Le fonti, i livelli di fiducia, il database,
la logica di retest, i test: tutto identico. `core/` non importa questo
modulo e non sa che esiste, esattamente come non sapeva di Streamlit — era
già una scelta presa (sta scritta in `core/config.py`), e qui si incassa.

**Cambia chi scrive l'HTML.** Con Streamlit il DOM lo generava lui e per
dargli una forma bisognava indovinare dall'esterno come aveva annidato i
suoi `div`, con che nomi, in quella versione: ogni errore non dava un
errore, dava un pezzo di pagina rimasto indietro in silenzio. Qui l'HTML
è nei template, il CSS è nostro, e il file consegnato dal disegno smette
di essere un riferimento da reinterpretare e diventa il modello.

## Come sono divise le cose

    core/            i dati e le fonti          — non tocca il web
    web/presenters   dati → testo leggibile     — nessuna rete, si collauda
    web/templates    testo → HTML               — nessuna decisione
    web/main         le rotte                   — nessuna formattazione

Un template che decide quando una data si scrive «rilevato 3 giorni fa» è
codice, solo scritto in un posto dove non si può collaudare. Per questo
qui i template ricevono dizionari già pronti.

## Il lavoro di sfondo

La scansione periodica continua a girare in un thread, come prima. Su un
host che addormenta il servizio quando nessuno lo visita, quel thread
dorme con lui: è la stessa condizione di Streamlit Community Cloud, ed è
il motivo per cui il salvataggio su Gist esiste già.
"""
from __future__ import annotations

import os
import shutil
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import (HTMLResponse, JSONResponse, RedirectResponse,
                               Response)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from core import aer_catalog, aiquery, appledevices, config as C
from core import extract, imeicheck, modelcodes, retest, scan, soc, sources, specs
from core import storage, suggest, versus
from core.util import fmt_date, fmt_relative, truncate

from . import presenters as P
from .cache import CacheATempo

RADICE = Path(__file__).resolve().parent

# La memoria corta delle ricerche. Vedi `web/cache.py` per i numeri che
# l'hanno motivata: una ricerca costa fino a tredici secondi di rete, e
# due ricerche identiche ne costavano ventisei.
RICERCHE = CacheATempo(C.SEARCH_CACHE_SECONDS, C.SEARCH_CACHE_MAX)

# Quante righe finiscono nella tabella dei dispositivi. Il taglio vive
# QUI e non nel template, perché è il taglio a decidere quante righe si
# costruiscono: nel template arrivava dopo, a lavoro già fatto.
IN_PAGINA = 200

@asynccontextmanager
async def ciclo_di_vita(app: FastAPI):
    avvio()
    yield


app = FastAPI(title=C.APP_TITLE, docs_url=None, redoc_url=None,
              lifespan=ciclo_di_vita)
app.mount("/static", StaticFiles(directory=RADICE / "static"), name="static")
templates = Jinja2Templates(directory=str(RADICE / "templates"))
templates.env.globals["fmt_relative"] = fmt_relative
templates.env.globals["truncate"] = truncate
templates.env.globals["fmt_date"] = fmt_date


# ======================================================================
# Avvio
# ======================================================================
STATO_AVVIO: dict = {}


def avvio() -> None:
    """L'ORDINE QUI DENTRO NON È INDIFFERENTE.

    Il ripristino deve precedere `init_db`, che crea un database vuoto se
    il file non c'è: a quel punto il ripristino non avverrebbe più —
    vedrebbe un archivio «già presente» e si asterrebbe per non
    sovrascrivere dati locali con una copia più vecchia. Ed è la stessa
    sequenza della versione Streamlit, perché il problema è dell'archivio,
    non dell'interfaccia.

    ## Due difetti trovati qui il 2026-08-10

    **Il ripristino non è mai avvenuto.** Questa funzione chiamava
    `backup.ripristina_se_serve()`, che in `core/backup.py` NON ESISTE:
    la funzione si chiama `ripristina()`. L'`AttributeError` finiva in un
    `except Exception: pass` e spariva. Su un host con il disco effimero
    l'effetto è preciso e invisibile: a ogni risveglio l'archivio
    ripartiva vuoto, e il salvataggio su Gist — che esiste apposta per
    questo — non veniva letto nemmeno una volta.

    **Due manutenzioni giravano solo altrove.** `migra_chiavi_dispositivo`
    e `purge_retired_sources` erano nella dashboard e nel worker, non
    qui. È l'errore 41 del passaggio consegne — «ciò che gira in un
    percorso d'avvio e non nell'altro vale a metà» — ripetuto sul terzo
    percorso, che nel frattempo è diventato quello principale.

    Nulla di tutto questo è più silenzioso: ogni passo lascia scritto
    cosa ha fatto in `STATO_AVVIO`, che la Diagnostica mostra.
    """
    from core import backup

    STATO_AVVIO.clear()
    corrotto = storage.ripara_se_corrotto()
    if corrotto:
        STATO_AVVIO["archivio riparato"] = f"copia guasta messa da parte in {corrotto}"

    # L'ARCHIVIO ESTERNO PER PRIMO: è la copia più recente che esista.
    if backup.configurato():
        try:
            ok, nota = backup.ripristina(solo_se_mancante=True)
            STATO_AVVIO["archivio esterno"] = nota
        except Exception as errore:      # una fonte esterna non deve bloccare l'avvio
            STATO_AVVIO["archivio esterno"] = f"non riuscito: {errore}"
    else:
        STATO_AVVIO["archivio esterno"] = "non configurato"

    STATO_AVVIO["copia di partenza"] = _semina_archivio()

    storage.init_db()
    rimossi = storage.rebuild_if_logic_changed()
    if rimossi:
        STATO_AVVIO["ricostruzione"] = (
            f"{rimossi} aggiornamenti riletti con la logica {C.DATA_LOGIC_VERSION}")
    storage.migra_chiavi_dispositivo()
    try:
        storage.purge_retired_sources([s.key for s in sources.all_sources()])
    except Exception as errore:  # pragma: no cover - percorso difensivo
        STATO_AVVIO["pulizia fonti"] = f"non riuscita: {errore}"
    if C.env_bool("AVVIA_WORKER", True):
        scan.start_background_worker()
    # Il preriscaldamento tiene insieme in RAM cataloghi enormi mentre la
    # scansione può caricarne altri: sul piano Render da 512 MB è un picco
    # evitabile. È opt-in per chi dispone di memoria sufficiente.
    if C.PRERISCALDA_CATALOGHI:
        _scalda_i_cataloghi()


def _scalda_i_cataloghi() -> None:
    """Carica i cataloghi pesanti in sottofondo, prima che serva.

    QUARANTOTTO SECONDI, misurati sul sito vero dopo un deploy: è quanto
    ha impiegato la PRIMA visita a `/dispositivi`. Non era la pagina —
    era il catalogo delle specifiche che si scaricava e si analizzava
    (1,6 MB compressi, 4766 schede) mentre qualcuno aspettava, perché la
    tabella risolve il processore di ogni riga e il processore passa di
    lì. Chi apriva per primo pagava per tutti, e concludeva che il sito
    era rotto.
    """
    import threading

    def scalda():
        # L'ordine è quello del costo: prima il più caro, che è anche
        # quello che la tabella dei dispositivi aspetta.
        # Il worker ha appena avviato le sue fonti: lasciargli qualche
        # secondo evita i picchi di RAM/rete che su Render portavano al
        # riavvio. Il sito intanto e' gia' disponibile per schede curate e
        # TAC locali, che non aspettano questo thread.
        import time
        time.sleep(max(0, C.PRERISCALDA_ATTESA_SECONDI))
        passi = (
            ("schede tecniche", specs.carica),
            ("codici modello", lambda: modelcodes.resolve("SM-S921B")),
            ("processori", lambda: soc.per_modello("SM-S921B")),
            ("catalogo aziendale", aer_catalog.carica),
        )
        for nome, carica in passi:
            try:
                carica()
                STATO_AVVIO[f"catalogo «{nome}»"] = "pronto"
            except Exception as errore:  # un catalogo in meno, non un guasto
                STATO_AVVIO[f"catalogo «{nome}»"] = f"non caricato: {errore}"

    # `daemon` perché non deve trattenere la chiusura del processo, e in
    # un thread perché l'avvio non deve aspettarlo: se la prima visita
    # arriva mentre sta ancora scaldando, paga come prima — ma è la
    # prima visita dopo un deploy, non tutte.
    threading.Thread(target=scalda, name="scalda-cataloghi", daemon=True).start()


# La copia dell'archivio che viaggia dentro l'immagine. La aggiorna ogni
# ora il workflow di GitHub Actions, che esegue una scansione e committa
# `tracker.db`: al momento della build è quindi vecchia al massimo di
# un'ora.
COPIA_DI_PARTENZA = RADICE.parent / "tracker.db"

# Sotto questa soglia un file non è un archivio popolato ma lo scheletro
# vuoto che SQLite crea da sé.
_ARCHIVIO_MINIMO = 64 * 1024


def _semina_archivio() -> str:
    """Se non c'è nessun archivio, si parte da quello del repository.

    PERCHÉ SERVE. Su Render il disco è effimero e `DB_PATH` sta in
    `/tmp`: a ogni risveglio l'applicazione ripartiva da zero
    dispositivi, e restava così finché una scansione intera non fosse
    finita — mezzo minuto buono — riscaricando nel frattempo una
    ventina di megabyte di cataloghi che nel file committato ci sono
    già. Chi apriva il sito in quella finestra vedeva un archivio vuoto
    e concludeva che il sito era rotto.

    Non è un ripiego del salvataggio su Gist, che resta la persistenza
    vera: questo interviene solo quando quello non c'è o non ha
    risposto, e non sovrascrive mai un archivio esistente.
    """
    percorso = C.DB_PATH
    if os.path.exists(percorso) and os.path.getsize(percorso) > _ARCHIVIO_MINIMO:
        return "non serviva: un archivio c'era già"
    if not COPIA_DI_PARTENZA.exists():
        return "nessuna copia nell'immagine"
    # SI CONTROLLA PRIMA DI INSTALLARE, come fa il ripristino esterno: una
    # copia illeggibile installata all'avvio fa fallire ogni pagina.
    guasto = storage.integrita_file(str(COPIA_DI_PARTENZA))
    if guasto:
        return f"copia del repository illeggibile ({guasto}): ignorata"
    try:
        os.makedirs(os.path.dirname(os.path.abspath(percorso)) or ".", exist_ok=True)
        shutil.copyfile(COPIA_DI_PARTENZA, percorso)
    except OSError as errore:
        return f"copia non riuscita: {errore}"
    return (f"partito dalla copia del repository "
            f"({os.path.getsize(percorso) // 1024} KB)")


def _rendi(request: Request, pagina: str, contesto: dict):
    """UNA SOLA FIRMA PER TUTTE LE PAGINE.

    Starlette ha cambiato l'ordine degli argomenti di `TemplateResponse`
    (prima la richiesta, poi il nome del template) e la forma vecchia non
    dà un errore chiaro: prova a usare il dizionario come chiave di cache
    e muore con «unhashable type». Passandoci da un punto solo, il giorno
    che cambia ancora si corregge qui.
    """
    return templates.TemplateResponse(request, pagina, contesto)


def _contesto(request: Request, **extra) -> dict:
    """Quello che serve a OGNI pagina: testata, stato fonti, ricerca."""
    stati = storage.get_source_status()
    base = {
        "titolo_sito": "Mobile Update Tracker",
        "sottotitolo": "Quale aggiornamento è arrivato, su quale modello, quando.",
        "fonti_ok": sum(1 for s in stati if s.get("ok")),
        "fonti_totali": len(stati),
        "ai_attiva": aiquery.disponibile(),
        "ai_verifica_attiva": bool(
            aiquery.fornitore() and aiquery.fornitore()[0] == "Gemini"),
        "query": "",
        "attiva": "",
        "verifica_ai": None,
    }
    base.update(extra)
    return base


# ======================================================================
# Pagine
# ======================================================================
@app.head("/")
def radice_head():
    """Un controllo di vita, non una pagina.

    Ha una funzione TUTTA SUA invece di stare sulla rotta `GET`, e la
    ragione è nel corpo che non ha: `HEAD` chiede solo se il servizio
    risponde. Appenderlo alla rotta normale vorrebbe dire interrogare
    l'archivio e costruire duecento righe per poi buttare via l'HTML —
    una scansione del database ogni pochi minuti, per sempre.
    """
    return Response(status_code=200)


@app.get("/", response_class=HTMLResponse)
def pagina_ricerca(request: Request, q: str = Query(default=""),
                    ai: str = Query(default=""),
                    alt: list[str] = Query(default=[]),
                    perche: str = Query(default=""),
                    verifica_ai: str = Query(default=""),
                    parco: int = Query(default=0),
                    saved: int = Query(default=0)):
    """La home, e la pagina di un modello cercato.

    SENZA DOMANDA È LA SOLA BARRA DI RICERCA. Prima qui c'era anche
    l'elenco di millecinquecento dispositivi, e le due cose si davano
    fastidio: la ricerca — che è il motivo per cui si apre il sito —
    stava schiacciata sopra una tabella che nessuno aveva chiesto, e la
    tabella si faceva pagare anche da chi voleva solo digitare un
    modello. L'elenco ora ha una pagina sua.

    CON UNA DOMANDA è la pagina di quel telefono: cosa dicono le fonti
    adesso, la scheda tecnica, gli aggiornamenti che ha ricevuto.
    """
    stats = storage.stats()
    domanda = q.strip()
    if not domanda:
        return _rendi(request, "home.html", _contesto(
            request, attiva="cerca", query="", stats=stats,
            archivio_vuoto=not stats.get("devices"),
        ))

    # L'IMEI PRIMA DI TUTTO. Quindici cifre non sono né un nome né un
    # codice modello: passarle a `search_model` significa cercare un
    # telefono che si chiama «867051060315467», e trovarne zero. Va prima
    # riconosciuto, ridotto al TAC (le prime otto cifre) e tradotto in un
    # modello; solo allora si cerca il firmware.
    imei = None
    if imeicheck.is_imei_like(domanda):
        imei = _esito_imei_salvato(domanda) if saved else _esito_imei(domanda)
        if imei["modello_cercato"]:
            # Un IMEI ha già risolto un'identità precisa dal TAC. La ricerca
            # firmware è informazione aggiuntiva e non può rinominare il
            # telefono con un alias regionale o con una voce errata di una
            # fonte news. Dopo un salvataggio manuale non la avviamo proprio:
            # la conferma deve tornare subito, senza aspettare la rete.
            risultato = (_esito_solo_identita(imei["modello_cercato"])
                         if saved else _esito_ricerca(imei["modello_cercato"]))
            risultato = _ancora_esito_imei(risultato, imei)
        else:
            risultato = _esito_vuoto(domanda)
    else:
        risultato = _esito_ricerca(domanda)

    verifica = None
    if verifica_ai == "1" and aiquery.fornitore() and aiquery.fornitore()[0] == "Gemini":
        contesto = " · ".join(x for x in (
            risultato.get("riga"), risultato.get("fonte"),
            (risultato.get("scheda") or {}).get("fonte"),
        ) if x)
        verifica = aiquery.verifica(risultato.get("nome") or domanda, contesto)

    return _rendi(request, "ricerca.html", _contesto(
        request, attiva="cerca", query=q, stats=stats,
        risultato=risultato, imei=imei, verifica_ai=verifica,
        aggiunto_al_parco=bool(parco),
        # L'INTERPRETAZIONE SI DICHIARA. Se l'AI ha tradotto «quel samsung
        # nero» in «Galaxy A56 5G», chi guarda deve vedere che cosa è
        # stato cercato al posto suo — altrimenti la pagina risponde a una
        # domanda che non ricorda di aver fatto.
        interpretato_da=ai.strip(),
        interpretato_perche=perche.strip(),
        alternative=[a for a in alt if a and a != q][:3],
    ))


@app.get("/confronto", response_class=HTMLResponse)
def pagina_confronto(request: Request, a: str = Query(default=""),
                     b: str = Query(default="")):
    """Due modelli, fianco a fianco.

    NASCE DA UN BUG, non da un capriccio estetico. La domanda "questi due
    nomi sono davvero lo stesso telefono, o due telefoni diversi che si
    somigliano nel nome" è esattamente quella dietro il bug «realme c63
    rispondeva C61» (vedi FONTI.md): lì la confusione veniva dal codice,
    qui la si dà in mano a chi guarda, con un modello alla volta messo
    accanto all'altro invece che indovinato dal sistema.

    Riusa `_esito_ricerca` — la STESSA funzione, la STESSA cache, la
    STESSA ricerca di sempre, chiamata due volte. Nessuna scorciatoia
    parallela che potrebbe rispondere diversamente da una ricerca singola:
    se «RMX3939» risponde una cosa cercato da solo, risponde la stessa
    cosa anche qui.
    """
    confronto = _confronta(a.strip(), b.strip())
    return _rendi(request, "confronto.html", _contesto(
        request, attiva="cerca", query_a=a, query_b=b, confronto=confronto,
    ))


@app.get("/dispositivi", response_class=HTMLResponse)
def pagina_dispositivi(request: Request,
                       filtro: str = Query(default=""),
                       brand: str = Query(default=""),
                       parco: int = Query(default=0),
                       scansione: str = Query(default="")):
    """L'archivio: una riga per telefono, senza interrogare nessuna fonte.

    Il campo `filtro` NON si chiama `q` di proposito. `q` è la ricerca —
    quella che esce in rete e può metterci qualche secondo — e questa
    pagina non la fa: qui si filtra soltanto ciò che è già in archivio.
    Due cose diverse con lo stesso nome finiscono per essere scambiate,
    e la prima volta che succede è nel collegamento di qualcun altro.
    """
    marche = [brand] if brand else None
    devices = storage.get_devices(brands=marche, search=filtro or None)
    if parco:
        devices = [d for d in devices if d.get("watched")]

    # SI COSTRUISCONO SOLO LE RIGHE CHE FINISCONO IN PAGINA.
    #
    # La tabella ne mostra duecento da sempre, ma il taglio stava nel
    # template: le righe si costruivano tutte e millecinquecento, e
    # milletrecento venivano buttate dopo essere state calcolate. Non era
    # lavoro gratis — ogni riga risolve il processore, che è la parte
    # cara: 50 ms contro 5 ms, misurati su questo archivio, su una
    # macchina molto più veloce di quella che serve il sito.
    righe = [P.riga_dispositivo(d) for d in devices[:IN_PAGINA]]
    stats = storage.stats()

    return _rendi(request, "dispositivi.html", _contesto(
        request, attiva="dispositivi", filtro=filtro, brand=brand, parco=parco,
        righe=righe, marche=sorted({d["brand"] for d in devices if d.get("brand")}),
        totale=len(devices), in_pagina=IN_PAGINA, stats=stats,
        scansione_avviata=(scansione == "avviata"),
        archivio_vuoto=not stats.get("devices"),
    ))


@app.get("/aggiornamenti", response_class=HTMLResponse)
def pagina_aggiornamenti(request: Request, giorni: int = Query(default=30)):
    voci = storage.get_updates(only_relevant=True, since_days=giorni, limit=300)
    return _rendi(request, "aggiornamenti.html", _contesto(
        request, attiva="aggiornamenti", giorni=giorni,
        righe=[P.riga_aggiornamento(v) for v in voci],
    ))


@app.get("/parco", response_class=HTMLResponse)
def pagina_parco(request: Request, test_salvato: int = Query(default=0),
                 errore_test: str = Query(default="")):
    parco = storage.get_watchlist()
    baseline = storage.get_test_baselines()
    devices = {d["device_key"]: d for d in storage.get_devices()}

    righe = []
    for voce in parco:
        chiave = voce["device_key"]
        device = devices.get(chiave, {})
        riferimento = baseline.get(chiave)
        # L'ORDINE DEGLI ARGOMENTI CONTA: prima lo stato ATTUALE, poi la
        # fotografia di riferimento. Invertirli non dà errore, dà un
        # confronto capovolto — «tornato indietro» al posto di
        # «aggiornato», che è peggio di non rispondere.
        confronto = retest.confronta(device, riferimento) if device else None
        righe.append({
            "chiave": chiave,
            "modello": voce.get("model") or device.get("model", ""),
            "brand": voce.get("brand") or device.get("brand", ""),
            "provato_il": (fmt_date(riferimento["tested_at"])
                           if riferimento and riferimento.get("tested_at") else None),
            # Il controllo nativo ``date`` vuole YYYY-MM-DD; la baseline
            # conserva invece un istante ISO completo. Tenerli distinti
            # rende modificabile la data senza esporre un orario inutile.
            "data_test": ((riferimento.get("tested_at") or "")[:10]
                           if riferimento and riferimento.get("tested_at")
                           else date.today().isoformat()),
            "puo_segnare_test": bool(device),
            "confronto": confronto,
        })
    messaggi_errore = {
        "data": "Inserisci una data valida per il test.",
        "dispositivo": "Questo modello non ha ancora dati firmware da salvare come riferimento.",
        "parco": "Il modello non risulta piu nel parco di test.",
    }
    return _rendi(request, "parco.html", _contesto(
        request, attiva="parco", righe=righe,
        test_salvato=bool(test_salvato),
        errore_test=messaggi_errore.get(errore_test, ""),
    ))


@app.get("/catalogo", response_class=HTMLResponse)
def pagina_catalogo(request: Request):
    devices = storage.get_devices()
    per_marca: dict[str, int] = {}
    for d in devices:
        if d.get("brand"):
            per_marca[d["brand"]] = per_marca.get(d["brand"], 0) + 1
    righe = [{"marca": marca, "modelli": quanti,
              "nota": sources.nota_copertura(marca) or ""}
             for marca, quanti in sorted(per_marca.items(),
                                         key=lambda kv: -kv[1])]
    return _rendi(request, "catalogo.html", _contesto(
        request, attiva="catalogo", righe=righe,
    ))


def _pagina_diagnostica(request: Request, **extra) -> HTMLResponse:
    """Il corpo comune della pagina Diagnostica — estratto perché le
    rotte del backup (sotto) devono ririsegnare la STESSA pagina con in
    più l'esito dell'azione appena fatta (creazione dell'archivio,
    salvataggio di prova), non un'altra pagina o un semplice redirect
    che perderebbe quel messaggio."""
    stati = storage.get_source_status()
    stats = storage.stats()
    return _rendi(request, "diagnostica.html", _contesto(
        request, attiva="diagnostica",
        righe=[P.riga_fonte(s) for s in stati],
        stats=stats,
        cataloghi=[
            ("Codici modello", modelcodes.status()),
            ("Dispositivi Apple", appledevices.status()),
            ("Catalogo aziendale (AER)", aer_catalog.status()),
            ("Processori", soc.status()),
            ("Specifiche hardware", specs.status()),
            ("Interprete AI della ricerca", aiquery.status()),
        ],
        backup=P.stato_backup(),
        logica=C.DATA_LOGIC_VERSION,
        **extra,
    ))


@app.get("/diagnostica", response_class=HTMLResponse)
def pagina_diagnostica(request: Request):
    return _pagina_diagnostica(request)


@app.post("/diagnostica/backup/crea", response_class=HTMLResponse)
def diagnostica_backup_crea(request: Request, token: str = Form(...)):
    """Crea da zero l'archivio (Gist privato) per il backup, a partire da
    un token GitHub incollato qui — invece dei passaggi manuali (creare
    il Gist a mano, copiarne l'id dall'indirizzo, capire se il token ha
    il permesso giusto solo quando qualcosa fallisce) che sono il modo
    più facile di sbagliare la configurazione.

    Segnalato dall'utente: aveva seguito le istruzioni passo passo per
    la via manuale e la pagina continuava a dire «Non configurato» — il
    sospetto più concreto è che il valore incollato su Render non fosse
    ancora arrivato a questo processo (serve un riavvio del servizio,
    che Render fa da solo dopo il salvataggio, ma non è istantaneo), non
    un errore nella configurazione in sé. Restare in balìa di tre pagine
    diverse (GitHub per il token, GitHub per il Gist, Render per le
    variabili) moltiplica le occasioni di un passaggio saltato o
    frainteso: qui bastano il token e un clic.

    NON PUÒ CONFIGURARE RENDER DA SOLA — l'app non ha né deve avere
    accesso al pannello Render (servirebbe una API key con permessi ben
    più ampi, ingiustificati solo per questo): verifica che il token
    funzioni, crea l'archivio, e lo dice; il passaggio finale — incollare
    i due valori su Render — resta all'utente, con l'identificativo già
    pronto da copiare invece che da andare a cercare nell'indirizzo del
    Gist.

    Il token non si salva da nessuna parte (non nel database, non nei
    log): serve solo per questa chiamata, e passa in un campo
    `type="password"` nel modulo — comunque in chiaro nella richiesta
    HTTP, come qualunque modulo su qualunque sito, ma mai scritto su
    disco da questa funzione.
    """
    from core import backup

    risultato_backup = {"token_valido": None, "gist_creato": None,
                        "prova_riuscita": None, "gist_id": None, "messaggio": ""}
    token_pulito = (token or "").strip()

    ok_token, msg_token = backup.verifica_token(token_pulito)
    risultato_backup["token_valido"] = ok_token
    risultato_backup["messaggio"] = msg_token

    if ok_token:
        ok_gist, msg_gist, gist_id = backup.crea_archivio(token_pulito)
        risultato_backup["gist_creato"] = ok_gist
        risultato_backup["messaggio"] = msg_gist
        risultato_backup["gist_id"] = gist_id

        if ok_gist:
            ok_prova, msg_prova = backup.prova_completa(gist_id, token_pulito)
            risultato_backup["prova_riuscita"] = ok_prova
            risultato_backup["messaggio"] = msg_prova

    return _pagina_diagnostica(request, risultato_backup=risultato_backup)


@app.post("/diagnostica/backup/salva", response_class=HTMLResponse)
def diagnostica_backup_salva(request: Request):
    """«Salva adesso»: forza un salvataggio vero con la configurazione
    ATTUALE (le variabili d'ambiente già impostate), invece di aspettare
    la prossima scansione o correzione — la verifica più diretta per
    sapere se quello che è stato messo su Render funziona davvero, senza
    aspettare un'ora o dover correggere un nome apposta per scoprirlo.
    """
    from core import backup

    ok, messaggio = backup.salva()
    return _pagina_diagnostica(request, risultato_salva={"ok": ok, "messaggio": messaggio})


# LA CHIAVE VA IN QUERY, NON NEL PERCORSO. Le chiavi dispositivo hanno
# dentro barre e barre verticali (`vivo / iqoo / motorola|v29`): in un
# segmento di percorso la barra è un separatore, e l'indirizzo non
# corrisponderebbe mai — un 404 su ogni scheda. Codificarla non basta,
# perché il server decodifica prima di instradare.
@app.get("/dispositivo", response_class=HTMLResponse)
def pagina_dispositivo(request: Request, k: str = Query(default="")):
    chiave = k
    device = next((d for d in storage.get_devices()
                   if d.get("device_key") == chiave), None)
    if device is None:
        return RedirectResponse("/", status_code=303)
    return _rendi(request, "dispositivo.html", _contesto(
        request, attiva="dispositivi",
        device=P.riga_dispositivo(device),
        scheda=P.scheda_tecnica(device["model"],
                                codice=device.get("model_code") or "",
                                brand=device["brand"], device=device),
        storico=[P.riga_aggiornamento(v)
                 for v in storage.get_device_history(chiave)],
    ))


# ======================================================================
# Azioni
# ======================================================================
@app.post("/parco/aggiungi")
def parco_aggiungi(chiave: str = Form(...), brand: str = Form(""),
                   modello: str = Form(""), ritorno: str = Form("")):
    storage.add_to_watchlist(chiave, brand, modello)
    # Il risultato appena visto e' nella cache corta: se non la si svuota,
    # tornando dalla form il pulsante resterebbe «Aggiungi» anche se il
    # telefono e' gia' entrato nel parco.
    RICERCHE.svuota()
    # Il parametro viene dal nostro template, ma non deve mai diventare un
    # redirect verso un dominio esterno se qualcuno costruisce una POST a
    # mano. Accettiamo solo la ricerca locale con la query gia' compilata.
    if ritorno.startswith("/?") and not ritorno.startswith("//"):
        return RedirectResponse(f"{ritorno}&parco=1", status_code=303)
    return RedirectResponse(f"/dispositivo?k={quote(chiave)}", status_code=303)


@app.post("/parco/togli")
def parco_togli(chiave: str = Form(...)):
    storage.remove_from_watchlist(chiave)
    return RedirectResponse(f"/dispositivo?k={quote(chiave)}", status_code=303)


def _istante_test(data_test: str) -> str | None:
    """Converte la sola data scelta nel parco in un istante ISO stabile.

    A mezzogiorno UTC, non a mezzanotte: una data di test non deve slittare
    al giorno precedente/successivo quando viene letta in un fuso diverso.
    """
    try:
        scelta = date.fromisoformat((data_test or "").strip())
    except ValueError:
        return None
    return f"{scelta.isoformat()}T12:00:00+00:00"


@app.post("/parco/segna-test")
def parco_segna_test(chiave: str = Form(...), data_test: str = Form("")):
    """Registra quando il telefono e' stato provato e la baseline attuale.

    La data da sola non basta al parco: il suo scopo e' capire *cosa* e'
    cambiato dal test. PerciÃ² il click salva insieme la versione/build/patch
    che il tracker conosce in quel momento, senza chiedere una seconda form.
    """
    if chiave not in storage.watched_keys():
        return RedirectResponse("/parco?errore_test=parco", status_code=303)
    dispositivo = next((d for d in storage.get_devices()
                        if d.get("device_key") == chiave), None)
    if not dispositivo:
        return RedirectResponse("/parco?errore_test=dispositivo", status_code=303)
    istante = _istante_test(data_test)
    if not istante:
        return RedirectResponse("/parco?errore_test=data", status_code=303)
    storage.set_test_baseline(dispositivo, tested_at=istante)
    # La data del test e' un dato inserito a mano: va nel backup subito,
    # come le correzioni TAC, per non dipendere dalla prossima scansione.
    _backup_subito()
    return RedirectResponse("/parco?test_salvato=1", status_code=303)


def _backup_subito() -> None:
    """Manda SUBITO al Gist esterno una correzione fatta a mano da una
    persona, invece di aspettare il prossimo giro di scansione.

    IL BUG SEGNALATO: «assicurati che quando correggo il nome il
    risultato si salvi perché sembra che non lo faccia». Il salvataggio
    in sé funzionava — la correzione finiva nella tabella `nomi_modello`
    di `tracker.db` — ma quel database vive in `/tmp` (`Dockerfile`,
    `DB_PATH=/tmp/tracker.db`, disco effimero per scelta) e la SOLA copia
    duratura è il backup su Gist, caricato da `backup.salva_se_serve()`
    SOLO a fine di ogni scansione periodica, non più spesso di
    `BACKUP_EVERY_MINUTES` (30 di default — vedi `core/backup.py`). Sul
    piano gratuito il servizio si addormenta dopo ~15 minuti senza
    visite, e il thread di scansione dorme con lui: una correzione fatta
    poco dopo l'ultimo backup periodico può restare SOLO nel database
    locale, e sparire al primo riavvio — che su questo piano è la norma,
    non l'eccezione. Da fuori sembra un salvataggio che «non ha
    funzionato», ma il salvataggio non era mai stato il problema: lo era
    il tempismo del backup.

    Una correzione verificata da una persona è rara e piccola: vale la
    pena caricarla subito, ignorando l'intervallo minimo pensato per i
    backup automatici dopo ogni scansione oraria. Gira in un thread,
    stessa idea di `/scansione`: aspettare la risposta di GitHub dentro
    la richiesta HTTP del modulo di correzione lo farebbe sembrare lento
    per un salvataggio che l'utente non ha bisogno di stare a guardare.

    Se il backup non è configurato (`BACKUP_GIST_ID`/`BACKUP_GITHUB_TOKEN`
    assenti), `backup.salva()` torna semplicemente `False` senza fare
    niente: qui non c'è nulla da controllare prima, e nessun errore da
    mostrare per una funzione che l'utente non ha attivato.
    """
    import threading
    from core import backup

    threading.Thread(target=backup.salva, daemon=True).start()


@app.post("/tac/salva")
def tac_salva(tac: str = Form(...), marca: str = Form(""),
              modello: str = Form(""), imei: str = Form("")):
    """Il modello verificato a mano, salvato dentro l'app.

    È la via d'uscita quando i database TAC non conoscono un telefono, e
    ha la precedenza su ogni database scaricato: se lo hai verificato tu,
    hai ragione tu. Vale per tutti gli IMEI di quel modello, non solo per
    quello digitato.
    """
    imeicheck.aggiungi_tac(tac, marca, modello)
    # LA MEMORIA CORTA VA DIMENTICATA QUI. Hai appena corretto a mano il
    # modello di quel TAC: se la ricerca rispondesse dalla cache, ti
    # rimanderebbe indietro la risposta sbagliata che sei venuto a
    # correggere — e sembrerebbe che il salvataggio non abbia funzionato.
    RICERCHE.svuota()
    # E VA MESSA AL SICURO SUBITO — vedi il docstring di `_backup_subito`.
    _backup_subito()
    return RedirectResponse(f"/?q={quote(imei or tac)}&saved=1", status_code=303)


@app.post("/modello/correggi")
def modello_correggi(codice: str = Form(...), nome: str = Form(""),
                     query: str = Form("")):
    """Il nome commerciale scelto a mano per un codice, salvato dentro l'app.

    Stessa logica di `tac_salva`, applicata al nome invece che al modello
    di un TAC: vedi il commento in `_cerca_davvero` per il perché esiste.
    Un `nome` vuoto cancella la correzione — `storage.set_nome_modello`
    torna alla scelta automatica invece di salvarne una vuota.
    """
    storage.set_nome_modello(codice, nome)
    # STESSA RAGIONE DI `tac_salva`: senza svuotare la memoria corta la
    # ricerca risponderebbe dalla cache col nome di prima, e sembrerebbe
    # che il salvataggio non abbia funzionato.
    RICERCHE.svuota()
    # E VA MESSA AL SICURO SUBITO — vedi il docstring di `_backup_subito`.
    _backup_subito()
    return RedirectResponse(f"/?q={quote(query or codice)}", status_code=303)


@app.post("/scansione")
def scansione():
    """Lancia una scansione e torna subito all'elenco.

    NON SI ASPETTA LA FINE. Una scansione completa dura una trentina di
    secondi: tenere aperta la richiesta HTTP per tutto quel tempo la
    espone al timeout dell'host, e a quel punto l'utente vede un errore
    mentre in realtà la scansione sta andando a buon fine. Parte in un
    thread e la pagina lo dice.
    """
    import threading

    def scansiona_e_dimentica():
        try:
            scan.run_scan(auto_notify=True)
        finally:
            # A scansione finita l'archivio è cambiato: le risposte
            # ricordate descrivono lo stato di prima. Si buttano, così
            # chi ha appena premuto «Scansiona adesso» vede il risultato
            # di quella scansione e non quello che c'era un minuto fa.
            RICERCHE.svuota()

    threading.Thread(target=scansiona_e_dimentica, daemon=True).start()
    return RedirectResponse("/dispositivi?scansione=avviata", status_code=303)


@app.post("/api/interpreta")
def api_interpreta(q: str = Form(...)):
    """L'interprete AI: restituisce CHIAVI DI RICERCA, non risposte.

    Vale qui la stessa regola del resto del progetto, e sta nel codice non
    nel prompt: il modello sceglie fra candidati che gli passiamo noi, e
    quello che propone viene ricontrollato contro i nostri cataloghi e
    scartato se non c'è. Da questa rotta non esce mai un dato tecnico.

    IL TASTO AI NON DEVE MAI RISPONDERE PEGGIO DI «CERCA» sullo stesso
    testo — un tasto «potenziato» che a volte trova di meno di quello
    semplice non è potenziato, è rotto. Due casi lo tradivano:

    1. **Un IMEI.** Quindici cifre non somigliano a nessun nome di
       catalogo: `candidati_per` tornava vuoto e l'interprete rispondeva
       «nessun candidato da sottoporre al modello» — un vicolo cieco su
       un input che «Cerca» riconosce e risolve da sempre. Qui non c'è
       niente da interpretare: si passa il numero così com'è, e la
       pagina del risultato lo riconosce da sola (stessa `pagina_ricerca`
       di sempre, con lo stesso confronto fra i database TAC).
    2. **Nessuna corrispondenza utile.** Prima finiva in un messaggio
       d'errore nel pannello AI, punto — mentre «Cerca» sullo stesso
       testo avrebbe comunque prodotto una pagina (anche se «nessun
       firmware trovato», che è un'informazione, non un buco). Ora si
       ripiega sul testo digitato: il motivo dell'interpretazione mancata
       resta scritto, onestamente, ma la ricerca parte comunque.
    """
    domanda = q.strip()

    if imeicheck.is_imei_like(domanda):
        return JSONResponse({
            "proposte": [domanda],
            "motivo": "un IMEI si cerca così com'è: qui non c'è niente da "
                      "interpretare.",
            "errore": None,
            "scartate": [],
        })

    esito = aiquery.interpreta(domanda)
    if esito.riuscita:
        return JSONResponse({
            "proposte": list(esito.proposte),
            "motivo": esito.motivo,
            "errore": None,
            "scartate": list(esito.scartate),
        })

    return JSONResponse({
        "proposte": [domanda] if domanda else [],
        "motivo": (f"l'AI non ha trovato un'interpretazione migliore "
                  f"({esito.errore}): si cerca il testo così com'è."
                  if esito.errore else
                  "l'AI non ha trovato un'interpretazione migliore: si "
                  "cerca il testo così com'è."),
        "errore": None,
        "scartate": list(esito.scartate),
    })


@app.get("/api/suggerimenti")
def api_suggerimenti(q: str = Query(default="")):
    return JSONResponse({"voci": suggest.suggest(q, limit=8)})


@app.get("/health")
@app.head("/health")
def health():
    """Per il servizio che tiene sveglio l'host.

    Deliberatamente leggerissima: non tocca il database. Un controllo di
    salute che interroga l'archivio ogni cinque minuti è un carico
    costante che nessuno ha chiesto, e per giunta fallirebbe proprio
    quando l'archivio è in riparazione — cioè quando l'host non deve
    riavviare il servizio.

    **RISPONDE ANCHE A `HEAD`, e non è una rifinitura.** Gli host e i
    servizi che tengono sveglio un sito controllano quasi sempre con
    `HEAD`, che costa una risposta senza corpo. FastAPI — a differenza di
    Starlette sotto di lui — non aggiunge `HEAD` da solo a una rotta
    dichiarata `GET`: rispondeva **405**, il controllo lo leggeva come
    «servizio giù» e faceva riavviare il contenitore. Ogni pochi minuti,
    all'infinito, e ogni riavvio è un avvio a freddo da mezzo minuto.
    Da fuori non si vede nessun errore: si vede un sito lento.
    """
    return {"ok": True, "app": C.APP_TITLE}


# ======================================================================
# IMEI
# ======================================================================
def _esito_imei(imei: str) -> dict:
    """Da quindici cifre a un modello, dicendo da dove arriva la risposta.

    **Il confronto fra le fonti si mostra sempre, anche quando l'IMEI è
    stato riconosciuto.** I database TAC sono alimentati dalla community,
    si contraddicono fra loro e nessuno è autorevole: lo stesso numero dà
    spesso un modello su un sito e un altro modello su un altro. Mostrare
    una risposta sola come se fosse LA risposta è il modo più efficace di
    far preparare un test sul telefono sbagliato.
    """
    trovato = imeicheck.identify(imei)
    raffronto = imeicheck.confronto(imei)

    modello_cercato = ""
    descrizione = ""
    codice = ""
    if trovato:
        marca, dettagli_grezzi = trovato
        dettagli = imeicheck.parse_specs(marca, dettagli_grezzi)
        descrizione = imeicheck.describe(marca, dettagli_grezzi)
        codice = dettagli.get("code") or ""
        # SI CERCA PER CODICE, NON PER NOME, quando il database TAC lo
        # contiene — e lo contiene quasi sempre. Il nome è ambiguo fra le
        # varianti di mercato, che montano firmware e perfino chip
        # diversi, e arriva in forme incoerenti; il codice è esatto ed è
        # la chiave che le fonti ufficiali accettano. È la differenza fra
        # «trova qualcosa» e «trova quel telefono».
        modello_cercato = codice or dettagli.get("model") or ""

    return {
        "imei": imei,
        "tac": raffronto.get("tac") or "",
        "luhn_valid": imeicheck.is_valid_imei(imei),
        "imei_corretto": imeicheck.imei_con_cifra_di_controllo(imei),
        "riconosciuto": bool(trovato),
        "descrizione": descrizione,
        "marca": (marca if trovato else ""),
        # «model» è il nome da mostrare; «modello_cercato» è invece la
        # chiave precisa (codice, quando presente) da passare alle fonti.
        # Tenerli separati evita che il codice sostituisca il modello nella UI.
        "modello": dettagli.get("model") if trovato else "",
        "codice": codice,
        "modello_cercato": modello_cercato,
        "voci": raffronto.get("voci") or [],
        "discordi": bool(raffronto.get("discordi")),
        "stato_database": imeicheck.status(),
        "siti": list(imeicheck.link_verifica(imei)),
    }


def _esito_imei_salvato(imei: str) -> dict:
    """Risposta immediata dopo un salvataggio manuale, senza ricreare l'indice TAC.

    Il redirect successivo a «Salva» deve confermare il dato appena scritto,
    non scaricare/indicizzare centinaia di migliaia di TAC prima di rendere
    la pagina. Al prossimo caricamento normale torna il confronto completo
    fra tutte le fonti.
    """
    tac = imeicheck.tac_di(imei)
    marca, dettagli_grezzi = imeicheck.tac_inseriti().get(tac, ("", ""))
    dettagli = imeicheck.parse_specs(marca, dettagli_grezzi) if dettagli_grezzi else {}
    modello = dettagli.get("model") or dettagli_grezzi
    return {
        "imei": imei, "tac": tac, "luhn_valid": imeicheck.is_valid_imei(imei),
        "imei_corretto": imeicheck.imei_con_cifra_di_controllo(imei),
        "riconosciuto": bool(modello),
        "descrizione": imeicheck.describe(marca, dettagli_grezzi) if modello else "",
        "marca": marca, "modello": modello,
        "codice": dettagli.get("code") or "",
        "modello_cercato": (dettagli.get("code") or modello or ""),
        "voci": ([{"fonte": imeicheck.FONTE_UTENTE, "marca": marca,
                   "modello": modello, "codice": dettagli.get("code"),
                   "anno": dettagli.get("year"), "raw": dettagli.get("raw", "")}]
                 if modello else []),
        "discordi": False, "stato_database": "conferma appena salvata",
        "siti": list(imeicheck.link_verifica(imei)),
    }


def _modello_con_marca(marca: str, modello: str, codice: str = "") -> str:
    """Nome commerciale leggibile, senza perdere la marca lungo la ricerca.

    Le fonti firmware spesso restituiscono solo il codice o il nome corto;
    il TAC invece tiene marca e modello separati. Questa è l'unica
    composizione del nome usata dal risultato, così una ricerca per IMEI e
    una per codice non possono più mostrare «A-16 4G» o «C63» nudi.
    """
    modello = " ".join(str(modello or "").split())
    marca = " ".join(str(marca or "").split())
    if not modello:
        return ""

    basso = modello.lower()
    # Un nome che dichiara già la sua marca non va prefissato di nuovo.
    marchi_nel_nome = ("samsung", "redmi", "xiaomi", "poco",
                       "realme", "oppo", "oneplus", "motorola", "moto",
                       "google", "honor", "huawei", "apple",
                       "vivo", "iqoo", "nothing", "nokia", "sony")
    if basso.startswith(marchi_nel_nome):
        return modello

    # Alcuni moduli usano il gruppo tecnico del tracker per realme/Oppo/
    # OnePlus o Redmi/Xiaomi/POCO. Per la UI serve il marchio che l'utente
    # riconosce; il codice modello dà questa distinzione senza euristiche.
    gruppo = marca.lower()
    codice = (codice or "").strip().upper()
    if "realme" in gruppo and codice.startswith(("RMX", "RMP")):
        marca = "realme"
    elif "oppo" in gruppo and codice.startswith("CPH"):
        marca = "OPPO"
    elif "xiaomi" in gruppo and codice:
        marca = "Xiaomi"
    elif "vivo" in gruppo:
        # Motorola e iQOO arrivano gia' con il marchio nel nome; per un
        # nome nudo del gruppo (V60, X200...) la forma commerciale e vivo.
        marca = "vivo"
    elif "/" in marca:
        marca = ""

    if not marca or marca.lower() in ("sconosciuto", "other", "altri brand"):
        return modello
    if basso.startswith(marca.lower() + " "):
        return modello
    return f"{marca} {modello}"


def _android_da_scheda(scheda: dict) -> str:
    """Versione Android di lancio come ultimo ripiego esplicito.

    Non la promuove mai a OTA corrente: serve a evitare una scheda tecnica
    corretta con una pagina che afferma di non sapere nemmeno Android.
    """
    for etichetta, valore in scheda.get("voci") or []:
        if etichetta == "Sistema di lancio" and valore:
            return " ".join(str(valore).split())
    return ""


def _ancora_esito_imei(risultato: dict, imei: dict) -> dict:
    """Il TAC stabilisce l'identità; il firmware può solo arricchirla.

    In precedenza qui veniva copiato ``modello_cercato`` nel titolo. Poiché
    quel campo è volutamente il codice da inviare alle fonti (SM-A165F,
    RMX3939…), la UI perdeva sistematicamente brand e nome commerciale.
    """
    identita = imei.get("modello_cercato") or ""
    if not identita:
        return risultato

    ancorato = dict(risultato)
    codice = imei.get("codice") or ancorato.get("codice", "")
    modello = imei.get("modello") or identita
    marca = imei.get("marca", "")
    ancorato["scheda"] = P.scheda_tecnica(
        modello, codice=codice or identita, brand=marca)
    # Il catalogo tecnico curato conserva la grafia commerciale completa
    # (es. «Galaxy A16 4G»). Il TAC puÃ² invece avere un nome abbreviato o
    # tutto maiuscolo: per la UI si privilegia quindi il titolo della scheda
    # che Ã¨ stata appena trovata per lo stesso codice, senza permettere alla
    # ricerca firmware di rinominare l'identitÃ .
    titolo_scheda = (ancorato["scheda"].get("titolo") or "").strip()
    if ancorato["scheda"].get("trovata") and titolo_scheda:
        modello = titolo_scheda
        marca = ancorato["scheda"].get("marca") or marca
    ancorato["query"] = identita
    ancorato["nome"] = _modello_con_marca(marca, modello, codice) or modello
    ancorato["codice"] = codice
    ancorato["codice_per_correzione"] = codice
    ancorato["trovato"] = True

    # Se nessuna fonte OTA è interrogabile, la versione Android della scheda
    # è comunque un dato tecnico utile. Viene etichettata come versione di
    # lancio, non falsamente come l'ultimo firmware.
    if not ancorato.get("riga"):
        android = _android_da_scheda(ancorato["scheda"])
        if android:
            ancorato["riga"] = f"Versione Android verificata: {android} (di lancio)"
            ancorato["fonte"] = (ancorato["scheda"].get("fonte")
                                  or "scheda tecnica verificata")
            ancorato["senza_firmware"] = False
            ancorato["tipo_versione"] = C.FW_FACTORY

    # Per un'identità TAC non si propongono modelli con un nome simile:
    # sarebbero candidati per una domanda testuale, non alternative allo
    # stesso dispositivo fisico.
    ancorato["forse"] = []
    ancorato["gemelli"] = []
    ancorato["opzioni_correzione"] = []
    return ancorato


def _esito_solo_identita(query: str) -> dict:
    """Risposta immediata dopo un salvataggio TAC, senza rete o cataloghi."""
    return {
        "query": query, "trovato": False, "nome": query, "codice": "",
        "codice_per_correzione": "", "corretto_a_mano": False,
        "riga": "", "fonte": "", "senza_firmware": False,
        "scheda": {"trovata": False}, "notizie": [], "quante_notizie": 0,
        "forse": [], "gemelli": [], "opzioni_correzione": [],
        "storico": [], "chiave": "", "nota_fonte": None, "errore": None,
    }


# ======================================================================
# La ricerca
# ======================================================================
def _chiave_ricerca(query: str) -> str:
    """«  SM-A075F » e «sm-a075f» sono la stessa domanda.

    Senza questa riduzione la cache risponderebbe solo a chi ridigita
    esattamente gli stessi spazi e le stesse maiuscole, cioè quasi a
    nessuno — e una cache che non risponde è solo memoria occupata.
    """
    return " ".join(str(query or "").split()).lower()


def _esito_ricerca(query: str) -> dict:
    """Cosa dicono le fonti su quello che è stato digitato.

    La stessa domanda posta due volte di seguito non ripaga tredici
    secondi di rete: la seconda risposta viene dalla memoria corta. La
    durata è in `SEARCH_CACHE_SECONDS`, e a zero questo ramo non esiste.
    """
    chiave = _chiave_ricerca(query)
    pronto = RICERCHE.leggi(chiave)
    if pronto is not None:
        return pronto
    esito = _cerca_davvero(query)
    RICERCHE.scrivi(chiave, esito)
    return esito


def _esito_vuoto(query: str) -> dict:
    """La forma di un risultato quando non c'è niente da dire.

    Serve al ramo dell'IMEI riconosciuto come valido ma di modello
    ignoto: senza, il template riceveva `None` e mezza pagina spariva,
    compreso il riquadro che spiega come salvare il modello a mano.
    """
    return {
        "query": query, "trovato": False, "nome": query, "codice": "",
        "riga": "", "fonte": "", "senza_firmware": False,
        "scheda": P.scheda_tecnica(query), "notizie": [], "quante_notizie": 0,
        "forse": _forse_cercavi(query, query, "", False),
        "gemelli": [],
        "storico": [], "chiave": "", "nota_fonte": None, "errore": None,
    }


def _codici_del_risultato(query: str, nome: str) -> list[str]:
    """Il codice che questa ricerca ha in mano — quello scritto, o quello
    che il nome trovato porta con sé — per guardare cos'altro il dataset
    sa su di lui. Non deduce niente: guarda solo cosa c'è già scritto o
    già risolto altrove nella stessa ricerca.

    IL CODICE SCRITTO VINCE SEMPRE SU QUELLO DEL NOME TROVATO, quando
    c'è. «realme RMX3933» risolve al nome «C61» (il nome canonico del
    codice, scelto perché il più corto — vedi `nome_canonico`), ma il
    codice DAVVERO cercato è RMX3933, non RMX3930 (il codice che «C61» da
    solo risolverebbe tramite `codes_for_name`). Confondere i due
    significherebbe mostrare i gemelli del codice sbagliato — misurato:
    senza questo passaggio, cercare «realme RMX3933» faceva vedere i
    gemelli di RMX3930, che non è quello scritto.

    `_code_candidates` riconosce solo un testo che HA GIÀ la forma di un
    codice: con la marca davanti («realme RMX3933») non ce l'ha più, va
    tolta prima di riprovare — stessa correzione già fatta in
    `expand_query` per la stessa ragione.
    """
    codici = list(sources._code_candidates(query))
    if not codici:
        senza_marca = sources._RE_MARCA_DAVANTI.sub("", query or "").strip()
        if senza_marca and senza_marca != query:
            codici = list(sources._code_candidates(senza_marca))
    if not codici and nome:
        codici = modelcodes.codes_for_name(nome)
    return codici


def _nomi_gemelli(query: str, nome: str) -> list[str]:
    """Altri nomi commerciali VERI dello stesso codice modello — non
    somiglianze di stringa come `_forse_cercavi`, ma la stessa riga del
    dataset.

    PERCHÉ SERVE. `modelcodes.nome_canonico` sceglie UN nome per codice,
    sempre allo stesso modo (il più corto), perché l'archivio ha bisogno
    di una chiave sola per dispositivo. Ma quando un codice ha più nomi
    commerciali VERI — `RMX3933` è insieme «C61», «Note 60», «Note 60s»
    e «NARZO N61», la stessa piattaforma venduta con nomi diversi in
    mercati diversi — quella scelta è ARBITRARIA dal punto di vista di
    chi ha in mano uno di quei telefoni: chi ha un «Note 60» vede la sua
    ricerca rispondere «C61» senza nessun segnale che non è l'unico nome
    possibile. Misurato: `RMX3933` e `CPH2781` (quest'ultimo «OPPO F31»
    / «OPPO A6 Pro» / «OPPO A6 Pro 5G» / «OPPO F31 5G») lo mostrano
    entrambi.

    Mostrare questi nomi — dichiarati come certi, non come un «forse» —
    è più onesto che tacere l'ambiguità: chi riconosce il proprio
    telefono in uno di essi sa di essere nel posto giusto anche se il
    titolo della pagina dice un nome diverso dal suo.

    UNA FORMA E «MARCA + QUELLA STESSA FORMA» NON SONO DUE GEMELLI.
    Segnalato dall'utente: `RMX3933` risolve anche a «realme Note 60»,
    che è «Note 60» col produttore scritto davanti — non un telefono in
    più, la stessa identica forma commerciale. Mostrarle come due voci
    separate fa sembrare che siano due cose diverse da scegliere, quando
    ce n'è solo una. Si tiene una forma sola per gruppo — la più corta,
    stessa preferenza di `modelcodes.nome_canonico` — confrontando le
    forme con `modelcodes._normalize_name`, che toglie il prefisso di
    marca proprio per questo motivo (vedi il suo docstring). «Note 60» e
    «Note 60s» restano invece due voci distinte: sono due telefoni
    regionali diversi, non la stessa forma scritta in due modi.
    """
    scritto = (query or "").strip().lower()
    for codice in _codici_del_risultato(query, nome)[:1]:
        nomi_reali = [n for n in modelcodes.resolve(codice)
                     if not modelcodes._e_il_codice(n, codice)]

        forma_per_chiave: dict[str, str] = {}
        ordine: list[str] = []
        for n in nomi_reali:
            chiave = modelcodes._normalize_name(n)
            if chiave not in forma_per_chiave:
                forma_per_chiave[chiave] = n
                ordine.append(chiave)
            elif len(n) < len(forma_per_chiave[chiave]):
                forma_per_chiave[chiave] = n

        chiave_nome = modelcodes._normalize_name(nome)
        gemelli = []
        for chiave in ordine:
            if chiave == chiave_nome:
                continue
            n = forma_per_chiave[chiave]
            if n.lower() == scritto or n in gemelli:
                continue
            gemelli.append(n)
        return gemelli[:6]
    return []


def _opzioni_correzione(nome: str, gemelli: list[str], codice: str) -> list[str]:
    """Le forme fra cui scegliere nella correzione a mano del nome — non
    sempre le stesse di `_nomi_gemelli`.

    Segnalato dall'utente su RMX3933: nessuno dei nomi VERI di quel codice
    scrive «realme» per esteso nel dataset (solo «NARZO N61», riconosciuto
    come sinonimo — vedi `core/versus.py::_MARCHE_SCOPERTE` e il docstring
    di `P.marca_probabile`), quindi «realme Note 60» non può comparire fra
    i «gemelli»: non è una forma che il dataset ha mai scritto, e mostrarla
    lì — dove sono presentati come fatto verificato, vedi il docstring di
    `_nomi_gemelli` — significherebbe spacciare un nome non verificato per
    uno che lo è.

    Qui invece — SOLO per il menu della correzione — si aggiunge anche la
    forma con la marca scritta davanti, quando la si conosce
    (`P.marca_probabile`: la STESSA marca che decide se la scheda tecnica
    si trova, non una indovinata apposta per l'occasione). Non è un rischio
    in più: qualunque forma si scelga qui resta collegata alla stessa
    identica scheda tecnica delle altre, perché `P.scheda_tecnica` calcola
    la marca dal CODICE, non dal nome mostrato — quindi anche la forma
    sintetica è comunque collegabile a una scheda, non solo quella scritta
    a mano.

    UNA FORMA SINTETICA PER OGNI NOME VERO, non solo per il più corto.
    Segnalato di nuovo dall'utente: con un unico «base» scelto per
    lunghezza (`min(..., key=len)`), su RMX3933 usciva «Realme C61» — «C61»
    è il più corto dei nomi veri, ma non è quello con cui l'utente
    riconosce il telefono, che voleva «Realme Note 60». Non c'è un modo
    di indovinare QUALE dei nomi veri sia quello «giusto» da vestire con
    la marca — è esattamente il problema che questa funzionalità esiste
    per risolvere — quindi si genera una forma sintetica per ciascuno
    (nome mostrato compreso), scartando solo i doppioni: chi cerca la
    riconosce comunque, qualunque sia la forma di partenza che aveva in
    mente.
    """
    opzioni = list(gemelli)
    if not codice:
        return opzioni
    marca = P.marca_probabile(codice, nome)
    if not marca:
        return opzioni
    presenti = {(f or "").strip().lower() for f in (nome, *gemelli)}
    for forma in (nome, *gemelli):
        sintetica = versus.con_marca(forma, marca)
        chiave = sintetica.strip().lower()
        if chiave in presenti:
            continue
        presenti.add(chiave)
        opzioni.append(sintetica)
    return opzioni


def _forse_cercavi(query: str, nome: str, brand: str, trovato: bool) -> list[str]:
    """«Forse cercavi», con la strada giusta per ciascuno dei due casi.

    SONO DUE DOMANDE DIVERSE, e usare lo stesso attrezzo per entrambe
    era il difetto. Guardando la pagina vera:

        «s 24»       → «荣耀手表 GS 4»   (un orologio Honor)
        «samsung s24» → «Samsung Z240, Samsung T249, Samsung S200…»

    Sono le risposte di `did_you_mean`, che confronta la somiglianza
    fra stringhe. È l'attrezzo giusto per **correggere un refuso** — chi
    ha scritto «galaxi s24» non trova niente e va rimesso in strada — ed
    è quello sbagliato quando una risposta è arrivata: lì la domanda non
    è «cosa volevi scrivere» ma «forse volevi il fratello di questo», e
    la risposta sono le varianti dello stesso modello.

        «Galaxy S24» → S24+, S24 FE, S24 Ultra

    Le grafie dello stesso telefono («Samsung Galaxy S24») si tolgono
    confrontando la radice del modello, cioè lo stesso criterio con cui
    l'archivio decide che due nomi sono un dispositivo solo: proporre lo
    stesso telefono con un altro nome non è un suggerimento.
    """
    scritto = (query or "").strip().lower()
    if not trovato:
        return [voce for voce in suggest.did_you_mean(query, limit=6)
                if voce.lower() != scritto][:5]

    radice = extract.radice_modello(brand, nome) if nome else ""
    varianti: list[str] = []
    for voce in suggest.suggest(nome, limit=14):
        if voce.lower() == scritto:
            continue
        if radice and extract.radice_modello(brand, voce) == radice:
            continue          # è lo stesso telefono, scritto in un altro modo
        if voce not in varianti:
            varianti.append(voce)
    return varianti[:5]


def _storico_del_modello(nome: str, brand: str) -> tuple[list[dict], str, str]:
    """Gli aggiornamenti che QUEL telefono ha ricevuto, se è in archivio.

    È la seconda metà della domanda. «A che versione sta» la risponde la
    riga dell'esito; «cosa gli è arrivato, e quando» la risponde questa —
    ed era l'unica delle due che il sito sapeva mostrare soltanto
    entrando nella scheda del dispositivo, cioè dopo aver capito che
    quella scheda esisteva.

    Si prova prima la chiave costruita dal nome, che è quella giusta nel
    caso normale; se non risponde si guarda l'archivio per nome, perché
    la marca dedotta dalla ricerca può non coincidere con quella con cui
    il telefono è stato salvato.
    """
    if not nome:
        return [], "", ""
    # `chiavi` in ordine di fiducia, e accanto il nome con cui l'archivio
    # conosce quel telefono: è quello che poi si mostra, così due forme
    # della stessa domanda non danno due nomi diversi.
    chiavi: list[str] = []
    nomi: dict[str, str] = {}
    if brand:
        chiave = extract.device_key(brand, nome)
        if chiave:
            chiavi.append(chiave)
    atteso = extract.device_key(brand, nome) if brand else ""
    try:
        for device in storage.get_devices(search=nome)[:3]:
            chiave = device.get("device_key")
            if not chiave:
                continue
            # IL NOME DELL'ARCHIVIO SI ADOTTA SOLO SE È LO STESSO TELEFONO.
            #
            # La ricerca per nome è tollerante di proposito, quindi
            # «Pixel 9» riporta anche il **Pixel 9a**: adottarne il nome
            # significava rispondere «Google Pixel 9a» a chi aveva
            # chiesto il 9 — un telefono diverso, con un altro chip.
            # Coerente e sbagliato, che è il modo peggiore di essere
            # coerenti. Il confronto è sulla chiave di dispositivo, cioè
            # la stessa regola con cui l'archivio decide che due nomi
            # sono un telefono solo.
            if not atteso or chiave == atteso:
                nomi.setdefault(chiave, device.get("model") or "")
            if chiave not in chiavi:
                chiavi.append(chiave)
    except Exception:  # pragma: no cover - l'archivio non deve fermare la ricerca
        pass

    for chiave in chiavi:
        voci = storage.get_device_history(chiave, limit=30)
        # SOLO LE RIGHE CHE DICONO QUALCOSA.
        #
        # Guardando la pagina vera: dodici righe con versione, build e
        # patch tutte a trattino. Erano notizie senza numero di build —
        # legittime in archivio, e infatti compaiono più sotto fra le
        # notizie — ma in una tabella intitolata «aggiornamenti» sono
        # dodici righe vuote che fanno sembrare rotta la pagina. È la
        # stessa regola che `scan._ha_firmware` applica alla scelta del
        # risultato: se non c'è né versione, né build, né livello di
        # patch, non è un aggiornamento osservato.
        con_dato = [v for v in voci
                    if v.get("os_version") or v.get("build") or v.get("patch_level")]
        if con_dato:
            return ([P.riga_aggiornamento(v) for v in con_dato[:12]],
                    chiave, nomi.get(chiave, ""))


    # Nessuno storico utile, ma il telefono può essere in archivio lo
    # stesso: il nome canonico serve comunque a far convergere le forme.
    for chiave in chiavi:
        if nomi.get(chiave):
            return [], "", nomi[chiave]
    return [], "", ""


def _cerca_davvero(query: str) -> dict:
    risultato = scan.search_model(query)
    fonti_dirette = [i for i in risultato.get("items", [])
                     if i.get("source") in ("official_lookup", "curated_lookup")]
    notizie = [i for i in risultato.get("items", [])
               if i.get("source") not in ("official_lookup", "curated_lookup")]

    def tipo(item: dict) -> str:
        # Le vecchie righe in archivio e i test precedenti alla distinzione
        # semantica non portano ancora il campo: una lookup ufficiale con
        # versione resta comunque una fonte corrente, non un buco UI.
        return (item.get("firmware_kind") or
                (C.FW_CURRENT if item.get("source") == "official_lookup"
                 else C.FW_REPORTED))

    def ha_versione(item: dict) -> bool:
        return bool(item and (item.get("os_version")
                              or item.get("android_version")
                              or item.get("build")
                              or item.get("patch_level")))

    # Primo risultato: una build/OTA realmente corrente. Secondo: una
    # versione riportata da una fonte controllata. Solo dopo vengono i
    # dati di lancio/supporto, che sono utili ma non vengono mai venduti
    # come «ultimo firmware».
    corrente = next((i for i in fonti_dirette
                     if tipo(i) == C.FW_CURRENT and ha_versione(i)), None)
    riportata = next((i for i in fonti_dirette
                       if tipo(i) == C.FW_REPORTED and ha_versione(i)), None)
    base_android = next((i for i in fonti_dirette
                          if tipo(i) in (C.FW_FACTORY, C.FW_SUPPORT)
                          and ha_versione(i)), None)
    # Alcuni produttori — HONOR in particolare — pubblicano una cadenza di
    # sicurezza per modello ma non il numero dell'OTA. Non è un firmware
    # corrente, ma è comunque un esito concreto e verificabile: lasciarlo
    # cadere produceva una scheda apparentemente vuota benché la fonte
    # ufficiale avesse risposto. La riga resta esplicita sul limite, così il
    # supporto non viene mai confuso con una build installata.
    supporto_senza_versione = next((i for i in fonti_dirette
                                    if tipo(i) == C.FW_SUPPORT and not ha_versione(i)
                                    # Il riconoscimento da catalogo identifica il
                                    # telefono, non e' un servizio firmware. Non
                                    # deve mai comparire come «Supporto ufficiale».
                                    and "riconoscimento del codice" not in
                                    (i.get("source_label") or "").lower()), None)
    versione_certa = corrente or riportata or base_android
    identita = versione_certa or (fonti_dirette[0] if fonti_dirette else {})

    codice = identita.get("model_code") or ""
    nome = identita.get("device_model") or query
    marca = identita.get("brand", "")

    # Un codice è più specifico di un alias restituito dalla fonte. Quando
    # il catalogo ne conosce il nome commerciale verificato lo preferiamo:
    # è ciò che impedisce a RMX3939 di ricadere su C61 e rende uguali la
    # ricerca per codice, per modello e per IMEI.
    # `scan.normalize` conserva il nome fornito da una fonte strutturata
    # quando è più preciso del dataset community dei codici (CPH2781 è A6
    # Pro in Europa, F31 in India). Qui non si deve annullare quella scelta.
    if codice and not identita.get("device_model"):
        try:
            canonico = modelcodes.nome_canonico(codice)
        except Exception:
            canonico = None
        if canonico:
            nome = canonico
    nome = _modello_con_marca(marca, nome, codice) or nome

    pezzi = []
    tipo_versione = ""
    if versione_certa:
        versione = versione_certa.get("os_version") or (
            f"Android {versione_certa['android_version']}"
            if versione_certa.get("android_version") else "")
        if versione:
            if versione_certa is base_android:
                etichetta = ("Versione Android verificata"
                             if versione.lower().startswith("android")
                             else "Versione di sistema verificata")
                pezzi.append(f"{etichetta}: {versione} (di lancio/supporto)")
                tipo_versione = tipo(versione_certa)
            elif versione_certa is riportata:
                etichetta = ("Versione Android riportata"
                             if versione.lower().startswith("android")
                             else "Versione di sistema riportata")
                pezzi.append(f"{etichetta}: {versione}")
                tipo_versione = C.FW_REPORTED
            else:
                etichetta = ("Ultimo Android verificato"
                             if versione.lower().startswith("android")
                             else "Ultima versione verificata")
                pezzi.append(f"{etichetta}: {versione}")
                tipo_versione = C.FW_CURRENT
        if versione_certa.get("build"):
            pezzi.append(f"build {versione_certa['build']}")
        if versione_certa.get("patch_level"):
            pezzi.append(f"patch {versione_certa['patch_level']}")
        if pezzi and versione_certa is not base_android:
            if versione_certa.get("published"):
                pezzi.append(f"uscito il {fmt_date(versione_certa['published'])}")
            else:
                mese = extract.mese_leggibile(versione_certa.get("build") or "")
                if mese:
                    pezzi.append(f"build di {mese}")

    if not pezzi and supporto_senza_versione:
        # ``size_info`` viene arricchito più avanti con il SoC per la scheda
        # tecnica. La riga di supporto deve invece descrivere SOLO la policy
        # firmware, quindi preferisce l'etichetta della fonte costruita prima
        # di quell'arricchimento.
        dettaglio_supporto = (supporto_senza_versione.get("source_label")
                              or supporto_senza_versione.get("size_info") or "").strip()
        dettaglio_supporto = dettaglio_supporto.removesuffix(" (ricerca diretta)")
        if dettaglio_supporto:
            pezzi.append(f"Supporto ufficiale: {dettaglio_supporto}")
        else:
            pezzi.append(
                "Supporto ufficiale confermato; il produttore non pubblica una build OTA per modello"
            )
        tipo_versione = C.FW_SUPPORT

    storico, chiave, nome_archivio = _storico_del_modello(
        nome, identita.get("brand", ""))

    # IL NOME LO DECIDE L'ARCHIVIO, quando quel telefono ci sta già.
    #
    # Misurato interrogando il sito con le forme che una persona scrive
    # davvero. Stesso telefono, stessa build, nomi diversi:
    #
    #     realme C63  → «realme C61»       RMX3939      → «C61»
    #     Moto G14    → «Moto G14»         motorola g14 → «Motorola G14»
    #     Pixel 9     → «Pixel 9»          pixel9       → «Google Pixel 9»
    #
    # Non è un dato sbagliato: è la grafia di chi ha risposto, e cambia
    # con la strada che la domanda ha preso. Ma per chi guarda sono due
    # risposte diverse alla stessa domanda, ed è esattamente ciò che
    # rende un'applicazione poco credibile.
    #
    # L'archivio è utile per le forme che non hanno un codice. Quando il
    # codice è noto, invece, il nome canonico del codice resta prioritario:
    # una vecchia riga con l'alias C61 non può più rinominare RMX3939/C63.
    if nome_archivio and not codice:
        nome = _modello_con_marca(marca, nome_archivio, codice) or nome_archivio

    # LA CORREZIONE A MANO VINCE SU TUTTO, ARCHIVIO COMPRESO.
    #
    # Nasce dal bug segnalato dall'utente: `RMX3933` ha più nomi
    # commerciali veri («C61», «Note 60», «Note 60s», «NARZO N61» — la
    # stessa piattaforma venduta con nomi diversi in mercati diversi, vedi
    # il docstring di `_nomi_gemelli`), e `modelcodes.nome_canonico` ne
    # sceglie uno solo, sempre allo stesso modo (il più corto): una scelta
    # ARBITRARIA che non può sapere qual è il nome giusto per il telefono
    # che chi cerca ha davvero in mano. Indovinare meglio non è possibile
    # — sono tutti nomi reali, nessuno "più corretto" degli altri secondo
    # il dataset — quindi la scelta si offre a chi il telefono ce l'ha, e
    # si ricorda: stessa idea di `imeicheck.aggiungi_tac` (una correzione
    # verificata da una persona vince su ogni fonte scaricata), applicata
    # al nome invece che al modello di un TAC.
    #
    # SI CERCA IL CODICE CON `_codici_del_risultato`, non con `codice` da
    # solo: chi ha corretto il nome può tornare a cercare con il NOME
    # («Note 60»), non solo col codice («RMX3933») — e senza questo la
    # correzione varrebbe solo per metà delle forme dello stesso telefono,
    # esattamente l'incoerenza che questo intero fix esiste per chiudere.
    codice_per_correzione = (codice or
                              next(iter(_codici_del_risultato(query, nome)), ""))
    nome_corretto = (storage.get_nome_modello(codice_per_correzione)
                     if codice_per_correzione else None)
    if nome_corretto:
        nome = nome_corretto

    # LA SCHEDA SI CALCOLA UNA VOLTA SOLA, PRIMA DEL NOME FINALE — perché
    # può correggere il nome anche lei, non solo mostrarlo.
    scheda = P.scheda_tecnica(nome, codice=codice or query,
                              brand=identita.get("brand", ""))

    # Per un codice esatto, la scheda curata/del catalogo è una fonte di
    # identità più precisa del nome libero della fonte firmware. Questo
    # chiude i casi di alias regionali: RMX3939 non può tornare C61 se la
    # scheda per RMX3939 dichiara realme C63.
    if codice and scheda.get("trovata") and scheda.get("titolo"):
        nome = (_modello_con_marca(scheda.get("marca") or marca,
                                   scheda["titolo"], codice)
                or scheda["titolo"])

    # QUANDO NON C'È UN FIRMWARE MA C'È UN TELEFONO VERO.
    #
    # Segnalato dall'utente cercando «m1910f4g» (Xiaomi Mi Note 10): nessuna
    # fonte firmware conosceva quel codice, quindi `nome` restava la query
    # grezza — ma `scheda_tecnica`, che prova il testo anche SENZA che
    # abbia la forma di un codice riconosciuto, il telefono lo trovava lo
    # stesso (foto, processore, tutto). Il risultato era una pagina con la
    # scheda di un telefono vero sotto il titolo «Nessun firmware per
    # «m1910f4g»» — nessun nome, solo il codice grezzo ripetuto, come se
    # l'app non avesse capito niente pur avendo capito tutto.
    #
    # Qui si usa il titolo che la scheda ha già trovato, ma SOLO quando non
    # c'è già un nome più autorevole (firmware, archivio o correzione a
    # mano, tutti sopra) e la scheda ha davvero risolto qualcosa di diverso
    # dalla query scritta — un titolo identico alla query non è una
    # risoluzione, è un'eco.
    if not nome_corretto and scheda["trovata"]:
        titolo_scheda = (scheda["titolo"] or "").strip()
        nome_tecnico = (nome or "").strip().upper() in {
            (query or "").strip().upper(), (codice or "").strip().upper()
        }
        # La scheda curata ha già risolto il nome quando la fonte diretta
        # restituisce soltanto il codice. In quel caso il suo titolo è più
        # preciso, anche se la fonte conosce una versione Android.
        if (titolo_scheda and titolo_scheda.lower() != query.strip().lower()
                and (not versione_certa or nome_tecnico)):
            nome = _modello_con_marca(
                scheda.get("marca") or marca, titolo_scheda, codice) or titolo_scheda
            # Il nome è cambiato: il codice di correzione e un'eventuale
            # correzione già salvata per QUEL nome vanno ricalcolati, stessa
            # ragione del blocco sopra.
            codice_per_correzione = (next(iter(_codici_del_risultato(query, nome)), "")
                                     or codice_per_correzione)
            nome_corretto = (storage.get_nome_modello(codice_per_correzione)
                             if codice_per_correzione else None)
            if nome_corretto:
                nome = nome_corretto

    # Calcolati una volta sola: `opzioni_correzione` (vedi il suo
    # docstring) parte dagli stessi «gemelli» mostrati sopra come fatto
    # verificato, e può aggiungerne una forma sintetica in più — non il
    # contrario, per non ricalcolare due volte gli stessi gemelli.
    #
    # Si calcolano anche senza `migliore`, quando c'è comunque un codice da
    # correggere (il caso qui sopra): senza, chi cercava «m1910f4g» vedeva
    # finalmente il nome giusto ma nessun modo di correggerlo se sbagliato.
    ha_un_risultato = bool(identita) or bool(codice_per_correzione)
    gemelli_veri = _nomi_gemelli(query, nome) if ha_un_risultato else []
    opzioni_correzione = (_opzioni_correzione(nome, gemelli_veri, codice_per_correzione)
                          if ha_un_risultato else [])
    chiave_parco = chiave or extract.device_key(marca, nome)

    return {
        "query": query,
        "trovato": bool(identita),
        "nome": nome,
        "codice": codice,
        "codice_per_correzione": codice_per_correzione,
        "corretto_a_mano": bool(nome_corretto),
        "riga": " · ".join(pezzi),
        "fonte": (versione_certa or identita).get("source_label", ""),
        # La fonte non e' una decorazione: chi vuole controllare la build
        # mostrata deve poterla aprire. Questo percorso e' deterministico
        # e non dipende dalla quota di un servizio AI esterno.
        "fonte_url": (versione_certa or identita).get("link", ""),
        # Una versione di lancio/supporto è un dato Android utile, quindi
        # non produce più una scheda apparentemente rotta. L'etichetta
        # nella riga distingue esplicitamente quel caso da un OTA corrente.
        "senza_firmware": bool(identita) and not bool(pezzi),
        "tipo_versione": tipo_versione,
        "scheda": scheda,
        "notizie": [P.riga_aggiornamento(n) for n in notizie[:6]],
        "quante_notizie": len(notizie),
        # IL «FORSE CERCAVI» ANCHE QUANDO LA RICERCA RIESCE.
        #
        # Stava solo nel ramo del fallimento, ed era il posto sbagliato.
        # Le forme vicine servono di più proprio quando una risposta è
        # arrivata ma non è quella giusta: chi scrive «galaxy s24» e
        # voleva l'Ultra riceve una risposta corretta e inutile, e non
        # ha nessun modo di accorgersi che l'Ultra è a un clic. Nel
        # fallimento totale è un ripiego; qui è una correzione di rotta.
        #
        "forse": _forse_cercavi(query, nome, identita.get("brand", ""),
                                bool(identita)),
        # GEMELLI VERI, NON UN «FORSE». Vedi il docstring di `_nomi_gemelli`:
        # stesso codice, più nomi commerciali reali. Si calcola solo se la
        # ricerca ha prodotto un nome — senza, non c'è niente con cui
        # confrontare i nomi risolti.
        "gemelli": gemelli_veri,
        "opzioni_correzione": opzioni_correzione,
        "storico": storico,
        "chiave": chiave,
        "chiave_parco": chiave_parco,
        "brand": marca,
        "in_parco": bool(chiave_parco and chiave_parco in storage.watched_keys()),
        "nota_fonte": risultato.get("structured_note"),
        "errore": risultato.get("error"),
    }


# ======================================================================
# Confronto fra due modelli
# ======================================================================
def _riga_confronto(etichetta: str, valore_a, valore_b) -> dict:
    """Una riga della tabella di confronto: due valori e se differiscono.

    IL CONFRONTO È TESTUALE, NON SEMANTICO — e lo dichiaro invece di
    fingere altrimenti. "Unisoc Tiger T612" e "unisoc tiger t612" sono lo
    stesso dato scritto diverso e qui NON verrebbero segnati come uguali
    se non fosse per la normalizzazione sotto; "128GB" e "128 GB" restano
    invece due stringhe diverse agli occhi di questo confronto, perché
    provano a interpretare il TESTO delle fonti sarebbe un altro genere
    di errore — quello per cui questo intero progetto esiste (vedi
    `core/soc.py`, `core/modelcodes.py`): meglio una differenza segnalata
    in più (falsa) che una vera taciuta perché "sembrava" la stessa cosa.
    """
    a = valore_a if valore_a not in (None, "") else "—"
    b = valore_b if valore_b not in (None, "") else "—"
    return {
        "etichetta": etichetta,
        "a": a,
        "b": b,
        "diversi": str(a).strip().lower() != str(b).strip().lower(),
    }


def _confronta(query_a: str, query_b: str) -> dict:
    """Due ricerche vere, messe fianco a fianco — non una terza ricerca.

    PERCHÉ RIUSA `_esito_ricerca` INVECE DI SCRIVERNE UNA VERSIONE SUA.
    Una funzione di confronto che rifà la ricerca a modo suo può
    rispondere diversamente dalla ricerca singola sullo stesso identico
    modello — ed è esattamente il tipo di doppio percorso che ha causato
    il bug «RMX3939 risponde con i dati di RMX3930» (due funzioni diverse
    che espandevano i nomi equivalenti, una corretta e una no: vedi
    FONTI.md). Qui non esiste un secondo percorso: la stessa funzione,
    la stessa cache, chiamata due volte.
    """
    query_a, query_b = (query_a or "").strip(), (query_b or "").strip()
    ra = _esito_ricerca(query_a) if query_a else None
    rb = _esito_ricerca(query_b) if query_b else None

    righe: list[dict] = []
    stesso_modello = False
    if ra and rb:
        sa, sb = ra["scheda"], rb["scheda"]
        righe = [
            _riga_confronto("Versione", ra["riga"], rb["riga"]),
            _riga_confronto("Fonte del firmware", ra["fonte"], rb["fonte"]),
            _riga_confronto("Processore", sa.get("cpu"), sb.get("cpu")),
            _riga_confronto("RAM", sa.get("ram"), sb.get("ram")),
            _riga_confronto("Archiviazione", sa.get("storage"), sb.get("storage")),
            _riga_confronto("Batteria", sa.get("batteria"), sb.get("batteria")),
            _riga_confronto("Patch garantite fino a",
                            sa.get("patch_fino_a"), sb.get("patch_fino_a")),
        ]
        # LE VOCI EXTRA (schermo, fotocamera...) NON SONO GARANTITE NELLO
        # STESSO INSIEME per i due modelli — uno può avere una scheda
        # completa e l'altro no. Si uniscono le etichette viste da
        # entrambi, nell'ordine in cui `scheda_tecnica` le costruisce
        # (fisso, vedi presenters.py), invece di presumere che le liste
        # combacino posizione per posizione.
        dizionario_a = dict(sa.get("voci") or [])
        dizionario_b = dict(sb.get("voci") or [])
        for etichetta in dict.fromkeys(list(dizionario_a) + list(dizionario_b)):
            righe.append(_riga_confronto(
                etichetta, dizionario_a.get(etichetta), dizionario_b.get(etichetta)))

        # STESSO TELEFONO, NOMI DIVERSI — SI DICE, NON SI LASCIA INDOVINARE.
        # `_esito_ricerca` fa già convergere le grafie diverse dello stesso
        # modello allo stesso nome d'archivio (vedi `_cerca_davvero`): se
        # dopo quella convergenza «C63» e «RMX3939» finiscono con lo
        # stesso nome E lo stesso codice, non sono un confronto fra due
        # telefoni ma lo stesso telefono chiesto due volte — il caso che
        # ha reso concreto il bug di questa sessione, mostrato qui come
        # informazione utile invece che come sorpresa silenziosa.
        stesso_modello = bool(
            ra.get("nome") and ra.get("nome") == rb.get("nome")
            and (ra.get("codice") or "") == (rb.get("codice") or ""))

    return {
        "query_a": query_a,
        "query_b": query_b,
        "a": ra,
        "b": rb,
        "righe": righe,
        "pronto": bool(ra and rb),
        "stesso_modello": stesso_modello,
    }
