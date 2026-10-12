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
    }

    @Override
    protected void onResume() {
        super.onResume();
        disegna();
    }

    private void disegna() {
        boolean attivo = servizioAttivo();
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
        TextView motto = testo("Ogni schermo è un ring.", 15, TENUE, false);
        motto.setPadding(0, px(14), 0, px(18));
        col.addView(motto);

        // Il blocco principale.
        LinearLayout blocco = superficie();
        if (attivo) {
            blocco.addView(stato("Pronto", VERDE));
            blocco.addView(nota("Tocca la bolla su qualsiasi schermo, anche sul blocco schermo."));
            blocco.addView(bottone("Gioca sulla Home", true, new View.OnClickListener() {
                @Override public void onClick(View v) { giocaSullaHome(); }
            }));
            blocco.addView(bottone("Apri un sito", false, new View.OnClickListener() {
                @Override public void onClick(View v) { startActivity(new Intent(Principale.this, Browser.class)); }
            }));
        } else {
            blocco.addView(stato("Da attivare", 0xFFF2C14E));
            blocco.addView(nota("Serve l'Accessibilità per disegnare sopra le app e il blocco schermo."));
            blocco.addView(bottone("Attiva", true, new View.OnClickListener() {
                @Override public void onClick(View v) { apri(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)); }
            }));
            final TextView aiuto = nota("Apri «Info app», tocca ⋮ in alto a destra → «Consenti impostazioni con restrizioni», poi riprova «Attiva». Nell'elenco: App installate → Page Brawl.");
            aiuto.setVisibility(aiutoAperto ? View.VISIBLE : View.GONE);
            TextView link = testo("Interruttore grigio?", 14, VERDE, false);
            link.setPadding(0, px(14), 0, px(2));
            link.setOnClickListener(new View.OnClickListener() {
                @Override public void onClick(View v) {
                    if (!aiutoAperto) { aiutoAperto = true; aiuto.setVisibility(View.VISIBLE); return; }
                    apri(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:" + getPackageName())));
                }
            });
            blocco.addView(link);
            blocco.addView(aiuto);
            if (Build.VERSION.SDK_INT < 33) link.setVisibility(View.GONE);
        }
        col.addView(blocco);

        // Le impostazioni.
        TextView titolo = testo("IMPOSTAZIONI", 12, TENUE, true);
        titolo.setLetterSpacing(0.08f);
        titolo.setPadding(px(4), px(26), 0, px(8));
        col.addView(titolo);
        LinearLayout lista = superficie();
        lista.setPadding(px(16), px(4), px(16), px(4));
        lista.addView(rigaInterruttore("Bolla", "Il guantone sopra le app", Memoria.bolla(this),
                new CompoundButton.OnCheckedChangeListener() {
                    @Override public void onCheckedChanged(CompoundButton b, boolean si) {
                        Memoria.bolla(Principale.this, si);
                        Ring r = Ring.istanza;
                        if (r != null) r.aggiornaBolla();
                    }
                }));
        lista.addView(linea());
        lista.addView(rigaInterruttore("Blocco schermo", "Ring appena accendi il telefono", Memoria.blocco(this),
                new CompoundButton.OnCheckedChangeListener() {
                    @Override public void onCheckedChanged(CompoundButton b, boolean si) { Memoria.blocco(Principale.this, si); }
                }));
        lista.addView(linea());
        LinearLayout riquadro = riga("Riquadro rapido", "Nella tendina delle notifiche");
        TextView aggiungi = testo("Aggiungi", 15, VERDE, true);
        riquadro.addView(aggiungi);
        riquadro.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { aggiungiRiquadro(); }
        });
        lista.addView(riquadro);
        lista.addView(linea());
        LinearLayout taglia = riga("Lottatori", null);
        taglia.addView(segmenti());
        lista.addView(taglia);
        col.addView(lista);

        TextView piede = testo("Dello schermo usa solo la posizione degli elementi, solo mentre giochi. Non legge testi e non invia niente.", 12, TENUE, false);
        piede.setPadding(px(4), px(18), px(4), 0);
        col.addView(piede);

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
                                    Toast.makeText(Principale.this, "C'è già", Toast.LENGTH_SHORT).show();
                                }
                            }
                        });
                return;
            }
        }
        Toast.makeText(this, "Abbassa la tendina, tocca la matita e trascina Page Brawl fra i riquadri.", Toast.LENGTH_LONG).show();
    }

    private void apri(Intent i) {
        try { startActivity(i); } catch (Exception e) {
            Toast.makeText(this, "Apri le Impostazioni a mano", Toast.LENGTH_SHORT).show();
        }
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
            t.setContentDescription("Lottatori " + v);
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
