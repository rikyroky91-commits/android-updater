#!/usr/bin/env python3
"""Riprese di Page Brawl per lo store (12/10/2026): il motore vero, in Chromium, a misura di telefono.

Ogni scena apre una pagina a 360x640 dp con densità 3 (1080x1920 px), ci mette il ring come fa l'app
(arene: arena.html; sistema, blocco schermo e Chrome: uno schermo finto con il ring iniettato come nel
browser interno) e i comandi nativi ridisegnati da vetrina.js. Poi:
  - foto:  alcune schermate PNG a 1080x1920, scelte a tempi fissi;
  - video: i fotogrammi del ring (Page.startScreencast) con il loro orario, per montarli dopo.

Prima: python3 android/costruisci.py --solo-asset --aab   (gli asset come nella versione per il Play)
Uso:   python3 android/store/promo/cattura.py [foto|video] [scena ...]
"""
import asyncio
import base64
import functools
import http.server
import json
import os
import shutil
import sys
import threading
from pathlib import Path

from playwright.async_api import async_playwright

QUI = Path(__file__).resolve().parent
ANDROID = QUI.parent.parent
ASSET = ANDROID / "build" / "assets" / "web"
USCITA = ANDROID / "store" / "consegna" / "grezzi"
PORTA = 8766

# La memoria dell'app per le riprese: grafica al massimo, inglese, lottatori medi.
DATI = {"pb-lingua": "en", "pb-fps": "60", "pb-risoluzione": "100", "pb-dettaglio": "alto", "pb-taglia": "grandi"}

SCENE = {
    # nome: pagina, dove sta la capsula (dp dall'alto, senza gli 8 di margine), stile, come si parte
    # "porta": dove si posano i lottatori trascinati col dito (y in dp e le x possibili), come si fa sulla Home.
    "home":   {"url": "promo/scene/home.html",   "alto": 30, "ring": True, "porta": (285, [60, 140, 220, 300])},
    "blocco": {"url": "promo/scene/blocco.html", "alto": 30, "ring": True, "stile": "maghi", "porta": (225, [80, 180, 280])},
    "web":    {"url": "promo/scene/web.html",    "alto": 86, "ring": True, "stile": "lame", "porta": (215, [90, 180, 270])},
    "lava":   {"url": "web/arena.html?tipo=lava",  "alto": 2, "tocca": (180, 378)},
    "cielo":  {"url": "web/arena.html?tipo=cielo", "alto": 2, "tocca": (180, 378), "stile": "maghi"},
    "ring":   {"url": "web/arena.html?tipo=ring",  "alto": 2, "tocca": (180, 378), "stile": "lame"},
    "corsa":  {"url": "web/arena.html?tipo=cielo", "alto": 2, "tocca": (180, 210), "corsa": True},
}
FOTO_A = [4.0 + 1.5 * i for i in range(11)]     # secondi dopo l'avvio: poi si scelgono le migliori
VIDEO_SECONDI = 9.0


def servi(radice):
    class Muto(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    gestore = functools.partial(Muto, directory=str(radice))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORTA), gestore)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def radice_servita():
    r = USCITA.parent / "sito"
    if r.exists():
        shutil.rmtree(r)
    r.mkdir(parents=True)
    os.symlink(ASSET, r / "web")
    os.symlink(QUI, r / "promo")
    return r


def preparazione(scena):
    dati = dict(DATI)
    if scena.get("stile"):
        dati["mut-ring-stile"] = scena["stile"]
    return (
        "window.PB = { dati: function(){ return %s; }, salva: function(){}, messaggio: function(){}, schermo: function(){},"
        " chiudi: function(){}, corpi: function(){} };\n"
        "window.__vetrinaAlto = %d; window.__vetrinaAutoMosse = true; window.__vetrinaOgni = 2200;\n"
        % (json.dumps(json.dumps(dati)), scena["alto"])
    ) + ("window.__pbModo = 'web'; window.__pbSceltaModo = false;\n" if scena.get("ring") else "")


async def avvia(pg, scena):
    base = f"http://127.0.0.1:{PORTA}/"
    await pg.goto(base + scena["url"])
    if scena.get("ring"):
        # Come Browser.inietta(): ponte, lingue, prepara, ring, comandi, uno dopo l'altro.
        for f in ("ponte.js", "lingue.js", "prepara.js", "ring.js", "comandi.js"):
            await pg.add_script_tag(url=base + "web/" + f)
    await pg.add_script_tag(url=base + "promo/vetrina.js")
    await pg.wait_for_timeout(1500)
    if scena.get("tocca"):
        await pg.mouse.click(*scena["tocca"])
        await pg.wait_for_timeout(1200)
    if scena.get("corsa"):
        # L'eroe come col tasto «Play as Robot»; le carte fra un round e l'altro si prendono da sole.
        await pg.evaluate("""() => { __ring.corsa.scegli('robot');
          setInterval(() => { try { const st = __ring.stato(); if (st.corsa && st.corsa.carte) __ring.corsa.carta(0); } catch (e) {} }, 1800); }""")
        await pg.wait_for_timeout(1500)


