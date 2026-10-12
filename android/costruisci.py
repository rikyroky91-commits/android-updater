#!/usr/bin/env python3
"""Costruisce l'APK di Page Brawl per Android (12/10/2026).

Il ring è lo stesso dell'estensione: `estensione/store/{lingue,prepara,ring}.js`
(rigenerati da `estensione/costruisci.py` a partire dai file del sito). Qui si
copiano negli asset dell'app, con `prepara.js` riscritto perché parli con Java
(`window.__pbSalva`, `window.__pbMessaggio`) invece che con le API di Chrome,
e si aggiungono le pagine di `android/web/`.

Niente Gradle: bastano gli attrezzi a riga di comando dell'SDK.
  - aapt2            risorse e manifest
  - android.jar      le API di Android (piattaforma 34)
  - javac            il JDK
  - d8 oppure dx     da .class a classes.dex
  - apksigner        la firma (v1 + v2 + v3)
Si trovano da soli in $ANDROID_HOME (build-tools e platforms/android-34), oppure
si indicano uno per uno: AAPT2, ANDROID_JAR, D8 (eseguibile) o DX_JAR, APKSIGNER_JAR.
Senza SDK, ~/tools con aapt2, android.jar, dx.jar e apksigner.jar va bene uguale.

Uso:
    python3 android/costruisci.py              # scrive android/build/PageBrawl.apk
    python3 android/costruisci.py --solo-asset # solo android/build/assets (per provare l'arena nel browser)
"""
import glob
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

QUI = Path(__file__).resolve().parent
RADICE = QUI.parent
ESTENSIONE = RADICE / "estensione" / "store"
COSTRUZIONE = QUI / "build"
APP = QUI / "app"

VERSIONE = "1.0.0"
CODICE_VERSIONE = 1
MIN_SDK = 26
TARGET_SDK = 34

FIRMA = QUI / "firma" / "pagebrawl-debug.jks"
FIRMA_PASSWORD = "pagebrawl"          # chiave di prova (come la debug.keystore di Android): non per lo store
FIRMA_ALIAS = "pagebrawl"


def esegui(comando, **kw):
    print("  $", " ".join(str(c) for c in comando)[:220])
    r = subprocess.run([str(c) for c in comando], capture_output=True, text=True, **kw)
    if r.returncode != 0:
        sys.stderr.write(r.stdout + r.stderr)
        raise SystemExit(f"fallito: {comando[0]}")
    return r


# --------------------------------------------------------------------------
# Gli asset: il ring dell'estensione + le pagine dell'app
# --------------------------------------------------------------------------
SOSTITUZIONI_PREPARA = [
    ("chrome.storage.local.set(o)", "window.__pbSalva(o)"),
    ("chrome.runtime.sendMessage(", "window.__pbMessaggio("),
]


# ring.js: la misura dei lottatori la decide l'app (ponte.js, `window.__pbScala`).
SOSTITUZIONI_RING = [
    ("S = Math.max(0.8, Math.min(1.2, W / 1100));",
     "S = window.__pbScala ? window.__pbScala(W, H) : Math.max(0.8, Math.min(1.2, W / 1100));"),
]


def sostituisci(testo, coppie, nome, tutte=False):
    for vecchio, nuovo in coppie:
        n = testo.count(vecchio)
        if n == 0 or (n > 1 and not tutte):
            raise SystemExit(f"{nome} è cambiato: {vecchio!r} compare {n} volte")
        testo = testo.replace(vecchio, nuovo)
    return testo


