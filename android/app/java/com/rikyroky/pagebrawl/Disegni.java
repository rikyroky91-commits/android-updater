package com.rikyroky.pagebrawl;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.ColorMatrix;
import android.graphics.ColorMatrixColorFilter;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.view.View;

/**
 * Le tre viste disegnate a mano dei comandi da telefono: le icone della
 * capsula, gli avatar con l'anello della vita, i tasti delle abilità.
 * Tutto vettoriale (niente PNG), bianco su vetro scuro.
 */
final class Disegni {
    private Disegni() {}

    static final int VETRO = 0x8C121614;        // fondo semitrasparente
    static final int FILO = 0x26FFFFFF;         // bordo sottile
    static final int BIANCO = 0xF2FFFFFF;

    // ------------------------------------------------------------- icone
    static final int PAUSA = 0, GIOCA = 1, ALTRO = 2, CHIUDI = 3, GUANTO = 4;

    static final class Icona extends View {
        private int tipo;
        private final Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Path path = new Path();
        private final float d;
        private final boolean tonda;

        Icona(Context c, int tipo, boolean tonda) {
            super(c);
            this.tipo = tipo;
            this.tonda = tonda;
            d = c.getResources().getDisplayMetrics().density;
        }

        void tipo(int t) { if (t != tipo) { tipo = t; invalidate(); } }

        @Override
        protected void onDraw(Canvas c) {
            float w = getWidth(), h = getHeight(), cx = w / 2, cy = h / 2, s = Math.min(w, h);
            if (tonda) {
                p.setStyle(Paint.Style.FILL); p.setColor(VETRO);
                c.drawCircle(cx, cy, s / 2 - d, p);
                p.setStyle(Paint.Style.STROKE); p.setStrokeWidth(d); p.setColor(FILO);
                c.drawCircle(cx, cy, s / 2 - d, p);
            }
            p.setColor(BIANCO);
            float u = s * 0.18f;                          // mezza misura del disegno
            switch (tipo) {
                case PAUSA:
                    p.setStyle(Paint.Style.FILL);
                    c.drawRoundRect(new RectF(cx - u, cy - u, cx - u * 0.3f, cy + u), d, d, p);
                    c.drawRoundRect(new RectF(cx + u * 0.3f, cy - u, cx + u, cy + u), d, d, p);
                    break;
                case GIOCA:
                    p.setStyle(Paint.Style.FILL);
                    path.reset();
                    path.moveTo(cx - u * 0.7f, cy - u * 1.05f);
                    path.lineTo(cx + u * 1.05f, cy);
                    path.lineTo(cx - u * 0.7f, cy + u * 1.05f);
                    path.close();
                    c.drawPath(path, p);
                    break;
                case ALTRO:
                    p.setStyle(Paint.Style.FILL);
                    for (int i = -1; i <= 1; i++) c.drawCircle(cx + i * u * 0.95f, cy, u * 0.24f, p);
                    break;
                case CHIUDI:
                    p.setStyle(Paint.Style.STROKE); p.setStrokeWidth(2 * d); p.setStrokeCap(Paint.Cap.ROUND);
                    c.drawLine(cx - u * 0.8f, cy - u * 0.8f, cx + u * 0.8f, cy + u * 0.8f, p);
                    c.drawLine(cx + u * 0.8f, cy - u * 0.8f, cx - u * 0.8f, cy + u * 0.8f, p);
                    break;
                case GUANTO:
                    p.setStyle(Paint.Style.FILL);
                    p.setColor(0xFFE53935);
                    c.drawCircle(cx - u * 0.15f, cy - u * 0.2f, u * 1.05f, p);
                    p.setColor(0xFFC62828);
                    c.drawCircle(cx + u * 0.75f, cy + u * 0.3f, u * 0.5f, p);
                    p.setColor(0xFFF4F1EA);
                    c.drawRoundRect(new RectF(cx - u * 0.75f, cy + u * 0.75f, cx + u * 0.45f, cy + u * 1.3f), d, d, p);
                    break;
            }
        }
    }

    // ------------------------------------------------------------ avatar
    /** Un lottatore: iniziale nel cerchio del suo colore, l'anello è la vita. */
    static final class Avatar extends View {
        private final Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final float d;
        private String lettera = "";
        private int colore = 0xFFFFFFFF;
        private float vita = 1, vitaVista = 1;
        private boolean ko, comandato;

        Avatar(Context c) {
            super(c);
            d = c.getResources().getDisplayMetrics().density;
            p.setTypeface(Typeface.create("sans-serif-medium", Typeface.BOLD));
            p.setTextAlign(Paint.Align.CENTER);
        }

        void imposta(String nome, int colore, float vita, boolean ko, boolean comandato) {
            String l = nome == null || nome.isEmpty() ? "?" : nome.substring(0, 1).toUpperCase();
            boolean cambia = !l.equals(lettera) || colore != this.colore || Math.abs(vita - this.vita) > 0.001f || ko != this.ko || comandato != this.comandato;
            lettera = l; this.colore = colore; this.vita = vita; this.ko = ko; this.comandato = comandato;
            setAlpha(ko ? 0.45f : 1f);
            if (cambia || Math.abs(vitaVista - vita) > 0.002f) invalidate();
        }

