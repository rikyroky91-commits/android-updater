#!/usr/bin/env python3
"""Monta le grafiche e i video per il Play Store dalle riprese di cattura.py (12/10/2026).

Escono in android/store/consegna/:
  store/icon-512.png                    icona dello store (512x512, senza trasparenza)
  store/feature-graphic.png             grafica in primo piano (1024x500)
  store/en/screenshot-N.png, store/it/  schermate del telefono (1080x1920), inglese e italiano
  video/page-brawl-promo-16x9.mp4       video per YouTube (1920x1080), da mettere nella scheda
  video/page-brawl-promo-9x16.mp4       stesso video in verticale (Shorts, Reels, storie)

Uso: python3 android/store/promo/componi.py [grafiche|video]
"""
import asyncio
import json
import subprocess
import sys
from pathlib import Path

from playwright.async_api import async_playwright

QUI = Path(__file__).resolve().parent
CONSEGNA = QUI.parent / "consegna"
GREZZI = CONSEGNA / "grezzi"
STORE = CONSEGNA / "store"
VIDEO = CONSEGNA / "video"
LAVORO = CONSEGNA / "lavoro"
FPS = 30

# Il guantone dell'icona dell'app (res/drawable/guantone.xml), stesso disegno in SVG.
GUANTO = ('<path fill="#F4F1EA" d="M38,66h26a4,4 0 0 1 4,4v8a4,4 0 0 1 -4,4h-26a4,4 0 0 1 -4,-4v-8a4,4 0 0 1 4,-4z"/>'
          '<path fill="#E53935" d="M28,46a23,23 0 1,0 46,0a23,23 0 1,0 -46,0z"/>'
          '<path fill="#C62828" d="M62,58a11,11 0 1,0 22,0a11,11 0 1,0 -22,0z"/>'
          '<path fill="rgba(255,255,255,0.8)" d="M36,38a7,4.5 -30 1,0 14,0a7,4.5 -30 1,0 -14,0z"/>')
FONDO_ICONA = "#183D30"

# Le schermate: ripresa scelta (scena, foto) e i testi, in inglese e in italiano.
SCHERMATE = [
    ("home", 3, ("Every screen is a ring", "Your apps become the arena. Drag the fighters around."),
                ("Ogni schermo è un ring", "Le tue app diventano l'arena. Trascina i lottatori dove vuoi.")),
    ("blocco", 6, ("Even your lock screen", "Wake the phone: the fight is already on."),
                  ("Anche il blocco schermo", "Accendi il telefono: la lotta è già iniziata.")),
    ("web", 9, ("Brawl on any web page", "Headlines and buttons turn into platforms."),
               ("Su qualsiasi pagina web", "Titoli e pulsanti diventano piattaforme.")),
    ("lava", 2, ("Don't touch the lava", "Knock your rival off the floating platform."),
                ("Non toccare la lava", "Butta giù il rivale dalla piattaforma sospesa.")),
    ("cielo", 6, ("Pick your fighters", "Robots, wizards and duelists, each with their own moves."),
                 ("Scegli i lottatori", "Robot, maghi e duellanti, ognuno con le sue mosse.")),
    ("corsa", 2, ("Endless run", "Survive the waves, pick upgrades, beat the bosses."),
                 ("Corsa infinita", "Sopravvivi alle ondate, scegli i potenziamenti, batti i boss.")),
    ("ringv", 1, ("Your phone stays usable", "Clean controls: pause, minimise or remove the game with one tap."),
                ("Il telefono resta usabile", "Comandi puliti: pausa, riduci o togli il gioco con un tocco.")),
]

