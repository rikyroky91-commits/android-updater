package com.rikyroky.pagebrawl;

import android.app.Activity;
import android.os.Build;
import android.view.View;
import android.view.WindowInsets;

/**
 * Schermo da bordo a bordo (12/10/2026, per il Play Store: dal 31/08/2026 le app nuove puntano ad API 36).
 * Da Android 15 in su, con target 35+, la finestra disegna anche sotto la barra di stato, quella di
 * navigazione e la tacca della fotocamera, e la tastiera non la ridimensiona più da sola: le schermate
 * normali (app, browser) si spostano dentro con un'imbottitura pari a quelle fasce.
 * Sotto Android 15 non serve: il sistema fa ancora da sé.
 */
final class Bordi {
    private Bordi() {}

    static void imbottisci(View radice) {
        if (Build.VERSION.SDK_INT < 35) return;
        radice.setOnApplyWindowInsetsListener(new View.OnApplyWindowInsetsListener() {
            @Override public WindowInsets onApplyWindowInsets(View v, WindowInsets wi) {
                android.graphics.Insets i = wi.getInsets(WindowInsets.Type.systemBars()
                        | WindowInsets.Type.displayCutout() | WindowInsets.Type.ime());
                v.setPadding(i.left, i.top, i.right, i.bottom);
                return WindowInsets.CONSUMED;
            }
        });
        radice.requestApplyInsets();
    }

    /** Il tasto Indietro. Con target 36 Android 16 non chiama più onBackPressed: si registra la richiamata. */
    static void indietro(Activity a, final Runnable cosa) {
        if (Build.VERSION.SDK_INT < 33) return;     // sotto Android 13 resta onBackPressed
        a.getOnBackInvokedDispatcher().registerOnBackInvokedCallback(
                android.window.OnBackInvokedDispatcher.PRIORITY_DEFAULT,
                new android.window.OnBackInvokedCallback() {
                    @Override public void onBackInvoked() { cosa.run(); }
                });
    }
}
