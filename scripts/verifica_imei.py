"""Banco di prova del percorso IMEI, su tutto il database TAC.

Nasce da un rimprovero giusto dell'utente il 17/08/2026: «non importano
soltanto i 3 casi ma deve essere risolto in modo sistemico». Il guasto
sulla scheda tecnica riguardava il filtro di marca — cioè OGNI marca il
cui nome corto non coincide col gruppo del catalogo — e verificarlo su
due IMEI presi a mano non dice niente sulle altre.

Qui si parte dal database TAC vero, si campiona marca per marca e si
percorre la stessa strada della pagina: TAC → modello → scheda tecnica.
Per ogni riga si misurano le tre cose che l'utente vede:

    nome    il nome COMMERCIALE, non il codice travestito da nome
            («Oppo Cph2781» è una bocciatura, «Oppo A6 Pro» no)
    scheda  specifiche vere, non la sola riga del processore
    foto    l'immagine del telefono

Non si interroga la rete: la ricerca firmware qui non c'entra, e il
percorso che porta nome/scheda/foto (`_ancora_esito_imei`) calcola la
scheda per conto suo. Il banco resta quindi ripetibile e veloce.

    python scripts/verifica_imei.py [quanti_per_marca]
"""
from __future__ import annotations

import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("AVVIA_WORKER", "0")

from core import imeicheck, storage  # noqa: E402
from web import main as M  # noqa: E402


def _cifra_di_controllo(quattordici: str) -> str:
    """Luhn, così gli IMEI del banco sono numeri validi e non stringhe."""
    somma = 0
    for posto, carattere in enumerate(reversed(quattordici)):
        cifra = int(carattere)
        if posto % 2 == 0:
            cifra *= 2
            if cifra > 9:
                cifra -= 9
        somma += cifra
    return str((10 - somma % 10) % 10)


def imei_dal_tac(tac: str) -> str:
    corpo = (tac + "000000")[:14]
    return corpo + _cifra_di_controllo(corpo)


def _sembra_un_codice(nome: str, codice: str) -> bool:
    """«Oppo Cph2781» è il codice con l'iniziale maiuscola, non un nome.

    Serve a distinguere una risposta utile da una che si limita a
    rimbalzare indietro la chiave di ricerca. Si confronta solo la parte
    alfanumerica: maiuscole, spazi e trattini qui non contano.
    """
    def piatto(t: str) -> str:
        return "".join(c for c in (t or "").lower() if c.isalnum())

    nudo, chiave = piatto(nome), piatto(codice)
    if not nudo:
        return True
    if chiave and (nudo == chiave or nudo.endswith(chiave)):
        return True
    # UNA CIFRA NEL NOME NON FA UN CODICE: «Honor 200», «realme 12» e
    # «OPPO 2 Pro» sono nomi commerciali veri, e la prima versione di
    # questo controllo li bocciava tutti — un banco che inventa guasti è
    # peggio di nessun banco. Il segno del codice è invece una parola che
    # MESCOLA lettere e cifre ed è lunga: «Rmx3628», «Yok-al10»,
    # «25028pc03y», «Maltalite21».
    # ...ma «Fold6», «Flip7», «Note20» sono nomi commerciali, e anche la
    # seconda versione di questo controllo li bocciava. Quel che separa un
    # codice da un nome non è la presenza di cifre: è QUANTE ne ha
    # («Rmx3628», «Cph2785»), un trattino interno («Yok-al10») o una
    # lunghezza da sigla («Maltalite21», «25028pc03y»).
    for parola in re.split(r"[\s/]+", nome.strip()):
        nuda = parola.replace("-", "").replace("_", "")
        if not (any(c.isdigit() for c in nuda) and any(c.isalpha() for c in nuda)):
            continue
        cifre = sum(c.isdigit() for c in nuda)
        if cifre >= 3 or len(nuda) >= 8 or ("-" in parola or "_" in parola):
            return True
    return False


#: Il perimetro dell'app: telefoni Android moderni. Il database TAC copre
#: trent'anni di telefonia — Nokia 3310, Sagem, i TAC generici «Shenzhen» —
#: e nessun catalogo di specifiche Android li contiene, giustamente. Contare
#: quelli fra le bocciature non misura un guasto: misura quanto del database
#: parla d'altro, e affoga i casi veri in centocinquanta righe di rumore.
IN_PERIMETRO = {
    "SAMSUNG", "XIAOMI", "REDMI", "POCO", "OPPO", "ONEPLUS", "REALME",
    "VIVO", "IQOO", "MOTOROLA", "HONOR", "HUAWEI", "GOOGLE", "APPLE",
}


def classifica(esito: dict) -> str:
    """Perché una riga non può essere pretesa: distinguere serve a non
    inseguire la scheda tecnica del Nokia 3310."""
    marca = (esito.get("marca") or "").strip().upper()
    modello = (esito.get("modello") or "").strip()
    if not modello or modello.upper() == marca or modello.upper() == "UNKNOWN":
        # Il database conosce il TAC ma non il modello: dice «Samsung» e
        # basta. Nessun catalogo può rispondere a una domanda non posta.
        return "senza_modello"
    prima_parola = marca.split()[0] if marca else ""
    if prima_parola not in IN_PERIMETRO:
        return "fuori_perimetro"
    # IL CODICE MODELLO DISTINGUE UN ANDROID DA UN TELEFONO DEL 2003. Il
    # database TAC copre anche Motorola StarTAC e V170, che sono in
    # perimetro per marca ma non lo sono per epoca: nessun catalogo di
    # specifiche Android li contiene, e contarli fra le bocciature nasconde
    # i casi veri sotto cinquanta righe che non si possono risolvere.
    if not (esito.get("codice") or "").strip():
        return "senza_codice"
    return "in_perimetro"