# Il video: scena, da che secondo della ripresa, testi (inglese).
SEGMENTI = [
    ("home", 1.0, "Every screen is a ring", "Fighters stand on your icons.\nDrag them anywhere."),
    ("blocco", 1.5, "Even your lock screen", "Wake the phone,\nthe fight is already on."),
    ("web", 1.0, "Any web page", "Headlines become platforms."),
    ("lava", 0.5, "Don't touch the lava", "Push your rival off\nthe floating platform."),
    ("cielo", 1.0, "Pick your fighters", "Robots, wizards, duelists:\neach with their own moves."),
    ("corsa", 2.0, "Endless run", "Waves, upgrades, bosses."),
    ("ringv", 0.0, "Your phone stays usable", "Pause, minimise or remove it\nwith one tap."),
]
DURATA_SEGMENTO, DURATA_CARTA, DISSOLVENZA = 4.5, 3.0, 0.4

STILE = """
* { box-sizing: border-box; margin: 0; }
html, body { width: %dpx; height: %dpx; overflow: hidden; }
body { font-family: Inter, sans-serif; color: #fff; -webkit-font-smoothing: antialiased; }
.fondo { position: absolute; inset: 0; background:
  radial-gradient(70%% 50%% at 85%% 8%%, rgba(60,207,145,.28), transparent 70%%),
  radial-gradient(60%% 45%% at 0%% 100%%, rgba(229,57,53,.22), transparent 70%%),
  linear-gradient(160deg, #13201a 0%%, #0e1311 55%%, #0a0e0c 100%%); }
h1 { font-family: "Inter Display", Inter, sans-serif; font-weight: 800; letter-spacing: -0.02em; line-height: 1.04; }
p { color: #b9c6be; font-weight: 500; line-height: 1.3; text-wrap: balance; }
h1.riga { white-space: nowrap; }
.icona { border-radius: 22%%; background: """ + FONDO_ICONA + """; box-shadow: 0 10px 30px rgba(0,0,0,.35); }
"""


def pagina(w, h, corpo, trasparente=False):
    return ("<!doctype html><html><head><meta charset='utf-8'><style>" + (STILE % (w, h)) +
            ("html,body{background:transparent}" if trasparente else "") + "</style></head><body>" + corpo +
            # I titoli su una riga sola: se non ci stanno, si rimpiccioliscono.
            "<script>document.querySelectorAll('h1.riga').forEach(function(h){var s=parseFloat(getComputedStyle(h).fontSize);"
            "while(h.scrollWidth>h.clientWidth&&s>40){s-=2;h.style.fontSize=s+'px';}});</script></body></html>")


def icona_svg(lato):
    return f"<svg class='icona' width='{lato}' height='{lato}' viewBox='0 0 108 108'>{GUANTO}</svg>"


async def foto(pg, html, uscita, w, h, trasparente=False):
    await pg.set_viewport_size({"width": w, "height": h})
    tmp = LAVORO / (uscita.stem + ".html")
    tmp.write_text(html, encoding="utf-8")
    await pg.goto(tmp.as_uri())
    await pg.wait_for_timeout(150)
    uscita.parent.mkdir(parents=True, exist_ok=True)
    await pg.screenshot(path=str(uscita), omit_background=trasparente)


# ----------------------------------------------------------------- grafiche
def schermata(img, titolo, sotto):
    # Telefono largo 860 px (0,796 della ripresa), bordo sottile, che esce dal fondo.
    return pagina(1080, 1920, f"""<div class='fondo'></div>
<div style='position:absolute;left:90px;right:90px;top:118px'>
  <h1 class='riga' style='font-size:78px'>{titolo}</h1>
  <p style='font-size:38px;margin-top:22px'>{sotto}</p>
</div>
<div style='position:absolute;left:100px;top:{1920 - 1529 - 40}px;width:880px;height:1569px;border-radius:64px;background:#050706;
            padding:10px;box-shadow:0 30px 80px rgba(0,0,0,.55), 0 0 0 2px rgba(255,255,255,.08)'>
  <img src='{img.as_uri()}' style='display:block;width:860px;height:1529px;border-radius:54px'>
</div>""")