        @Override
        protected void onDraw(Canvas c) {
            vitaVista += (vita - vitaVista) * 0.35f;
            if (Math.abs(vitaVista - vita) > 0.002f) postInvalidateOnAnimation();
            float w = getWidth(), h = getHeight(), cx = w / 2, cy = h / 2;
            float r = Math.min(w, h) / 2 - 2.5f * d;
            // fondo
            p.setStyle(Paint.Style.FILL);
            p.setColor((colore & 0x00FFFFFF) | 0x40000000);
            c.drawCircle(cx, cy, r, p);
            // anello: traccia e vita
            p.setStyle(Paint.Style.STROKE);
            p.setStrokeWidth((comandato ? 3f : 2.2f) * d);
            p.setStrokeCap(Paint.Cap.ROUND);
            p.setColor(0x33FFFFFF);
            c.drawCircle(cx, cy, r, p);
            p.setColor(vitaVista < 0.34f ? 0xFFFF5A4E : colore);
            RectF o = new RectF(cx - r, cy - r, cx + r, cy + r);
            c.drawArc(o, -90, 360 * Math.max(0, Math.min(1, vitaVista)), false, p);
            // iniziale
            p.setStyle(Paint.Style.FILL);
            p.setColor(BIANCO);
            p.setTextSize(r * 0.95f);
            c.drawText(lettera, cx, cy + r * 0.34f, p);
            // chi si comanda: un puntino sotto
            if (comandato) {
                p.setColor(colore);
                c.drawCircle(cx, h - 1.2f * d, 1.6f * d, p);
            }
        }
    }

    // ------------------------------------------------------------- tasto
    /**
     * Un'abilità: l'icona è in bianco e nero finché è scarica e prende colore
     * man mano che si ricarica; l'anello mostra la carica, e quando è pronta
     * diventa del colore del lottatore e il tasto fa un piccolo balzo.
     */
    static final class Tasto extends View {
        private final Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint testo = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final ColorMatrix cm = new ColorMatrix();
        private final float d;
        private String icona = "";
        private float carica = 0;            // 0..1
        private boolean pronta, usabile = true;
        private int colore = 0xFFFFFFFF;
        private long balzo, entra;

        Tasto(Context c) {
            super(c);
            d = c.getResources().getDisplayMetrics().density;
            testo.setTextAlign(Paint.Align.CENTER);
        }

        /** Dice se si è appena ricaricata (per la vibrazione). */
        boolean imposta(String icona, float carica, boolean usabile, int colore) {
            boolean nuova = !icona.equals(this.icona);
            boolean ora = usabile && carica >= 1f, appena = false;
            if (nuova) entra = System.currentTimeMillis();
            else if (ora && !pronta) { balzo = System.currentTimeMillis(); appena = true; }
            this.icona = icona; this.carica = carica; this.usabile = usabile; this.pronta = ora; this.colore = colore;
            invalidate();
            return appena;
        }

        boolean pronta() { return pronta; }
        String icona() { return icona; }

        void rifiuta() { setTranslationX(0); animate().translationX(4 * d).setDuration(40).withEndAction(new Runnable() {
            @Override public void run() { animate().translationX(-4 * d).setDuration(60).withEndAction(new Runnable() {
                @Override public void run() { animate().translationX(0).setDuration(40); } }); } }); }

        @Override
        public void setPressed(boolean pressed) {
            super.setPressed(pressed);
            animate().scaleX(pressed ? 0.9f : 1f).scaleY(pressed ? 0.9f : 1f).setDuration(80);
        }

        @Override
        protected void onDraw(Canvas c) {
            long ora = System.currentTimeMillis();
            float w = getWidth(), h = getHeight(), cx = w / 2, cy = h / 2;
            float r = Math.min(w, h) / 2 - 3 * d;
            float scala = 1;
            if (ora - balzo < 260) { scala = 1 + 0.12f * (float) Math.sin(Math.PI * (ora - balzo) / 260.0); postInvalidateOnAnimation(); }
            float comparsa = Math.min(1, (ora - entra) / 180f);
            if (comparsa < 1) postInvalidateOnAnimation();
            c.save();
            c.scale(scala * (0.7f + 0.3f * comparsa), scala * (0.7f + 0.3f * comparsa), cx, cy);
            // vetro
            p.setStyle(Paint.Style.FILL);
            p.setColor(pronta ? 0xA6121614 : 0x73121614);
            c.drawCircle(cx, cy, r, p);
            // anello: traccia, carica, pronto
            p.setStyle(Paint.Style.STROKE);
            p.setStrokeCap(Paint.Cap.ROUND);
            p.setStrokeWidth(2.5f * d);
            p.setColor(0x2EFFFFFF);
            c.drawCircle(cx, cy, r, p);
            if (pronta) {
                p.setColor(colore);
                c.drawCircle(cx, cy, r, p);
            } else if (carica > 0) {
                p.setColor(0xCCFFFFFF);
                c.drawArc(new RectF(cx - r, cy - r, cx + r, cy + r), -90, 360 * carica, false, p);
            }
            // icona: dal bianco e nero al colore, man mano che si carica
            float sat = usabile ? carica : Math.min(carica, 0.15f);
            cm.setSaturation(sat * sat);
            testo.setColorFilter(new ColorMatrixColorFilter(cm));
            testo.setAlpha((int) (255 * (pronta ? 1f : 0.45f + 0.4f * carica) * comparsa));
            testo.setTextSize(r * 0.95f);
            Paint.FontMetrics fm = testo.getFontMetrics();
            c.drawText(icona, cx, cy - (fm.ascent + fm.descent) / 2, testo);
            c.restore();
        }
    }
}