async def trascina(pg, scena, fermo):
    """Ogni 3 secondi un lottatore preso col dito e posato in alto, sulle icone (si fa anche sul telefono)."""
    y, xs = scena["porta"]
    i = 0
    while not fermo.is_set():
        try:
            corpi = await pg.evaluate("window.__ring ? __ring.corpi() : []")
            c = corpi[i % 2] if corpi and len(corpi) > i % 2 else None
            if c:
                cx, cy = (c[0] + c[2]) / 2, (c[1] + c[3]) / 2
                dx = xs[(i * 3) % len(xs)]
                await pg.mouse.move(cx, cy)
                await pg.mouse.down()
                for k in range(1, 9):
                    await pg.mouse.move(cx + (dx - cx) * k / 8, cy + (y - cy) * k / 8)
                    await asyncio.sleep(0.03)
                await pg.mouse.up()
        except Exception:
            pass
        i += 1
        try:
            await asyncio.wait_for(fermo.wait(), 3.0)
        except asyncio.TimeoutError:
            pass


async def una(browser, nome, modo):
    scena = SCENE[nome]
    ctx = await browser.new_context(viewport={"width": 360, "height": 640}, device_scale_factor=3, is_mobile=True, has_touch=True)
    await ctx.add_init_script(preparazione(scena))
    pg = await ctx.new_page()
    pg.on("pageerror", lambda e: print(f"  [{nome}] errore nella pagina: {e}"))
    await avvia(pg, scena)
    cartella = USCITA / nome
    cartella.mkdir(parents=True, exist_ok=True)
    fermo = asyncio.Event()
    mano = asyncio.ensure_future(trascina(pg, scena, fermo)) if scena.get("porta") else None
    if modo == "foto":
        passato = 0.0
        for i, t in enumerate(FOTO_A):
            await pg.wait_for_timeout(int((t - passato) * 1000))
            passato = t
            await pg.screenshot(path=str(cartella / f"foto-{i + 1}.png"))
        print(f"  {nome}: {len(FOTO_A)} foto")
    else:
        cdp = await ctx.new_cdp_session(pg)
        fotogrammi = []

        async def arrivato(ev):
            fotogrammi.append((ev["metadata"]["timestamp"], ev["data"]))
            try:
                await cdp.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]})
            except Exception:
                pass
        cdp.on("Page.screencastFrame", lambda ev: asyncio.ensure_future(arrivato(ev)))
        await pg.wait_for_timeout(2500)
        await cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 92, "maxWidth": 1080, "maxHeight": 1920, "everyNthFrame": 1})
        await pg.wait_for_timeout(int(VIDEO_SECONDI * 1000))
        await cdp.send("Page.stopScreencast")
        await pg.wait_for_timeout(200)
        fv = cartella / "fotogrammi"
        if fv.exists():
            shutil.rmtree(fv)
        fv.mkdir()
        elenco = []
        for i, (ts, dati) in enumerate(sorted(fotogrammi)):
            f = fv / f"{i:05d}.jpg"
            f.write_bytes(base64.b64decode(dati))
            elenco.append({"file": f.name, "t": ts})
        (cartella / "fotogrammi.json").write_text(json.dumps(elenco))
        durata = (elenco[-1]["t"] - elenco[0]["t"]) if len(elenco) > 1 else 0
        print(f"  {nome}: {len(elenco)} fotogrammi in {durata:.1f} s ({len(elenco) / max(durata, 0.01):.0f} al secondo)")
    fermo.set()
    if mano:
        await mano
    await ctx.close()


async def main():
    modo = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ("foto", "video") else "foto"
    nomi = [a for a in sys.argv[1:] if a in SCENE] or list(SCENE)
    if not ASSET.exists():
        raise SystemExit("mancano gli asset: python3 android/costruisci.py --solo-asset --aab")
    srv = servi(radice_servita())
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(args=["--enable-gpu-rasterization", "--ignore-gpu-blocklist"])
            for n in nomi:
                await una(browser, n, modo)
            await browser.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
