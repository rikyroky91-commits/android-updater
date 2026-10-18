package com.rikyroky.pagebrawl;

import android.app.Activity;
import android.app.StatusBarManager;
import android.content.ComponentName;
import android.content.Intent;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.Icon;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.widget.CompoundButton;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;

import java.util.function.Consumer;

/**
 * La schermata dell'app, ridotta all'essenziale (12/10/2026, Riccardo: «più
 * pulito e minimale possibile»):
 *  - un blocco in alto che cambia con lo stato: da spento un solo tasto per
 *    attivare il servizio; da acceso «Gioca» e «Apri un sito»;
 *  - quattro righe di impostazioni, una frase ciascuna.
 * Costruita in codice e ridisegnata a ogni ritorno (onResume).
 */
public class Principale extends Activity {
    private static final int FONDO = 0xFF0E1311;
    private static final int SUPERFICIE = 0xFF171E1A;
    private static final int LINEA = 0xFF232D27;
    private static final int TESTO = 0xFFEEF1EE;
    private static final int TENUE = 0xFF8E9A92;
    private static final int VERDE = 0xFF3CCF91;
    private static final int SU_VERDE = 0xFF0B1410;

    private ScrollView scorri;
    private boolean aiutoAperto;
    /** L'avviso sull'accessibilità a tutta pagina (norme del Play Store: prima del permesso, con consenso). */
    private boolean avvisoAperto;
    private Object richiamata;      // il tasto Indietro mentre l'avviso è aperto (Android 13+)
    private float d;

    @Override
    protected void onCreate(Bundle stato) {
        super.onCreate(stato);
        d = getResources().getDisplayMetrics().density;
        getWindow().setStatusBarColor(FONDO);
        getWindow().setNavigationBarColor(FONDO);
        scorri = new ScrollView(this);
        scorri.setBackgroundColor(FONDO);
        scorri.setFillViewport(true);
        setContentView(scorri);
        Bordi.imbottisci(scorri);
        if (Variante.LEGGERA) Memoria.modo(this, "app");
    }

    @Override
    @SuppressWarnings("deprecation")
    public void onBackPressed() {
        if (avvisoAperto) rifiuta(); else super.onBackPressed();
    }

    private final Premium.Ascoltatore ascoltaPremium = new Premium.Ascoltatore() {
        @Override public void cambiato(boolean si) { if (!avvisoAperto) disegna(); }
    };

    @Override
    protected void onPause() {
        Premium.di(this).smetti(ascoltaPremium);
        super.onPause();
    }

    @Override
    protected void onResume() {
        super.onResume();
        Premium.di(this).ascolta(ascoltaPremium);
        Ring r = Ring.istanza;
        if (r != null) r.riprendiBolla();
        disegna();
    }