def grafica_primo_piano(img1, img2):
    return pagina(1024, 500, f"""<div class='fondo'></div>
<div style='position:absolute;left:64px;top:118px;width:470px'>
  {icona_svg(104)}
  <h1 style='font-size:76px;margin-top:22px'>Page Brawl</h1>
  <p style='font-size:30px;margin-top:10px;color:#d9e3dc'>Every screen is a ring.</p>
</div>
<div style='position:absolute;left:600px;top:46px;width:236px;height:420px;border-radius:30px;background:#050706;padding:6px;
            transform:rotate(-7deg);box-shadow:0 20px 50px rgba(0,0,0,.6)'>
  <img src='{img1.as_uri()}' style='width:224px;height:398px;border-radius:25px;display:block'></div>
<div style='position:absolute;left:790px;top:86px;width:236px;height:420px;border-radius:30px;background:#050706;padding:6px;
            transform:rotate(6deg);box-shadow:0 20px 50px rgba(0,0,0,.6)'>
  <img src='{img2.as_uri()}' style='width:224px;height:398px;border-radius:25px;display:block'></div>""")


async def grafiche(pg):
    await foto(pg, pagina(512, 512, f"<svg width='512' height='512' viewBox='0 0 108 108' style='display:block'>"
                                    f"<rect width='108' height='108' fill='{FONDO_ICONA}'/>{GUANTO}</svg>"), STORE / "icon-512.png", 512, 512)
    for lingua, k in (("en", 2), ("it", 3)):
        for i, voce in enumerate(SCHERMATE):
            scena, n, testi = voce[0], voce[1], voce[k]
            await foto(pg, schermata(GREZZI / scena / f"foto-{n}.png", *testi), STORE / lingua / f"screenshot-{i + 1}.png", 1080, 1920)
    await foto(pg, grafica_primo_piano(GREZZI / "home" / "foto-3.png", GREZZI / "lava" / "foto-2.png"), STORE / "feature-graphic.png", 1024, 500)
    # Le PNG dello store non devono avere trasparenza: si tolgono i canali alfa.
    from PIL import Image
    for f in STORE.rglob("*.png"):
        Image.open(f).convert("RGB").save(f, optimize=True)
    print("grafiche in", STORE)


# -------------------------------------------------------------------- video
def esegui(cmd):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stderr[-3000:])
        raise SystemExit("ffmpeg fallito")


def clip(scena):
    """I fotogrammi della ripresa (orari irregolari) in un video a 30 fotogrammi al secondo."""
    cartella = GREZZI / scena
    uscita = LAVORO / f"clip-{scena}.mp4"
    if uscita.exists():
        return uscita
    elenco = json.loads((cartella / "fotogrammi.json").read_text())
    righe = ["ffconcat version 1.0"]
    for a, b in zip(elenco, elenco[1:] + [None]):
        righe.append(f"file '{(cartella / 'fotogrammi' / a['file']).as_posix()}'")
        righe.append(f"duration {(b['t'] - a['t']) if b else 1 / FPS:.4f}")
    lista = LAVORO / f"clip-{scena}.txt"
    lista.write_text("\n".join(righe) + "\n")
    esegui(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lista, "-vf", f"fps={FPS},scale=1080:1920,format=yuv420p",
            "-c:v", "libx264", "-crf", "15", "-preset", "fast", uscita.with_suffix(".tmp.mp4")])
    uscita.with_suffix(".tmp.mp4").rename(uscita)        # mai una clip a metà nella cache
    return uscita