def asset():
    dest = COSTRUZIONE / "assets" / "web"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    shutil.copy2(ESTENSIONE / "lingue.js", dest / "lingue.js")
    ring = sostituisci((ESTENSIONE / "ring.js").read_text(encoding="utf-8"), SOSTITUZIONI_RING, "ring.js")
    (dest / "ring.js").write_text(ring, encoding="utf-8")
    prepara = sostituisci((ESTENSIONE / "prepara.js").read_text(encoding="utf-8"), SOSTITUZIONI_PREPARA, "prepara.js", tutte=True)
    resti = re.findall(r"\bchrome\.[a-zA-Z.]+\s*\(", prepara)   # chiamate, non i commenti
    if resti:
        raise SystemExit(f"prepara.js usa ancora API di Chrome: {sorted(set(resti))}")
    (dest / "prepara.js").write_text(prepara, encoding="utf-8")
    for f in sorted((QUI / "web").iterdir()):
        if f.is_file() and f.suffix != ".css":
            shutil.copy2(f, dest / f.name)
    # Lo stile per telefono entra in comandi.js come stringa: nel browser interno
    # la pagina è un sito qualunque e non può leggere file dell'app.
    comandi = (QUI / "web" / "comandi.js").read_text(encoding="utf-8")
    css = (QUI / "web" / "mobile.css").read_text(encoding="utf-8")
    comandi = sostituisci(comandi, [("__MOBILE_CSS__", json.dumps(css))], "comandi.js")
    (dest / "comandi.js").write_text(comandi, encoding="utf-8")
    print(f"asset in {dest} ({len(list(dest.iterdir()))} file)")
    return dest.parent


# --------------------------------------------------------------------------
# Gli attrezzi
# --------------------------------------------------------------------------
def attrezzi():
    casa = Path(os.environ.get("ATTREZZI_ANDROID", Path.home() / "tools"))
    sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    bt = None
    if sdk and (Path(sdk) / "build-tools").is_dir():
        versioni = sorted((Path(sdk) / "build-tools").iterdir(), key=lambda p: [int(x) if x.isdigit() else 0 for x in re.split(r"[.-]", p.name)])
        bt = versioni[-1] if versioni else None

    def primo(*candidati):
        for c in candidati:
            if c and Path(c).exists():
                return Path(c)
        return None

    t = {
        "aapt2": primo(os.environ.get("AAPT2"), bt and bt / "aapt2", casa / "aapt2", shutil.which("aapt2")),
        "android_jar": primo(os.environ.get("ANDROID_JAR"), sdk and Path(sdk) / "platforms" / f"android-{TARGET_SDK}" / "android.jar", casa / "android.jar"),
        "d8": primo(os.environ.get("D8"), bt and bt / "d8", shutil.which("d8")),
        "dx_jar": primo(os.environ.get("DX_JAR"), casa / "dx.jar"),
        "apksigner_jar": primo(os.environ.get("APKSIGNER_JAR"), bt and bt / "lib" / "apksigner.jar", casa / "apksigner.jar"),
    }
    mancano = [k for k in ("aapt2", "android_jar", "apksigner_jar") if not t[k]]
    if not (t["d8"] or t["dx_jar"]):
        mancano.append("d8 o dx_jar")
    if mancano:
        raise SystemExit("mancano gli attrezzi: " + ", ".join(mancano) + " (vedi android/LEGGIMI.md)")
    return t


# --------------------------------------------------------------------------
# zipalign in Python: i file non compressi (resources.arsc) a 4 byte
# --------------------------------------------------------------------------
def allinea_e_aggiungi(base_apk, dex, uscita):
    with zipfile.ZipFile(base_apk) as src, open(uscita, "wb") as fp:
        dst = zipfile.ZipFile(fp, "w")
        voci = [(i, src.read(i.filename)) for i in src.infolist()]
        voci.append((None, Path(dex).read_bytes()))
        for info, dati in voci:
            if info is None:
                nuova = zipfile.ZipInfo("classes.dex", date_time=(2026, 10, 12, 0, 0, 0))
                nuova.compress_type = zipfile.ZIP_DEFLATED
            else:
                nuova = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                nuova.compress_type = info.compress_type
                nuova.external_attr = info.external_attr
            nuova.create_system = 0
            if nuova.compress_type == zipfile.ZIP_STORED:
                # Campo extra 0xD935 (quello di zipalign) lungo quanto serve
                # perché i dati comincino su un multiplo di 4.
                inizio = fp.tell() + 30 + len(nuova.filename.encode("utf-8"))
                pad = (-(inizio + 6)) % 4
                nuova.extra = struct.pack("<HHH", 0xD935, 2 + pad, 4) + b"\0" * pad
            dst.writestr(nuova, dati)
        dst.close()
    with zipfile.ZipFile(uscita) as z:
        for i in z.infolist():
            if i.compress_type == zipfile.ZIP_STORED:
                dati = i.header_offset + 30 + len(i.filename.encode("utf-8")) + len(i.extra)
                assert dati % 4 == 0, f"{i.filename} non allineato"


