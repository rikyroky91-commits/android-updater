package com.rikyroky.pagebrawl;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.text.InputType;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputMethodManager;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.URLEncoder;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Il browser di Page Brawl: una pagina vera con dentro il ring, come
 * l'estensione per computer (stessi file: ponte, lingue, prepara, ring).
 * Si apre dall'app, da «Condividi → Page Brawl» e da «Apri con».
 * In alto solo l'indirizzo e il guantone che accende o spegne la lotta.
 */
public class Browser extends Activity {
    static final String EXTRA_INDIRIZZO = "indirizzo";
    private static final String CASA = "https://www.wikipedia.org";
    private static final Pattern URL = Pattern.compile("https?://[^\\s<>\"]+");

    private WebView web;
    private Comandi comandi;
    private android.widget.FrameLayout scena;
    private EditText barra;
    private TextView guantone;
    private static String pacchetto;     // i file del ring, letti una volta sola
    private float d;

    @SuppressLint({"SetJavaScriptEnabled", "AddJavascriptInterface"})
    @Override
    protected void onCreate(Bundle stato) {
        super.onCreate(stato);
        d = getResources().getDisplayMetrics().density;
        int fondo = 0xFF0F1512;
        getWindow().setStatusBarColor(fondo);
        getWindow().setNavigationBarColor(fondo);

        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        col.setBackgroundColor(fondo);

        LinearLayout testa = new LinearLayout(this);
        testa.setOrientation(LinearLayout.HORIZONTAL);
        testa.setGravity(Gravity.CENTER_VERTICAL);
        testa.setPadding(px(10), px(8), px(10), px(8));

        barra = new EditText(this);
        barra.setSingleLine(true);
        barra.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
        barra.setTextColor(0xFFEDEFEC);
        barra.setHintTextColor(0xFF6F7B73);
        barra.setHint("Search or type an address");
        barra.setSelectAllOnFocus(true);
        barra.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        barra.setImeOptions(EditorInfo.IME_ACTION_GO);
        GradientDrawable g = new GradientDrawable();
        g.setColor(0xFF1B2620);
        g.setCornerRadius(px(22));
        barra.setBackground(g);
        barra.setPadding(px(16), px(10), px(16), px(10));
        barra.setOnEditorActionListener(new TextView.OnEditorActionListener() {
            @Override public boolean onEditorAction(TextView v, int a, KeyEvent e) {
                carica(barra.getText().toString());
                InputMethodManager imm = (InputMethodManager) getSystemService(INPUT_METHOD_SERVICE);
                if (imm != null) imm.hideSoftInputFromWindow(barra.getWindowToken(), 0);
                web.requestFocus();
                return true;
            }
        });
        testa.addView(barra, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));

