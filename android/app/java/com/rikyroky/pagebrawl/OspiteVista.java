package com.rikyroky.pagebrawl;

import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.WebView;
import android.widget.FrameLayout;

/**
 * I comandi dentro un'attività (browser, arene): viste sopra la WebView in un
 * FrameLayout. Qui i tocchi la pagina li riceve già: la superficie è sempre toccabile.
 */
class OspiteVista implements Comandi.Ospite {
    private final FrameLayout sopra;
    private final WebView web;
    private final Runnable chiudi;
    int alto, basso;

    OspiteVista(FrameLayout sopra, WebView web, Runnable chiudi) {
        this.sopra = sopra;
        this.web = web;
        this.chiudi = chiudi;
    }

    private FrameLayout.LayoutParams parametri(int gravita, int x, int y, int w, int h) {
        FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(w == -2 ? ViewGroup.LayoutParams.WRAP_CONTENT : w,
                h == -2 ? ViewGroup.LayoutParams.WRAP_CONTENT : h, gravita);
        int oriz = gravita & Gravity.HORIZONTAL_GRAVITY_MASK, vert = gravita & Gravity.VERTICAL_GRAVITY_MASK;
        if (oriz == Gravity.RIGHT) lp.rightMargin = x;
        else if (oriz == Gravity.CENTER_HORIZONTAL) lp.leftMargin = 2 * x;     // al centro il margine sposta di metà
        else lp.leftMargin = x;
        if (vert == Gravity.BOTTOM) lp.bottomMargin = y; else lp.topMargin = y;
        return lp;
    }

    @Override public void metti(View v, int gravita, int x, int y, int w, int h, boolean tocchiFuori) {
        if (v.getParent() != null) ((ViewGroup) v.getParent()).removeView(v);
        sopra.addView(v, parametri(gravita, x, y, w, h));
    }

    @Override public void sposta(View v, int gravita, int x, int y, int w, int h) {
        if (v.getParent() == sopra) v.setLayoutParams(parametri(gravita, x, y, w, h));
    }

    @Override public void togli(View v) { if (v.getParent() == sopra) sopra.removeView(v); }
    @Override public void superficieToccabile(boolean si) { }
    @Override public void mostraLottatori(boolean si) {
        web.evaluateJavascript("(function(){var o=document.getElementById('page-brawl');if(o)o.style.visibility='" + (si ? "visible" : "hidden") + "';})()", null);
    }
    @Override public void chiudiGioco() { chiudi.run(); }
    @Override public int margineAlto() { return alto; }
    @Override public int margineBasso() { return basso; }
}