def finestra_orizzontale(titolo, sotto, numero):
    # Il telefono a sinistra (540x960 a x=330, y=60) visto attraverso un buco con gli angoli tondi.
    righe = sotto.replace("\n", "<br>")
    return pagina(1920, 1080, f"""
<svg width='1920' height='1080' style='position:absolute;inset:0'>
  <defs><mask id='m'><rect width='1920' height='1080' fill='white'/><rect x='330' y='60' width='540' height='960' rx='44' fill='black'/></mask>
  <radialGradient id='g1' cx='85%' cy='10%' r='60%'><stop offset='0' stop-color='rgba(60,207,145,.30)'/><stop offset='1' stop-color='rgba(60,207,145,0)'/></radialGradient>
  <radialGradient id='g2' cx='0%' cy='100%' r='55%'><stop offset='0' stop-color='rgba(229,57,53,.22)'/><stop offset='1' stop-color='rgba(229,57,53,0)'/></radialGradient>
  <linearGradient id='g0' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='#13201a'/><stop offset='.55' stop-color='#0e1311'/><stop offset='1' stop-color='#0a0e0c'/></linearGradient></defs>
  <g mask='url(#m)'><rect width='1920' height='1080' fill='url(#g0)'/><rect width='1920' height='1080' fill='url(#g1)'/><rect width='1920' height='1080' fill='url(#g2)'/></g>
  <rect x='322' y='52' width='556' height='976' rx='52' fill='none' stroke='#050706' stroke-width='16'/>
  <rect x='313' y='43' width='574' height='994' rx='60' fill='none' stroke='rgba(255,255,255,.10)' stroke-width='2'/>
</svg>
<div style='position:absolute;left:1010px;top:330px;width:820px'>
  <p style='font-size:30px;color:#3ccf91;font-weight:700;letter-spacing:.12em'>{numero:02d}</p>
  <h1 class='riga' style='font-size:92px;margin-top:14px'>{titolo}</h1>
  <p style='font-size:44px;margin-top:26px'>{righe}</p>
</div>""", trasparente=True)


def finestra_verticale(titolo, sotto):
    righe = sotto.replace("\n", " ")
    return pagina(1080, 1920, f"""
<svg width='1080' height='1920' style='position:absolute;inset:0'>
  <defs><mask id='m'><rect width='1080' height='1920' fill='white'/><rect x='110' y='351' width='860' height='1529' rx='54' fill='black'/></mask>
  <radialGradient id='g1' cx='85%' cy='8%' r='60%'><stop offset='0' stop-color='rgba(60,207,145,.30)'/><stop offset='1' stop-color='rgba(60,207,145,0)'/></radialGradient>
  <linearGradient id='g0' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='#13201a'/><stop offset='.55' stop-color='#0e1311'/><stop offset='1' stop-color='#0a0e0c'/></linearGradient></defs>
  <g mask='url(#m)'><rect width='1080' height='1920' fill='url(#g0)'/><rect width='1080' height='1920' fill='url(#g1)'/></g>
  <rect x='105' y='346' width='870' height='1539' rx='59' fill='none' stroke='#050706' stroke-width='10'/>
</svg>
<div style='position:absolute;left:90px;right:90px;top:118px'>
  <h1 class='riga' style='font-size:78px'>{titolo}</h1>
  <p style='font-size:38px;margin-top:22px'>{righe}</p>
</div>""", trasparente=True)


def carta(w, h, inizio):
    grande = w > h
    titolo = "Page Brawl"
    sotto = "Every screen is a ring." if inizio else "Turn every screen into a ring.<br><span style='color:#3ccf91'>Now on Android</span>"
    lato = 200 if grande else 240
    return pagina(w, h, f"""<div class='fondo'></div>
<div style='position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center'>
  {icona_svg(lato)}
  <h1 style='font-size:{150 if grande else 140}px;margin-top:40px'>{titolo}</h1>
  <p style='font-size:{52 if grande else 50}px;margin-top:18px;color:#d9e3dc'>{sotto}</p>
</div>""")


