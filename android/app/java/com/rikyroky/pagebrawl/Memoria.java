package com.rikyroky.pagebrawl;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONObject;

import java.util.Iterator;
import java.util.Locale;
import java.util.Map;

/**
 * Due memorie separate:
 *  - "gioco": le chiavi del ring (quello che i lottatori imparano, gettoni,
 *    opzioni della tendina), le stesse che l'estensione tiene in
 *    chrome.storage.local. Uguali sopra lo schermo e nel browser interno;
 *  - "opzioni": le scelte dell'app (bolla, ring sul blocco schermo).
 */
final class Memoria {
    private Memoria() {}

    private static final String[] LINGUE = {"it", "en", "es", "fr", "de"};
    private static final int CHIAVE_MAX = 80;
    private static final int VALORE_MAX = 200_000;
    private static final int CHIAVI_MAX = 300;

    static SharedPreferences gioco(Context c) {
        return c.getSharedPreferences("gioco", Context.MODE_PRIVATE);
    }

    static SharedPreferences opzioni(Context c) {
        return c.getSharedPreferences("opzioni", Context.MODE_PRIVATE);
    }

    /** Dove si gioca: "blocco" (solo blocco schermo), "sistema" (ovunque), "chrome" (solo Chrome), "app" (arene). */
    static final String[] MODI = {"blocco", "sistema", "chrome", "app"};
    static String modo(Context c) { return opzioni(c).getString("modo", "sistema"); }
    static void modo(Context c, String m) { opzioni(c).edit().putString("modo", m).apply(); }

    static boolean bolla(Context c) { return opzioni(c).getBoolean("bolla", true); }
    static void bolla(Context c, boolean si) { opzioni(c).edit().putBoolean("bolla", si).apply(); }
    static boolean blocco(Context c) { return opzioni(c).getBoolean("blocco", false); }
    static void blocco(Context c, boolean si) { opzioni(c).edit().putBoolean("blocco", si).apply(); }
    static boolean webAuto(Context c) { return opzioni(c).getBoolean("web_auto", true); }
    static void webAuto(Context c, boolean si) { opzioni(c).edit().putBoolean("web_auto", si).apply(); }
    static int[] posBolla(Context c) {
        SharedPreferences p = opzioni(c);
        return new int[]{p.getInt("bolla_x", -1), p.getInt("bolla_y", -1)};
    }
    static void posBolla(Context c, int x, int y) {
        opzioni(c).edit().putInt("bolla_x", x).putInt("bolla_y", y).apply();
    }

    /** La memoria del ring come oggetto JSON di stringhe (window.__ringDati). */
    static String dati(Context c) {
        JSONObject o = new JSONObject();
        try {
            for (Map.Entry<String, ?> e : gioco(c).getAll().entrySet()) {
                o.put(e.getKey(), String.valueOf(e.getValue()));
            }
            if (!o.has("pb-lingua")) o.put("pb-lingua", linguaDiSistema());
        } catch (Exception ignorata) { /* memoria vuota */ }
        return o.toString();
    }

    /** Una o più chiavi dal ring. Limiti larghi: nel browser interno PB è visibile anche ai siti. */
    static void salva(Context c, String json) {
        try {
            JSONObject o = new JSONObject(json);
            SharedPreferences p = gioco(c);
            int gia = p.getAll().size();
            SharedPreferences.Editor ed = p.edit();
            Iterator<String> chiavi = o.keys();
            while (chiavi.hasNext()) {
                String k = chiavi.next();
                String v = o.optString(k, "");
                if (k.length() == 0 || k.length() > CHIAVE_MAX || v.length() > VALORE_MAX) continue;
                if (!p.contains(k) && ++gia > CHIAVI_MAX) continue;
                ed.putString(k, v);
            }
            ed.apply();
        } catch (Exception ignorata) { /* JSON rotto: niente */ }
    }

    static String linguaDiSistema() {
        String l = Locale.getDefault().getLanguage();
        for (String x : LINGUE) if (x.equals(l)) return x;
        return "en";
    }
}
