# Immagine del sito.
#
# Serve a due cose diverse con lo stesso file: eseguire in locale
# (`docker run -p 8000:8000`) e su un host gratuito. Render legge questo
# Dockerfile da solo; Hugging Face Spaces pretende la porta 7860, e per
# questo la porta si prende dall'ambiente invece di essere scritta qui.
FROM python:3.12-slim

# `curl` serve al controllo di salute dell'host, `ca-certificates` alle
# chiamate HTTPS verso le fonti: senza, ogni scansione fallirebbe con un
# errore di certificato che sembra un problema delle fonti e non nostro.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Utente non privilegiato con UID 1000: è quello che usa Hugging Face
# Spaces, e girare come root non serve a niente qui.
RUN useradd -m -u 1000 app
WORKDIR /home/app

# Le dipendenze PRIMA del codice: così una modifica ai template non
# invalida la cache dell'installazione, e il tempo di deploy resta di
# secondi invece che di minuti.
#
# `requirements-web.txt`, NON `requirements.txt`: dall'11/08/2026 il
# secondo è quello che legge Streamlit Cloud per `app.py` (streamlit e
# le sue dipendenze indirette) — vedi il commento in cima a entrambi i
# file. Puntare qui al file sbagliato rimetterebbe streamlit nell'
# immagine di Render, il tempo di build e il peso che il passaggio
# consegne v46 aveva tolto apposta.
COPY --chown=app requirements-web.txt .
RUN pip install --no-cache-dir -r requirements-web.txt

COPY --chown=app core ./core
COPY --chown=app web ./web
COPY --chown=app data ./data

# L'ARCHIVIO DI PARTENZA VIAGGIA CON L'IMMAGINE.
#
# Il disco qui è effimero (vedi la nota su DB_PATH più sotto), quindi a
# ogni risveglio l'applicazione ripartiva da zero dispositivi e restava
# così finché una scansione intera non fosse finita — riscaricando nel
# frattempo una ventina di megabyte di cataloghi che in questo file ci
# sono già dentro. Chi apriva il sito in quella finestra vedeva un
# archivio vuoto.
#
# Il file lo aggiorna ogni ora il workflow di GitHub Actions, quindi al
# momento della build è vecchio al massimo di un'ora. Non sostituisce il
# salvataggio su Gist: `web/main._semina_archivio()` lo usa SOLO quando
# non c'è già un archivio, e mai sopra uno esistente.
#
# `tracker.db*` (CON L'ASTERISCO), non `tracker.db`: il file è normale
# che manchi — non viaggia negli zip di consegna (contiene dati veri di
# produzione, non c'entra col codice), e lo stesso vale la prima volta
# che il repository viene ricreato da zero, prima che il workflow orario
# lo committi. Un `COPY` sul nome esatto fa fallire l'intera build se il
# file non c'è ("not found"), portando giù il sito per un file che
# `_semina_archivio()` sopra sa già gestire da solo (vedi il suo
# docstring: "nessuna copia nell'immagine" non è un errore, è un ramo
# previsto). Con l'asterisco il file si copia se c'è e non succede
# niente se non c'è — mai un build che fallisce per questo.
COPY --chown=app tracker.db* ./

USER app
ENV PYTHONUNBUFFERED=1 \
    PORT=8000 \
    DB_PATH=/tmp/tracker.db

# L'ARCHIVIO STA IN /tmp DI PROPOSITO. Su tutti gli host gratuiti il disco
# è effimero: si azzera a ogni riavvio, e i riavvii sono all'ordine del
# giorno. Fingere una persistenza che non c'è significherebbe scoprire il
# problema il giorno che servono i dati. La persistenza vera è il
# salvataggio su Gist, che esiste già ed è pensato per questo.

EXPOSE 8000
HEALTHCHECK --interval=60s --timeout=5s --start-period=30s \
  CMD curl -fsS "http://127.0.0.1:${PORT}/health" || exit 1

CMD ["sh", "-c", "uvicorn web.main:app --host 0.0.0.0 --port ${PORT}"]
