"""Stati separati per identità TAC, servizio e disponibilità della scheda."""
import re
from core import imeicheck, tac_missing


def stato(imei):
    if not imei.get("riconosciuto"):
        if imei.get("chiesto_invano"):
            return "tac_non_trovato"
        if imei.get("servizio_esterno_guasto"):
            return "servizio_indisponibile"
        if imei.get("cerco_fuori"):
            return "in_corso"
        return "tac_non_trovato"
    nome = (imei.get("nome_mostrato") or imei.get("modello") or "").strip()
    codice = (imei.get("codice") or "").strip()
    grezzo = (nome == codice and bool(codice)) or bool(re.fullmatch(r"[A-Z]{4,}(?:5G)?[0-9]{2}", nome))
    verificato = any(v.get("fonte") in (imeicheck.FONTE_UTENTE, imeicheck.FONTE_CURATA)
                     for v in imei.get("voci", []))
    if (imei.get("discordi") and not verificato) or not nome or grezzo:
        return "nome_da_verificare"
    return "identificato"


def annota(imei, conteggia=True):
    esito = stato(imei)
    imei["stato_identita"] = esito
    try:
        if esito == "identificato":
            tac_missing.risolto(imei.get("tac"))
        else:
            tac_missing.registra(imei.get("tac"), esito, conteggia=conteggia)
    except Exception:
        # Un registro diagnostico non deve impedire la ricerca del telefono.
        pass
    return esito
