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
    python3 android/costruisci.py              # scrive android/build/PageBrawl.apk (chiave di prova)
    python3 android/costruisci.py --aab        # anche android/build/PageBrawl.aab per il Play Store
    python3 android/costruisci.py --leggera    # variante senza accessibilità (piano B per il Play Store)
    python3 android/costruisci.py --solo-asset # solo android/build/assets (per provare l'arena nel browser)
    python3 android/costruisci.py --gradle --aab [--leggera]
                                               # prepara android/build per android/gradle-progetto (build del Play
                                               # con Google Play Billing, su GitHub Actions); poi si firma l'AAB
                                               # con `python3 android/costruisci.py --firma file.aab`

Per il Play Store (12/10/2026): target API 36 (obbligatorio dal 31/08/2026), android.jar della
piattaforma 36 (`android-36.jar` in ~/tools va bene), AAB fatto con bundletool (`bundletool.jar` in
~/tools) e firmato con la chiave di caricamento `firma/pagebrawl-upload.jks`, che resta fuori dal repo
(password in `firma/pagebrawl-upload.txt`, o in $PB_FIRMA_PASSWORD). Se la chiave manca la crea.
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

VERSIONE = "1.5.1"
CODICE_VERSIONE = 9          # la variante leggera prende CODICE_VERSIONE + 1 (vedi LEGGIMI, piano B)
MIN_SDK = 26
TARGET_SDK = 36

LEGGERA = "--leggera" in sys.argv
NOME = "PageBrawl-lite" if LEGGERA else "PageBrawl"

CARICAMENTO = QUI / "firma" / "pagebrawl-upload.jks"
CARICAMENTO_PASSWORD = QUI / "firma" / "pagebrawl-upload.txt"
CARICAMENTO_ALIAS = "upload"

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
    # Sopra lo schermo si entra subito nel combattimento libero (la corsa è nelle arene dell'app).
    ("window.__ringSceltaModo = true;", "window.__ringSceltaModo = window.__pbSceltaModo !== false;"),
    # La classifica globale (13/10/2026): nell'app la chiama ponte.js direttamente, senza service worker.
    ("window.__ringClassifica = {", "window.__ringClassifica = window.__pbClassifica || {"),
]


# Per il Play Store (--aab) i personaggi di partenza sono robot e mela invece dei super guerrieri: Zefir
# (capelli a punte, casacca arancione, onda di energia, capelli dorati alla trasformazione) richiama troppo
# Dragon Ball per la prima schermata che vede un revisore. I guerrieri restano sceglibili nel menu.
# Per tenere i guerrieri di serie anche nello store: --guerrieri.
if "--aab" in sys.argv and "--guerrieri" not in sys.argv:
    SOSTITUZIONI_PREPARA.append(('memoria["mut-ring-stile"] = "guerrieri";', 'memoria["mut-ring-stile"] = "";'))


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
        "android_jar": primo(os.environ.get("ANDROID_JAR"), sdk and Path(sdk) / "platforms" / f"android-{TARGET_SDK}" / "android.jar",
                             casa / f"android-{TARGET_SDK}.jar", casa / "android.jar"),
        "bundletool": primo(os.environ.get("BUNDLETOOL_JAR"), casa / "bundletool.jar"),
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
def manifesto():
    """Il manifest. Nella variante leggera senza i due servizi: niente accessibilità, niente riquadro."""
    testo = (APP / "AndroidManifest.xml").read_text(encoding="utf-8")
    if LEGGERA:
        servizi = re.findall(r"\n\s*<service\b.*?</service>", testo, flags=re.S)
        if len(servizi) != 2 or "BIND_ACCESSIBILITY_SERVICE" not in testo:
            raise SystemExit("AndroidManifest.xml è cambiato: attesi 2 servizi, uno di accessibilità")
        for sv in servizi:
            testo = testo.replace(sv, "")
        if "accessibility" in testo.lower():
            raise SystemExit("la variante leggera parla ancora di accessibilità nel manifest")
    uscita = COSTRUZIONE / "AndroidManifest.xml"
    uscita.write_text(testo, encoding="utf-8")
    return uscita