def prova(tac: str) -> dict:
    imei = imei_dal_tac(tac)
    esito = M._esito_imei(imei)
    if not esito.get("riconosciuto") or not esito.get("modello_cercato"):
        return {"tac": tac, "saltato": True}

    pagina = M._ancora_esito_imei(
        M._esito_solo_identita(esito["modello_cercato"]), esito)
    scheda = pagina.get("scheda") or {}
    nome = pagina.get("nome") or ""
    return {
        "tac": tac,
        "saltato": False,
        "classe": classifica(esito),
        "marca": esito.get("marca") or "",
        "codice": esito.get("codice") or "",
        "dal_database": esito.get("modello") or "",
        "nome": nome,
        "nome_ok": not _sembra_un_codice(nome, esito.get("codice") or ""),
        "scheda_ok": bool(scheda.get("trovata")) and len(scheda.get("voci") or []) >= 3,
        "foto_ok": bool(scheda.get("foto")),
    }


def _rimetti_il_filtro_vecchio() -> None:
    """Ripristina il confronto esatto, per misurare cosa cambia davvero.

    Con `BANCO_MARCA_ESATTA=1` il banco gira col filtro di marca com'era
    prima della correzione. Serve a non ripetere l'errore di cambiare
    insieme il codice e il metro di misura, e poi attribuire alla
    correzione un miglioramento che veniva dal metro nuovo.
    """
    from core import specs

    def esatto(scheda, richiesta):
        if not richiesta:
            return True
        trovata = (scheda.marca or "").strip()
        return specs._MARCHE.get(trovata.lower(), trovata) == richiesta

    specs._marca_compatibile = esatto


def main() -> int:
    per_marca = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    storage.init_db()
    if os.environ.get("BANCO_MARCA_ESATTA") == "1":
        _rimetti_il_filtro_vecchio()
        print(">>> filtro di marca com'era PRIMA della correzione <<<\n")

    indice = imeicheck._build_index()
    if not indice:
        print("indice TAC vuoto: scaricalo prima di usare il banco")
        return 2

    per_gruppo: dict[str, list[str]] = {}
    for tac, voci in indice.items():
        if not voci:
            continue
        per_gruppo.setdefault((voci[0][1] or "?").strip().upper(), []).append(tac)

    # SI CAMPIONA A FONDO SOLO DOVE C'È QUALCOSA DA MISURARE. Le marche più
    # numerose del database sono anche le più vecchie: pescare a caso su
    # tutto significa collaudare l'app sui telefoni del 2003.
    random.seed(20260817)                        # banco ripetibile
    marche = [m for m in sorted(per_gruppo, key=lambda m: -len(per_gruppo[m]))
              if (m.split()[0] if m else "") in IN_PERIMETRO]

    print(f"Database TAC: {len(indice)} TAC, {len(per_gruppo)} marche")
    print(f"Campione: {per_marca} per marca, {len(marche)} marche in perimetro\n")
    print(f"{'marca':<12}{'in perim.':>10}{'nome':>8}{'scheda':>8}{'foto':>8}"
          f"{'   (esclusi: no modello / fuori perim.)'}")
    print("-" * 46)

    bocciati: list[dict] = []
    totali = [0, 0, 0, 0]
    scartati = [0, 0, 0]
    for marca in marche:
        campione = random.sample(per_gruppo[marca],
                                 min(per_marca, len(per_gruppo[marca])))
        tutte = [r for r in (prova(t) for t in campione) if not r["saltato"]]
        scartati[0] += sum(r["classe"] == "senza_modello" for r in tutte)
        scartati[1] += sum(r["classe"] == "fuori_perimetro" for r in tutte)
        scartati[2] += sum(r["classe"] == "senza_codice" for r in tutte)
        righe = [r for r in tutte if r["classe"] == "in_perimetro"]
        if not righe:
            continue
        n = len(righe)
        nomi = sum(r["nome_ok"] for r in righe)
        schede = sum(r["scheda_ok"] for r in righe)
        foto = sum(r["foto_ok"] for r in righe)
        totali[0] += n
        totali[1] += nomi
        totali[2] += schede
        totali[3] += foto
        bocciati += [r for r in righe
                     if not (r["nome_ok"] and r["scheda_ok"] and r["foto_ok"])]
        senza = sum(r["classe"] == "senza_modello" for r in tutte)
        print(f"{marca[:11]:<12}{n:>10}{nomi:>8}{schede:>8}{foto:>8}"
              f"      ({senza} senza modello)")

    n, nomi, schede, foto = totali
    print("-" * 46)
    if n:
        print(f"{'TOTALE':<12}{n:>10}{nomi:>8}{schede:>8}{foto:>8}")
        print(f"{'':<12}{'':>10}{nomi*100//n:>7}%{schede*100//n:>7}%{foto*100//n:>7}%")
    print(f"\nEsclusi dal conteggio: {scartati[0]} righe in cui il database TAC dà "
          f"solo la marca,\n{' ' * 23}{scartati[1]} fuori dal perimetro Android, "
          f"{scartati[2]} senza codice modello\n{' ' * 23}(telefoni d'anteguerra "
          f"Android: StarTAC, V170, Nokia a tasti).")

    if bocciati:
        print(f"\nDa guardare ({len(bocciati)}):")
        for r in bocciati[:60]:
            manca = " ".join(x for x, ok in (("nome", r["nome_ok"]),
                                             ("scheda", r["scheda_ok"]),
                                             ("foto", r["foto_ok"])) if not ok)
            print(f"  {r['tac']}  {r['codice']:<14}{r['dal_database'][:24]:<26}"
                  f"-> {r['nome'][:26]:<28} manca: {manca}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