    private void disegna() {
        if (avvisoAperto) { disegnaAvviso(); return; }
        boolean attivo = !Variante.LEGGERA && servizioAttivo();
        boolean consenso = Memoria.consenso(this);
        boolean pronto = attivo && consenso;
        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        col.setPadding(px(20), px(28), px(20), px(24));

        // Testata: icona e nome, niente altro.
        LinearLayout testa = new LinearLayout(this);
        testa.setGravity(Gravity.CENTER_VERTICAL);
        ImageView logo = new ImageView(this);
        logo.setImageResource(R.mipmap.icona);
        testa.addView(logo, new LinearLayout.LayoutParams(px(40), px(40)));
        TextView nome = testo("Page Brawl", 22, TESTO, true);
        nome.setPadding(px(12), 0, 0, 0);
        testa.addView(nome);
        col.addView(testa);
        TextView motto = testo("Every screen is a ring.", 15, TENUE, false);
        motto.setPadding(0, px(14), 0, px(18));
        col.addView(motto);

        // Il servizio, se la modalità ne ha bisogno e non è acceso.
        final String modo = Memoria.modo(this);
        boolean serveServizio = !"app".equals(modo);
        if (serveServizio && !pronto) {
            LinearLayout blocco = superficie();
            blocco.addView(stato(attivo ? "Needs your OK" : "Not turned on", 0xFFF2C14E));
            blocco.addView(nota("Page Brawl needs Accessibility to draw over your apps and the lock screen."));
            blocco.addView(bottone(consenso ? "Turn on" : "Review and turn on", true, new View.OnClickListener() {
                @Override public void onClick(View v) {
                    if (Memoria.consenso(Principale.this)) apri(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS));
                    else apriAvviso(true);
                }
            }));
            final TextView aiuto = nota("Open App info, tap ⋮ in the top right → Allow restricted settings, then tap Turn on again. In the list: Installed apps → Page Brawl.");
            aiuto.setVisibility(aiutoAperto ? View.VISIBLE : View.GONE);
            TextView link = testo("Switch greyed out?", 14, VERDE, false);
            link.setPadding(0, px(14), 0, px(2));
            link.setOnClickListener(new View.OnClickListener() {
                @Override public void onClick(View v) {
                    if (!aiutoAperto) { aiutoAperto = true; aiuto.setVisibility(View.VISIBLE); return; }
                    apri(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:" + getPackageName())));
                }
            });
            blocco.addView(link);
            blocco.addView(aiuto);
            if (Build.VERSION.SDK_INT < 33 || attivo) link.setVisibility(View.GONE);
            col.addView(blocco);
            col.addView(spazio(22));
        }

        // Dove giocare: quattro modalità.
        // Nella variante senza accessibilità (piano B per il Play Store) ci sono solo le arene.
        if (Variante.LEGGERA) {
            col.addView(titoletto("ARENAS"));
        } else {
            col.addView(titoletto("WHERE TO PLAY"));
            LinearLayout modi = superficie();
            modi.setPadding(px(6), px(6), px(6), px(6));
            String[][] voci = {
                    {"blocco", "\uD83D\uDD12", "Lock screen", "The ring appears when you wake the screen"},
                    {"sistema", "\uD83D\uDCF1", "Whole phone", "Tap the bubble on any app"},
                    {"chrome", "\uD83C\uDF10", "Chrome only", "The bubble shows while you browse"},
                    {"app", "\uD83C\uDFDF\uFE0F", "In the app", "Arenas: stone, lava, sky, ring"}};
            for (final String[] v : voci) modi.addView(rigaModo(v[0], v[1], v[2], v[3], v[0].equals(modo)));
            col.addView(modi);
            col.addView(spazio(14));
        }

        // Cosa fare adesso, secondo la modalità.
        if ("app".equals(modo)) {
            LinearLayout arene = new LinearLayout(this);
            // (18/10/2026) il cortile di pietra, con le lastre che si rompono: il primo, il più largo per lottare
            arene.addView(arena("arena", "Arena", new int[]{0xFF2C2342, 0xFFC9714C}, 0xFF918578), pesoUno());
            arene.addView(spazio(10, true));
            arene.addView(arena("lava", "Lava", new int[]{0xFF5C1608, 0xFF0D0403}, 0xFFFF8A1F), pesoUno());
            arene.addView(spazio(10, true));
            arene.addView(arena("cielo", "Sky", new int[]{0xFF5AA9E6, 0xFFDFF1FF}, 0xFF5BB04C), pesoUno());
            arene.addView(spazio(10, true));
            arene.addView(arena("ring", "Ring", new int[]{0xFF2A2F3A, 0xFF07080B}, 0xFF1F3A8A), pesoUno());
            col.addView(arene);
        } else if (pronto) {
            if ("sistema".equals(modo)) {
                col.addView(bottone("Play on the Home screen", true, new View.OnClickListener() {
                    @Override public void onClick(View v) { giocaSullaHome(); }
                }));
            } else if ("chrome".equals(modo)) {
                col.addView(bottone("Open Chrome", true, new View.OnClickListener() {
                    @Override public void onClick(View v) {
                        Intent i = getPackageManager().getLaunchIntentForPackage("com.android.chrome");
                        if (i != null) startActivity(i);
                        else Toast.makeText(Principale.this, "Chrome is not installed", Toast.LENGTH_SHORT).show();
                    }
                }));
            } else {
                TextView n = nota("Turn the screen off and on: the lock screen becomes the ring. It disappears when you unlock.");
                n.setPadding(px(4), 0, px(4), 0);
                col.addView(n);
            }
        }

        // Le impostazioni.
        col.addView(spazio(22));
        col.addView(titoletto("SETTINGS"));
        LinearLayout lista = superficie();
        lista.setPadding(px(16), px(4), px(16), px(4));
        // Il Premium (solo nella build col pagamento di Google Play).
        final Premium premium = Premium.di(this);
        if (premium.vero()) {
            boolean preso = premium.attivo();
            LinearLayout pr = riga("Premium", preso ? "Unlocked. Thanks!" : "Wizards, duelists, super warriors, weapons, big surprises");
            pr.addView(testo(preso ? "\u2713" : "Unlock", 15, VERDE, true));
            pr.setOnClickListener(new View.OnClickListener() {
                @Override public void onClick(View v) { Acquisto.apri(Principale.this, ""); }
            });
            lista.addView(pr);
            lista.addView(linea());
        }
        LinearLayout taglia = riga("Fighters", null);
        taglia.addView(segmenti());
        lista.addView(taglia);
        lista.addView(linea());
        LinearLayout lingua = riga("Language", "In-game text");
        lingua.addView(lingue());
        lista.addView(lingua);
        lista.addView(linea());
        LinearLayout riquadro = riga("Quick settings tile", "Start the ring from quick settings");
        riquadro.addView(testo("Add", 15, VERDE, true));
        riquadro.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { aggiungiRiquadro(); }
        });
        if (!Variante.LEGGERA) {
            lista.addView(riquadro);
            lista.addView(linea());
        }
        LinearLayout sito = riga("Web page", "The ring inside a real web page");
        sito.addView(testo("Open", 15, VERDE, true));
        sito.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { startActivity(new Intent(Principale.this, Browser.class)); }
        });
        lista.addView(sito);
        col.addView(lista);

        // La grafica: fps, risoluzione, dettaglio (valgono subito, anche a partita aperta).
        col.addView(spazio(22));
        col.addView(titoletto("GRAPHICS"));
        LinearLayout gr = superficie();
        gr.setPadding(px(16), px(4), px(16), px(8));
        LinearLayout rFps = riga("Frame rate", "120 needs a 120 Hz screen");
        rFps.addView(scelte(new String[]{"30", "60", "120"}, new String[]{"30", "60", "120"}, String.valueOf(Memoria.fps(this)), "pb-fps", 40));
        gr.addView(rFps);
        gr.addView(linea());
        final LinearLayout rRis = riga("Resolution", Memoria.risoluzione(this) + "% of the screen");
        gr.addView(rRis);
        android.widget.SeekBar ris = new android.widget.SeekBar(this);
        ris.setMax(50);
        ris.setProgress(Memoria.risoluzione(this) - 50);
        ris.setOnSeekBarChangeListener(new android.widget.SeekBar.OnSeekBarChangeListener() {
            @Override public void onProgressChanged(android.widget.SeekBar b, int v, boolean utente) {
                int pct = 50 + v;
                TextView sotto = (TextView) ((LinearLayout) rRis.getChildAt(0)).getChildAt(1);
                sotto.setText(pct + "% of the screen");
                if (utente) Memoria.grafica(Principale.this, "pb-risoluzione", String.valueOf(pct));
            }
            @Override public void onStartTrackingTouch(android.widget.SeekBar b) { }
            @Override public void onStopTrackingTouch(android.widget.SeekBar b) { }
        });
        LinearLayout.LayoutParams lpr = new LinearLayout.LayoutParams(-1, -2);
        lpr.bottomMargin = px(10);
        gr.addView(ris, lpr);
        gr.addView(linea());
        LinearLayout rDet = riga("Detail", "Particles and glow effects");
        rDet.addView(scelte(new String[]{"Low", "Med", "High"}, new String[]{"basso", "medio", "alto"}, Memoria.dettaglio(this), "pb-dettaglio", 46));
        gr.addView(rDet);
        col.addView(gr);

        TextView piede = testo(Variante.LEGGERA ? "Nothing you do here is collected or sent anywhere."
                : "Accessibility is used only to find where things are on screen while the ring is on. Nothing is stored or sent.", 12, TENUE, false);
        if (!Variante.LEGGERA && consenso) {
            piede.setText(piede.getText() + "  Details");
            piede.setOnClickListener(new View.OnClickListener() {
                @Override public void onClick(View v) { apriAvviso(false); }
            });
        }
        piede.setPadding(px(4), px(18), px(4), 0);
        col.addView(piede);

        scorri.removeAllViews();
        scorri.addView(col);
    }

    // ------------------------------------------------- l'avviso e il consenso
    /** Testo dell'avviso: dice cosa fa il servizio, una riga per cosa (va tenuto vero: è quello che si dichiara). */
    private static final String[] COSA_FA = {
            "Reads the position and size of the elements on your screen (buttons, icons, text boxes) so the fighters can stand on them and bump into them.",
            "Checks whether an element has text or a label, only to decide if it counts as solid. The text itself is never kept.",
            "Notices which app is in front, so the bubble can show only on the lock screen or only in Chrome.",
            "Draws the fighters and their controls over your apps and over the lock screen.",
            "When you start the ring from the quick settings tile, it closes the notification shade for you.",
    };

    private boolean chiedePermesso;     // l'avviso porta poi alle impostazioni (no se lo si rilegge e basta)

    private void apriAvviso(boolean permesso) {
        avvisoAperto = true;
        chiedePermesso = permesso;
        if (Build.VERSION.SDK_INT >= 33 && richiamata == null) {
            android.window.OnBackInvokedCallback cb = new android.window.OnBackInvokedCallback() {
                @Override public void onBackInvoked() { rifiuta(); }
            };
            getOnBackInvokedDispatcher().registerOnBackInvokedCallback(android.window.OnBackInvokedDispatcher.PRIORITY_DEFAULT, cb);
            richiamata = cb;
        }
        disegna();
        scorri.scrollTo(0, 0);
    }

    private void chiudiAvviso() {
        avvisoAperto = false;
        if (Build.VERSION.SDK_INT >= 33 && richiamata != null) {
            getOnBackInvokedDispatcher().unregisterOnBackInvokedCallback((android.window.OnBackInvokedCallback) richiamata);
            richiamata = null;
        }
    }

    private void accetta() {
        Memoria.consenso(this, true);
        boolean vai = chiedePermesso && !servizioAttivo();
        chiudiAvviso();
        Ring r = Ring.istanza;
        if (r != null) r.aggiornaBolla();
        disegna();
        if (vai) apri(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS));
    }

    /** «No thanks»: niente permesso, si gioca nelle arene, che non ne hanno bisogno. */
    private void rifiuta() {
        boolean primaVolta = !Memoria.consenso(this);
        chiudiAvviso();
        if (primaVolta) {
            Memoria.modo(this, "app");
            Toast.makeText(this, "No problem: the arenas work without it.", Toast.LENGTH_LONG).show();
        }
        disegna();
    }

    private void disegnaAvviso() {
        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        col.setPadding(px(20), px(28), px(20), px(24));
        col.addView(testo("Accessibility permission", 22, TESTO, true));
        TextView sotto = nota("To turn your lock screen, apps and web pages into a ring, Page Brawl uses Android's Accessibility Service API. Page Brawl is a game, not an accessibility tool.");
        sotto.setPadding(0, px(10), 0, px(18));
        col.addView(sotto);

        LinearLayout cosa = superficie();
        cosa.addView(testo("While the service is on, Page Brawl:", 15, TESTO, true));
        for (String r : COSA_FA) {
            TextView t = testo("•  " + r, 14, TESTO, false);
            t.setPadding(0, px(10), 0, 0);
            cosa.addView(t);
        }
        col.addView(cosa);
        col.addView(spazio(14));

        LinearLayout mai = superficie();
        mai.addView(testo("It never:", 15, TESTO, true));
        String[] no = {
                "stores or sends anything it sees: there is no account, no analytics and no server;",
                "taps, types or acts inside other apps for you;",
                "reads the screen while the ring is off (positions are read only while you play)."};
        for (String r : no) {
            TextView t = testo("•  " + r, 14, TESTO, false);
            t.setPadding(0, px(10), 0, 0);
            mai.addView(t);
        }
        col.addView(mai);

        TextView via = nota("You can turn it off at any time in Settings › Accessibility › Page Brawl. Without it you can still play in the arenas.");
        via.setPadding(0, px(16), 0, 0);
        col.addView(via);

        col.addView(bottone(chiedePermesso ? "Agree and continue" : "OK", true, new View.OnClickListener() {
            @Override public void onClick(View v) { accetta(); }
        }));
        col.addView(bottone(chiedePermesso ? "No thanks" : "Withdraw consent", false, new View.OnClickListener() {
            @Override public void onClick(View v) {
                if (!chiedePermesso) {
                    // Ritirare il consenso: il servizio resta acceso nelle impostazioni ma non fa più niente.
                    Memoria.consenso(Principale.this, false);
                    Ring r = Ring.istanza;
                    if (r != null) r.aggiornaBolla();
                    Toast.makeText(Principale.this, "Consent withdrawn. You can also turn the service off in Settings.", Toast.LENGTH_LONG).show();
                    chiudiAvviso();
                    Memoria.modo(Principale.this, "app");
                    disegna();
                    return;
                }
                rifiuta();
            }
        }));

        scorri.removeAllViews();
        scorri.addView(col);
    }

    private void giocaSullaHome() {
        Ring r = Ring.istanza;
        if (r == null) { disegna(); return; }
        startActivity(new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
        r.avvia(900);
    }

    private boolean servizioAttivo() {
        if (Ring.istanza != null) return true;
        String attivi = Settings.Secure.getString(getContentResolver(), Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES);
        if (attivi == null) return false;
        ComponentName mio = new ComponentName(this, Ring.class);
        for (String s : attivi.split(":")) {
            if (mio.equals(ComponentName.unflattenFromString(s))) return true;
        }
        return false;
    }

    private void aggiungiRiquadro() {
        if (Build.VERSION.SDK_INT >= 33) {
            StatusBarManager sbm = getSystemService(StatusBarManager.class);
            if (sbm != null) {
                sbm.requestAddTileService(new ComponentName(this, Riquadro.class), "Page Brawl",
                        Icon.createWithResource(this, R.drawable.riquadro), getMainExecutor(),
                        new Consumer<Integer>() {
                            @Override public void accept(Integer esito) {
                                if (esito != null && esito == StatusBarManager.TILE_ADD_REQUEST_RESULT_TILE_ALREADY_ADDED) {
                                    Toast.makeText(Principale.this, "Already added", Toast.LENGTH_SHORT).show();
                                }
                            }
                        });
                return;
            }
        }
        Toast.makeText(this, "Pull down the quick settings, tap the pencil and drag Page Brawl into your tiles.", Toast.LENGTH_LONG).show();
    }

    private void apri(Intent i) {
        try { startActivity(i); } catch (Exception e) {
            Toast.makeText(this, "Open Settings manually", Toast.LENGTH_SHORT).show();
        }
    }

    private LinearLayout rigaModo(final String id, String icona, String titolo, String sotto, boolean scelto) {
        LinearLayout r = new LinearLayout(this);
        r.setGravity(Gravity.CENTER_VERTICAL);
        r.setPadding(px(12), px(12), px(14), px(12));
        if (scelto) r.setBackground(tondo(0xFF1F2A24, 14));
        TextView ic = testo(icona, 20, TESTO, false);
        ic.setGravity(Gravity.CENTER);
        ic.setBackground(tondo(scelto ? 0x333CCF91 : 0xFF212A25, 12));
        r.addView(ic, new LinearLayout.LayoutParams(px(42), px(42)));
        LinearLayout testi = new LinearLayout(this);
        testi.setOrientation(LinearLayout.VERTICAL);
        testi.setPadding(px(12), 0, 0, 0);
        testi.addView(testo(titolo, 16, TESTO, scelto));
        testi.addView(testo(sotto, 13, TENUE, false));
        r.addView(testi, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        View segno = new View(this);
        GradientDrawable g = new GradientDrawable();
        g.setShape(GradientDrawable.OVAL);
        if (scelto) g.setColor(VERDE); else g.setStroke(Math.max(1, px(2)), 0xFF3A4740);
        segno.setBackground(g);
        r.addView(segno, new LinearLayout.LayoutParams(px(18), px(18)));
        r.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) {
                Memoria.modo(Principale.this, id);
                Ring ring = Ring.istanza;
                if (ring != null) ring.aggiornaBolla();
                disegna();
            }
        });
        return r;
    }

    private View arena(final String tipo, String nome, int[] cielo, int accento) {
        LinearLayout a = new LinearLayout(this);
        a.setOrientation(LinearLayout.VERTICAL);
        a.setGravity(Gravity.BOTTOM);
        GradientDrawable g = new GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM, cielo);
        g.setCornerRadius(px(16));
        a.setBackground(g);
        a.setMinimumHeight(px(112));
        View pedana = new View(this);
        pedana.setBackground(tondo(accento, 3));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, px(6));
        lp.leftMargin = px(16); lp.rightMargin = px(16); lp.bottomMargin = px(16);
        a.addView(pedana, lp);
        TextView t = testo(nome, 15, 0xFFFFFFFF, true);
        t.setPadding(px(12), 0, 0, px(10));
        a.addView(t);
        a.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) {
                startActivity(new Intent(Principale.this, Arena.class).putExtra(Arena.EXTRA_TIPO, tipo));
            }
        });
        return a;
    }

    private LinearLayout.LayoutParams pesoUno() { return new LinearLayout.LayoutParams(0, px(112), 1); }

    private View spazio(int dp) { return spazio(dp, false); }

    private View spazio(int dp, boolean orizzontale) {
        View v = new View(this);
        v.setLayoutParams(orizzontale ? new LinearLayout.LayoutParams(px(dp), 1) : new LinearLayout.LayoutParams(1, px(dp)));
        return v;
    }

    private TextView titoletto(String s) {
        TextView t = testo(s, 12, TENUE, true);
        t.setLetterSpacing(0.08f);
        t.setPadding(px(4), 0, 0, px(8));
        return t;
    }

    // ------------------------------------------------------------- mattoni
    private int px(float dp) { return Math.round(dp * d); }

    private TextView testo(String s, float sp, int colore, boolean grassetto) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, sp);
        t.setTextColor(colore);
        t.setLineSpacing(0, 1.15f);
        if (grassetto) t.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        return t;
    }

    private TextView nota(String s) {
        TextView t = testo(s, 14, TENUE, false);
        t.setPadding(0, px(4), 0, px(2));
        return t;
    }

    private GradientDrawable tondo(int colore, float raggio) {
        GradientDrawable g = new GradientDrawable();
        g.setColor(colore);
        g.setCornerRadius(px(raggio));
        return g;
    }

    private LinearLayout superficie() {
        LinearLayout s = new LinearLayout(this);
        s.setOrientation(LinearLayout.VERTICAL);
        s.setPadding(px(18), px(18), px(18), px(18));
        s.setBackground(tondo(SUPERFICIE, 20));
        return s;
    }

    private TextView stato(String s, int colore) {
        TextView t = testo("●  " + s, 17, colore, true);
        t.setPadding(0, 0, 0, px(4));
        return t;
    }

    private TextView bottone(String s, boolean pieno, View.OnClickListener clic) {
        TextView b = testo(s, 16, pieno ? SU_VERDE : TESTO, true);
        b.setGravity(Gravity.CENTER);
        b.setBackground(tondo(pieno ? VERDE : 0xFF212A25, 14));
        b.setOnClickListener(clic);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, px(52));
        lp.topMargin = px(pieno ? 16 : 10);
        b.setLayoutParams(lp);
        return b;
    }

    private View linea() {
        View v = new View(this);
        v.setBackgroundColor(LINEA);
        v.setLayoutParams(new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, Math.max(1, px(1))));
        return v;
    }

    private LinearLayout riga(String titolo, String sotto) {
        LinearLayout r = new LinearLayout(this);
        r.setGravity(Gravity.CENTER_VERTICAL);
        r.setMinimumHeight(px(60));
        r.setPadding(0, px(10), 0, px(10));
        LinearLayout testi = new LinearLayout(this);
        testi.setOrientation(LinearLayout.VERTICAL);
        testi.addView(testo(titolo, 16, TESTO, false));
        if (sotto != null) testi.addView(testo(sotto, 13, TENUE, false));
        r.addView(testi, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        return r;
    }

    private LinearLayout rigaInterruttore(String titolo, String sotto, boolean acceso, CompoundButton.OnCheckedChangeListener cambia) {
        LinearLayout r = riga(titolo, sotto);
        Switch sw = new Switch(this);
        sw.setChecked(acceso);
        sw.setOnCheckedChangeListener(cambia);
        r.addView(sw);
        return r;
    }

    /** Un gruppo di scelte a pillola salvato nella chiave del ring `chiave`. */
    private LinearLayout scelte(String[] nomi, final String[] valori, String scelto, final String chiave, int largo) {
        LinearLayout box = new LinearLayout(this);
        box.setBackground(tondo(0xFF212A25, 10));
        box.setPadding(px(3), px(3), px(3), px(3));
        for (int i = 0; i < nomi.length; i++) {
            final String v = valori[i];
            TextView t = testo(nomi[i], 13, v.equals(scelto) ? SU_VERDE : TESTO, true);
            t.setGravity(Gravity.CENTER);
            if (v.equals(scelto)) t.setBackground(tondo(VERDE, 8));
            t.setOnClickListener(new View.OnClickListener() {
                @Override public void onClick(View x) { Memoria.grafica(Principale.this, chiave, v); disegna(); }
            });
            box.addView(t, new LinearLayout.LayoutParams(px(largo), px(30)));
        }
        return box;
    }

    /** La lingua del gioco (chiave del ring `pb-lingua`): inglese di serie. */
    private LinearLayout lingue() {
        final String[] codici = {"en", "it", "es", "fr", "de"};
        String scelta = Memoria.lingua(this);
        LinearLayout box = new LinearLayout(this);
        box.setBackground(tondo(0xFF212A25, 10));
        box.setPadding(px(3), px(3), px(3), px(3));
        for (final String c : codici) {
            TextView t = testo(c.toUpperCase(), 13, c.equals(scelta) ? SU_VERDE : TESTO, true);
            t.setGravity(Gravity.CENTER);
            if (c.equals(scelta)) t.setBackground(tondo(VERDE, 8));
            t.setOnClickListener(new View.OnClickListener() {
                @Override public void onClick(View x) { Memoria.lingua(Principale.this, c); disegna(); }
            });
            box.addView(t, new LinearLayout.LayoutParams(px(34), px(30)));
        }
        return box;
    }

    /** Piccoli · Medi · Grandi: la misura dei lottatori (chiave del ring `pb-taglia`). */
    private LinearLayout segmenti() {
        final String[] valori = {"piccoli", "medi", "grandi"};
        final String[] nomi = {"S", "M", "L"};
        String scelta = Memoria.gioco(this).getString("pb-taglia", "medi");
        LinearLayout box = new LinearLayout(this);
        box.setBackground(tondo(0xFF212A25, 10));
        box.setPadding(px(3), px(3), px(3), px(3));
        for (int i = 0; i < valori.length; i++) {
            final String v = valori[i];
            TextView t = testo(nomi[i], 14, v.equals(scelta) ? SU_VERDE : TESTO, true);
            t.setGravity(Gravity.CENTER);
            t.setContentDescription("Fighters " + v);
            if (v.equals(scelta)) t.setBackground(tondo(VERDE, 8));
            t.setOnClickListener(new View.OnClickListener() {
                @Override public void onClick(View x) {
                    Memoria.gioco(Principale.this).edit().putString("pb-taglia", v).apply();
                    disegna();
                }
            });
            box.addView(t, new LinearLayout.LayoutParams(px(40), px(32)));
        }
        return box;
    }
}