def variante(gen):
    """La variante si sceglie qui: una costante che Principale legge (nascosti modalità e riquadro)."""
    var = gen / "com" / "rikyroky" / "pagebrawl" / "Variante.java"
    var.parent.mkdir(parents=True, exist_ok=True)
    var.write_text("package com.rikyroky.pagebrawl;\n\n/** Generato da costruisci.py. */\n"
                   f"final class Variante {{\n    private Variante() {{}}\n    static final boolean LEGGERA = {'true' if LEGGERA else 'false'};\n}}\n",
                   encoding="utf-8")


def prepara_gradle():
    """Per la build Gradle (quella del Play, con Google Play Billing): asset, manifest, variante e versione
    in android/build, dove li legge android/gradle-progetto. Niente aapt2 né javac: li fa Gradle."""
    asset()
    dest = COSTRUZIONE / "gradle"
    if dest.exists():
        shutil.rmtree(dest)
    (dest / "gen").mkdir(parents=True)
    # Con Gradle il pacchetto lo dà `namespace` in build.gradle.kts: nel manifest non ci deve stare.
    testo = manifesto().read_text(encoding="utf-8")
    testo2 = re.sub(r'\s+package="[^"]+"', "", testo, count=1)
    if testo2 == testo:
        raise SystemExit("AndroidManifest.xml è cambiato: manca package=")
    (dest / "AndroidManifest.xml").write_text(testo2, encoding="utf-8")
    variante(dest / "gen")
    (dest / "config.properties").write_text(
        f"versionCode={CODICE_VERSIONE + (1 if LEGGERA else 0)}\nversionName={VERSIONE + ('-lite' if LEGGERA else '')}\n", encoding="utf-8")
    print(f"pronto per Gradle in {dest} ({'leggera' if LEGGERA else 'completa'}, codice {CODICE_VERSIONE + (1 if LEGGERA else 0)})")


def collega(t, res_zip, cartella_asset, gen, uscita, proto=False):
    esegui([t["aapt2"], "link", "-I", t["android_jar"], "--manifest", manifesto(),
            "-A", cartella_asset, "--java", gen, "-o", uscita,
            "--min-sdk-version", MIN_SDK, "--target-sdk-version", TARGET_SDK,
            "--version-code", CODICE_VERSIONE + (1 if LEGGERA else 0), "--version-name", VERSIONE + ("-lite" if LEGGERA else ""),
            "--auto-add-overlay"] + (["--proto-format"] if proto else []) + [res_zip])


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
    collega(t, res_zip, cartella_asset, gen, base)
    variante(gen)

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
    finale = COSTRUZIONE / f"{NOME}.apk"
    esegui(["java", "-jar", t["apksigner_jar"], "sign", "--ks", FIRMA, "--ks-pass", f"pass:{FIRMA_PASSWORD}",
            "--ks-key-alias", FIRMA_ALIAS, "--min-sdk-version", MIN_SDK, "--out", finale, allineato])
    esegui(["java", "-jar", t["apksigner_jar"], "verify", "--min-sdk-version", MIN_SDK, finale])
    print(f"\nAPK pronto: {finale} ({finale.stat().st_size // 1024} KB)")
    if "--aab" in sys.argv:
        aab(t, res_zip, cartella_asset, dex_dir / "classes.dex")
    return finale