# --------------------------------------------------------------------------
# L'APK
# --------------------------------------------------------------------------
def apk():
    t = attrezzi()
    cartella_asset = asset()
    res_zip = COSTRUZIONE / "res.zip"
    gen = COSTRUZIONE / "gen"
    classi = COSTRUZIONE / "classes"
    for d in (gen, classi):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)

    print("risorse")
    esegui([t["aapt2"], "compile", "--dir", APP / "res", "-o", res_zip])
    base = COSTRUZIONE / "base.apk"
    esegui([t["aapt2"], "link", "-I", t["android_jar"], "--manifest", APP / "AndroidManifest.xml",
            "-A", cartella_asset, "--java", gen, "-o", base,
            "--min-sdk-version", MIN_SDK, "--target-sdk-version", TARGET_SDK,
            "--version-code", CODICE_VERSIONE, "--version-name", VERSIONE, "--auto-add-overlay", res_zip])

    print("java")
    sorgenti = sorted(glob.glob(str(APP / "java" / "**" / "*.java"), recursive=True) + glob.glob(str(gen / "**" / "*.java"), recursive=True))
    esegui(["javac", "-nowarn", "-Xlint:-options", "-encoding", "UTF-8", "-source", "8", "-target", "8",
            "-bootclasspath", t["android_jar"], "-classpath", t["android_jar"], "-d", classi] + sorgenti)

    print("dex")
    dex_dir = COSTRUZIONE / "dex"
    if dex_dir.exists():
        shutil.rmtree(dex_dir)
    dex_dir.mkdir()
    if t["d8"]:
        file_classe = sorted(glob.glob(str(classi / "**" / "*.class"), recursive=True))
        esegui([t["d8"], "--release", "--lib", t["android_jar"], "--min-api", MIN_SDK, "--output", dex_dir] + file_classe)
    else:
        esegui(["java", "-jar", t["dx_jar"], "--dex", f"--min-sdk-version={MIN_SDK}", f"--output={dex_dir / 'classes.dex'}", classi])

    print("pacchetto")
    allineato = COSTRUZIONE / "allineato.apk"
    allinea_e_aggiungi(base, dex_dir / "classes.dex", allineato)

    if not FIRMA.exists():
        FIRMA.parent.mkdir(parents=True, exist_ok=True)
        esegui(["keytool", "-genkeypair", "-keystore", FIRMA, "-storepass", FIRMA_PASSWORD, "-keypass", FIRMA_PASSWORD,
                "-alias", FIRMA_ALIAS, "-keyalg", "RSA", "-keysize", "2048", "-validity", "10000",
                "-dname", "CN=Page Brawl (prova), O=rikyroky91"])
    finale = COSTRUZIONE / "PageBrawl.apk"
    esegui(["java", "-jar", t["apksigner_jar"], "sign", "--ks", FIRMA, "--ks-pass", f"pass:{FIRMA_PASSWORD}",
            "--ks-key-alias", FIRMA_ALIAS, "--min-sdk-version", MIN_SDK, "--out", finale, allineato])
    esegui(["java", "-jar", t["apksigner_jar"], "verify", "--min-sdk-version", MIN_SDK, finale])
    print(f"\nAPK pronto: {finale} ({finale.stat().st_size // 1024} KB)")
    return finale


if __name__ == "__main__":
    COSTRUZIONE.mkdir(exist_ok=True)
    if "--solo-asset" in sys.argv:
        asset()
    else:
        apk()
