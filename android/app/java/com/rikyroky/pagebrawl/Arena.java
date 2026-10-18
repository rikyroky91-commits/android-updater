package com.rikyroky.pagebrawl;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;

import org.json.JSONObject;

/**
 * Le arene dentro l'app (modalità 4): a schermo intero, con la stessa capsula
 * e gli stessi 4 tasti di sopra lo schermo. Qui i lottatori si prendono anche
 * col dito, e c'è la corsa infinita.
 *   lava   piattaforma sospesa sopra la lava: chi ci cade va K.O.
 *   cielo  tre pedane nel cielo sopra un prato
 *   ring   il ring classico sotto i riflettori
 */
public class Arena extends Activity {
    static final String EXTRA_TIPO = "tipo";

    private WebView web;
    private Comandi comandi;

    @SuppressLint({"SetJavaScriptEnabled", "AddJavascriptInterface"})
    @Override
    protected void onCreate(Bundle stato) {
        super.onCreate(stato);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        if (Build.VERSION.SDK_INT >= 28) {
            getWindow().getAttributes().layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES;
        }
        FrameLayout scena = new FrameLayout(this);
        scena.setBackgroundColor(Color.BLACK);
        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setAllowFileAccess(false);
        s.setTextZoom(100);
        web.setBackgroundColor(Color.BLACK);
        web.setVerticalScrollBarEnabled(false);
        web.setOverScrollMode(View.OVER_SCROLL_NEVER);
        web.addJavascriptInterface(new Ponte(), "PB");
        Premium.di(this).ascolta(ascoltaPremium);
        // Spegnendo lo schermo Android può chiudere il motore della pagina per liberare memoria, e la corsa si
        // perdeva: il motore resta «importante» anche quando l'arena non si vede.
        if (Build.VERSION.SDK_INT >= 26) web.setRendererPriorityPolicy(WebView.RENDERER_PRIORITY_IMPORTANT, false);
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                return !r.getUrl().toString().startsWith("file:///android_asset/");
            }
            @Override public boolean onRenderProcessGone(WebView v, android.webkit.RenderProcessGoneDetail d) {
                // Se il motore della pagina cade comunque, si riapre l'arena invece di chiudere l'app.
                recreate();
                return true;
            }
        });
        scena.addView(web, new FrameLayout.LayoutParams(-1, -1));
        setContentView(scena);
        schermoIntero();

        OspiteVista ospite = new OspiteVista(scena, web, new Runnable() {
            @Override public void run() { finish(); }
        });
        final int dieci = Math.round(10 * getResources().getDisplayMetrics().density);
        ospite.alto = dieci;
        comandi = new Comandi(this, ospite, web);
        comandi.avvia();
        // Con target 35+ l'arena a schermo intero va anche sotto la tacca della fotocamera: la capsula e i
        // tasti si tengono fuori dalla tacca (i lottatori no, il campo resta tutto lo schermo).
        if (Build.VERSION.SDK_INT >= 30) {
            final OspiteVista o = ospite;
            scena.setOnApplyWindowInsetsListener(new View.OnApplyWindowInsetsListener() {
                @Override public WindowInsets onApplyWindowInsets(View v, WindowInsets wi) {
                    android.graphics.Insets t = wi.getInsets(WindowInsets.Type.displayCutout());
                    int alto = dieci + t.top, basso = t.bottom;
                    if (alto != o.alto || basso != o.basso) { o.alto = alto; o.basso = basso; comandi.ridisponi(); }
                    return wi;
                }
            });
        }

        String tipo = getIntent().getStringExtra(EXTRA_TIPO);
        if (tipo == null || !tipo.matches("lava|cielo|ring|arena")) tipo = "lava";
        web.loadUrl("file:///android_asset/web/arena.html?tipo=" + tipo);
    }

    @SuppressWarnings("deprecation")
    private void schermoIntero() {
        if (Build.VERSION.SDK_INT >= 30) {
            getWindow().setDecorFitsSystemWindows(false);
            WindowInsetsController c = getWindow().getInsetsController();
            if (c != null) {
                c.hide(WindowInsets.Type.systemBars());
                c.setSystemBarsBehavior(WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
            }
        } else {
            getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY | View.SYSTEM_UI_FLAG_FULLSCREEN
                    | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                    | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION);
        }
    }

    @Override
    public void onWindowFocusChanged(boolean focus) {
        super.onWindowFocusChanged(focus);
        if (focus) schermoIntero();
    }

    @Override
    protected void onPause() {
        super.onPause();
        // Uscendo dall'app il gioco si ferma da solo.
        web.evaluateJavascript("window.__ring&&__ring.pausa(true)", null);
    }

    @Override
    protected void onDestroy() {
        comandi.ferma();
        Premium.di(this).smetti(ascoltaPremium);
        web.destroy();
        super.onDestroy();
    }

    /** Il Premium comprato (o tolto) mentre la pagina è aperta: lo si dice al ring. */
    private final Premium.Ascoltatore ascoltaPremium = new Premium.Ascoltatore() {
        @Override public void cambiato(boolean si) { if (web != null) web.evaluateJavascript(Premium.js(si), null); }
    };

    private final class Ponte {
        @JavascriptInterface public String dati() { return Memoria.dati(Arena.this); }
        @JavascriptInterface public void salva(String json) { Memoria.salva(Arena.this, json); }
        @JavascriptInterface public String premium() { return Premium.di(Arena.this).stato(); }
        @JavascriptInterface public void compra(String gruppo) { Acquisto.apri(Arena.this, gruppo); }
        @JavascriptInterface public void messaggio(String json) {
            String tipo = "";
            try { tipo = new JSONObject(json).optString("tipo", ""); } catch (Exception ignorata) { }
            if ("opzioni".equals(tipo) || "guida".equals(tipo)) startActivity(new Intent(Arena.this, Principale.class));
        }
    }
}
