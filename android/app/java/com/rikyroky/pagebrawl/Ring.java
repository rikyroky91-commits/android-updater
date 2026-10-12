package com.rikyroky.pagebrawl;

import android.accessibilityservice.AccessibilityService;
import android.annotation.SuppressLint;
import android.app.KeyguardManager;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.res.Configuration;
import android.graphics.Color;
import android.graphics.PixelFormat;
import android.graphics.Point;
import android.graphics.Rect;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.util.DisplayMetrics;
import android.util.Log;
import android.view.ContextThemeWrapper;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewConfiguration;
import android.view.ViewTreeObserver;
import android.view.WindowInsets;
import android.view.WindowManager;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;
import android.view.accessibility.AccessibilityWindowInfo;
import android.webkit.ConsoleMessage;
import android.webkit.JavascriptInterface;
import android.webkit.JsPromptResult;
import android.webkit.JsResult;
import android.webkit.RenderProcessGoneDetail;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.List;

/**
 * IL RING SOPRA LO SCHERMO VERO (12/10/2026).
 *
 * Un servizio di accessibilità, perché è l'unico modo che Android dà a un'app per
 *  1. sapere dove stanno gli elementi delle altre app e del blocco schermo
 *     (icone, testi, tasti, notifiche, l'orologio): diventano i corpi solidi
 *     su cui i lottatori atterrano, camminano e si arrampicano;
 *  2. disegnare sopra tutto, blocco schermo compreso (TYPE_ACCESSIBILITY_OVERLAY).
 *
 * Dello schermo si leggono SOLO le posizioni dei riquadri, e solo mentre il
 * ring è acceso: niente testi, niente salvato, niente inviato.
 *
 * Il ring è una WebView trasparente col ring.js dell'estensione (assets/web).
 * Si accende dalla bolla, dal riquadro delle impostazioni rapide, dall'app, o
 * da solo quando si accende lo schermo (se l'utente l'ha chiesto).
 * Si spegne con ✕, col tasto Indietro, spegnendo le lotte dalla tendina,
 * spegnendo lo schermo, o sbloccando il telefono se era partito da solo.
 */
public class Ring extends AccessibilityService {
    private static final String TAG = "PageBrawl";
    private static final int NODI_MAX = 260;
    private static final int VISITE_MAX = 6000;

    static volatile Ring istanza;
    private static final int FINESTRA_PASSA = WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN
            | WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS
            | WindowManager.LayoutParams.FLAG_HARDWARE_ACCELERATED
            | WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
            | WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE;
    private static final java.util.Set<String> CHROME = new java.util.HashSet<String>(java.util.Arrays.asList(
            "com.android.chrome", "com.chrome.beta", "com.chrome.dev", "com.chrome.canary"));

    private Comandi comandi;
    private int bassoPx;
    private boolean inChrome;
    private String modo = "sistema";
    private boolean bollaNascosta;      // tolta con una pressione lunga: torna riaprendo l'app o riaccendendo lo schermo

    private WindowManager wm;
    private Handler h;

    private ImageView bolla;
    private WindowManager.LayoutParams lpBolla;

    private FrameLayout arena;
    private WebView web;
    private WindowManager.LayoutParams lpArena;
    private boolean inAvvio;
    private boolean apertoDaBlocco;
    private volatile String schermo = "{}";
    private String ultimiNodi = "";
    private int ox, oy, alto;
    private boolean scansioneProgrammata;
    private int visite;
    private BroadcastReceiver ricevitore;

    // ------------------------------------------------------------------ ciclo
    @Override
    protected void onServiceConnected() {
        istanza = this;
        wm = (WindowManager) getSystemService(WINDOW_SERVICE);
        h = new Handler(Looper.getMainLooper());
        try {
            AccessibilityNodeInfo r = getRootInActiveWindow();
            inChrome = r != null && r.getPackageName() != null && CHROME.contains(r.getPackageName().toString());
        } catch (Exception ignorata) { }
        aggiornaBolla();
        ricevitore = new BroadcastReceiver() {
            @Override
            public void onReceive(Context c, Intent i) {
                String a = i.getAction();
                if (Intent.ACTION_SCREEN_ON.equals(a)) {
                    // Modalità «solo blocco schermo»: il ring compare appena si accende lo schermo.
                    if ("blocco".equals(Memoria.modo(Ring.this)) && bloccato() && arena == null && Memoria.consenso(Ring.this)) {
                        apertoDaBlocco = true;
                        avvia(650);
                    } else aggiornaBolla();
                } else if (Intent.ACTION_USER_PRESENT.equals(a)) {
                    if (apertoDaBlocco || ("blocco".equals(Memoria.modo(Ring.this)) && arena != null)) chiudi();
                    aggiornaBolla();
                } else if (Intent.ACTION_SCREEN_OFF.equals(a)) {
                    bollaNascosta = false;
                    if (arena != null) chiudi();
                    aggiornaBolla();
                }
            }
        };
        IntentFilter f = new IntentFilter();
        f.addAction(Intent.ACTION_SCREEN_ON);
        f.addAction(Intent.ACTION_SCREEN_OFF);
        f.addAction(Intent.ACTION_USER_PRESENT);
        registerReceiver(ricevitore, f);
        Riquadro.aggiorna(this);
    }