async def video(pg):
    VIDEO.mkdir(parents=True, exist_ok=True)
    for orient, (w, h) in (("16x9", (1920, 1080)), ("9x16", (1080, 1920))):
        pezzi = []
        await foto(pg, carta(w, h, True), LAVORO / f"carta-inizio-{orient}.png", w, h)
        await foto(pg, carta(w, h, False), LAVORO / f"carta-fine-{orient}.png", w, h)
        p = LAVORO / f"pezzo-{orient}-00.mp4"
        # Un'immagine sola: zoompan ne fa da sé i fotogrammi (con -loop ne farebbe d per ognuno).
        esegui(["ffmpeg", "-y", "-loglevel", "error", "-i", LAVORO / f"carta-inizio-{orient}.png",
                "-vf", f"scale={w}:{h},zoompan=z='1+0.0006*on':d={int(DURATA_CARTA * FPS)}:s={w}x{h}:fps={FPS},format=yuv420p",
                "-c:v", "libx264", "-crf", "16", "-r", FPS, p])
        pezzi.append(p)
        for i, (scena, da, titolo, sotto) in enumerate(SEGMENTI):
            sopra = LAVORO / f"sopra-{orient}-{scena}.png"
            if orient == "16x9":
                await foto(pg, finestra_orizzontale(titolo, sotto, i + 1), sopra, w, h, trasparente=True)
                misura, dove = "540:960", "330:60"
            else:
                await foto(pg, finestra_verticale(titolo, sotto), sopra, w, h, trasparente=True)
                misura, dove = "860:1529", "110:351"
            p = LAVORO / f"pezzo-{orient}-{i + 1:02d}.mp4"
            esegui(["ffmpeg", "-y", "-loglevel", "error", "-ss", da, "-t", DURATA_SEGMENTO, "-i", clip(scena), "-loop", "1", "-t", DURATA_SEGMENTO, "-i", sopra,
                    "-filter_complex", f"color=c=#0e1311:s={w}x{h}:d={DURATA_SEGMENTO}:r={FPS}[f];[0:v]scale={misura}:flags=lanczos,setsar=1[c];"
                                       f"[f][c]overlay={dove}[b];[b][1:v]overlay=0:0,format=yuv420p",
                    "-c:v", "libx264", "-crf", "16", "-r", FPS, "-t", DURATA_SEGMENTO, p])
            pezzi.append(p)
        p = LAVORO / f"pezzo-{orient}-99.mp4"
        esegui(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-t", DURATA_CARTA + 0.5, "-i", LAVORO / f"carta-fine-{orient}.png",
                "-vf", "format=yuv420p", "-c:v", "libx264", "-crf", "16", "-r", FPS, p])
        pezzi.append(p)
        # Dissolvenze incrociate fra un pezzo e l'altro.
        durate = [DURATA_CARTA] + [DURATA_SEGMENTO] * len(SEGMENTI) + [DURATA_CARTA + 0.5]
        ingressi, filtro, prima, t = [], [], "[0:v]", 0.0
        for k, f in enumerate(pezzi):
            ingressi += ["-i", f]
        for k in range(1, len(pezzi)):
            t += durate[k - 1] - DISSOLVENZA
            out = f"[x{k}]" if k < len(pezzi) - 1 else "[v]"
            filtro.append(f"{prima}[{k}:v]xfade=transition=fade:duration={DISSOLVENZA}:offset={t:.3f}{out}")
            prima = out
        uscita = VIDEO / f"page-brawl-promo-{orient}.mp4"
        esegui(["ffmpeg", "-y", "-loglevel", "error"] + ingressi + ["-filter_complex", ";".join(filtro) + ";[v]format=yuv420p[o]", "-map", "[o]",
                "-c:v", "libx264", "-crf", "18", "-preset", "slow", "-profile:v", "high", "-movflags", "+faststart", "-r", FPS, uscita])
        print("video:", uscita)


async def main():
    cosa = sys.argv[1] if len(sys.argv) > 1 else "tutto"
    LAVORO.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page()
        if cosa in ("grafiche", "tutto"):
            await grafiche(pg)
        if cosa in ("video", "tutto"):
            await video(pg)
        await b.close()


if __name__ == "__main__":
    asyncio.run(main())