        guantone = new TextView(this);
        guantone.setText("🥊");
        guantone.setTextSize(TypedValue.COMPLEX_UNIT_SP, 20);
        guantone.setGravity(Gravity.CENTER);
        guantone.setContentDescription("Turn the brawl on or off on this page");
        guantone.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { alterna(); }
        });
        LinearLayout.LayoutParams lpg = new LinearLayout.LayoutParams(px(44), px(44));
        lpg.leftMargin = px(8);
        testa.addView(guantone, lpg);
        col.addView(testa);

        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);
        s.setSupportMultipleWindows(false);
        web.setBackgroundColor(Color.WHITE);
        web.addJavascriptInterface(new Ponte(), "PB");
        web.setWebChromeClient(new WebChromeClient());
        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                Uri u = r.getUrl();
                String sc = u.getScheme();
                if ("http".equals(sc) || "https".equals(sc)) return false;
                try { startActivity(new Intent(Intent.ACTION_VIEW, u)); } catch (Exception ignorata) { }
                return true;
            }

            @Override
            public void onPageStarted(WebView v, String url, Bitmap icona) {
                if (!barra.hasFocus()) barra.setText(url);
                segna(false);
            }

            @Override
            public void onPageFinished(WebView v, String url) {
                if (!barra.hasFocus()) barra.setText(url);
                if (Memoria.webAuto(Browser.this)) inietta();
            }
        });
        scena = new android.widget.FrameLayout(this);
        scena.addView(web, new android.widget.FrameLayout.LayoutParams(-1, -1));
        col.addView(scena, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1));
        setContentView(col);
        // I comandi da telefono (capsula e 4 abilità) sopra la pagina; ✕ spegne il ring sulla pagina.
        OspiteVista ospite = new OspiteVista(scena, web, new Runnable() {
            @Override public void run() {
                web.evaluateJavascript("window.__ringEstensione&&window.__ring&&window.__ring.mosse().acceso&&window.__ringEstensione.alterna()", null);
                Memoria.webAuto(Browser.this, false);
                segna(false);
            }
        });
        ospite.alto = px(8);
        comandi = new Comandi(this, ospite, web);
        comandi.avvia();

        String inizio = daIntent(getIntent());
        if (stato != null) web.restoreState(stato);
        if (stato == null || web.getUrl() == null) carica(inizio != null ? inizio : CASA);
    }

    @Override
    protected void onNewIntent(Intent i) {
        super.onNewIntent(i);
        String u = daIntent(i);
        if (u != null) carica(u);
    }

    @Override
    protected void onSaveInstanceState(Bundle out) {
        super.onSaveInstanceState(out);
        web.saveState(out);
    }

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) web.goBack();
        else super.onBackPressed();
    }

    @Override
    protected void onDestroy() {
        comandi.ferma();
        web.destroy();
        super.onDestroy();
    }

    private String daIntent(Intent i) {
        if (i == null) return null;
        if (Intent.ACTION_VIEW.equals(i.getAction()) && i.getData() != null) return i.getData().toString();
        if (Intent.ACTION_SEND.equals(i.getAction())) {
            String t = i.getStringExtra(Intent.EXTRA_TEXT);
            if (t == null) return null;
            Matcher m = URL.matcher(t);
            return m.find() ? m.group() : t;
        }
        return i.getStringExtra(EXTRA_INDIRIZZO);
    }

    private void carica(String testo) {
        String t = testo == null ? "" : testo.trim();
        if (t.length() == 0) return;
        String url;
        if (t.matches("(?i)^https?://.*")) url = t;
        else if (!t.contains(" ") && t.contains(".")) url = "https://" + t;
        else {
            try { url = "https://www.google.com/search?q=" + URLEncoder.encode(t, "UTF-8"); }
            catch (Exception e) { url = CASA; }
        }
        web.loadUrl(url);
    }

    /** Accende il ring sulla pagina, o lo spegne/riaccende se c'è già. */
    private void alterna() {
        web.evaluateJavascript("!!window.__ringEstensione", new android.webkit.ValueCallback<String>() {
            @Override public void onReceiveValue(String gia) {
                if ("true".equals(gia)) {
                    web.evaluateJavascript("window.__ringEstensione.alterna()", null);
                    Memoria.webAuto(Browser.this, !Memoria.webAuto(Browser.this));
                    segna(Memoria.webAuto(Browser.this));
                } else {
                    Memoria.webAuto(Browser.this, true);
                    inietta();
                }
            }
        });
    }

    private void inietta() {
        final String js = pacchetto();
        if (js == null) return;
        web.evaluateJavascript("!!window.__ringEstensione", new android.webkit.ValueCallback<String>() {
            @Override public void onReceiveValue(String gia) {
                if (!"true".equals(gia)) web.evaluateJavascript(js, null);
                segna(true);
            }
        });
    }

    private void segna(boolean acceso) {
        GradientDrawable g = new GradientDrawable();
        g.setShape(GradientDrawable.OVAL);
        g.setColor(acceso ? 0xFF2E9E72 : 0xFF1B2620);
        guantone.setBackground(g);
    }

    private String pacchetto() {
        if (pacchetto != null) return pacchetto;
        try {
            StringBuilder sb = new StringBuilder("window.__pbModo='web';\n");
            for (String f : new String[]{"ponte.js", "lingue.js", "prepara.js", "ring.js", "comandi.js"}) {
                sb.append(leggi("web/" + f)).append("\n;\n");
            }
            pacchetto = sb.toString();
        } catch (Exception e) {
            pacchetto = null;
        }
        return pacchetto;
    }

    private String leggi(String nome) throws Exception {
        InputStream in = getAssets().open(nome);
        try {
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] buf = new byte[16384];
            int n;
            while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
            return out.toString("UTF-8");
        } finally {
            in.close();
        }
    }

    private int px(float dp) { return Math.round(dp * d); }

    /** Visibile anche agli script dei siti: solo la memoria del ring, con limiti (Memoria.salva). */
    private final class Ponte {
        @JavascriptInterface public String dati() { return Memoria.dati(Browser.this); }
        @JavascriptInterface public void salva(String json) { Memoria.salva(Browser.this, json); }
        @JavascriptInterface public void messaggio(String json) {
            String tipo = "";
            try { tipo = new JSONObject(json).optString("tipo", ""); } catch (Exception ignorata) { }
            if ("opzioni".equals(tipo) || "guida".equals(tipo)) {
                startActivity(new Intent(Browser.this, Principale.class));
            }
        }
    }
}
