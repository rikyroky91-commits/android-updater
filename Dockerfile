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
COPY --chown=app data ./data
COPY --chown=app scripts/preload_cataloghi.py ./scripts/preload_cataloghi.py
COPY --chown=app scripts/verifica_servizi_tac.py ./scripts/verifica_servizi_tac.py

# L'archivio iniziale viene generato dai cataloghi pubblici durante la
# build. Non si copia il database di produzione e non esiste più un
# workflow che lo committi ogni ora. Account e parco si ripristinano
# dal backup configurato; `_semina_archivio` prepara solo un DB assente.
RUN PYTHONPATH=/home/app DB_PATH=/home/app/tracker.db \
    python /home/app/scripts/preload_cataloghi.py \
 && chown app:app /home/app/tracker.db

# Il database qui contiene solo cataloghi pubblici costruiti durante la
# build. Al primo avvio viene copiato in /tmp da `_semina_archivio()`;
# cosi' il limite Render da 512 MB non deve assorbire download e parsing
# concorrenti prima della prima ricerca.
COPY --chown=app web ./web
COPY --chown=app scripts/scrivi_versione.py ./scripts/scrivi_versione.py
ARG RENDER_GIT_COMMIT
RUN python scripts/scrivi_versione.py

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
