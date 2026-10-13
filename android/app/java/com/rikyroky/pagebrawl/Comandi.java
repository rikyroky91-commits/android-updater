package com.rikyroky.pagebrawl;

import android.content.Context;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.HapticFeedbackConstants;
import android.view.MotionEvent;
import android.view.View;
import android.webkit.ValueCallback;
import android.webkit.WebView;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * I COMANDI DA TELEFONO (12/10/2026, Riccardo: «la vita e i dati del round in
 * un'icona semitrasparente e pulita; i comandi 4 tasti con abilità pronte che
 * si intercambiano, in bianco e nero quando sono scarichi e pian piano si
 * colorano, con feedback aptico»; «in qualsiasi momento togliere qualsiasi
 * elemento a schermo e mettere in pausa»).
 *
 *  - In alto la capsula: pausa · i due lottatori (anello = vita, tocco = lo
 *    comandi tu) e il punteggio · menu ⋯ · ✕ che toglie il gioco.
 *  - Il menu ⋯: tasti sì/no, lottatori sì/no, riduci tutto a un puntino,
 *    opzioni del ring (la tendina del motore).
 *  - In basso a destra 4 tasti ad arco, uno per finestra (sopra lo schermo
 *    il resto lascia passare i tocchi).
 *
 * Stessa classe sopra lo schermo (finestre di accessibilità), nel browser e
 * nelle arene (viste dentro l'attività): cambia solo l'`Ospite`.
 * I dati vengono dal motore: `__ring.mosse()` ogni 120 ms.
 */
final class Comandi {

    /** Dove stanno i comandi e cosa sa fare chi li ospita. */
    interface Ospite {
        /** Mette una vista: `gravita` come in FrameLayout/WindowManager, x/y distanze dal bordo indicato. */
        void metti(View v, int gravita, int x, int y, int w, int h, boolean tocchiFuori);
        void sposta(View v, int gravita, int x, int y, int w, int h);
        void togli(View v);
        /** La superficie del ring deve ricevere i tocchi (tendina aperta) o lasciarli passare. */
        void superficieToccabile(boolean si);
        void mostraLottatori(boolean si);
        /** Le zone toccabili che seguono i lottatori (per prenderli col dito) servono o no. */
        void seguiLottatori(boolean si);
        /** La frequenza dello schermo che serve (120 per i 120 fps, 0 = quella di sistema). */
        void frequenza(float hz);
        void apriApp();
        void chiudiGioco();
        int margineAlto();
        int margineBasso();
    }

    private static final long OGNI = 120;
    private static final String[] PRIORITA_BASE = {"pugno", "calcio", "presa", "salto", "para", "montante", "jet", "lancia"};

    private final Context ctx;
    private final Ospite ospite;
    private final WebView web;
    private final Handler h = new Handler(Looper.getMainLooper());
    private final SharedPreferences pref;
    private final float d;

    private LinearLayout capsula;
    private Disegni.Icona tastoPausa, tastoAltro, tastoChiudi, puntino;
    private Disegni.Avatar avatarA, avatarB;
    private TextView punti;
    private LinearLayout menu;
    private TextView vTasti, vLottatori;
    private final Disegni.Tasto[] tasti = new Disegni.Tasto[4];
    private final String[] posti = new String[4];

    private int giro;
    private boolean attivo, finito, visibili, ridotto, mostraTasti, mostraLottatori, inPausa, pannello, menuAperto;
    private String chi = "robot", tipoA = "robot", tipoB = "mela";
    private int coloreChi = Color.WHITE;
    private String firmaVoci = "";
    private final Map<String, Voce> voci = new HashMap<String, Voce>();
    private final List<String> ordine = new ArrayList<String>();
    private long ultimoTick;

    private static final class Voce {
        String id, icona;
        int costo;
        boolean pronta;
        long usata, durata;
        float carica;
        boolean eraPronta;
    }

    Comandi(Context ctx, Ospite ospite, WebView web) {
        this.ctx = ctx;
        this.ospite = ospite;
        this.web = web;
        this.pref = Memoria.opzioni(ctx);
        this.d = ctx.getResources().getDisplayMetrics().density;
        mostraTasti = pref.getBoolean("ui_tasti", true);
        mostraLottatori = true;
        costruisci();
    }

    void avvia() {
        if (finito) return;
        attivo = true;
        h.post(leggi);
    }

    /**
     * Toglie i comandi e smette di leggere il motore, per sempre.
     *
     * 13/10/2026 (Riccardo: «si è creato un layer di gioco bloccato che non si toglie con niente»): la lettura
     * del motore è asincrona e la sua risposta poteva arrivare DOPO `ferma()` (spegnendo lo schermo il ring si
     * chiudeva a metà di una lettura): `applica` → `dispone` rimetteva capsula e tasti in finestre nuove che
     * nessuno conosceva più, e restavano sullo schermo, ferme, finché non si spegneva il servizio. Ora, da
     * fermi, ogni risposta in ritardo si butta e `dispone` non mette più niente.
     */
    void ferma() {
        finito = true;
        sospendi();
    }

    /** Toglie i comandi e smette di leggere il motore, ma tiene lo stato: `riprendi()` li rimette com'erano. */
    void sospendi() {
        attivo = false;
        giro++;                              // le letture già partite non valgono più

        if (seguendo) { seguendo = false; ospite.seguiLottatori(false); }
        if (superficie) { superficie = false; ospite.superficieToccabile(false); }
        h.removeCallbacksAndMessages(null);
        togliTutto();
    }

    void riprendi() {
        if (finito || attivo) return;
        attivo = true;
        dispone();
        h.post(leggi);
    }

    /** Il gioco era in pausa (dall'utente o dal motore). */
    boolean inPausa() { return inPausa; }

    private int px(float dp) { return Math.round(dp * d); }

    // ------------------------------------------------------------ le viste
    private void costruisci() {
        capsula = new LinearLayout(ctx);
        capsula.setOrientation(LinearLayout.HORIZONTAL);
        capsula.setGravity(Gravity.CENTER_VERTICAL);
        capsula.setPadding(px(4), px(2), px(4), px(2));
        GradientDrawable g = new GradientDrawable();
        g.setColor(Disegni.VETRO);
        g.setCornerRadius(px(24));
        g.setStroke(Math.max(1, px(1)), Disegni.FILO);
        capsula.setBackground(g);

        tastoPausa = icona(Disegni.PAUSA, "Pause", new View.OnClickListener() {
            @Override public void onClick(View v) { pausa(!inPausa); }
        });
        capsula.addView(tastoPausa, new LinearLayout.LayoutParams(px(40), px(40)));
        avatarA = new Disegni.Avatar(ctx);
        avatarA.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { comanda(tipoA); }
        });
        capsula.addView(avatarA, new LinearLayout.LayoutParams(px(36), px(40)));
        punti = new TextView(ctx);
        punti.setTextColor(Disegni.BIANCO);
        punti.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
        punti.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        punti.setGravity(Gravity.CENTER);
        punti.setMinWidth(px(52));
        capsula.addView(punti, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, px(40)));
        avatarB = new Disegni.Avatar(ctx);
        avatarB.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { comanda(tipoB); }
        });
        capsula.addView(avatarB, new LinearLayout.LayoutParams(px(36), px(40)));
        tastoAltro = icona(Disegni.ALTRO, "More", new View.OnClickListener() {
            @Override public void onClick(View v) { apriMenu(!menuAperto); }
        });
        capsula.addView(tastoAltro, new LinearLayout.LayoutParams(px(40), px(40)));
        tastoChiudi = icona(Disegni.CHIUDI, "Remove the game from the screen", new View.OnClickListener() {
            @Override public void onClick(View v) { tocco(v); ospite.chiudiGioco(); }
        });
        capsula.addView(tastoChiudi, new LinearLayout.LayoutParams(px(40), px(40)));

        // Ridotto a icona: un puntino col guantone; un tocco e torna tutto.
        puntino = new Disegni.Icona(ctx, Disegni.GUANTO, true);
        puntino.setContentDescription("Show Page Brawl controls");
        puntino.setAlpha(0.8f);
        puntino.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { tocco(v); riduci(false); }
        });

        // Il menu ⋯
        menu = new LinearLayout(ctx);
        menu.setOrientation(LinearLayout.VERTICAL);
        menu.setPadding(px(6), px(6), px(6), px(6));
        GradientDrawable gm = new GradientDrawable();
        gm.setColor(0xE6121614);
        gm.setCornerRadius(px(18));
        gm.setStroke(Math.max(1, px(1)), Disegni.FILO);
        menu.setBackground(gm);
        vTasti = voceMenu("", new View.OnClickListener() {
            @Override public void onClick(View v) {
                mostraTasti = !mostraTasti;
                pref.edit().putBoolean("ui_tasti", mostraTasti).apply();
                aggiornaMenu(); dispone();
            }
        });
        vLottatori = voceMenu("", new View.OnClickListener() {
            @Override public void onClick(View v) {
                mostraLottatori = !mostraLottatori;
                ospite.mostraLottatori(mostraLottatori);
                if (!mostraLottatori) pausa(true);
                aggiornaMenu();
            }
        });
        voceMenu("Minimise", new View.OnClickListener() {
            @Override public void onClick(View v) { riduci(true); }
        });
        voceMenu("Game options", new View.OnClickListener() {
            @Override public void onClick(View v) {
                apriMenu(false);
                pannello = true;
                tocchi(true);
                web.evaluateJavascript("window.__ring&&__ring.pannello(true)", null);
            }
        });
        voceMenu("Open Page Brawl", new View.OnClickListener() {
            @Override public void onClick(View v) { apriMenu(false); ospite.apriApp(); }
        });
        menu.setOnTouchListener(new View.OnTouchListener() {
            @Override public boolean onTouch(View v, MotionEvent e) {
                if (e.getActionMasked() == MotionEvent.ACTION_OUTSIDE) { apriMenu(false); return true; }
                return false;
            }
        });
        aggiornaMenu();

        for (int i = 0; i < 4; i++) {
            final int n = i;
            Disegni.Tasto t = new Disegni.Tasto(ctx);
            t.setOnClickListener(new View.OnClickListener() {
                @Override public void onClick(View v) { usa(n); }
            });
            tasti[i] = t;
        }
    }

    private Disegni.Icona icona(int tipo, String nome, final View.OnClickListener clic) {
        Disegni.Icona i = new Disegni.Icona(ctx, tipo, false);
        i.setContentDescription(nome);
        i.setOnClickListener(clic);
        return i;
    }

    private TextView voceMenu(String testo, View.OnClickListener clic) {
        TextView t = new TextView(ctx);
        t.setText(testo);
        t.setTextColor(Disegni.BIANCO);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
        t.setPadding(px(14), px(12), px(18), px(12));
        t.setOnClickListener(clic);
        menu.addView(t, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT));
        return t;
    }

    private void aggiornaMenu() {
        vTasti.setText((mostraTasti ? "✓  " : "     ") + "Ability buttons");
        vLottatori.setText((mostraLottatori ? "✓  " : "     ") + "Fighters");
    }

    // --------------------------------------------------------- disposizione
    private boolean capsulaMessa, puntinoMesso, menuMesso;
    private final boolean[] tastoMesso = new boolean[4];

    /** Mette o toglie ogni pezzo secondo lo stato. */
    private void dispone() {
        if (!attivo) return;                 // fermi o sospesi: niente finestre nuove (vedi `ferma`)
        boolean vedoCapsula = visibili && !ridotto;
        boolean vedoTasti = visibili && !ridotto && mostraTasti && !inPausa && mostraLottatori;
        int alto = ospite.margineAlto() + px(8);
        if (vedoCapsula != capsulaMessa) {
            if (vedoCapsula) ospite.metti(capsula, Gravity.TOP | Gravity.CENTER_HORIZONTAL, 0, alto, -2, px(44), false);
            else ospite.togli(capsula);
            capsulaMessa = vedoCapsula;
        }
        boolean vedoPuntino = visibili && ridotto;
        if (vedoPuntino != puntinoMesso) {
            if (vedoPuntino) ospite.metti(puntino, Gravity.TOP | Gravity.RIGHT, px(10), alto, px(36), px(36), false);
            else ospite.togli(puntino);
            puntinoMesso = vedoPuntino;
        }
        boolean vedoMenu = vedoCapsula && menuAperto;
        if (vedoMenu != menuMesso) {
            if (vedoMenu) ospite.metti(menu, Gravity.TOP | Gravity.CENTER_HORIZONTAL, px(70), alto + px(50), px(220), -2, true);
            else ospite.togli(menu);
            menuMesso = vedoMenu;
        }
        // I 4 tasti nell'angolo in basso a destra, come nei giochi d'azione da telefono: il primo (la mossa
        // base, sempre a portata) più grande nell'angolo, gli altri tre attorno a lui (sinistra, diagonale, su).
        int centro = px(60), raggio = px(94), basso = ospite.margineBasso();
        for (int i = 0; i < 4; i++) {
            boolean vedo = vedoTasti && posti[i] != null;
            if (vedo != tastoMesso[i]) {
                if (vedo) {
                    int lato = i == 0 ? px(66) : px(54), cx = centro, cy = centro;
                    if (i > 0) {
                        double a = Math.toRadians(180 + 45 * (i - 1));    // 180° sinistra, 225° diagonale, 270° su
                        cx += (int) Math.round(-Math.cos(a) * raggio);
                        cy += (int) Math.round(-Math.sin(a) * raggio);
                    }
                    ospite.metti(tasti[i], Gravity.BOTTOM | Gravity.RIGHT, cx - lato / 2, basso + cy - lato / 2, lato, lato, false);
                } else ospite.togli(tasti[i]);
                tastoMesso[i] = vedo;
            }
        }
    }

    private void togliTutto() {
        if (capsulaMessa) ospite.togli(capsula);
        if (puntinoMesso) ospite.togli(puntino);
        if (menuMesso) ospite.togli(menu);
        for (int i = 0; i < 4; i++) if (tastoMesso[i]) ospite.togli(tasti[i]);
        capsulaMessa = puntinoMesso = menuMesso = false;
        for (int i = 0; i < 4; i++) tastoMesso[i] = false;
    }

    /** Rimette tutto al suo posto, per esempio quando cambiano i margini (tacca della fotocamera). */
    void ridisponi() {
        if (!attivo) return;
        togliTutto();
        dispone();
    }

    private void apriMenu(boolean si) { menuAperto = si; dispone(); }

    private void riduci(boolean si) {
        ridotto = si;
        menuAperto = false;
        dispone();
    }

    // -------------------------------------------------------------- azioni
    private void tocco(View v) {
        v.performHapticFeedback(Build.VERSION.SDK_INT >= 30 ? HapticFeedbackConstants.CONFIRM : HapticFeedbackConstants.VIRTUAL_KEY,
                HapticFeedbackConstants.FLAG_IGNORE_VIEW_SETTING);
    }

    private void rifiuto(View v) {
        v.performHapticFeedback(Build.VERSION.SDK_INT >= 30 ? HapticFeedbackConstants.REJECT : HapticFeedbackConstants.LONG_PRESS,
                HapticFeedbackConstants.FLAG_IGNORE_VIEW_SETTING);
    }

    private void pausa(boolean si) {
        inPausa = si;
        tastoPausa.tipo(si ? Disegni.GIOCA : Disegni.PAUSA);
        tastoPausa.setContentDescription(si ? "Resume" : "Pause");
        tocco(tastoPausa);
        web.evaluateJavascript("window.__ring&&__ring.pausa(" + si + ")", null);
        aggiornaPunti(null);
        dispone();
    }

    private void comanda(String tipo) {
        if (tipo.equals(chi)) return;
        tocco(capsula);
        web.evaluateJavascript("window.__ring&&__ring.cambia()", null);
    }

    private void usa(final int i) {
        final String id = posti[i];
        final Voce v = id == null ? null : voci.get(id);
        final Disegni.Tasto t = tasti[i];
        if (v == null || !t.pronta()) { rifiuto(t); t.rifiuta(); return; }
        String js = "__finale".equals(id) ? "window.__ring?__ring.corsaFinale():false"
                : id.startsWith("__oggetto") ? "window.__ring?__ring.corsaOggetto(" + id.substring(9) + "):false"
                : "window.__ring?__ring.ordina(" + JSONObject.quote(chi) + "," + JSONObject.quote(id) + "):false";
        final boolean speciale = id.startsWith("__");
        web.evaluateJavascript(js,
                new ValueCallback<String>() {
                    @Override public void onReceiveValue(String ok) {
                        if ("true".equals(ok)) {
                            tocco(t);
                            if (speciale) return;                     // nella corsa carica e oggetti li conta il gioco
                            v.usata = SystemClock.uptimeMillis();
                            v.durata = attesa(id);
                            v.carica = 0;
                            ruota();
                            mostraTasto(i);
                        } else { rifiuto(t); t.rifiuta(); }
                    }
                });
    }

    /** Dopo l'uso ogni mossa si ricarica: le mosse a energia aspettano anche l'energia. */
    private static long attesa(String id) {
        switch (id) {
            case "pugno": case "calcio": case "montante": case "fendente": case "affondo": case "rovescio": case "rush": return 900;
            case "para": case "salto": return 1200;
            case "lancia": return 2000;
            case "presa": return 2600;
            case "carica": return 3000;
            case "jet": return 6000;
            case "trasforma": return 8000;
            default: return 1500;
        }
    }

    // ------------------------------------------------------- lettura stato
    private String graficaData = "";
    private final Runnable leggi = new Runnable() {
        @Override public void run() {
            if (!attivo) return;
            final int questo = giro;
            // La grafica scelta nell'app vale subito, anche a partita aperta.
            String g = Memoria.graficaJs(ctx), prima = "";
            if (!g.equals(graficaData)) {
                prima = "window.__ring&&window.__ring.grafica&&__ring.grafica(" + g + ");";
                graficaData = g;
                ospite.frequenza(Memoria.fps(ctx) == 120 ? 120f : 0f);
            }
            web.evaluateJavascript(prima + "(function(){try{return window.__ring&&window.__ring.mosse?JSON.stringify({m:__ring.mosse(),p:__ring.pannello(),z:__ring.pausa()}):''}catch(e){return ''}})()",
                    new ValueCallback<String>() {
                        @Override public void onReceiveValue(String s) {
                            if (!attivo || questo != giro) return;      // arrivata dopo ferma()/sospendi(): si butta
                            try { applica(s); } catch (Exception ignorata) { /* il prossimo giro */ }
                            if (attivo) h.postDelayed(leggi, ridotto ? 400 : OGNI);
                        }
                    });
        }
    };

    private void applica(String risposta) throws Exception {
        if (risposta == null || risposta.length() < 4 || "null".equals(risposta)) { visibili = false; dispone(); return; }
        String json = new JSONArray("[" + risposta + "]").getString(0);       // la risposta è una stringa JS tra virgolette
        if (json.isEmpty()) { visibili = false; dispone(); return; }
        JSONObject o = new JSONObject(json), m = o.getJSONObject("m");
        boolean p = o.optBoolean("p"), z = o.optBoolean("z");
        pannello = p;
        // La superficie prende i tocchi quando il gioco li chiede (tendina, corsa, mira, scelta del modo);
        // il resto del tempo li lascia al telefono, tranne sulle zone che seguono i lottatori.
        tocchi(p || m.optBoolean("vuoleTocchi"));
        if (z != inPausa) { inPausa = z; tastoPausa.tipo(z ? Disegni.GIOCA : Disegni.PAUSA); }
        visibili = m.optBoolean("acceso", true);
        boolean gioco = !m.optBoolean("scelta") && !m.optBoolean("corsa");
        chi = m.optString("chi", chi);
        JSONObject ch = m.optJSONObject("corsaHud");          // la corsa infinita, con l'eroe in campo
        boolean corsaLotta = ch != null && "lotta".equals(ch.optString("fase"));

        JSONArray ls = m.optJSONArray("lottatori");
        if (ls != null && ls.length() >= 2) {
            JSONObject a = ls.getJSONObject(0), b = ls.getJSONObject(1);
            tipoA = a.optString("tipo"); tipoB = b.optString("tipo");
            int ca = colore(a.optString("colore")), cb = colore(b.optString("colore"));
            avatarA.imposta(a.optString("nome"), ca, (float) a.optDouble("vita", 1), a.optBoolean("ko"), chi.equals(tipoA));
            avatarB.imposta(b.optString("nome"), cb, (float) b.optDouble("vita", 1), b.optBoolean("ko"), chi.equals(tipoB));
            coloreChi = chi.equals(tipoA) ? ca : cb;
            avatarA.setVisibility(gioco || ch != null ? View.VISIBLE : View.GONE);
            avatarB.setVisibility(gioco ? View.VISIBLE : View.GONE);
            if (gioco) {
                JSONObject pt = m.optJSONObject("punteggio");
                if (pt != null) aggiornaPunti(pt.optInt(tipoA) + " – " + pt.optInt(tipoB));
                double ki = (chi.equals(tipoA) ? a : b).optDouble("ki", 0);
                leggiVoci(m.optJSONArray("voci"), ki);
            } else if (ch != null) {
                // Corsa: l'eroe nella capsula (anello = vita), poi vite, round e cosa c'è da fare.
                JSONObject e = ch.optString("chi").equals(tipoB) ? b : a;
                coloreChi = colore(e.optString("colore"));
                float k = (float) (ch.optDouble("hp", 0) / Math.max(1, ch.optDouble("hpMax", 1)));
                avatarA.imposta(e.optString("nome"), coloreChi, k, false, true);
                String ob = ch.optString("obiettivo", "");
                aggiornaPunti("♥" + ch.optInt("vite") + "  ·  R" + ch.optInt("round") + (ob.isEmpty() ? "" : "  ·  " + ob));
            }
        }
        punti.setVisibility(gioco || ch != null || inPausa ? View.VISIBLE : View.GONE);
        if (corsaLotta) postiCorsa(ch);
        else if (!gioco) { for (int i = 0; i < 4; i++) posti[i] = null; inCorsa = false; }
        else {
            if (inCorsa) { inCorsa = false; for (int i = 0; i < 4; i++) posti[i] = null; }
            if (posti[0] == null) ruota();
        }
        dispone();
        for (int i = 0; i < 4; i++) mostraTasto(i);
        boolean segui = visibili && mostraLottatori && !inPausa && !superficie;
        if (segui != seguendo) { seguendo = segui; ospite.seguiLottatori(segui); }
    }

    private boolean superficie, seguendo;
    private void tocchi(boolean si) {
        if (si == superficie) return;
        superficie = si;
        ospite.superficieToccabile(si);
    }

    // ·· La corsa infinita: il colpo finale nell'angolo, i tre oggetti attorno ··
    private boolean inCorsa;
    private void postiCorsa(JSONObject ch) {
        if (!inCorsa) { inCorsa = true; firmaVoci = ""; voci.clear(); ordine.clear(); }
        Voce f = voce("__finale", "\uD83C\uDFAF");
        f.carica = (float) ch.optDouble("energia", 0);
        f.pronta = f.carica >= 1f;
        posti[0] = f.id;
        JSONArray og = ch.optJSONArray("oggetti");
        for (int i = 0; i < 3; i++) {
            JSONObject o = og == null ? null : og.optJSONObject(i);
            if (o == null) { posti[i + 1] = null; continue; }
            Voce v = voce("__oggetto" + i, o.optString("icona"));
            v.carica = 1f; v.pronta = true;
            posti[i + 1] = v.id;
        }
    }
    private Voce voce(String id, String icona) {
        Voce v = voci.get(id);
        if (v == null) { v = new Voce(); v.id = id; voci.put(id, v); }
        v.icona = icona;
        return v;
    }

    private String ultimiPunti = "0 – 0";
    private void aggiornaPunti(String s) {
        if (s != null) ultimiPunti = s;
        punti.setText(inPausa ? "Paused" : ultimiPunti);
    }

    private static int colore(String s) {
        try { return Color.parseColor(s); } catch (Exception e) { return Color.WHITE; }
    }

    private void leggiVoci(JSONArray arr, double ki) throws Exception {
        if (arr == null) return;
        StringBuilder firma = new StringBuilder();
        for (int i = 0; i < arr.length(); i++) firma.append(arr.getJSONObject(i).optString("id")).append(',');
        if (!firma.toString().equals(firmaVoci)) {
            // Personaggi cambiati: mosse nuove, tasti da rifare.
            firmaVoci = firma.toString();
            voci.clear(); ordine.clear();
            for (int i = 0; i < 4; i++) posti[i] = null;
        }
        long ora = SystemClock.uptimeMillis();
        boolean nuovaPronta = false;
        for (int i = 0; i < arr.length(); i++) {
            JSONObject j = arr.getJSONObject(i);
            String id = j.optString("id");
            Voce v = voci.get(id);
            if (v == null) { v = new Voce(); v.id = id; voci.put(id, v); ordine.add(id); }
            v.icona = j.optString("icona");
            v.costo = j.optInt("costo");
            v.pronta = j.optBoolean("pronta");
            float energia = v.costo > 0 ? (float) Math.min(1, ki / v.costo) : 1f;
            float attesa = v.durata > 0 ? Math.min(1f, (ora - v.usata) / (float) v.durata) : 1f;
            v.carica = Math.min(energia, attesa);
            boolean pronta = v.pronta && v.carica >= 1f;
            if (pronta && !v.eraPronta && !inPosto(id)) nuovaPronta = true;
            v.eraPronta = pronta;
        }
        if (nuovaPronta) ruota();
    }

    private boolean inPosto(String id) {
        for (String s : posti) if (id.equals(s)) return true;
        return false;
    }

    private boolean pronta(Voce v) { return v != null && v.pronta && v.carica >= 1f; }

    /**
     * I quattro posti. All'inizio le prime quattro per importanza (la prima, una mossa base, nell'angolo e lì
     * resta); poi, quando
     * un'abilità che non si vede diventa pronta, prende il posto di quella
     * più scarica fra le quattro (se non sono tutte pronte).
     */
    private void ruota() {
        if (voci.isEmpty()) return;
        if (posti[0] == null) {
            List<String> scelte = perImportanza();
            for (int i = 0; i < 4; i++) posti[i] = i < scelte.size() ? scelte.get(i) : null;
            return;
        }
        boolean cambiato = false;
        for (String id : perImportanza()) {
            Voce v = voci.get(id);
            if (!pronta(v) || inPosto(id)) continue;
            // Il posto più scarico: vuoto, poi una mossa che adesso non si può fare, poi la meno carica.
            int peggiore = -1;
            float min = 1f;
            for (int i = 1; i < 4; i++) {                       // il posto 0 (l'angolo) resta alla mossa base
                Voce w = posti[i] == null ? null : voci.get(posti[i]);
                float c = w == null ? -2f : !w.pronta ? -1f : w.carica;
                if (c < min) { min = c; peggiore = i; }
            }
            if (peggiore < 0 || min >= 1f) break;
            posti[peggiore] = id;
            cambiato = true;
        }
        if (cambiato) {
            for (int i = 0; i < 4; i++) if (tastoMesso[i]) {
                tasti[i].performHapticFeedback(HapticFeedbackConstants.CLOCK_TICK, HapticFeedbackConstants.FLAG_IGNORE_VIEW_SETTING);
                break;
            }
        }
    }

    /** Le mosse a energia (le più spettacolari) prima, poi le base nell'ordine di PRIORITA_BASE, poi il resto. */
    private List<String> perImportanza() {
        List<String> speciali = new ArrayList<String>(), base = new ArrayList<String>(), resto = new ArrayList<String>();
        for (String id : ordine) {
            Voce v = voci.get(id);
            if (v.costo > 0) speciali.add(id);
            else resto.add(id);
        }
        for (String b : PRIORITA_BASE) if (resto.remove(b)) base.add(b);
        List<String> tutte = new ArrayList<String>();
        // Una mossa base resta sempre a portata: i super guerrieri senza energia non devono restare a mani vuote.
        if (!base.isEmpty() && !speciali.isEmpty()) { tutte.add(base.remove(0)); }
        tutte.addAll(speciali);
        tutte.addAll(base);
        tutte.addAll(resto);
        return tutte;
    }

    private void mostraTasto(int i) {
        String id = posti[i];
        Voce v = id == null ? null : voci.get(id);
        if (v == null) return;
        if (tasti[i].imposta(v.icona, v.carica, v.pronta && !inPausa, coloreChi) && tastoMesso[i]) {
            long ora = SystemClock.uptimeMillis();
            if (ora - ultimoTick > 400) {          // carica: un tocchetto leggero, non più di uno ogni 0,4 s
                ultimoTick = ora;
                tasti[i].performHapticFeedback(HapticFeedbackConstants.CLOCK_TICK, HapticFeedbackConstants.FLAG_IGNORE_VIEW_SETTING);
            }
        }
        tasti[i].setContentDescription(id);
    }
}