# --------------------------------------------------------------------------
# L'AAB per il Play Store
# --------------------------------------------------------------------------
def chiave_caricamento():
    """La chiave di caricamento (Play App Signing: Google firma le APK vere, questa prova solo che sei tu)."""
    pw = os.environ.get("PB_FIRMA_PASSWORD") or (CARICAMENTO_PASSWORD.read_text().strip() if CARICAMENTO_PASSWORD.exists() else "")
    if not CARICAMENTO.exists():
        import secrets
        pw = pw or secrets.token_urlsafe(18)
        esegui(["keytool", "-genkeypair", "-keystore", CARICAMENTO, "-storetype", "PKCS12", "-storepass", pw, "-keypass", pw,
                "-alias", CARICAMENTO_ALIAS, "-keyalg", "RSA", "-keysize", "4096", "-validity", "10000",
                "-dname", "CN=Page Brawl upload key, O=rikyroky91"])
        CARICAMENTO_PASSWORD.write_text(pw + "\n")
        print(f"  nuova chiave di caricamento: {CARICAMENTO} (password in {CARICAMENTO_PASSWORD.name}) - tienile al sicuro")
    if not pw:
        raise SystemExit(f"manca la password di {CARICAMENTO.name}: $PB_FIRMA_PASSWORD o {CARICAMENTO_PASSWORD.name}")
    return pw


def aab(t, res_zip, cartella_asset, dex):
    if not t["bundletool"]:
        raise SystemExit("manca bundletool.jar (github.com/google/bundletool/releases) in ~/tools o $BUNDLETOOL_JAR")
    print("aab")
    proto = COSTRUZIONE / "base-proto.apk"
    collega(t, res_zip, cartella_asset, COSTRUZIONE / "gen-proto", proto, proto=True)
    modulo = COSTRUZIONE / "base-modulo.zip"
    with zipfile.ZipFile(proto) as src, zipfile.ZipFile(modulo, "w", zipfile.ZIP_DEFLATED) as dst:
        for i in src.infolist():
            nome = "manifest/AndroidManifest.xml" if i.filename == "AndroidManifest.xml" else i.filename
            dst.writestr(nome, src.read(i.filename))
        dst.write(dex, "dex/classes.dex")
    grezzo = COSTRUZIONE / f"{NOME}-non-firmato.aab"
    finale = COSTRUZIONE / f"{NOME}.aab"
    for f in (grezzo, finale):
        if f.exists():
            f.unlink()
    esegui(["java", "-jar", t["bundletool"], "build-bundle", f"--modules={modulo}", f"--output={grezzo}"])
    firma_aab(t, grezzo, finale)
    print(f"AAB pronto: {finale} ({finale.stat().st_size // 1024} KB)")
    print("  ATTENZIONE: questo AAB non ha Google Play Billing (Premium sempre aperto). Per il Play usa quello di\n"
          "  GitHub Actions (workflow android-play), firmato con: python3 android/costruisci.py --firma <file>.aab")
    return finale


def firma_aab(t, grezzo, finale):
    """Firma un AAB con la chiave di caricamento (anche uno fatto da Gradle su GitHub Actions) e lo controlla."""
    finale = Path(finale)
    if finale.exists():
        finale.unlink()
    pw = chiave_caricamento()
    esegui(["jarsigner", "-sigalg", "SHA256withRSA", "-digestalg", "SHA-256", "-keystore", CARICAMENTO,
            "-storepass", pw, "-signedjar", finale, grezzo, CARICAMENTO_ALIAS])
    v = esegui(["jarsigner", "-verify", finale])          # chiave autofirmata: niente -strict, come per ogni chiave Android
    if "jar verified" not in v.stdout:
        raise SystemExit("firma dell'AAB non valida")
    esegui(["java", "-jar", t["bundletool"], "validate", f"--bundle={finale}"])
    return finale


if __name__ == "__main__":
    COSTRUZIONE.mkdir(exist_ok=True)
    if "--firma" in sys.argv:
        # python3 android/costruisci.py --firma entrata.aab [uscita.aab]
        i = sys.argv.index("--firma")
        entrata = Path(sys.argv[i + 1])
        uscita = Path(sys.argv[i + 2]) if len(sys.argv) > i + 2 and sys.argv[i + 2].endswith(".aab") else entrata.with_name(entrata.stem.replace("-nonfirmato", "") + ".aab")
        firma_aab(attrezzi(), entrata, uscita)
        print(f"AAB firmato: {uscita}")
    elif "--gradle" in sys.argv:
        prepara_gradle()
    elif "--solo-asset" in sys.argv:
        asset()
    else:
        apk()