    @Override
    public boolean onUnbind(Intent intent) {
        spegniTutto();
        return super.onUnbind(intent);
    }

    @Override
    public void onDestroy() {
        spegniTutto();
        super.onDestroy();
    }

    private void spegniTutto() {
        if (istanza == this) istanza = null;
        try { if (ricevitore != null) unregisterReceiver(ricevitore); } catch (Exception ignorata) { }
        ricevitore = null;
        chiudi();
        nascondiBolla();
        Riquadro.aggiorna(this);
    }

    @Override
    public void onInterrupt() { }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent e) {
        if (e == null || !Memoria.consenso(this)) return;     // senza consenso nell'app non si guarda niente
        CharSequence p = e.getPackageName();
        if (p != null && getPackageName().contentEquals(p)) return;
        // Quale app è in primo piano (per la modalità «solo Chrome»): la tendina e la tastiera non contano.
        if (e.getEventType() == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED && p != null) {
            String pk = p.toString();
            CharSequence cl = e.getClassName();
            boolean tastiera = cl != null && (cl.toString().contains("inputmethod") || cl.toString().contains("SoftInputWindow"));
            if (!tastiera && !"com.android.systemui".equals(pk)) {
                boolean era = inChrome;
                inChrome = CHROME.contains(pk);
                if (era != inChrome) {
                    if ("chrome".equals(modo) && !inChrome && arena != null) chiudi();
                    else aggiornaBolla();
                }
            }
        }
        // Lo schermo sotto è cambiato (una notifica, l'orologio, un'altra app):
        // i solidi si rileggono, al massimo una volta ogni 1,2 secondi.
        if (arena == null || web == null) return;
        if (scansioneProgrammata) return;
        scansioneProgrammata = true;
        h.postDelayed(riscansiona, 1200);
    }

    @Override
    public void onConfigurationChanged(Configuration nuova) {
        super.onConfigurationChanged(nuova);
        if (arena != null) h.postDelayed(ridimensiona, 400);
    }

    // ----------------------------------------------------------- accensione
    /** Accende il ring sullo schermo che c'è adesso. */
    void avvia(long ritardo) {
        if (arena != null || inAvvio || wm == null) return;
        if (!Memoria.consenso(this)) {
            // Servizio acceso dalle impostazioni senza passare dall'avviso: prima l'avviso, nell'app.
            startActivity(new Intent(this, Principale.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
            return;
        }
        inAvvio = true;
        nascondiBolla();
        h.postDelayed(new Runnable() {
            @Override public void run() {
                inAvvio = false;
                try {
                    apriArena();
                } catch (Exception e) {
                    Log.e(TAG, "arena", e);
                    chiudi();
                }
            }
        }, ritardo);
    }

    /** Dal riquadro delle impostazioni rapide: prima si chiude la tendina. */
    void avviaDaRiquadro() {
        if (Build.VERSION.SDK_INT >= 31) performGlobalAction(GLOBAL_ACTION_DISMISS_NOTIFICATION_SHADE);
        else performGlobalAction(GLOBAL_ACTION_BACK);
        apertoDaBlocco = bloccato();
        avvia(700);
    }

    private boolean bloccato() {
        KeyguardManager km = (KeyguardManager) getSystemService(KEYGUARD_SERVICE);
        return km != null && km.isKeyguardLocked();
    }

    @SuppressLint({"SetJavaScriptEnabled", "AddJavascriptInterface"})
    private void apriArena() {
        if (arena != null) return;
        modo = Memoria.modo(this);
        // Prima si legge lo schermo, poi si mette il ring sopra.
        ultimiNodi = raccogli();
        Context tema = new ContextThemeWrapper(this, android.R.style.Theme_DeviceDefault_NoActionBar);
        // Il telefono resta usabile: la finestra dei lottatori non prende né tocchi né tastiera
        // (tutto passa all'app sotto). I comandi stanno in finestre loro, piccole (Comandi.java).
        arena = new FrameLayout(tema);
        // Il ring non si fa leggere dall'accessibilità: non è un contenuto, ed è pesante.
        arena.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS);

        web = new WebView(tema);
        web.setBackgroundColor(Color.TRANSPARENT);
        web.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setSupportZoom(false);
        s.setTextZoom(100);
        web.setVerticalScrollBarEnabled(false);
        web.setHorizontalScrollBarEnabled(false);
        web.setOverScrollMode(View.OVER_SCROLL_NEVER);
        web.addJavascriptInterface(new Ponte(), "PB");
        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                return !r.getUrl().toString().startsWith("file:///android_asset/");
            }

            @Override
            public void onPageFinished(WebView v, String url) {
                if (v != web || comandi != null) return;
                comandi = new Comandi(Ring.this, new OspiteFinestre(), web);
                comandi.avvia();
            }

            @Override
            public boolean onRenderProcessGone(WebView v, RenderProcessGoneDetail d) {
                // Il motore della pagina è caduto: si chiude il ring, non l'app.
                if (v == web) { web = null; chiudi(); }
                return true;
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            // Sopra le altre app non ci sono finestre di dialogo: si rifiutano in silenzio.
            @Override public boolean onJsAlert(WebView v, String u, String m, JsResult r) { r.cancel(); return true; }
            @Override public boolean onJsConfirm(WebView v, String u, String m, JsResult r) { r.cancel(); return true; }
            @Override public boolean onJsPrompt(WebView v, String u, String m, String d, JsPromptResult r) { r.cancel(); return true; }
            @Override public boolean onConsoleMessage(ConsoleMessage m) {
                if (m.messageLevel() == ConsoleMessage.MessageLevel.ERROR) Log.w(TAG, "js: " + m.message() + " @" + m.lineNumber());
                return true;
            }
        });
        arena.addView(web, new FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));

        lpArena = new WindowManager.LayoutParams(
                WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
                FINESTRA_PASSA,
                PixelFormat.TRANSLUCENT);
        Point schermoReale = schermoReale();
        lpArena.width = schermoReale.x;
        lpArena.height = schermoReale.y;
        lpArena.gravity = Gravity.TOP | Gravity.LEFT;
        lpArena.x = 0;
        lpArena.y = 0;
        lpArena.softInputMode = WindowManager.LayoutParams.SOFT_INPUT_ADJUST_PAN;
        if (Build.VERSION.SDK_INT >= 28) {
            lpArena.layoutInDisplayCutoutMode = Build.VERSION.SDK_INT >= 30
                    ? WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_ALWAYS
                    : WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES;
        }
        if (Build.VERSION.SDK_INT >= 30) lpArena.setFitInsetsTypes(0);
        wm.addView(arena, lpArena);
        creaZone();          // sopra il ring ma sotto i comandi (che arrivano dopo)

        dopoIlDisegno(new Runnable() {
            @Override public void run() {
                misura();
                if (web != null) web.loadUrl("file:///android_asset/web/schermo.html");
            }
        });
    }

    /** Una volta, appena la finestra del ring ha le sue misure. */
    private void dopoIlDisegno(final Runnable r) {
        if (arena == null) return;
        final FrameLayout questa = arena;
        questa.getViewTreeObserver().addOnGlobalLayoutListener(new ViewTreeObserver.OnGlobalLayoutListener() {
            private boolean fatto;
            @Override public void onGlobalLayout() {
                if (fatto) return;
                fatto = true;
                questa.getViewTreeObserver().removeOnGlobalLayoutListener(this);
                if (arena == questa) r.run();
            }
        });
        questa.requestLayout();
    }

    /**
     * Dove sta la pagina sullo schermo. La pagina finisce sopra la barra di
     * navigazione: così il pavimento del ring è lì e i lottatori non
     * camminano dietro il trattino dei gesti.
     */
    @SuppressWarnings("deprecation")
    private void misura() {
        if (arena == null || web == null) return;
        int sx = 0, dx = 0, giu = 0;
        alto = 0;
        WindowInsets wi = arena.getRootWindowInsets();
        if (wi != null) {
            if (Build.VERSION.SDK_INT >= 30) {
                android.graphics.Insets nav = wi.getInsets(WindowInsets.Type.navigationBars());
                android.graphics.Insets su = wi.getInsets(WindowInsets.Type.statusBars() | WindowInsets.Type.displayCutout());
                sx = nav.left; dx = nav.right; giu = nav.bottom; alto = su.top;
            } else {
                sx = wi.getSystemWindowInsetLeft(); dx = wi.getSystemWindowInsetRight();
                giu = wi.getSystemWindowInsetBottom(); alto = wi.getSystemWindowInsetTop();
            }
        }
        if (alto == 0 && giu == 0 && sx == 0 && dx == 0) {
            // Alcune versioni non danno le barre a una finestra senza limiti:
            // si usano le misure di sistema (barra di stato in alto, navigazione in basso).
            alto = dimensioneDiSistema("status_bar_height");
            if (getResources().getConfiguration().orientation == Configuration.ORIENTATION_PORTRAIT) {
                giu = dimensioneDiSistema("navigation_bar_height");
            }
        }
        FrameLayout.LayoutParams lp = (FrameLayout.LayoutParams) web.getLayoutParams();
        if (lp.leftMargin != sx || lp.rightMargin != dx || lp.bottomMargin != giu) {
            lp.leftMargin = sx; lp.rightMargin = dx; lp.bottomMargin = giu;
            web.setLayoutParams(lp);
        }
        bassoPx = giu;
        int[] pos = new int[2];
        arena.getLocationOnScreen(pos);
        ox = pos[0] + sx;
        oy = pos[1];
        schermo = componi(ultimiNodi);
    }

    private int dimensioneDiSistema(String nome) {
        int id = getResources().getIdentifier(nome, "dimen", "android");
        return id > 0 ? getResources().getDimensionPixelSize(id) : 0;
    }

    private String componi(String nodi) {
        return "{\"nodi\":" + nodi + ",\"ox\":" + ox + ",\"oy\":" + oy + ",\"alto\":" + alto + "}";
    }

    private final Runnable riscansiona = new Runnable() {
        @Override public void run() {
            scansioneProgrammata = false;
            if (arena == null || web == null) return;
            String n = raccogli();
            if (n.equals(ultimiNodi)) return;
            ultimiNodi = n;
            schermo = componi(n);
            web.evaluateJavascript("window.__pbSchermo&&window.__pbSchermo.disegna(" + schermo + ")", null);
        }
    };

    private final Runnable ridimensiona = new Runnable() {
        @Override public void run() {
            if (arena == null || lpArena == null) return;
            Point p = schermoReale();
            lpArena.width = p.x;
            lpArena.height = p.y;
            try { wm.updateViewLayout(arena, lpArena); } catch (Exception ignorata) { return; }
            dopoIlDisegno(new Runnable() {
                @Override public void run() {
                    misura();
                    ultimiNodi = "";
                    riscansiona.run();
                }
            });
        }
    };

    /** Spegne il ring e ridà lo schermo. */
    void chiudi() {
        if (h != null) {
            h.removeCallbacks(riscansiona);
            h.removeCallbacks(ridimensiona);
        }
        scansioneProgrammata = false;
        inAvvio = false;
        apertoDaBlocco = false;
        if (comandi != null) { comandi.ferma(); comandi = null; }
        togliZone();
        if (arena != null) {
            try { wm.removeView(arena); } catch (Exception ignorata) { }
        }
        if (web != null) {
            try { web.stopLoading(); web.destroy(); } catch (Exception ignorata) { }
        }
        web = null;
        arena = null;
        aggiornaBolla();
    }

    boolean acceso() { return arena != null; }

    // ------------------------------------------------- gli elementi a schermo
    /**
     * I riquadri degli elementi visibili, in pixel dello schermo, in tutte le
     * finestre (l'app, la barra di stato, la tastiera, il blocco schermo).
     * Si tengono le "foglie utili": un elemento con testo, descrizione,
     * cliccabile o immagine, che non contiene già altri elementi presi.
     * Gli sfondi grandi restano fuori.
     */
    private String raccogli() {
        JSONArray out = new JSONArray();
        visite = 0;
        Point s = schermoReale();
        Limiti lim = new Limiti();
        lim.larghezza = s.x;
        lim.altezza = s.y;
        lim.areaMax = (long) s.x * s.y * 30 / 100;
        lim.altezzaMax = s.y * 28 / 100;
        float d = getResources().getDisplayMetrics().density;
        lim.minL = Math.round(10 * d);
        lim.minA = Math.round(8 * d);
        lim.barraStato = dimensioneDiSistema("status_bar_height") + Math.round(2 * d);
        List<AccessibilityWindowInfo> finestre = null;
        try { finestre = getWindows(); } catch (Exception ignorata) { }
        if (finestre != null && !finestre.isEmpty()) {
            for (AccessibilityWindowInfo w : finestre) {
                if (w.getType() == AccessibilityWindowInfo.TYPE_ACCESSIBILITY_OVERLAY) continue;
                AccessibilityNodeInfo radice;
                try { radice = w.getRoot(); } catch (Exception e) { radice = null; }
                if (radice == null) continue;
                if ("chrome".equals(modo)) {
                    CharSequence pk = radice.getPackageName();
                    if (pk == null || !CHROME.contains(pk.toString())) continue;
                }
                // La bolla e il ring stesso sono finestre di accessibilità: già escluse sopra.
                visita(radice, out, 0, lim);
            }
        } else {
            AccessibilityNodeInfo r = null;
            try { r = getRootInActiveWindow(); } catch (Exception ignorata) { }
            if (r != null) visita(r, out, 0, lim);
        }
        return out.toString();
    }

    private static final class Limiti {
        int larghezza, altezza, altezzaMax, minL, minA, barraStato;
        long areaMax;
    }

    private boolean visita(AccessibilityNodeInfo n, JSONArray out, int prof, Limiti lim) {
        if (n == null || out.length() >= NODI_MAX || visite++ > VISITE_MAX || prof > 60) return false;
        try {
            if (!n.isVisibleToUser()) return false;
            boolean figli = false;
            int quanti = n.getChildCount();
            for (int i = 0; i < quanti; i++) {
                AccessibilityNodeInfo c = n.getChild(i);
                if (c != null && visita(c, out, prof + 1, lim)) figli = true;
            }
            if (figli) return true;
            Rect r = new Rect();
            n.getBoundsInScreen(r);
            if (!r.intersect(0, 0, lim.larghezza, lim.altezza)) return false;
            // La barra di stato (orologio, batteria, icone delle notifiche) non è terreno: sta sotto la capsula
            // dei comandi, e lassù negli angoli i lottatori restavano incastrati.
            if (r.bottom <= lim.barraStato) return false;
            if (r.width() < lim.minL || r.height() < lim.minA) return false;
            if ((long) r.width() * r.height() > lim.areaMax || r.height() > lim.altezzaMax) return false;
            if (!utile(n)) return false;
            out.put(new JSONArray().put(r.left).put(r.top).put(r.right).put(r.bottom));
            return true;
        } catch (Exception e) {
            return false;   // un nodo sparito mentre lo si leggeva
        }
    }

    private static boolean utile(AccessibilityNodeInfo n) {
        CharSequence t = n.getText(), d = n.getContentDescription();
        if (t != null && t.toString().trim().length() > 0) return true;
        if (d != null && d.toString().trim().length() > 0) return true;
        if (n.isClickable() || n.isCheckable() || n.isEditable() || n.isLongClickable()) return true;
        CharSequence cl = n.getClassName();
        if (cl != null) {
            String c = cl.toString();
            return c.endsWith("ImageView") || c.endsWith("Image") || c.endsWith("Button")
                    || c.contains("EditText") || c.endsWith("Switch") || c.endsWith("CheckBox");
        }
        return false;
    }

    @SuppressWarnings("deprecation")
    private Point schermoReale() {
        DisplayMetrics dm = new DisplayMetrics();
        wm.getDefaultDisplay().getRealMetrics(dm);
        return new Point(dm.widthPixels, dm.heightPixels);
    }

    // ------------------------------------------------------------- la bolla
    void aggiornaBolla() {
        if (wm == null) return;
        modo = Memoria.modo(this);
        boolean serve = Memoria.consenso(this)
                && ("sistema".equals(modo) || ("chrome".equals(modo) && inChrome) || ("blocco".equals(modo) && bloccato()));
        if (serve && !bollaNascosta && arena == null && !inAvvio) mostraBolla();
        else nascondiBolla();
    }

    @SuppressLint("ClickableViewAccessibility")
    private void mostraBolla() {
        if (bolla != null) return;
        final float d = getResources().getDisplayMetrics().density;
        final int lato = Math.round(54 * d);
        bolla = new ImageView(this);
        bolla.setImageResource(R.drawable.guantone);
        bolla.setScaleType(ImageView.ScaleType.FIT_CENTER);
        GradientDrawable fondo = new GradientDrawable();
        fondo.setShape(GradientDrawable.OVAL);
        fondo.setColor(0xFF183D30);
        fondo.setStroke(Math.round(2 * d), 0xCCFFFFFF);
        bolla.setBackground(fondo);
        bolla.setElevation(8 * d);
        bolla.setAlpha(0.88f);
        bolla.setContentDescription("Page Brawl: tap to start the ring on this screen, hold to hide");

        lpBolla = new WindowManager.LayoutParams(lato, lato,
                WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
                        | WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS
                        | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
                PixelFormat.TRANSLUCENT);
        lpBolla.gravity = Gravity.TOP | Gravity.LEFT;
        final Point s = schermoReale();
        int[] pos = Memoria.posBolla(this);
        lpBolla.x = pos[0] >= 0 ? Math.min(pos[0], s.x - lato) : s.x - lato - Math.round(6 * d);
        lpBolla.y = pos[1] >= 0 ? Math.min(pos[1], s.y - lato) : s.y * 2 / 5;

        final int soglia = ViewConfiguration.get(this).getScaledTouchSlop();
        bolla.setOnTouchListener(new View.OnTouchListener() {
            float tx, ty;
            int bx, by;
            boolean trascina, lungo;
            final Runnable pressioneLunga = new Runnable() {
                @Override public void run() {
                    // Pressione lunga: la bolla sparisce (si riprende dall'app o riaccendendo lo schermo).
                    lungo = true;
                    if (bolla != null) bolla.performHapticFeedback(android.view.HapticFeedbackConstants.LONG_PRESS);
                    bollaNascosta = true;
                    nascondiBolla();
                    Toast.makeText(Ring.this, "Bubble hidden: it comes back when you open Page Brawl", Toast.LENGTH_SHORT).show();
                }
            };

            @Override
            public boolean onTouch(View v, MotionEvent e) {
                switch (e.getActionMasked()) {
                    case MotionEvent.ACTION_DOWN:
                        tx = e.getRawX(); ty = e.getRawY();
                        bx = lpBolla.x; by = lpBolla.y;
                        trascina = false; lungo = false;
                        h.postDelayed(pressioneLunga, 650);
                        return true;
                    case MotionEvent.ACTION_MOVE:
                        float mx = e.getRawX() - tx, my = e.getRawY() - ty;
                        if (!trascina && Math.hypot(mx, my) > soglia) {
                            trascina = true;
                            h.removeCallbacks(pressioneLunga);
                        }
                        if (trascina && bolla != null) {
                            lpBolla.x = Math.round(bx + mx);
                            lpBolla.y = Math.round(by + my);
                            try { wm.updateViewLayout(bolla, lpBolla); } catch (Exception ignorata) { }
                        }
                        return true;
                    case MotionEvent.ACTION_UP:
                        h.removeCallbacks(pressioneLunga);
                        if (lungo) return true;
                        if (!trascina) {
                            avvia(120);
                        } else if (bolla != null) {
                            // Si attacca al bordo più vicino.
                            Point sc = schermoReale();
                            int w = bolla.getWidth();
                            lpBolla.x = lpBolla.x + w / 2 < sc.x / 2 ? Math.round(6 * d) : sc.x - w - Math.round(6 * d);
                            lpBolla.y = Math.max(0, Math.min(lpBolla.y, sc.y - w));
                            try { wm.updateViewLayout(bolla, lpBolla); } catch (Exception ignorata) { }
                            Memoria.posBolla(Ring.this, lpBolla.x, lpBolla.y);
                        }
                        return true;
                    case MotionEvent.ACTION_CANCEL:
                        h.removeCallbacks(pressioneLunga);
                        return true;
                }
                return false;
            }
        });
        try {
            wm.addView(bolla, lpBolla);
        } catch (Exception e) {
            Log.e(TAG, "bolla", e);
            bolla = null;
        }
    }

    /** L'app è stata riaperta: la bolla tolta con la pressione lunga torna. */
    void riprendiBolla() {
        bollaNascosta = false;
        aggiornaBolla();
    }

    void nascondiBolla() {
        if (bolla != null) {
            try { wm.removeView(bolla); } catch (Exception ignorata) { }
            bolla = null;
        }
    }

    private void apriApp() {
        Intent i = new Intent(this, Principale.class);
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED);
        try { startActivity(i); } catch (Exception e) {
            Toast.makeText(this, "Open Page Brawl from your apps", Toast.LENGTH_SHORT).show();
        }
    }

    // ---------------------------------------------- i comandi in finestre loro
    /** Ogni pezzo dei comandi è una finestra di accessibilità piccola quanto lui: il resto dello schermo resta del telefono. */
    private final class OspiteFinestre implements Comandi.Ospite {
        @Override public void metti(View v, int gravita, int x, int y, int w, int hh, boolean tocchiFuori) {
            WindowManager.LayoutParams lp = new WindowManager.LayoutParams(
                    w == -2 ? WindowManager.LayoutParams.WRAP_CONTENT : w, hh == -2 ? WindowManager.LayoutParams.WRAP_CONTENT : hh,
                    WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
                    WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN
                            | WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS
                            | (tocchiFuori ? WindowManager.LayoutParams.FLAG_WATCH_OUTSIDE_TOUCH : 0),
                    PixelFormat.TRANSLUCENT);
            lp.gravity = gravita; lp.x = x; lp.y = y;
            if (Build.VERSION.SDK_INT >= 28) lp.layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES;
            v.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_YES);
            try { wm.addView(v, lp); } catch (Exception e) { Log.w(TAG, "comandi", e); }
        }
        @Override public void sposta(View v, int gravita, int x, int y, int w, int hh) {
            try {
                WindowManager.LayoutParams lp = (WindowManager.LayoutParams) v.getLayoutParams();
                lp.gravity = gravita; lp.x = x; lp.y = y;
                wm.updateViewLayout(v, lp);
            } catch (Exception ignorata) { }
        }
        @Override public void togli(View v) { try { wm.removeView(v); } catch (Exception ignorata) { } }
        @Override public void superficieToccabile(boolean si) {
            // La tendina del ring aperta: la finestra dei lottatori prende i tocchi finché si chiude.
            if (arena == null || lpArena == null) return;
            lpArena.flags = si ? (FINESTRA_PASSA & ~WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE) : FINESTRA_PASSA;
            try { wm.updateViewLayout(arena, lpArena); } catch (Exception ignorata) { }
        }
        @Override public void mostraLottatori(boolean si) { if (web != null) web.setVisibility(si ? View.VISIBLE : View.INVISIBLE); }
        @Override public void seguiLottatori(boolean si) { seguendo = si; if (!si) for (int i = 0; i < 2; i++) nascondiZona(i); }
        @Override public void apriApp() { Ring.this.apriApp(); }
        @Override public void frequenza(float hz) {
            if (arena == null || lpArena == null) return;
            lpArena.preferredRefreshRate = hz;
            try { wm.updateViewLayout(arena, lpArena); } catch (Exception ignorata) { }
        }
        @Override public void chiudiGioco() { chiudi(); }
        @Override public int margineAlto() { return Math.max(alto, dimensioneDiSistema("status_bar_height")); }
        @Override public int margineBasso() { return bassoPx; }
    }

    // ------------------------------------------- le zone che seguono i lottatori
    // Sopra lo schermo la finestra del ring lascia passare i tocchi. Per poter comunque prendere, trascinare e
    // lanciare i lottatori, su ognuno c'è una finestrella invisibile e toccabile che lo segue (la pagina ne
    // manda la posizione 20 volte al secondo, `PB.corpi`). Il gesto che parte lì va alla pagina, intero, anche
    // quando il dito esce dalla finestrella: Android consegna tutto il gesto alla finestra dove è cominciato.
    private final View[] zone = new View[2];
    private final WindowManager.LayoutParams[] lpZone = new WindowManager.LayoutParams[2];
    private final boolean[] zonaPremuta = new boolean[2];
    private boolean seguendo;

    private void creaZone() {
        for (int i = 0; i < 2; i++) {
            final int n = i;
            View z = new View(this) {
                @Override public boolean onTouchEvent(MotionEvent e) { return inoltra(n, e); }
            };
            z.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
            WindowManager.LayoutParams lp = new WindowManager.LayoutParams(1, 1,
                    WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
                    WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE | WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE
                            | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN | WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
                    PixelFormat.TRANSLUCENT);
            lp.gravity = Gravity.TOP | Gravity.LEFT;
            lp.x = -10; lp.y = -10;
            if (Build.VERSION.SDK_INT >= 28) lp.layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES;
            try { wm.addView(z, lp); zone[i] = z; lpZone[i] = lp; } catch (Exception e) { Log.w(TAG, "zona", e); }
        }
    }

    private void togliZone() {
        for (int i = 0; i < 2; i++) {
            if (zone[i] != null) { try { wm.removeView(zone[i]); } catch (Exception ignorata) { } }
            zone[i] = null; lpZone[i] = null; zonaPremuta[i] = false;
        }
        seguendo = false;
    }

    private void nascondiZona(int i) {
        WindowManager.LayoutParams lp = lpZone[i];
        if (zone[i] == null || lp == null || zonaPremuta[i] || (lp.flags & WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE) != 0) return;
        lp.flags |= WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE;
        lp.width = 1; lp.height = 1; lp.x = -10; lp.y = -10;
        try { wm.updateViewLayout(zone[i], lp); } catch (Exception ignorata) { }
    }

    /** I riquadri dei lottatori in pixel della pagina: [[l,t,r,b] | null, ...]. */
    private void aggiornaZone(String json) {
        if (!seguendo || web == null) return;
        try {
            JSONArray a = new JSONArray(json);
            float dp = getResources().getDisplayMetrics().density;
            int margine = Math.round(14 * dp), minimo = Math.round(56 * dp);
            for (int i = 0; i < 2 && i < a.length(); i++) {
                WindowManager.LayoutParams lp = lpZone[i];
                if (zone[i] == null || lp == null || zonaPremuta[i]) continue;      // durante una presa la zona sta ferma
                JSONArray q = a.optJSONArray(i);
                if (q == null) { nascondiZona(i); continue; }
                int l = ox + Math.round((float) q.getDouble(0) * dp), t = oy + Math.round((float) q.getDouble(1) * dp);
                int r = ox + Math.round((float) q.getDouble(2) * dp), b = oy + Math.round((float) q.getDouble(3) * dp);
                int w = Math.max(minimo, r - l + 2 * margine), hh = Math.max(minimo, b - t + 2 * margine);
                int x = (l + r) / 2 - w / 2, y = (t + b) / 2 - hh / 2;
                boolean nascosta = (lp.flags & WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE) != 0;
                if (!nascosta && Math.abs(lp.x - x) < 3 && Math.abs(lp.y - y) < 3 && Math.abs(lp.width - w) < 3 && Math.abs(lp.height - hh) < 3) continue;
                lp.flags &= ~WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE;
                lp.x = x; lp.y = y; lp.width = w; lp.height = hh;
                try { wm.updateViewLayout(zone[i], lp); } catch (Exception ignorata) { }
            }
        } catch (Exception ignorata) { /* il prossimo giro */ }
    }

    /** Il gesto preso da una zona va alla pagina del ring, nelle sue coordinate. */
    private boolean inoltra(int i, MotionEvent e) {
        if (web == null) return false;
        int azione = e.getActionMasked();
        if (azione == MotionEvent.ACTION_DOWN) zonaPremuta[i] = true;
        int[] w = new int[2];
        web.getLocationOnScreen(w);
        MotionEvent c = MotionEvent.obtain(e);
        c.offsetLocation(e.getRawX() - e.getX() - w[0], e.getRawY() - e.getY() - w[1]);
        web.dispatchTouchEvent(c);
        c.recycle();
        if (azione == MotionEvent.ACTION_UP || azione == MotionEvent.ACTION_CANCEL) zonaPremuta[i] = false;
        return true;
    }

    // --------------------------------------------------- il ponte con la pagina
    /** Chiamato dal JavaScript della pagina del ring (su un thread suo). */
    private final class Ponte {
        @JavascriptInterface public String dati() { return Memoria.dati(Ring.this); }
        @JavascriptInterface public void salva(String json) { Memoria.salva(Ring.this, json); }
        @JavascriptInterface public String schermo() { return schermo; }
        @JavascriptInterface public void corpi(final String json) {
            h.post(new Runnable() { @Override public void run() { aggiornaZone(json); } });
        }

        @JavascriptInterface public void chiudi() {
            h.post(new Runnable() { @Override public void run() { Ring.this.chiudi(); } });
        }

        @JavascriptInterface public void messaggio(String json) {
            String tipo = "";
            try { tipo = new JSONObject(json).optString("tipo", ""); } catch (Exception ignorata) { }
            if ("opzioni".equals(tipo) || "guida".equals(tipo)) {
                h.post(new Runnable() {
                    @Override public void run() {
                        Ring.this.chiudi();
                        apriApp();
                    }
                });
            }
        }
    }
}
