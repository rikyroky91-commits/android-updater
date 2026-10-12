package com.rikyroky.pagebrawl;

import android.app.Activity;
import android.app.KeyguardManager;
import android.content.Context;
import android.content.Intent;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.os.Bundle;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;

/**
 * La scheda del Premium: cosa sblocca, il prezzo di Google Play, «Unlock», «Restore purchase», «Not now».
 * Si apre da ovunque: dall'app, dalle arene, dal browser e da sopra le altre app (dal servizio), quando
 * si tocca qualcosa di chiuso. È un'attività a sé perché il pagamento di Google Play ne vuole una.
 */
public class Acquisto extends Activity implements Premium.Ascoltatore {
    static final String EXTRA_GRUPPO = "gruppo";
    private static final int FONDO = 0xFF171E1A, TESTO = 0xFFEEF1EE, TENUE = 0xFF8E9A92, VERDE = 0xFF3CCF91, SU_VERDE = 0xFF0B1410;

    private Premium premium;
    private TextView compra;
    private float d;

    /** Da chiamare ovunque (anche da un servizio). */
    static void apri(Context c, String gruppo) {
        Intent i = new Intent(c, Acquisto.class).putExtra(EXTRA_GRUPPO, gruppo == null ? "" : gruppo);
        if (!(c instanceof Activity)) i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        c.startActivity(i);
    }

    @Override
    protected void onCreate(Bundle stato) {
        super.onCreate(stato);
        d = getResources().getDisplayMetrics().density;
        if (Build.VERSION.SDK_INT >= 27) setShowWhenLocked(true);     // si può aprire dal ring sul blocco schermo
        premium = Premium.di(this);
        disegna();
    }

    @Override protected void onStart() { super.onStart(); premium.ascolta(this); }
    @Override protected void onStop() { premium.smetti(this); super.onStop(); }

    @Override public void cambiato(boolean attivo) { disegna(); }

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

    private GradientDrawable tondo(int colore, float raggio) {
        GradientDrawable g = new GradientDrawable();
        g.setColor(colore);
        g.setCornerRadius(px(raggio));
        return g;
    }

    private TextView bottone(String s, boolean pieno, View.OnClickListener clic) {
        TextView b = testo(s, 16, pieno ? SU_VERDE : TESTO, true);
        b.setGravity(Gravity.CENTER);
        b.setBackground(tondo(pieno ? VERDE : 0xFF212A25, 14));
        b.setOnClickListener(clic);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, px(52));
        lp.topMargin = px(pieno ? 20 : 10);
        b.setLayoutParams(lp);
        return b;
    }

    private static String perche(String gruppo) {
        if ("guerrieri".equals(gruppo)) return "These fighters are part of Premium.";
        if ("armi".equals(gruppo)) return "Weapons are part of Premium.";
        if ("meteo".equals(gruppo)) return "This surprise is part of Premium.";
        return null;
    }

    private void disegna() {
        FrameLayout velo = new FrameLayout(this);
        velo.setBackgroundColor(0x99000000);
        velo.setOnClickListener(new View.OnClickListener() { @Override public void onClick(View v) { finish(); } });

        LinearLayout scheda = new LinearLayout(this);
        scheda.setOrientation(LinearLayout.VERTICAL);
        scheda.setPadding(px(22), px(24), px(22), px(22));
        GradientDrawable g = new GradientDrawable();
        g.setColor(FONDO);
        g.setCornerRadii(new float[]{px(26), px(26), px(26), px(26), 0, 0, 0, 0});
        scheda.setBackground(g);
        scheda.setClickable(true);                        // un tocco sulla scheda non la chiude

        boolean attivo = premium.attivo();
        String motivo = perche(getIntent().getStringExtra(EXTRA_GRUPPO));
        if (motivo != null && !attivo) {
            TextView m = testo(motivo, 14, VERDE, true);
            m.setPadding(0, 0, 0, px(8));
            scheda.addView(m);
        }
        scheda.addView(testo("Page Brawl Premium", 22, TESTO, true));
        TextView sotto = testo(attivo ? "Premium is active on this account. Thanks for supporting Page Brawl!"
                : "One purchase, yours for good on every phone with this Google account.", 14, TENUE, false);
        sotto.setPadding(0, px(6), 0, px(14));
        scheda.addView(sotto);

        String[][] cosa = {
                {"🧙", "Wizards, duelists and super warriors, with their own moves, finishers and transformations"},
                {"🗡️", "Weapons in the ring: pistol, sword, bomb, bazooka, flamethrower"},
                {"☄️", "The big surprises: meteors, zombie horde, black hole, low gravity"},
                {"🏃", "Every fighter style in the endless run"}};
        for (String[] r : cosa) {
            LinearLayout riga = new LinearLayout(this);
            riga.setPadding(0, px(7), 0, px(7));
            TextView ic = testo(r[0], 20, TESTO, false);
            riga.addView(ic, new LinearLayout.LayoutParams(px(36), ViewGroup.LayoutParams.WRAP_CONTENT));
            riga.addView(testo(r[1], 15, TESTO, false), new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
            scheda.addView(riga);
        }
        TextView gratis = testo("Robot and apple, all four modes, the arenas and the endless run stay free.", 13, TENUE, false);
        gratis.setPadding(0, px(10), 0, 0);
        scheda.addView(gratis);

        if (attivo) {
            scheda.addView(bottone("Done", true, new View.OnClickListener() { @Override public void onClick(View v) { finish(); } }));
        } else {
            compra = bottone("Loading price…", true, new View.OnClickListener() {
                @Override public void onClick(View v) { paga(); }
            });
            compra.setEnabled(false);
            compra.setAlpha(0.6f);
            scheda.addView(compra);
            premium.prezzo(new Premium.Prezzo() {
                @Override public void pronto(String prezzo) {
                    if (compra == null) return;
                    compra.setEnabled(prezzo != null);
                    compra.setAlpha(prezzo != null ? 1f : 0.6f);
                    compra.setText(prezzo != null ? "Unlock for " + prezzo : "Google Play is not available right now");
                }
            });
            scheda.addView(bottone("Restore purchase", false, new View.OnClickListener() {
                @Override public void onClick(View v) { premium.ripristina(); }
            }));
            scheda.addView(bottone("Not now", false, new View.OnClickListener() {
                @Override public void onClick(View v) { finish(); }
            }));
        }

        FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.BOTTOM);
        velo.addView(scheda, lp);
        setContentView(velo);
        // Da bordo a bordo (Android 15+): la scheda resta sopra la barra di navigazione.
        if (Build.VERSION.SDK_INT >= 35) {
            scheda.setOnApplyWindowInsetsListener(new View.OnApplyWindowInsetsListener() {
                @Override public android.view.WindowInsets onApplyWindowInsets(View v, android.view.WindowInsets wi) {
                    int giu = wi.getInsets(android.view.WindowInsets.Type.systemBars()).bottom;
                    v.setPadding(px(22), px(24), px(22), px(22) + giu);
                    return wi;
                }
            });
        }
    }

    private void paga() {
        // Sul blocco schermo il pagamento di Google Play non si apre: prima si sblocca il telefono.
        KeyguardManager km = (KeyguardManager) getSystemService(KEYGUARD_SERVICE);
        if (Build.VERSION.SDK_INT >= 26 && km != null && km.isKeyguardLocked()) {
            km.requestDismissKeyguard(this, new KeyguardManager.KeyguardDismissCallback() {
                @Override public void onDismissSucceeded() { premium.compra(Acquisto.this); }
            });
            return;
        }
        premium.compra(this);
    }
}
