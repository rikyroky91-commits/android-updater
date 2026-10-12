package com.rikyroky.pagebrawl;

import android.app.PendingIntent;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.service.quicksettings.Tile;
import android.service.quicksettings.TileService;

/**
 * Il riquadro nelle impostazioni rapide: abbassi la tendina, tocchi, e il
 * ring parte sullo schermo che avevi sotto (anche sul blocco schermo).
 */
public class Riquadro extends TileService {

    static void aggiorna(Context c) {
        try {
            TileService.requestListeningState(c, new ComponentName(c, Riquadro.class));
        } catch (Exception ignorata) { /* riquadro non aggiunto */ }
    }

    @Override
    public void onStartListening() {
        Tile t = getQsTile();
        if (t == null) return;
        boolean pronto = Ring.istanza != null;
        // Sempre toccabile: da spento apre l'app che spiega come accenderlo.
        t.setState(Tile.STATE_INACTIVE);
        t.setLabel("Page Brawl");
        if (Build.VERSION.SDK_INT >= 29) t.setSubtitle(pronto ? "Ring qui" : "Da attivare");
        t.updateTile();
    }

    @Override
    @SuppressWarnings("deprecation")
    public void onClick() {
        Ring r = Ring.istanza;
        if (r != null) {
            r.avviaDaRiquadro();
            return;
        }
        // Servizio spento: si apre l'app, che spiega come accenderlo.
        Intent i = new Intent(this, Principale.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        if (Build.VERSION.SDK_INT >= 34) {
            startActivityAndCollapse(PendingIntent.getActivity(this, 0, i, PendingIntent.FLAG_IMMUTABLE));
        } else {
            startActivityAndCollapse(i);
        }
    }
}
