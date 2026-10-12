package com.rikyroky.pagebrawl;

import android.app.Activity;
import android.content.Context;
import android.os.Handler;
import android.os.Looper;

import java.util.ArrayList;
import java.util.List;

/**
 * Lo sblocco Premium (12/10/2026, Riccardo: «facciamo gratuito con sblocco premium»).
 *
 * Gratis: robot e mela, tutte e quattro le modalità, le arene, la corsa infinita.
 * Premium, acquisto unico: i tre gruppi che il motore sa già chiudere (`window.__ringPremium.bloccate`):
 *   guerrieri = gli stili di personaggi (super guerrieri, maghi, duellanti);
 *   armi      = le armi da mettere in campo e quelle che cadono;
 *   meteo     = gli imprevisti grossi (meteoriti, orda, buco nero) e la gravità.
 *
 * Il pagamento vero sta in `PremiumGoogle` (cartella `java-billing`), compilata solo dalla build Gradle,
 * che ha la libreria di Google Play Billing. La build senza Gradle (APK di prova) non ce l'ha: lì vale
 * `Finto`, con tutto sbloccato, così le prove sul telefono restano complete.
 *
 * Lo stato si ricorda nelle opzioni dell'app (non nella memoria del gioco, che le pagine web del browser
 * interno possono scrivere) e si riconferma con Google a ogni avvio.
 */
abstract class Premium {
    static final String PRODOTTO = "premium";

    interface Ascoltatore { void cambiato(boolean attivo); }
    interface Prezzo { void pronto(String prezzo); }

    private static Premium unico;
    private final List<Ascoltatore> ascoltatori = new ArrayList<Ascoltatore>();
    protected final Context app;
    protected final Handler h = new Handler(Looper.getMainLooper());

    protected Premium(Context c) { app = c.getApplicationContext(); }

    static synchronized Premium di(Context c) {
        if (unico == null) {
            try {
                Class<?> k = Class.forName("com.rikyroky.pagebrawl.PremiumGoogle");
                unico = (Premium) k.getDeclaredConstructor(Context.class).newInstance(c.getApplicationContext());
            } catch (Throwable senzaLibreria) {
                unico = new Finto(c);
            }
            unico.avvia();
        }
        return unico;
    }

    /** True se in questa build c'è davvero qualcosa da comprare. */
    abstract boolean vero();
    /** Collega Google Play e riconferma gli acquisti. */
    abstract void avvia();
    /** Il prezzo localizzato del Premium (null se Google Play non risponde). */
    abstract void prezzo(Prezzo p);
    /** Apre il pagamento di Google Play. */
    abstract void compra(Activity a);
    /** Richiede a Google Play gli acquisti già fatti (stesso account, altro telefono, reinstallazione). */
    abstract void ripristina();

    boolean attivo() { return !vero() || Memoria.opzioni(app).getBoolean("premium", false); }

    /** Per la pagina: "libero" (niente da comprare in questa build), "attivo" o "chiuso". */
    String stato() { return !vero() ? "libero" : attivo() ? "attivo" : "chiuso"; }

    void ascolta(Ascoltatore a) { synchronized (ascoltatori) { if (!ascoltatori.contains(a)) ascoltatori.add(a); } }
    void smetti(Ascoltatore a) { synchronized (ascoltatori) { ascoltatori.remove(a); } }

    /** Da chiamare quando Google Play conferma (o toglie, dopo un rimborso) l'acquisto. */
    protected void imposta(final boolean si) {
        boolean prima = Memoria.opzioni(app).getBoolean("premium", false);
        Memoria.opzioni(app).edit().putBoolean("premium", si).apply();
        if (prima == si) return;
        h.post(new Runnable() {
            @Override public void run() {
                List<Ascoltatore> copia;
                synchronized (ascoltatori) { copia = new ArrayList<Ascoltatore>(ascoltatori); }
                for (Ascoltatore a : copia) { try { a.cambiato(si); } catch (Exception ignorata) { } }
            }
        });
    }

    /** Il JavaScript che dice al ring lo stato attuale (per le pagine già aperte). */
    static String js(boolean attivo) { return "window.__pbPremium&&window.__pbPremium(" + attivo + ")"; }

    /** La build senza libreria di pagamento: niente da comprare, tutto aperto. */
    private static final class Finto extends Premium {
        Finto(Context c) { super(c); }
        @Override boolean vero() { return false; }
        @Override void avvia() { }
        @Override void prezzo(Prezzo p) { p.pronto(null); }
        @Override void compra(Activity a) { }
        @Override void ripristina() { }
    }
}
