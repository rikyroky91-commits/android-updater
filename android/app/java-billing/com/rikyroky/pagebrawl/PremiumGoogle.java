package com.rikyroky.pagebrawl;

import android.app.Activity;
import android.content.Context;
import android.util.Log;

import com.android.billingclient.api.AcknowledgePurchaseParams;
import com.android.billingclient.api.BillingClient;
import com.android.billingclient.api.BillingClientStateListener;
import com.android.billingclient.api.BillingFlowParams;
import com.android.billingclient.api.BillingResult;
import com.android.billingclient.api.PendingPurchasesParams;
import com.android.billingclient.api.ProductDetails;
import com.android.billingclient.api.Purchase;
import com.android.billingclient.api.QueryProductDetailsParams;
import com.android.billingclient.api.QueryPurchasesParams;

import java.util.Collections;
import java.util.List;

/**
 * Il Premium vero, con Google Play Billing (libreria 9.1.0; dal 31/08/2026 il Play vuole la 8 o più).
 * Solo la build Gradle compila questa cartella; `Premium.di()` la carica per nome.
 *
 * Un prodotto solo, a acquisto unico, con ID `premium` (da creare nella Play Console: Monetizza →
 * Prodotti → Prodotti a pagamento singolo). Gli acquisti vanno confermati (acknowledge) entro 3 giorni,
 * altrimenti Google li rimborsa: si fa appena arrivano e a ogni avvio per quelli rimasti indietro.
 */
final class PremiumGoogle extends Premium {
    private static final String TAG = "PageBrawlPremium";
    private final BillingClient client;
    private ProductDetails dettagli;
    private boolean pronto;

    PremiumGoogle(Context c) {
        super(c);
        client = BillingClient.newBuilder(app)
                .setListener((risultato, acquisti) -> {
                    if (risultato.getResponseCode() == BillingClient.BillingResponseCode.OK && acquisti != null) {
                        for (Purchase p : acquisti) gestisci(p);
                    } else if (risultato.getResponseCode() == BillingClient.BillingResponseCode.ITEM_ALREADY_OWNED) {
                        ripristina();
                    }
                })
                .enablePendingPurchases(PendingPurchasesParams.newBuilder().enableOneTimeProducts().build())
                .enableAutoServiceReconnection()
                .build();
    }

    @Override boolean vero() { return true; }

    @Override void avvia() {
        client.startConnection(new BillingClientStateListener() {
            @Override public void onBillingSetupFinished(BillingResult r) {
                pronto = r.getResponseCode() == BillingClient.BillingResponseCode.OK;
                if (!pronto) { Log.w(TAG, "Google Play Billing non disponibile: " + r.getDebugMessage()); return; }
                ripristina();
                carica(null);
            }
            @Override public void onBillingServiceDisconnected() { pronto = false; }
        });
    }

    private void carica(final Prezzo dopo) {
        QueryProductDetailsParams q = QueryProductDetailsParams.newBuilder()
                .setProductList(Collections.singletonList(QueryProductDetailsParams.Product.newBuilder()
                        .setProductId(PRODOTTO).setProductType(BillingClient.ProductType.INAPP).build()))
                .build();
        client.queryProductDetailsAsync(q, (risultato, esito) -> {
            List<ProductDetails> lista = esito != null ? esito.getProductDetailsList() : null;
            if (lista != null && !lista.isEmpty()) dettagli = lista.get(0);
            if (dopo != null) {
                final String p = prezzoDi(dettagli);
                h.post(() -> dopo.pronto(p));
            }
        });
    }

    private static String prezzoDi(ProductDetails d) {
        if (d == null || d.getOneTimePurchaseOfferDetails() == null) return null;
        return d.getOneTimePurchaseOfferDetails().getFormattedPrice();
    }

    @Override void prezzo(Prezzo p) {
        if (dettagli != null) { p.pronto(prezzoDi(dettagli)); return; }
        if (pronto) carica(p); else p.pronto(null);
    }

    @Override void compra(Activity a) {
        if (dettagli == null) { Log.w(TAG, "prodotto non caricato: è stato creato nella Play Console?"); return; }
        BillingFlowParams.ProductDetailsParams pd = BillingFlowParams.ProductDetailsParams.newBuilder()
                .setProductDetails(dettagli).build();
        BillingResult r = client.launchBillingFlow(a, BillingFlowParams.newBuilder()
                .setProductDetailsParamsList(Collections.singletonList(pd)).build());
        if (r.getResponseCode() == BillingClient.BillingResponseCode.ITEM_ALREADY_OWNED) ripristina();
    }

    @Override void ripristina() {
        if (!pronto) return;
        client.queryPurchasesAsync(QueryPurchasesParams.newBuilder().setProductType(BillingClient.ProductType.INAPP).build(),
                (risultato, acquisti) -> {
                    if (risultato.getResponseCode() != BillingClient.BillingResponseCode.OK) return;
                    boolean trovato = false;
                    for (Purchase p : acquisti) {
                        if (p.getProducts().contains(PRODOTTO) && p.getPurchaseState() == Purchase.PurchaseState.PURCHASED) {
                            trovato = true;
                            gestisci(p);
                        }
                    }
                    // Nessun acquisto valido (mai fatto, o rimborsato): il Premium si richiude.
                    if (!trovato) imposta(false);
                });
    }

    private void gestisci(Purchase p) {
        if (!p.getProducts().contains(PRODOTTO)) return;
        if (p.getPurchaseState() != Purchase.PurchaseState.PURCHASED) return;   // in attesa (contanti, ecc.): si sblocca a pagamento fatto
        imposta(true);
        if (!p.isAcknowledged()) {
            client.acknowledgePurchase(AcknowledgePurchaseParams.newBuilder().setPurchaseToken(p.getPurchaseToken()).build(),
                    r -> { if (r.getResponseCode() != BillingClient.BillingResponseCode.OK) Log.w(TAG, "conferma non riuscita: " + r.getDebugMessage()); });
        }
    }
}
