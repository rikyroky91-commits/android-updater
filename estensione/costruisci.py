#!/usr/bin/env python3
"""Costruisce l'estensione del browser a partire dai file del sito.

Il ring ha UNA sola sorgente: `web/static/ring.js`, la tendina di
`web/templates/home.html` e il suo stile in `web/static/style.css`. Questo
script li copia in `estensione/pacchetto/` aggiungendo quello che serve a un
browser: il manifest, il service worker che parte al clic sull'icona, e
`prepara.js`, che crea canvas e tendina dentro uno shadow DOM (così lo stile
dei siti non li tocca) prima di far partire il ring.

Si costruiscono DUE varianti:
  - `pacchetto/`  da caricare a mano per provare: nella tendina c'è un
    interruttore «Premium di prova» per vedere il gioco bloccato e sbloccato;
  - `store/`      da pubblicare. Con `sblocco_gratis: true` in `premium.json`
    (05/10/2026: si esce così, in attesa dei pareri di chi la usa) ha lo
    stesso interruttore della prova, col nome «Sblocca Premium gratis»: un clic
    e si apre tutto. Con `sblocco_gratis: false` l'interruttore non c'è e
    Premium si compra dall'indirizzo `url_acquisto`; finché è vuoto il tasto
    dice «Premium arriva presto».

Uso:
    python3 estensione/costruisci.py            # rigenera pacchetto/ e store/
    python3 estensione/costruisci.py --verifica # esce con 1 se sono vecchi
    python3 estensione/costruisci.py --zip      # rigenera e prepara i due zip in estensione/zip/

Il test `tests/test_estensione.py` usa `--verifica`: chi cambia il ring e
dimentica di rigenerare l'estensione se ne accorge subito.
"""
import json
import re
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
QUI = Path(__file__).resolve().parent
VARIANTI = {"pacchetto": {"premium_di_prova": True}, "store": {"premium_di_prova": False}}
VERSIONE = "0.7.0"
NOME = "Page Brawl"

MANIFEST = {
    "manifest_version": 3,
    "name": "__MSG_nome__",
    "version": VERSIONE,
    "description": "__MSG_descrizione__",
    "default_locale": "en",
    "action": {"default_title": "__MSG_titolo__"},
    "background": {"service_worker": "sfondo.js"},
    # Il permesso minimo: solo la scheda su cui si clicca l'icona.
    "permissions": ["activeTab", "scripting", "storage"],
    # Facoltativo, chiesto solo a chi accende «tasto su tutti i siti» nelle opzioni.
    "optional_host_permissions": ["<all_urls>"],
    "options_ui": {"page": "opzioni.html", "open_in_tab": False},
    "icons": {"16": "icone/16.png", "48": "icone/48.png", "128": "icone/128.png"},
}

# Nome, descrizione breve (al massimo 132 caratteri: è il limite dello store),
# titolo del tasto e i testi della pagina delle opzioni, nelle lingue dell'estensione.
MESSAGGI = {
    "en": {
        "descrizione": "A robot and an apple brawl on the page you are viewing. Grab them, throw them, bet on the winner.",
        "titolo": "Start or stop the brawl on this page",
        "opzioniTitolo": "Page Brawl options",
        "sempreEtichetta": "Show the power button on every site",
        "sempreSpiega": "A small button stays in the bottom right corner of every page: one click starts the brawl, without going through the toolbar icon. To put it there, the browser will ask you to let Page Brawl run on all sites. Nothing is read from the pages and nothing is sent anywhere.",
        "sempreNegato": "Permission not granted: the button stays off.",
    },
    "it": {
        "descrizione": "Un robot e una mela si picchiano sulla pagina che stai guardando. Prendili, lanciali, scommetti su chi vince.",
        "titolo": "Accendi o spegni la lotta su questa pagina",
        "opzioniTitolo": "Opzioni di Page Brawl",
        "sempreEtichetta": "Mostra il tasto di accensione su tutti i siti",
        "sempreSpiega": "Un tastino resta nell'angolo in basso a destra di ogni pagina: un clic e la lotta parte, senza passare dall'icona nella barra. Per metterlo lì il browser ti chiede di lasciar funzionare Page Brawl su tutti i siti. Dalle pagine non viene letto niente e non viene inviato niente.",
        "sempreNegato": "Permesso non concesso: il tasto resta spento.",
    },
    "es": {
        "descrizione": "Un robot y una manzana se pelean en la página que estás viendo. Agárralos, lánzalos y apuesta por el ganador.",
        "titolo": "Enciende o apaga la pelea en esta página",
        "opzioniTitolo": "Opciones de Page Brawl",
        "sempreEtichetta": "Mostrar el botón de encendido en todos los sitios",
        "sempreSpiega": "Un botoncito se queda en la esquina inferior derecha de cada página: un clic y empieza la pelea, sin pasar por el icono de la barra. Para ponerlo ahí, el navegador te pedirá que dejes funcionar Page Brawl en todos los sitios. No se lee nada de las páginas y no se envía nada.",
        "sempreNegato": "Permiso no concedido: el botón sigue apagado.",
    },
    "fr": {
        "descrizione": "Un robot et une pomme se battent sur la page que vous regardez. Attrapez-les, lancez-les, pariez sur le vainqueur.",
        "titolo": "Lancer ou arrêter le combat sur cette page",
        "opzioniTitolo": "Options de Page Brawl",
        "sempreEtichetta": "Afficher le bouton de mise en marche sur tous les sites",
        "sempreSpiega": "Un petit bouton reste dans le coin inférieur droit de chaque page : un clic et le combat commence, sans passer par l'icône de la barre. Pour l'y placer, le navigateur vous demandera de laisser Page Brawl fonctionner sur tous les sites. Rien n'est lu dans les pages et rien n'est envoyé.",
        "sempreNegato": "Autorisation refusée : le bouton reste désactivé.",
    },
    "de": {
        "descrizione": "Ein Roboter und ein Apfel prügeln sich auf der Seite, die du gerade ansiehst. Pack sie, wirf sie, wette auf den Sieger.",
        "titolo": "Kampf auf dieser Seite starten oder stoppen",
        "opzioniTitolo": "Optionen von Page Brawl",
        "sempreEtichetta": "Einschaltknopf auf allen Websites anzeigen",
        "sempreSpiega": "Ein kleiner Knopf bleibt unten rechts auf jeder Seite: ein Klick und der Kampf beginnt, ohne das Symbol in der Leiste. Dafür fragt der Browser, ob Page Brawl auf allen Websites laufen darf. Aus den Seiten wird nichts gelesen und nichts wird gesendet.",
        "sempreNegato": "Berechtigung nicht erteilt: Der Knopf bleibt aus.",
    },
}

# ---------------------------------------------------------------------------
# LA GUIDA PER CHI HA APPENA INSTALLATO (02/10/2026, su richiesta).
# Una pagina dell'estensione (`benvenuto.html`) che si apre da sola alla prima
# installazione e si riapre dalla tendina («Come funziona») e dalle opzioni.
# I testi stanno nei messaggi dell'estensione, come quelli delle opzioni.
# ---------------------------------------------------------------------------
GUIDA = {
    "en": {
        "guidaLink": "How it works",
        "guidaTitolo": "How Page Brawl works",
        "guidaIntro": "Two fighters brawl on top of the page you are viewing. The page underneath stays as it is: nothing is read and nothing is sent anywhere.",
        "guidaP1T": "Open any page",
        "guidaP1": "A news site, a shop, anything you like. It cannot start on the browser's internal pages, on the Chrome Web Store or in PDFs.",
        "guidaP2T": "Click the Page Brawl icon",
        "guidaP2": "It sits in the browser toolbar, inside the extensions menu (the puzzle piece): pin it to keep it at hand. One click and the fighters walk in.",
        "guidaP3T": "Turn it off and on with the button in the bottom right",
        "guidaP3": "The power button is always visible: it stops the brawl and starts it again without reloading the page.",
        "guidaP4T": "Grab them with the mouse",
        "guidaP4": "Drag a fighter and let go to throw them. The same goes for the things that fall from above: smoke bombs, jars and weapons.",
        "guidaP5T": "Open the panel with the glove button",
        "guidaP5": "There you pick the characters, drop items into the ring, trigger an earthquake or jetpacks, turn on the health bars and bet your tokens on the winner.",
        "guidaSapereT": "Good to know",
        "guidaS1": "First to ten: whoever reaches ten K.O.s sends the opponent flying out of the ring, then the score starts again from zero.",
        "guidaS2": "A thrown jar releases a creature of fire, lightning or water that fights for whoever threw it. A smoke bomb blinds anyone caught in the cloud.",
        "guidaS3": "The fighters learn: the more they fight, the better they get. What they learn and your tokens stay in your browser.",
        "guidaS4": "Gore effects are off: if you want them, turn them on from the panel.",
        "guidaS5": "Super warriors, wizards, duelists, weapons, weather and gravity are part of Premium: in the panel they carry a padlock.",
        "guidaS6": "Want the power button on every site, without going through the icon? Turn it on in the options.",
        "guidaP6T": "Take control with the gamepad button",
        "guidaP6": "A quarter wheel opens in the bottom right corner. The portrait in the corner is the fighter you command: click a slice and they do that move, click the portrait to switch to the other one.",
        "guidaS7": "Now and then something happens: a storm, an earthquake with an eruption, meteorites, a black hole that swallows whatever is nearby and spits it out on the other side of the screen. After a couple of minutes zombies show up: the two stop fighting each other, stand back to back and team up (leapfrog over the partner, side swap, double strike, cannonball). The horde comes in waves, never the same twice, and the pair has three lives (the hearts at the top).",
        "guidaS9": "About one round in three ends with a finishing move: the scene goes dark and the winner sends the other into orbit, bounces them between the edges of the window or flattens them like a pancake. Each character set has its own. You can also call one from the panel.",
        "guidaS10": "Powering up changes the body: the super warriors bulk up with a blazing crest and a jacket torn to shreds, the robot becomes a steel colossus, the apple a towering tree, the duelists hooded knights with a double blade. In the free ring it happens on its own when one of them is one hit from a K.O.",
        "guidaS8": "When two energy attacks collide, two buttons pop up at the ends of the bar: hammer the one on your fighter's side and the clash goes their way.",
        "guidaS5gratis": "Super warriors, wizards, duelists, weapons, weather, meteorites, the black hole, the zombie horde and gravity are part of Premium. For now it is free: open the panel and press “Unlock Premium for free”.",
        "guidaOpzioni": "Open the options",
        "guidaPiede": "You can reopen this page any time from “How it works”, at the bottom of the panel.",
    },
    "it": {
        "guidaLink": "Come funziona",
        "guidaTitolo": "Come funziona Page Brawl",
        "guidaIntro": "Due lottatori si picchiano sopra la pagina che stai guardando. La pagina sotto resta com'è: non viene letto né inviato niente.",
        "guidaP1T": "Apri una pagina qualsiasi",
        "guidaP1": "Un sito di notizie, un negozio, quello che vuoi. Non può partire sulle pagine interne del browser, sul Chrome Web Store e nei PDF.",
        "guidaP2T": "Clicca l'icona di Page Brawl",
        "guidaP2": "È nella barra del browser, dentro il menu delle estensioni (il pezzo di puzzle): fissala con la puntina per averla sempre a portata. Un clic e i lottatori entrano.",
        "guidaP3T": "Spegni e riaccendi dal tasto in basso a destra",
        "guidaP3": "Il tasto di accensione resta sempre visibile: ferma la lotta e la fa ripartire senza ricaricare la pagina.",
        "guidaP4T": "Prendili col mouse",
        "guidaP4": "Trascina un lottatore e lascialo per lanciarlo. Vale anche per gli oggetti che cadono dall'alto: fumogeni, barattoli e armi.",
        "guidaP5T": "Apri la tendina col guantone",
        "guidaP5": "Lì scegli i personaggi, metti in campo gli oggetti, scateni terremoto e jetpack, accendi le barre della vita e scommetti i gettoni su chi vince.",
        "guidaSapereT": "Cose da sapere",
        "guidaS1": "Si gioca a dieci: chi arriva a dieci K.O. manda l'avversario fuori dal ring, poi si riparte da zero.",
        "guidaS2": "Un barattolo lanciato libera una creatura di fuoco, di fulmini o d'acqua che combatte per chi l'ha lanciato. Un fumogeno acceca chi finisce nella nube.",
        "guidaS3": "I lottatori imparano: più lottano, più diventano bravi. Quello che imparano e i tuoi gettoni restano nel tuo browser.",
        "guidaS4": "Gli effetti cruenti sono spenti: se li vuoi, si accendono dalla tendina.",
        "guidaS5": "Super guerrieri, maghi, duellanti, armi, meteo e gravità fanno parte di Premium: nella tendina hanno il lucchetto.",
        "guidaS6": "Vuoi il tasto di accensione su ogni sito, senza passare dall'icona? Si accende dalle opzioni.",
        "guidaP6T": "Prendi il comando col tasto del joypad",
        "guidaP6": "Nell'angolo in basso a destra si apre un quarto di ruota. Il ritratto nell'angolo è il lottatore che comandi: clicca uno spicchio e fa quella mossa, clicca il ritratto per passare all'altro.",
        "guidaS7": "Ogni tanto succede qualcosa: un temporale, un terremoto con l'eruzione, i meteoriti, un buco nero che risucchia quello che ha intorno e lo risputa dall'altra parte dello schermo. Dopo un paio di minuti arrivano gli zombie: i due smettono di picchiarsi, si mettono spalle a spalla e si danno una mano (cavallina sopra il compagno, cambio di lato, colpo insieme, palla di cannone). L'orda arriva a ondate, mai due volte uguali, e i due hanno tre vite (i cuori in alto).",
        "guidaS9": "Circa un round su tre si chiude con un colpo finale: la scena si fa buia e chi vince manda l'altro in orbita, lo fa rimbalzare fra i bordi della finestra o lo schiaccia come una frittella. Ogni coppia di personaggi ha il suo. Lo puoi anche chiamare dalla tendina.",
        "guidaS10": "Chi si potenzia cambia corpo: i super guerrieri si gonfiano, con la cresta accesa e la casacca a brandelli, il robot diventa un colosso d'acciaio, la mela un albero enorme, i duellanti cavalieri incappucciati con la lama doppia. Nel ring libero succede da solo quando a uno manca un colpo al K.O.",
        "guidaS8": "Quando due colpi d'energia si scontrano spuntano due tasti ai capi della barra: martella quello dalla parte del tuo lottatore e lo scontro va a lui.",
        "guidaS5gratis": "Super guerrieri, maghi, duellanti, armi, meteo, meteoriti, buco nero, orda di zombie e gravità fanno parte di Premium. Per ora è gratis: apri la tendina e premi «Sblocca Premium gratis».",
        "guidaOpzioni": "Apri le opzioni",
        "guidaPiede": "Questa pagina si riapre quando vuoi da «Come funziona», in fondo alla tendina.",
    },
    "es": {
        "guidaLink": "Cómo funciona",
        "guidaTitolo": "Cómo funciona Page Brawl",
        "guidaIntro": "Dos luchadores se pelean encima de la página que estás viendo. La página de debajo se queda como está: no se lee ni se envía nada.",
        "guidaP1T": "Abre cualquier página",
        "guidaP1": "Un sitio de noticias, una tienda, lo que quieras. No puede arrancar en las páginas internas del navegador, en Chrome Web Store ni en los PDF.",
        "guidaP2T": "Haz clic en el icono de Page Brawl",
        "guidaP2": "Está en la barra del navegador, dentro del menú de extensiones (la pieza de puzle): fíjalo con la chincheta para tenerlo a mano. Un clic y entran los luchadores.",
        "guidaP3T": "Apaga y enciende con el botón de abajo a la derecha",
        "guidaP3": "El botón de encendido siempre está a la vista: detiene la pelea y la reanuda sin recargar la página.",
        "guidaP4T": "Agárralos con el ratón",
        "guidaP4": "Arrastra a un luchador y suéltalo para lanzarlo. Lo mismo vale para los objetos que caen de arriba: bombas de humo, tarros y armas.",
        "guidaP5T": "Abre el panel con el botón del guante",
        "guidaP5": "Ahí eliges los personajes, pones objetos en el ring, desatas un terremoto o los jetpacks, enciendes las barras de vida y apuestas tus fichas por el ganador.",
        "guidaSapereT": "Cosas que conviene saber",
        "guidaS1": "Se juega a diez: quien llega a diez K.O. manda al rival fuera del ring y luego se vuelve a empezar de cero.",
        "guidaS2": "Un tarro lanzado libera una criatura de fuego, de rayos o de agua que lucha por quien lo lanzó. Una bomba de humo ciega a quien queda dentro de la nube.",
        "guidaS3": "Los luchadores aprenden: cuanto más pelean, mejores son. Lo que aprenden y tus fichas se quedan en tu navegador.",
        "guidaS4": "Los efectos sangrientos están apagados: si los quieres, se encienden desde el panel.",
        "guidaS5": "Los superguerreros, los magos, los duelistas, las armas, el clima y la gravedad forman parte de Premium: en el panel llevan un candado.",
        "guidaS6": "¿Quieres el botón de encendido en todos los sitios, sin pasar por el icono? Se activa en las opciones.",
        "guidaP6T": "Toma el mando con el botón del gamepad",
        "guidaP6": "En la esquina inferior derecha se abre un cuarto de rueda. El retrato de la esquina es el luchador que controlas: haz clic en un sector y hará ese movimiento, haz clic en el retrato para pasar al otro.",
        "guidaS7": "De vez en cuando pasa algo: una tormenta, un terremoto con erupción, meteoritos, un agujero negro que se traga lo que tiene cerca y lo escupe al otro lado de la pantalla. Al cabo de un par de minutos llegan los zombis: los dos dejan de pelearse, se ponen espalda con espalda y se ayudan (salto sobre el compañero, cambio de lado, golpe conjunto, bala de cañón). La horda llega en oleadas, nunca dos veces igual, y la pareja tiene tres vidas (los corazones de arriba).",
        "guidaS9": "Más o menos una ronda de cada tres acaba con un golpe final: la escena se oscurece y el que gana manda al otro a la órbita, lo hace rebotar entre los bordes de la ventana o lo aplasta como una tortita. Cada pareja de personajes tiene el suyo. También puedes pedirlo desde el panel.",
        "guidaS10": "Al potenciarse cambia el cuerpo: los superguerreros se hinchan, con la cresta encendida y la chaqueta hecha jirones, el robot se vuelve un coloso de acero, la manzana un árbol enorme, los duelistas caballeros encapuchados con hoja doble. En el ring libre pasa solo cuando a uno le falta un golpe para el K.O.",
        "guidaS8": "Cuando dos ataques de energía chocan aparecen dos botones en los extremos de la barra: machaca el del lado de tu luchador y el choque se inclina a su favor.",
        "guidaS5gratis": "Los superguerreros, los magos, los duelistas, las armas, el clima, los meteoritos, el agujero negro, la horda de zombis y la gravedad forman parte de Premium. Por ahora es gratis: abre el panel y pulsa «Desbloquear Premium gratis».",
        "guidaOpzioni": "Abrir las opciones",
        "guidaPiede": "Puedes volver a abrir esta página cuando quieras desde «Cómo funciona», al final del panel.",
    },
    "fr": {
        "guidaLink": "Comment ça marche",
        "guidaTitolo": "Comment fonctionne Page Brawl",
        "guidaIntro": "Deux combattants se battent par-dessus la page que vous regardez. La page en dessous reste telle quelle : rien n'est lu, rien n'est envoyé.",
        "guidaP1T": "Ouvrez n'importe quelle page",
        "guidaP1": "Un site d'actualités, une boutique, ce que vous voulez. Il ne peut pas démarrer sur les pages internes du navigateur, sur le Chrome Web Store ni dans les PDF.",
        "guidaP2T": "Cliquez sur l'icône de Page Brawl",
        "guidaP2": "Elle se trouve dans la barre du navigateur, dans le menu des extensions (la pièce de puzzle) : épinglez-la pour l'avoir sous la main. Un clic et les combattants arrivent.",
        "guidaP3T": "Arrêtez et relancez avec le bouton en bas à droite",
        "guidaP3": "Le bouton de mise en marche reste toujours visible : il arrête le combat et le relance sans recharger la page.",
        "guidaP4T": "Attrapez-les à la souris",
        "guidaP4": "Faites glisser un combattant et lâchez-le pour le lancer. Pareil pour les objets qui tombent d'en haut : fumigènes, bocaux et armes.",
        "guidaP5T": "Ouvrez le panneau avec le bouton au gant",
        "guidaP5": "Vous y choisissez les personnages, déposez des objets sur le ring, déclenchez un séisme ou les jetpacks, affichez les barres de vie et pariez vos jetons sur le vainqueur.",
        "guidaSapereT": "Bon à savoir",
        "guidaS1": "La partie se joue en dix : celui qui atteint dix K.-O. envoie l'adversaire hors du ring, puis on repart de zéro.",
        "guidaS2": "Un bocal lancé libère une créature de feu, de foudre ou d'eau qui se bat pour celui qui l'a lancé. Un fumigène aveugle quiconque se trouve dans le nuage.",
        "guidaS3": "Les combattants apprennent : plus ils se battent, meilleurs ils deviennent. Ce qu'ils apprennent et vos jetons restent dans votre navigateur.",
        "guidaS4": "Les effets sanglants sont désactivés : si vous les voulez, activez-les depuis le panneau.",
        "guidaS5": "Super guerriers, mages, duellistes, armes, météo et gravité font partie de Premium : dans le panneau, ils portent un cadenas.",
        "guidaS6": "Vous voulez le bouton de mise en marche sur tous les sites, sans passer par l'icône ? Activez-le dans les options.",
        "guidaP6T": "Prenez les commandes avec le bouton manette",
        "guidaP6": "Un quart de roue s'ouvre dans le coin inférieur droit. Le portrait dans le coin est le combattant que vous commandez : cliquez sur une tranche et il fait ce coup, cliquez sur le portrait pour passer à l'autre.",
        "guidaS7": "De temps en temps il se passe quelque chose : un orage, un séisme avec une éruption, des météorites, un trou noir qui avale ce qui l'entoure et le recrache de l'autre côté de l'écran. Au bout de deux minutes environ, les zombies arrivent : les deux cessent de se battre, se mettent dos à dos et s'entraident (saute-mouton par-dessus le partenaire, changement de côté, coup à deux, boulet de canon). La horde arrive par vagues, jamais deux fois la même, et le duo a trois vies (les cœurs en haut).",
        "guidaS9": "Environ une manche sur trois se termine par un coup final : la scène s'assombrit et le vainqueur envoie l'autre en orbite, le fait rebondir entre les bords de la fenêtre ou l'aplatit comme une crêpe. Chaque duo de personnages a le sien. Vous pouvez aussi le déclencher depuis le panneau.",
        "guidaS10": "Celui qui se renforce change de corps : les super guerriers gonflent, avec une crête enflammée et une veste en lambeaux, le robot devient un colosse d'acier, la pomme un arbre immense, les duellistes des chevaliers encapuchonnés à la lame double. Dans le ring libre, cela arrive tout seul quand il ne reste qu'un coup avant le K.O.",
        "guidaS8": "Quand deux attaques d'énergie se rencontrent, deux boutons apparaissent aux extrémités de la barre : martelez celui du côté de votre combattant et le choc tourne en sa faveur.",
        "guidaS5gratis": "Super guerriers, mages, duellistes, armes, météo, météorites, trou noir, horde de zombies et gravité font partie de Premium. Pour l'instant c'est gratuit : ouvrez le panneau et appuyez sur « Débloquer Premium gratuitement ».",
        "guidaOpzioni": "Ouvrir les options",
        "guidaPiede": "Vous pouvez rouvrir cette page à tout moment depuis « Comment ça marche », en bas du panneau.",
    },
    "de": {
        "guidaLink": "So funktioniert es",
        "guidaTitolo": "So funktioniert Page Brawl",
        "guidaIntro": "Zwei Kämpfer prügeln sich über der Seite, die du gerade ansiehst. Die Seite darunter bleibt, wie sie ist: Es wird nichts gelesen und nichts gesendet.",
        "guidaP1T": "Öffne irgendeine Seite",
        "guidaP1": "Eine Nachrichtenseite, ein Shop, was du willst. Auf den internen Seiten des Browsers, im Chrome Web Store und in PDFs kann es nicht starten.",
        "guidaP2T": "Klicke auf das Page-Brawl-Symbol",
        "guidaP2": "Es sitzt in der Symbolleiste des Browsers, im Erweiterungsmenü (das Puzzleteil): Hefte es an, damit es immer griffbereit ist. Ein Klick und die Kämpfer kommen herein.",
        "guidaP3T": "Aus- und einschalten mit dem Knopf unten rechts",
        "guidaP3": "Der Einschaltknopf bleibt immer sichtbar: Er stoppt den Kampf und startet ihn wieder, ohne die Seite neu zu laden.",
        "guidaP4T": "Pack sie mit der Maus",
        "guidaP4": "Zieh einen Kämpfer und lass los, um ihn zu werfen. Das gilt auch für alles, was von oben fällt: Rauchbomben, Gläser und Waffen.",
        "guidaP5T": "Öffne das Menü mit dem Handschuh-Knopf",
        "guidaP5": "Dort wählst du die Figuren, wirfst Gegenstände in den Ring, löst ein Erdbeben oder Jetpacks aus, schaltest die Lebensbalken ein und setzt deine Jetons auf den Sieger.",
        "guidaSapereT": "Gut zu wissen",
        "guidaS1": "Gespielt wird bis zehn: Wer zehn K.o. erreicht, schleudert den Gegner aus dem Ring, dann geht es wieder bei null los.",
        "guidaS2": "Ein geworfenes Glas befreit ein Wesen aus Feuer, Blitz oder Wasser, das für den Werfer kämpft. Eine Rauchbombe blendet jeden, der in der Wolke steht.",
        "guidaS3": "Die Kämpfer lernen dazu: Je mehr sie kämpfen, desto besser werden sie. Was sie lernen und deine Jetons bleiben in deinem Browser.",
        "guidaS4": "Blutige Effekte sind aus: Wenn du sie willst, schaltest du sie im Menü ein.",
        "guidaS5": "Superkrieger, Magier, Duellanten, Waffen, Wetter und Schwerkraft gehören zu Premium: Im Menü tragen sie ein Schloss.",
        "guidaS6": "Du willst den Einschaltknopf auf jeder Website, ohne über das Symbol zu gehen? Schalte ihn in den Optionen ein.",
        "guidaP6T": "Übernimm die Steuerung mit der Gamepad-Taste",
        "guidaP6": "Unten rechts in der Ecke öffnet sich ein Viertelrad. Das Porträt in der Ecke ist der Kämpfer, den du steuerst: Klicke auf ein Segment und er führt diesen Angriff aus, klicke auf das Porträt, um zum anderen zu wechseln.",
        "guidaS7": "Ab und zu passiert etwas: ein Gewitter, ein Erdbeben mit Ausbruch, Meteoriten, ein Schwarzes Loch, das alles in der Nähe einsaugt und auf der anderen Seite des Bildschirms wieder ausspuckt. Nach ein paar Minuten tauchen Zombies auf: Die beiden hören auf zu kämpfen, stellen sich Rücken an Rücken und helfen einander (Bocksprung über den Partner, Seitenwechsel, Doppelschlag, Kanonenkugel). Die Horde kommt in Wellen, nie zweimal gleich, und das Duo hat drei Leben (die Herzen oben).",
        "guidaS9": "Etwa jede dritte Runde endet mit einem Finalschlag: Die Szene wird dunkel und der Sieger schießt den anderen in die Umlaufbahn, lässt ihn zwischen den Fensterrändern abprallen oder drückt ihn platt wie einen Pfannkuchen. Jedes Figurenpaar hat seinen eigenen. Du kannst ihn auch aus dem Menü auslösen.",
        "guidaS10": "Wer sich auflädt, bekommt einen neuen Körper: Die Superkrieger legen an Masse zu, mit leuchtendem Kamm und zerfetzter Jacke, der Roboter wird zum Stahlkoloss, der Apfel zu einem riesigen Baum, die Duellanten zu Kapuzenrittern mit doppelter Klinge. Im freien Ring passiert es von selbst, wenn einem noch ein Treffer bis zum K.o. fehlt.",
        "guidaS8": "Wenn zwei Energieangriffe aufeinanderprallen, erscheinen zwei Tasten an den Enden des Balkens: Hämmere auf die Taste deines Kämpfers, dann kippt das Duell zu seinen Gunsten.",
        "guidaS5gratis": "Superkrieger, Magier, Duellanten, Waffen, Wetter, Meteoriten, das Schwarze Loch, die Zombiehorde und Schwerkraft gehören zu Premium. Im Moment ist es gratis: Öffne das Menü und drücke „Premium gratis freischalten“.",
        "guidaOpzioni": "Optionen öffnen",
        "guidaPiede": "Diese Seite öffnest du jederzeit wieder über „So funktioniert es“ unten im Menü.",
    },
}
for _lingua, _testi in GUIDA.items():
    MESSAGGI[_lingua].update(_testi)


def pagina_guida(nome: str, passi: int, sapere: list) -> str:
    """La pagina di benvenuto: `passi` passi numerati e le cose da sapere (`sapere`: le chiavi dei messaggi)."""
    righe = "\n".join(f'<li><h2 data-msg="guidaP{i}T"></h2><p data-msg="guidaP{i}"></p></li>' for i in range(1, passi + 1))
    note = "\n".join(f'<li data-msg="{chiave}"></li>' for chiave in sapere)
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{nome}</title>
<link rel="stylesheet" href="benvenuto.css">
</head>
<body>
<main>
<header><img src="icone/128.png" width="64" height="64" alt=""><div><h1 data-msg="guidaTitolo"></h1><p data-msg="guidaIntro"></p></div></header>
<ol>
{righe}
</ol>
<h2 class="sapere" data-msg="guidaSapereT"></h2>
<ul>
{note}
</ul>
<p><button type="button" id="opzioni" data-msg="guidaOpzioni"></button></p>
<p class="piede" data-msg="guidaPiede"></p>
</main>
<script src="benvenuto.js"></script>
</body>
</html>
"""


GUIDA_CSS = """:root { --carta: #ffffff; --fondo: #f4f1ea; --ink: #201e1d; --tenue: #5a5652; --filo: #dcd7cd; --tinta: #1f7a5a; --su-tinta: #ffffff; }
@media (prefers-color-scheme: dark) { :root { --carta: #1c1b1a; --fondo: #121110; --ink: #ebe9e6; --tenue: #b3aea7; --filo: #3a3835; --tinta: #46c291; --su-tinta: #10201a; } }
* { box-sizing: border-box; }
body { margin: 0; background: var(--fondo); color: var(--ink); font: 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
main { max-width: 680px; margin: 0 auto; padding: 40px 20px 56px; }
header { display: flex; gap: 18px; align-items: center; margin-bottom: 28px; }
header img { border-radius: 14px; flex: none; }
h1 { font-size: 28px; line-height: 1.15; margin: 0 0 8px; text-wrap: balance; }
header p { margin: 0; color: var(--tenue); }
ol { list-style: none; margin: 0; padding: 0; counter-reset: passo; display: grid; gap: 12px; }
ol li { counter-increment: passo; position: relative; background: var(--carta); border: 1px solid var(--filo); border-radius: 12px; padding: 16px 18px 16px 62px; }
ol li::before { content: counter(passo); position: absolute; left: 16px; top: 16px; width: 32px; height: 32px; border-radius: 50%;
  background: var(--tinta); color: var(--su-tinta); font-weight: 700; display: grid; place-items: center; font-variant-numeric: tabular-nums; }
h2 { font-size: 17px; margin: 0 0 4px; }
ol p { margin: 0; color: var(--tenue); }
h2.sapere { margin: 32px 0 10px; font-size: 19px; }
ul { margin: 0; padding-left: 20px; display: grid; gap: 8px; color: var(--tenue); }
button { font: inherit; font-weight: 600; margin-top: 22px; padding: 10px 18px; border-radius: 10px; border: 0; background: var(--tinta); color: var(--su-tinta); cursor: pointer; }
button:focus-visible { outline: 3px solid var(--ink); outline-offset: 2px; }
.piede { margin: 18px 0 0; font-size: 14px; color: var(--tenue); }
@media (max-width: 480px) { header { align-items: flex-start; } h1 { font-size: 23px; } main { padding-top: 24px; } }
"""
GUIDA_JS = """/* GENERATO da estensione/costruisci.py: non modificare a mano.
 *
 * La pagina di benvenuto: riempie i testi nella lingua del browser e porta
 * alle opzioni.
 */
(function () {
  "use strict";
  var m = function (chiave) { return chrome.i18n.getMessage(chiave) || chiave; };
  document.querySelectorAll("[data-msg]").forEach(function (el) { el.textContent = m(el.getAttribute("data-msg")); });
  document.title = m("guidaTitolo");
  try { document.documentElement.lang = chrome.i18n.getUILanguage(); } catch (e) { /* resta senza */ }
  document.getElementById("opzioni").addEventListener("click", function () { chrome.runtime.openOptionsPage(); });
})();
"""
# In coda al service worker: la guida si apre alla prima installazione (non agli aggiornamenti).
SFONDO_GUIDA = """// Appena installata: la pagina che spiega come si usa.
chrome.runtime.onInstalled.addListener((dettagli) => {
  if (dettagli && dettagli.reason === "install") chrome.tabs.create({ url: chrome.runtime.getURL("benvenuto.html") });
});
"""

SFONDO = """/* Il service worker dell'estensione: al clic sull'icona accende il ring
 * sulla scheda attiva; a un secondo clic lo spegne (e poi lo riaccende). */
async function avvia(tab) {
  if (!tab || !tab.id) return "nessuna scheda";
  const dove = { tabId: tab.id };
  try {
    const [{ result: gia }] = await chrome.scripting.executeScript({ target: dove, func: () => !!window.__ringEstensione });
    if (gia) {
      await chrome.scripting.executeScript({ target: dove, func: () => window.__ringEstensione.alterna() });
      return "alternato";
    }
    // La memoria dei lottatori (quello che hanno imparato, i gettoni, le
    // opzioni) è dell'estensione: uguale su tutti i siti.
    const dati = await chrome.storage.local.get(null);
    // `__lingueSoloDizionario`: il dizionario delle lingue serve solo alla tendina, la pagina non si tocca.
    await chrome.scripting.executeScript({ target: dove, func: (d) => { window.__ringDati = d; window.__lingueSoloDizionario = true; }, args: [dati] });
    // Il cursore a manina sopra i lottatori: inserito dall'estensione, così passa anche
    // sui siti con una Content-Security-Policy che vieta gli stili scritti nella pagina.
    await chrome.scripting.insertCSS({ target: dove, css: __STILE_PAGINA__ });
    await chrome.scripting.executeScript({ target: dove, files: ["lingue.js", "prepara.js", "ring.js"] });
    return "acceso";
  } catch (errore) {
    // Pagine dove un'estensione non può entrare (chrome://, il Web Store, i PDF).
    return "non permesso: " + (errore && errore.message);
  }
}
chrome.action.onClicked.addListener(avvia);
// Dal tasto sempre visibile (per chi l'ha acceso nelle opzioni) e dalla tendina.
chrome.runtime.onMessage.addListener((messaggio, mittente) => {
  if (!messaggio) return;
  if (messaggio.tipo === "avvia" && mittente.tab) avvia(mittente.tab);
  if (messaggio.tipo === "opzioni") chrome.runtime.openOptionsPage();
  if (messaggio.tipo === "guida") chrome.tabs.create({ url: chrome.runtime.getURL("benvenuto.html") });
});
// Tolto il permesso su tutti i siti dalle impostazioni del browser: via anche il tasto.
chrome.permissions.onRemoved.addListener(async () => {
  try {
    if (await chrome.permissions.contains({ origins: ["<all_urls>"] })) return;
    await chrome.scripting.unregisterContentScripts({ ids: ["pb-tasto"] });
    await chrome.storage.local.set({ "pb-sempre": "off" });
  } catch (errore) { /* non era registrato */ }
});
"""

STILE_BASE = """
:host {
  --carta: #ffffff; --ink: #201e1d; --bordo: #d4d0c8; --filo: rgba(32, 30, 29, .14);
  --verde: #1f7a5a; --verde-tenue: rgba(31, 122, 90, .14); --fondo-firmware: #f3f7f5; --su-tinta: #ffffff;
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; font-size: 15px; line-height: 1.35;
}
@media (prefers-color-scheme: dark) {
  :host { --carta: #1c1b1a; --ink: #ebe9e6; --bordo: #3a3835; --filo: rgba(235, 233, 230, .14);
          --verde: #46c291; --verde-tenue: rgba(70, 194, 145, .16); --fondo-firmware: #17231e; }
}
/* Il carattere si fissa QUI DENTRO e non sull'ospite: lo stile della pagina può
   arrivare fino all'ospite (un `* { font-family: … !important }`), ma non oltre. */
.barretta, .ring-pannello {
  font: 15px/1.35 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; color: var(--ink);
  text-align: left; letter-spacing: normal; text-transform: none; word-spacing: normal;
}
*, *::before, *::after { box-sizing: border-box; }
[hidden] { display: none !important; }
.tela { position: fixed; top: 0; left: 0; display: block; pointer-events: none; touch-action: none; }
.ancora { position: fixed; right: 0; left: 0; bottom: 58px; height: 0; pointer-events: none; }
.barretta {
  position: fixed; right: 12px; bottom: 12px; display: flex; gap: 6px; padding: 5px;
  pointer-events: auto; background: var(--carta); color: var(--ink);
  border: 1px solid var(--bordo); border-radius: 999px; box-shadow: 0 6px 18px rgba(0, 0, 0, .18);
}
.tasto {
  width: 36px; height: 36px; border-radius: 50%; border: 1px solid var(--bordo); background: var(--carta);
  color: var(--ink); font: inherit; font-size: 17px; cursor: pointer; display: grid; place-items: center; padding: 0;
}
.tasto:hover { border-color: var(--verde); }
.tasto[aria-expanded="true"], .tasto[data-radiale][aria-pressed="true"] { background: var(--verde-tenue); }
/* Col controller aperto nell'angolo, i tasti gli si mettono accanto (la larghezza la scrive il ring). */
.barretta.con-controller { right: calc(var(--controller, 0px) + 12px); }
.tasto[data-gioca] { color: var(--verde); }
.tasto[data-gioca][aria-pressed="false"] { color: var(--ink); opacity: .65; }
/* Spento: resta solo il tasto di accensione. */
:host([data-spento]) .tela, :host([data-spento]) .ancora, :host([data-spento]) [data-opzioni], :host([data-spento]) [data-radiale] { display: none !important; }
:host([data-spento]) .barretta { right: 12px; }
h3 { font-weight: 700; }
/* Premium: i tasti chiusi portano il lucchetto; in cima alla tendina il riquadro che spiega e sblocca. */
.ring-tasto.bloccato { opacity: .72; }
.ring-tasto.bloccato::after { content: "\\1F512"; float: right; margin-left: .3rem; font-size: .8em; }
.premio { border: 1px solid var(--bordo); border-radius: 10px; padding: .55rem .65rem; margin: .5rem 0 .2rem; background: var(--fondo-firmware); }
.premio p { margin: 0 0 .45rem; font-size: .84rem; }
.premio .premio-avviso { font-weight: 700; color: #b3261e; }
.premio.cercato { outline: 2px solid var(--verde); }
.premio .ring-tasto { margin-top: .3rem; }
.premio [data-premio-compra] { background: var(--verde); border-color: var(--verde); color: var(--su-tinta); font-weight: 700; }
"""

STILE_PAGINA = ("html.ring-presa, html.ring-presa * { cursor: grab !important; } "
                "html.ring-trascina, html.ring-trascina * { cursor: grabbing !important; user-select: none !important; } "
                "html.ring-punta, html.ring-punta * { cursor: pointer !important; }")

ICONA_ACCENSIONE = ('<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">'
                    '<path d="M12 3v9" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/>'
                    '<path d="M7.1 6.3a8 8 0 1 0 9.8 0" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg>')

# Il tasto di accensione è `data-gioca`, quello che il ring già conosce: acceso
# c'è tutto, spento resta solo lui (vedi `:host([data-spento])`).
BARRETTA = """
  <div class="barretta">
    <button type="button" class="tasto" data-radiale hidden aria-pressed="false"
            title="Controller: scegli il personaggio e fagli fare le sue mosse">&#127918;</button>
    <button type="button" class="tasto" data-opzioni hidden aria-expanded="false"
            title="Opzioni del combattimento: scommesse, armi, imprevisti">&#129354;</button>
    <button type="button" class="tasto" data-gioca hidden aria-pressed="true" aria-label="Lotte accese o spente"
            title="Spegni le lotte">__ICONA__</button>
  </div>
""".replace("__ICONA__", ICONA_ACCENSIONE)

# Il tasto per chi lo vuole su ogni pagina: uno script minuscolo, registrato
# solo dopo che l'utente l'ha chiesto nelle opzioni e ha dato il permesso.
TASTO = """/* GENERATO da estensione/costruisci.py: non modificare a mano.
 *
 * Il tasto di accensione sempre visibile: in basso a destra, su ogni pagina.
 * Un clic chiede al service worker di far partire il ring su questa scheda.
 */
(function () {
  "use strict";
  if (window.top !== window || window.__ringEstensione || document.getElementById("page-brawl") || document.getElementById("page-brawl-tasto")) return;
  var ospite = document.createElement("div");
  ospite.id = "page-brawl-tasto";
  ospite.style.cssText = "all: initial; position: fixed; right: 12px; bottom: 12px; z-index: 2147483646;";
  var radice = ospite.attachShadow({ mode: "open" });
  radice.innerHTML = __HTML__;
  try {
    var foglio = new CSSStyleSheet();
    foglio.replaceSync(__STILE__);
    radice.adoptedStyleSheets = [foglio];
  } catch (e) { /* senza stile resta un tasto qualunque */ }
  var tasto = radice.querySelector("button"), titolo = "";
  try { titolo = chrome.i18n.getMessage("titolo"); } catch (e) { /* niente titolo */ }
  tasto.title = titolo; tasto.setAttribute("aria-label", titolo);
  tasto.addEventListener("click", function () {
    try { chrome.runtime.sendMessage({ tipo: "avvia" }); }
    catch (e) { ospite.remove(); }             // estensione aggiornata o tolta: il tasto non serve più
  });
  document.documentElement.appendChild(ospite);
})();
"""
STILE_TASTO = """
button {
  width: 48px; height: 48px; border-radius: 50%; border: 1px solid #d4d0c8; background: #ffffff; color: #201e1d;
  opacity: .75; cursor: pointer; display: grid; place-items: center; padding: 0; box-shadow: 0 6px 18px rgba(0, 0, 0, .18);
}
button:hover { opacity: 1; border-color: #1f7a5a; color: #1f7a5a; }
@media (prefers-color-scheme: dark) { button { background: #1c1b1a; color: #ebe9e6; border-color: #3a3835; } }
"""

OPZIONI_HTML = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Page Brawl</title>
<link rel="stylesheet" href="opzioni.css">
</head>
<body>
<h1 data-msg="opzioniTitolo"></h1>
<label><input type="checkbox" id="sempre"> <span data-msg="sempreEtichetta"></span></label>
<p data-msg="sempreSpiega"></p>
<p id="esito" role="status"></p>
<p><a href="benvenuto.html" target="_blank" rel="noopener" data-msg="guidaLink"></a></p>
<script src="opzioni.js"></script>
</body>
</html>
"""
OPZIONI_CSS = """body { font: 15px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; margin: 16px 18px; min-width: 320px; max-width: 520px; color: #201e1d; }
h1 { font-size: 18px; margin: 0 0 12px; }
label { display: flex; gap: 8px; align-items: flex-start; font-weight: 600; }
p { margin: 10px 0 0; color: #4a4744; }
#esito { color: #b3261e; min-height: 1.4em; }
a { color: #1f7a5a; font-weight: 600; }
@media (prefers-color-scheme: dark) { body { background: #1c1b1a; color: #ebe9e6; } p { color: #bdb9b3; } a { color: #46c291; } }
"""
OPZIONI_JS = """/* GENERATO da estensione/costruisci.py: non modificare a mano.
 *
 * La pagina delle opzioni: una sola scelta, il tasto di accensione su tutti i
 * siti. Accenderla fa chiedere al browser il permesso (facoltativo) su tutti
 * i siti e registra lo script del tasto; spegnerla toglie l'uno e l'altro.
 */
(function () {
  "use strict";
  var TUTTI = { origins: ["<all_urls>"] }, ID = "pb-tasto";
  var casella = document.getElementById("sempre"), esito = document.getElementById("esito");
  var m = function (chiave) { return chrome.i18n.getMessage(chiave) || chiave; };
  document.querySelectorAll("[data-msg]").forEach(function (el) { el.textContent = m(el.getAttribute("data-msg")); });
  document.title = m("opzioniTitolo");
  async function registrato() { return (await chrome.scripting.getRegisteredContentScripts({ ids: [ID] })).length > 0; }
  async function leggi() { casella.checked = (await chrome.permissions.contains(TUTTI)) && (await registrato()); }
  casella.addEventListener("change", async function () {
    esito.textContent = "";
    try {
      if (casella.checked) {
        // La richiesta va fatta subito, dentro il clic: è il browser a mostrare la domanda.
        var concesso = await chrome.permissions.request(TUTTI);
        if (!concesso) { casella.checked = false; esito.textContent = m("sempreNegato"); return; }
        if (!(await registrato())) {
          await chrome.scripting.registerContentScripts([{ id: ID, js: ["tasto.js"], matches: ["<all_urls>"], runAt: "document_idle" }]);
        }
        await chrome.storage.local.set({ "pb-sempre": "on" });
      } else {
        if (await registrato()) await chrome.scripting.unregisterContentScripts({ ids: [ID] });
        await chrome.storage.local.set({ "pb-sempre": "off" });
        try { await chrome.permissions.remove(TUTTI); } catch (e) { /* già tolto */ }
      }
    } catch (e) {
      esito.textContent = String((e && e.message) || e);
      await leggi();
    }
  });
  leggi();
})();
"""

PREPARA = """/* GENERATO da estensione/costruisci.py: non modificare a mano.
 *
 * Prepara la pagina per il ring: crea, dentro uno shadow DOM, il canvas, la
 * tendina delle opzioni e i due tasti; dichiara al ring dove stanno
 * (`window.__ringRadice`) e gli dà una memoria che vale su tutti i siti
 * (`window.__ringDeposito`, sopra `chrome.storage.local`).
 */
(function () {
  "use strict";
  if (window.__ringEstensione) return;
  var CONFIG = __CONFIG__;
  var memoria = Object.assign({}, window.__ringDati || {});
  memoria["mut-ring"] = "on";                    // chi clicca l'icona vuole la lotta accesa
  // Schizzi e arti staccati partono spenti: si accendono dalla tendina.
  if (!Object.prototype.hasOwnProperty.call(memoria, "mut-ring-cruento")) memoria["mut-ring-cruento"] = "off";
  function ricorda(k, v) {
    memoria[k] = String(v);
    try { var o = {}; o[k] = String(v); chrome.storage.local.set(o); } catch (e) { /* resta in memoria */ }
  }
  window.__ringDeposito = {
    getItem: function (k) { return Object.prototype.hasOwnProperty.call(memoria, k) ? memoria[k] : null; },
    setItem: function (k, v) {
      if (k === "mut-ring") { memoria[k] = String(v); return; }   // acceso/spento vale solo per questa pagina
      ricorda(k, v);
    },
  };

  // PREMIUM. Tre gruppi di funzioni sono a pagamento; lo stato sta nella
  // memoria dell'estensione. Il ring chiede qui se un gruppo è libero e, se
  // non lo è, fa aprire il riquadro in cima alla tendina.
  var premiumAttivo = memoria["pb-premium"] === "on", inAscolto = [];
  function impostaPremium(valore) {
    premiumAttivo = !!valore;
    ricorda("pb-premium", premiumAttivo ? "on" : "off");
    for (var i = 0; i < inAscolto.length; i++) { try { inAscolto[i](); } catch (e) { /* un ascoltatore rotto non ferma gli altri */ } }
    aggiornaRiquadro(false);
  }
  // `premium_attivo: false` in premium.json: niente di chiuso, tutto gratis.
  if (CONFIG.premium) window.__ringPremium = {
    bloccate: { guerrieri: true, armi: true, meteo: true },
    attivo: function () { return premiumAttivo; },
    chiedi: function () { aggiornaRiquadro(true); },
    ascolta: function (fn) { inAscolto.push(fn); },
  };
  var ospite = document.createElement("div");
  ospite.id = "page-brawl";
  ospite.style.cssText = "all: initial; position: fixed; inset: 0; z-index: 2147483646; pointer-events: none;";
  var radice = ospite.attachShadow({ mode: "open" });
  radice.innerHTML = __HTML__;
  // Lo stile come foglio «costruito»: a differenza di un <style> non lo ferma
  // la Content-Security-Policy dei siti che vietano gli stili in pagina.
  try {
    var foglio = new CSSStyleSheet();
    foglio.replaceSync(__STILE__);
    radice.adoptedStyleSheets = [foglio];
  } catch (e) {
    var stile = document.createElement("style");
    stile.textContent = __STILE__;
    radice.appendChild(stile);
  }
  document.documentElement.appendChild(ospite);
  window.__ringRadice = radice;
  // Se c'era il tasto sempre visibile, da qui in poi lo sostituisce la barretta.
  var solo = document.getElementById("page-brawl-tasto");
  if (solo) solo.remove();

  // Il tasto di accensione resta sempre in vista: spento, il resto sparisce
  // (canvas, tendina, tasto delle opzioni); riacceso, torna tutto.
  var accensione = radice.querySelector("[data-gioca]");
  function allinea() {
    if (accensione.getAttribute("aria-pressed") === "true") { ospite.removeAttribute("data-spento"); return; }
    ospite.setAttribute("data-spento", "");
    var tendina = radice.querySelector("[data-pannello]"), apri = radice.querySelector("[data-opzioni]");
    if (tendina) tendina.classList.remove("aperto");
    if (apri) apri.setAttribute("aria-expanded", "false");
  }
  new MutationObserver(allinea).observe(accensione, { attributes: true, attributeFilter: ["aria-pressed"] });
  var versoOpzioni = radice.querySelector("[data-opzioni-estensione]");
  if (versoOpzioni) versoOpzioni.addEventListener("click", function () {
    try { chrome.runtime.sendMessage({ tipo: "opzioni" }); } catch (e) { /* estensione ricaricata */ }
  });
  var versoGuida = radice.querySelector("[data-guida]");
  if (versoGuida) versoGuida.addEventListener("click", function () {
    try { chrome.runtime.sendMessage({ tipo: "guida" }); } catch (e) { /* estensione ricaricata */ }
  });

  // Il riquadro Premium: cosa sblocca, il tasto per comprarlo e l'interruttore
  // che lo apre e lo chiude senza pagare: nella variante di prova sempre, in
  // quella da pubblicare finché `sblocco_gratis` è acceso in premium.json.
  function aggiornaRiquadro(cercato) {
    var q = function (sel) { return radice.querySelector(sel); };
    var riquadro = q("[data-premio]");
    if (!riquadro) return;
    q("[data-premio-avviso]").hidden = premiumAttivo || !cercato;
    q("[data-premio-attivo]").hidden = !premiumAttivo;
    q("[data-premio-cosa]").hidden = premiumAttivo;
    var gratis = q("[data-premio-gratis]");
    if (gratis) gratis.hidden = premiumAttivo;
    var compra = q("[data-premio-compra]");
    // Finché si sblocca gratis e non c'è dove comprare, il tasto «arriva presto» non serve.
    compra.hidden = premiumAttivo || (CONFIG.sbloccoGratis && !CONFIG.urlAcquisto);
    compra.disabled = !CONFIG.urlAcquisto;
    compra.textContent = CONFIG.urlAcquisto ? "Sblocca Premium" : "Premium arriva presto";
    var prova = q("[data-premio-prova]");
    if (prova) prova.setAttribute("aria-pressed", premiumAttivo ? "true" : "false");
    riquadro.classList.toggle("cercato", !!cercato && !premiumAttivo);
    if (cercato && !premiumAttivo) {
      var pannello = q("[data-pannello]"), apri = q("[data-opzioni]");
      if (pannello && !pannello.classList.contains("aperto") && apri) apri.click();
      if (pannello) pannello.scrollTop = 0;
    }
  }
  (function () {
    var compra = radice.querySelector("[data-premio-compra]"), prova = radice.querySelector("[data-premio-prova]");
    if (compra) compra.addEventListener("click", function () { if (CONFIG.urlAcquisto) window.open(CONFIG.urlAcquisto, "_blank", "noopener"); });
    if (prova) prova.addEventListener("click", function () { impostaPremium(!premiumAttivo); });
    aggiornaRiquadro(false);
  })();

  // La lingua: quella del browser, se è una delle cinque; altrimenti inglese.
  // Il dizionario è lo stesso del sito (`lingue.js`), applicato solo qui dentro.
  try {
    var lingua = (memoria["pb-lingua"] || (chrome.i18n && chrome.i18n.getUILanguage()) || navigator.language || "en").slice(0, 2).toLowerCase();
    if (window.__lingue) window.__lingue.copri(radice, window.__lingue.codici.indexOf(lingua) >= 0 ? lingua : "en");
  } catch (e) { /* resta in italiano */ }
  window.__ringEstensione = {
    ospite: ospite,
    premium: impostaPremium,
    // Un altro clic sull'icona nella barra fa lo stesso del tasto di accensione.
    alterna: function () { accensione.click(); },
  };
})();
"""


def tendina() -> str:
    pagina = (RADICE / "web/templates/home.html").read_text(encoding="utf-8")
    inizio = pagina.index('<div class="ring-pannello"')
    fine = pagina.index('<div class="ultimora-barra">')
    blocco = pagina[inizio:fine].rstrip()
    if "{%" in blocco or "{{" in blocco or "{#" in blocco:
        raise SystemExit("la tendina contiene Jinja: l'estensione non la può usare così")
    return blocco


def stile_tendina() -> str:
    css = (RADICE / "web/static/style.css").read_text(encoding="utf-8")
    inizio = css.index("/* --- La tendina del ring")
    coda = "@media (prefers-reduced-motion: reduce) { .ring-pannello, .ring-pannello.aperto { transition: none; } }"
    fine = css.index(coda, inizio) + len(coda)
    return css[inizio:fine]


def icona(lato: int) -> bytes:
    """Un guantone rosso su fondo verde scuro, disegnato qui (niente file esterni)."""
    import io
    from PIL import Image, ImageDraw
    k = 4
    n = lato * k
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, n - 1, n - 1], radius=n * 0.22, fill=(22, 70, 54, 255))
    # il polsino, poi il guanto e il pollice
    d.rounded_rectangle([n * 0.30, n * 0.68, n * 0.66, n * 0.86], radius=n * 0.05, fill=(245, 245, 245, 255))
    d.ellipse([n * 0.22, n * 0.16, n * 0.74, n * 0.74], fill=(224, 58, 47, 255))
    d.ellipse([n * 0.58, n * 0.36, n * 0.84, n * 0.66], fill=(200, 44, 36, 255))
    d.arc([n * 0.30, n * 0.24, n * 0.60, n * 0.54], start=190, end=280, fill=(255, 255, 255, 200), width=max(1, n // 24))
    uscita = io.BytesIO()
    img.resize((lato, lato), Image.LANCZOS).save(uscita, format="PNG", optimize=True)
    return uscita.getvalue()


RIQUADRO_PREMIO = """
    <section class="premio" data-premio>
      <p class="premio-avviso" data-premio-avviso hidden>Questa funzione fa parte di Premium.</p>
      <p data-premio-attivo hidden>Premium attivo.</p>
      <p data-premio-cosa>Premium sblocca i personaggi (super guerrieri, maghi e duellanti) con le loro mosse, le armi e le bombe, il meteo, i meteoriti, il buco nero, l'orda di zombie e la gravità.</p>__GRATIS__
      <button type="button" class="ring-tasto ring-largo" data-premio-compra>Sblocca Premium</button>__PROVA__
    </section>"""
VERSO_OPZIONI = """  <section class="ring-sezione">
      <button type="button" class="ring-tasto ring-largo" data-opzioni-estensione>&#9881; Tasto di accensione su tutti i siti</button>
      <button type="button" class="ring-tasto ring-largo" data-guida>&#10067; Come funziona</button>
    </section>
  """
TASTO_PROVA = """
      <button type="button" class="ring-tasto ring-largo" data-premio-prova aria-pressed="false">Premium di prova (solo in questa versione)</button>"""
# Lo stesso interruttore, col nome che ha quando Premium si regala a tutti (`sblocco_gratis`).
TASTO_GRATIS = """
      <button type="button" class="ring-tasto ring-largo" data-premio-prova aria-pressed="false">Sblocca Premium gratis</button>"""
RIGA_GRATIS = """
      <p data-premio-gratis>Per ora è gratis: un clic qui sotto e si apre tutto.</p>"""


def premium() -> dict:
    """Le tre scelte di `premium.json`.

    `premium_attivo`: se falso non c'è niente di chiuso, né lucchetti né
    riquadro. `sblocco_gratis`: Premium resta com'è (lucchetti e riquadro), ma
    chiunque lo apre con un clic, anche nella variante da pubblicare: è lo
    stesso interruttore della variante di prova. `url_acquisto`: dove si
    compra; finché è vuoto il tasto di acquisto resta spento (e con lo sblocco
    gratis non si vede).
    """
    percorso = QUI / "premium.json"
    dati = json.loads(percorso.read_text(encoding="utf-8")) if percorso.exists() else {}
    url = str(dati.get("url_acquisto") or "").strip()
    if url and not url.startswith("https://"):
        raise SystemExit("premium.json: url_acquisto deve cominciare con https://")
    return {"premium": bool(dati.get("premium_attivo", True)), "urlAcquisto": url,
            "sbloccoGratis": bool(dati.get("premium_attivo", True)) and bool(dati.get("sblocco_gratis", False))}


def file_attesi(variante: str) -> dict:
    opzioni = VARIANTI[variante]
    pannello = tendina()
    testa = '<div class="ring-pannello-testa">'
    fine_testa = pannello.index("</div>", pannello.index(testa)) + len("</div>")
    scelte = premium()
    # L'interruttore che apre Premium senza pagare: sempre nella variante di
    # prova, e anche in quella da pubblicare quando Premium si regala.
    interruttore = scelte["premium"] and (opzioni["premium_di_prova"] or scelte["sbloccoGratis"])
    if scelte["premium"]:
        tasto = (TASTO_GRATIS if scelte["sbloccoGratis"] else TASTO_PROVA) if interruttore else ""
        riquadro = (RIQUADRO_PREMIO.replace("__PROVA__", tasto)
                    .replace("__GRATIS__", RIGA_GRATIS if scelte["sbloccoGratis"] else ""))
        pannello = pannello[:fine_testa] + riquadro + pannello[fine_testa:]
    # Nell'estensione non ci sono telefoni (02/10/2026, su richiesta): via i
    # tasti che li mettono in campo, e la pioggia diventa di oggetti.
    for forma in ("classico", "orologio", "tablet", "pc"):
        pannello = re.sub(r'\s*<button type="button" class="ring-tasto" data-metti="%s">[^<]*</button>' % forma, "", pannello)
    assert 'data-metti="classico"' not in pannello and 'data-metti="fumogeno"' in pannello
    assert "Pioggia di telefoni" in pannello
    pannello = pannello.replace("&#128242; Pioggia di telefoni", "&#127776; Pioggia di oggetti")
    # In fondo alla tendina, la strada per le opzioni dell'estensione.
    fine = pannello.rindex("</div>")
    pannello = pannello[:fine] + VERSO_OPZIONI + pannello[fine:]
    html = '<canvas class="tela" data-ring aria-hidden="true"></canvas>\n<div class="ancora">\n  ' + pannello + "\n</div>" + BARRETTA
    if "style=" in html:
        raise SystemExit("la tendina ha stili in linea: una CSP severa li bloccherebbe")
    config = dict(scelte, premiumDiProva=interruttore)
    prepara = (PREPARA
               .replace("__CONFIG__", json.dumps(config, ensure_ascii=False))
               .replace("__STILE__", json.dumps(STILE_BASE + stile_tendina(), ensure_ascii=False))
               .replace("__HTML__", json.dumps(html, ensure_ascii=False)))
    attesi = {
        "manifest.json": json.dumps(MANIFEST, ensure_ascii=False, indent=2) + "\n",
        "sfondo.js": SFONDO.replace("__STILE_PAGINA__", json.dumps(STILE_PAGINA, ensure_ascii=False)) + SFONDO_GUIDA,
        "benvenuto.html": pagina_guida(NOME, 6, ["guidaS1", "guidaS2", "guidaS7", "guidaS9", "guidaS10", "guidaS8", "guidaS3", "guidaS4"]
                                       + ([("guidaS5gratis" if scelte["sbloccoGratis"] else "guidaS5")] if scelte["premium"] else []) + ["guidaS6"]),
        "benvenuto.css": GUIDA_CSS, "benvenuto.js": GUIDA_JS,
        "prepara.js": prepara,
        "ring.js": (RADICE / "web/static/ring.js").read_text(encoding="utf-8"),
        "lingue.js": (RADICE / "web/static/lingue.js").read_text(encoding="utf-8"),
        "tasto.js": (TASTO.replace("__HTML__", json.dumps('<button type="button">' + ICONA_ACCENSIONE + "</button>"))
                          .replace("__STILE__", json.dumps(STILE_TASTO))),
        "opzioni.html": OPZIONI_HTML, "opzioni.css": OPZIONI_CSS, "opzioni.js": OPZIONI_JS,
    }
    for lingua, testi in MESSAGGI.items():
        if set(testi) != set(MESSAGGI["en"]):
            raise SystemExit(f"messaggi {lingua}: chiavi diverse dall'inglese")
        if len(testi["descrizione"]) > 132:
            raise SystemExit(f"descrizione {lingua} troppo lunga per lo store: {len(testi['descrizione'])} caratteri")
        messaggi = {"nome": {"message": NOME}}
        messaggi.update({chiave: {"message": testo} for chiave, testo in testi.items()})
        attesi[f"_locales/{lingua}/messages.json"] = json.dumps(messaggi, ensure_ascii=False, indent=2) + "\n"
    return attesi


# ---------------------------------------------------------------------------
# PAGE SNOW: la seconda estensione, solo il tema di Natale (02/10/2026).
# Il cuore è `web/static/natale.js`, lo stesso file del sito: qui gli si dice
# dove mettere il canvas e gli si mette accanto un tasto per accendere e
# spegnere. Gratis, nessun Premium.
# ---------------------------------------------------------------------------
NATALE_VERSIONE = "0.2.0"
NATALE_NOME = "Page Snow"
NATALE_MANIFEST = {
    "manifest_version": 3,
    "name": "__MSG_nome__",
    "version": NATALE_VERSIONE,
    "description": "__MSG_descrizione__",
    "default_locale": "en",
    "action": {"default_title": "__MSG_titolo__"},
    "background": {"service_worker": "sfondo.js"},
    "permissions": ["activeTab", "scripting", "storage"],
    # Facoltativo: solo per chi sceglie, nelle opzioni, il Natale su tutti i siti.
    "optional_host_permissions": ["<all_urls>"],
    "options_ui": {"page": "opzioni.html", "open_in_tab": False},
    "icons": {"16": "icone/16.png", "48": "icone/48.png", "128": "icone/128.png"},
}
NATALE_MESSAGGI = {
    "en": {
        "descrizione": "Snow falls on the page you are viewing and piles up on it. Lights, icicles, a tree with gifts, snowmen to take apart.",
        "titolo": "Turn the snow on or off on this page",
        "opzioniTitolo": "Page Snow options",
        "sempreEtichetta": "Turn the Christmas theme on automatically on every site",
        "sempreSpiega": "Every page you open gets the snow without clicking the toolbar icon; the snowflake button in the bottom right corner turns it off and on again everywhere. To do this, the browser will ask you to let Page Snow run on all sites. Nothing is read from the pages and nothing is sent anywhere.",
        "sempreNegato": "Permission not granted: the theme stays manual.",
    },
    "it": {
        "descrizione": "Nevica sulla pagina che stai guardando, e la neve si accumula. Lucine, ghiaccioli, un albero coi regali, pupazzi da smontare.",
        "titolo": "Accendi o spegni la neve su questa pagina",
        "opzioniTitolo": "Opzioni di Page Snow",
        "sempreEtichetta": "Accendi da solo il tema di Natale su tutti i siti",
        "sempreSpiega": "Ogni pagina che apri ha la neve senza cliccare l'icona nella barra; il tasto col fiocco in basso a destra la spegne e la riaccende dappertutto. Per farlo il browser ti chiede di lasciar funzionare Page Snow su tutti i siti. Dalle pagine non viene letto niente e non viene inviato niente.",
        "sempreNegato": "Permesso non concesso: il tema resta manuale.",
    },
    "es": {
        "descrizione": "Nieva sobre la página que estás viendo y la nieve se acumula. Luces, carámbanos, un árbol con regalos y muñecos de nieve.",
        "titolo": "Enciende o apaga la nieve en esta página",
        "opzioniTitolo": "Opciones de Page Snow",
        "sempreEtichetta": "Encender solo el tema de Navidad en todos los sitios",
        "sempreSpiega": "Cada página que abres tiene nieve sin pulsar el icono de la barra; el botón del copo, abajo a la derecha, la apaga y la vuelve a encender en todas partes. Para ello, el navegador te pedirá que dejes funcionar Page Snow en todos los sitios. No se lee nada de las páginas y no se envía nada.",
        "sempreNegato": "Permiso no concedido: el tema sigue siendo manual.",
    },
    "fr": {
        "descrizione": "Il neige sur la page que vous regardez et la neige s'accumule. Guirlandes, glaçons, sapin et cadeaux, bonshommes de neige.",
        "titolo": "Activer ou arrêter la neige sur cette page",
        "opzioniTitolo": "Options de Page Snow",
        "sempreEtichetta": "Activer automatiquement le thème de Noël sur tous les sites",
        "sempreSpiega": "Chaque page ouverte a sa neige sans cliquer sur l'icône de la barre ; le bouton au flocon, en bas à droite, l'arrête et la relance partout. Pour cela, le navigateur vous demandera de laisser Page Snow fonctionner sur tous les sites. Rien n'est lu dans les pages et rien n'est envoyé.",
        "sempreNegato": "Autorisation refusée : le thème reste manuel.",
    },
    "de": {
        "descrizione": "Es schneit auf der Seite, die du ansiehst, und der Schnee bleibt liegen. Lichter, Eiszapfen, ein Baum mit Geschenken, Schneemänner.",
        "titolo": "Schnee auf dieser Seite ein- oder ausschalten",
        "opzioniTitolo": "Optionen von Page Snow",
        "sempreEtichetta": "Weihnachtsdesign auf allen Websites automatisch einschalten",
        "sempreSpiega": "Jede geöffnete Seite bekommt Schnee, ohne das Symbol in der Leiste anzuklicken; der Knopf mit der Flocke unten rechts schaltet ihn überall aus und wieder ein. Dafür fragt der Browser, ob Page Snow auf allen Websites laufen darf. Aus den Seiten wird nichts gelesen und nichts wird gesendet.",
        "sempreNegato": "Berechtigung nicht erteilt: Das Design bleibt manuell.",
    },
}
NATALE_GUIDA = {
    "en": {
        "guidaLink": "How it works",
        "guidaTitolo": "How Page Snow works",
        "guidaIntro": "Snow falls on top of the page you are viewing and settles on headings, images and buttons. The page underneath stays as it is: nothing is read and nothing is sent anywhere.",
        "guidaP1T": "Open any page",
        "guidaP1": "A news site, a shop, anything you like. It cannot start on the browser's internal pages, on the Chrome Web Store or in PDFs.",
        "guidaP2T": "Click the Page Snow icon",
        "guidaP2": "It sits in the browser toolbar, inside the extensions menu (the puzzle piece): pin it to keep it at hand. One click and it starts snowing.",
        "guidaP3T": "Turn it off and on with the snowflake button",
        "guidaP3": "It stays in the bottom right corner: it stops the snow and starts it again without reloading the page.",
        "guidaP4T": "Play with what you find",
        "guidaP4": "Touch the snowmen with the pointer: they fall apart, and you can grab the pieces with the mouse. Click the gifts under the tree to open them. Every now and then the sleigh flies by.",
        "guidaSapereT": "Good to know",
        "guidaS1": "The snow piles up over time: the longer you stay on the page, the higher the heaps.",
        "guidaS2": "Want snow on every page you open, without clicking the icon? Turn it on in the options.",
        "guidaOpzioni": "Open the options",
        "guidaPiede": "You can reopen this page any time from the extension's options.",
    },
    "it": {
        "guidaLink": "Come funziona",
        "guidaTitolo": "Come funziona Page Snow",
        "guidaIntro": "Nevica sopra la pagina che stai guardando, e la neve si posa sui titoli, sulle immagini e sui tasti. La pagina sotto resta com'è: non viene letto né inviato niente.",
        "guidaP1T": "Apri una pagina qualsiasi",
        "guidaP1": "Un sito di notizie, un negozio, quello che vuoi. Non può partire sulle pagine interne del browser, sul Chrome Web Store e nei PDF.",
        "guidaP2T": "Clicca l'icona di Page Snow",
        "guidaP2": "È nella barra del browser, dentro il menu delle estensioni (il pezzo di puzzle): fissala con la puntina per averla sempre a portata. Un clic e comincia a nevicare.",
        "guidaP3T": "Spegni e riaccendi dal tasto col fiocco",
        "guidaP3": "Resta in basso a destra: ferma la neve e la fa ripartire senza ricaricare la pagina.",
        "guidaP4T": "Gioca con quello che trovi",
        "guidaP4": "Tocca i pupazzi di neve col puntatore: vanno in pezzi, e i pezzi si prendono col mouse. Clicca i regali sotto l'albero per aprirli. Ogni tanto passa la slitta.",
        "guidaSapereT": "Cose da sapere",
        "guidaS1": "La neve si accumula col tempo: più resti sulla pagina, più i mucchi crescono.",
        "guidaS2": "Vuoi la neve su ogni pagina che apri, senza cliccare l'icona? Si accende dalle opzioni.",
        "guidaOpzioni": "Apri le opzioni",
        "guidaPiede": "Questa pagina si riapre quando vuoi dalle opzioni dell'estensione.",
    },
    "es": {
        "guidaLink": "Cómo funciona",
        "guidaTitolo": "Cómo funciona Page Snow",
        "guidaIntro": "Nieva encima de la página que estás viendo, y la nieve se posa sobre los títulos, las imágenes y los botones. La página de debajo se queda como está: no se lee ni se envía nada.",
        "guidaP1T": "Abre cualquier página",
        "guidaP1": "Un sitio de noticias, una tienda, lo que quieras. No puede arrancar en las páginas internas del navegador, en Chrome Web Store ni en los PDF.",
        "guidaP2T": "Haz clic en el icono de Page Snow",
        "guidaP2": "Está en la barra del navegador, dentro del menú de extensiones (la pieza de puzle): fíjalo con la chincheta para tenerlo a mano. Un clic y empieza a nevar.",
        "guidaP3T": "Apaga y enciende con el botón del copo",
        "guidaP3": "Se queda abajo a la derecha: detiene la nieve y la reanuda sin recargar la página.",
        "guidaP4T": "Juega con lo que encuentres",
        "guidaP4": "Toca los muñecos de nieve con el puntero: se desmontan, y las piezas se agarran con el ratón. Haz clic en los regalos bajo el árbol para abrirlos. De vez en cuando pasa el trineo.",
        "guidaSapereT": "Cosas que conviene saber",
        "guidaS1": "La nieve se acumula con el tiempo: cuanto más te quedas en la página, más crecen los montones.",
        "guidaS2": "¿Quieres nieve en cada página que abras, sin pulsar el icono? Se activa en las opciones.",
        "guidaOpzioni": "Abrir las opciones",
        "guidaPiede": "Puedes volver a abrir esta página cuando quieras desde las opciones de la extensión.",
    },
    "fr": {
        "guidaLink": "Comment ça marche",
        "guidaTitolo": "Comment fonctionne Page Snow",
        "guidaIntro": "Il neige par-dessus la page que vous regardez, et la neige se pose sur les titres, les images et les boutons. La page en dessous reste telle quelle : rien n'est lu, rien n'est envoyé.",
        "guidaP1T": "Ouvrez n'importe quelle page",
        "guidaP1": "Un site d'actualités, une boutique, ce que vous voulez. Il ne peut pas démarrer sur les pages internes du navigateur, sur le Chrome Web Store ni dans les PDF.",
        "guidaP2T": "Cliquez sur l'icône de Page Snow",
        "guidaP2": "Elle se trouve dans la barre du navigateur, dans le menu des extensions (la pièce de puzzle) : épinglez-la pour l'avoir sous la main. Un clic et il se met à neiger.",
        "guidaP3T": "Arrêtez et relancez avec le bouton au flocon",
        "guidaP3": "Il reste en bas à droite : il arrête la neige et la relance sans recharger la page.",
        "guidaP4T": "Jouez avec ce que vous trouvez",
        "guidaP4": "Touchez les bonshommes de neige avec le pointeur : ils tombent en morceaux, et les morceaux s'attrapent à la souris. Cliquez sur les cadeaux sous le sapin pour les ouvrir. De temps en temps, le traîneau passe.",
        "guidaSapereT": "Bon à savoir",
        "guidaS1": "La neige s'accumule avec le temps : plus vous restez sur la page, plus les tas grandissent.",
        "guidaS2": "Vous voulez de la neige sur chaque page ouverte, sans cliquer sur l'icône ? Activez-la dans les options.",
        "guidaOpzioni": "Ouvrir les options",
        "guidaPiede": "Vous pouvez rouvrir cette page à tout moment depuis les options de l'extension.",
    },
    "de": {
        "guidaLink": "So funktioniert es",
        "guidaTitolo": "So funktioniert Page Snow",
        "guidaIntro": "Es schneit über der Seite, die du gerade ansiehst, und der Schnee bleibt auf Überschriften, Bildern und Knöpfen liegen. Die Seite darunter bleibt, wie sie ist: Es wird nichts gelesen und nichts gesendet.",
        "guidaP1T": "Öffne irgendeine Seite",
        "guidaP1": "Eine Nachrichtenseite, ein Shop, was du willst. Auf den internen Seiten des Browsers, im Chrome Web Store und in PDFs kann es nicht starten.",
        "guidaP2T": "Klicke auf das Page-Snow-Symbol",
        "guidaP2": "Es sitzt in der Symbolleiste des Browsers, im Erweiterungsmenü (das Puzzleteil): Hefte es an, damit es immer griffbereit ist. Ein Klick und es beginnt zu schneien.",
        "guidaP3T": "Aus- und einschalten mit dem Flocken-Knopf",
        "guidaP3": "Er bleibt unten rechts: Er stoppt den Schnee und startet ihn wieder, ohne die Seite neu zu laden.",
        "guidaP4T": "Spiel mit dem, was du findest",
        "guidaP4": "Berühre die Schneemänner mit dem Zeiger: Sie fallen auseinander, und die Teile kannst du mit der Maus packen. Klicke auf die Geschenke unter dem Baum, um sie zu öffnen. Ab und zu fliegt der Schlitten vorbei.",
        "guidaSapereT": "Gut zu wissen",
        "guidaS1": "Der Schnee sammelt sich mit der Zeit: Je länger du auf der Seite bleibst, desto höher werden die Haufen.",
        "guidaS2": "Du willst Schnee auf jeder Seite, die du öffnest, ohne das Symbol anzuklicken? Schalte es in den Optionen ein.",
        "guidaOpzioni": "Optionen öffnen",
        "guidaPiede": "Diese Seite öffnest du jederzeit wieder über die Optionen der Erweiterung.",
    },
}
for _lingua, _testi in NATALE_GUIDA.items():
    NATALE_MESSAGGI[_lingua].update(_testi)
NATALE_PAGINA_CSS = ("html.natale-presa, html.natale-presa * { cursor: grab !important; }\n"
                     "html.natale-trascina, html.natale-trascina * { cursor: grabbing !important; user-select: none !important; }\n")
NATALE_SFONDO = """/* Il service worker di Page Snow: al clic sull'icona accende la neve sulla
 * scheda attiva; a un secondo clic la spegne (e poi la riaccende). */
async function avvia(tab) {
  if (!tab || !tab.id) return "nessuna scheda";
  const dove = { tabId: tab.id };
  try {
    const [{ result: gia }] = await chrome.scripting.executeScript({ target: dove, func: () => !!window.__nataleEstensione });
    if (gia) {
      await chrome.scripting.executeScript({ target: dove, func: () => window.__nataleEstensione.alterna() });
      return "alternato";
    }
    // `__nataleAvvio`: chiesto con un clic, parte acceso (da solo, su tutti i siti, guarda prima se è stato spento).
    await chrome.scripting.executeScript({ target: dove, func: () => { window.__nataleAvvio = true; } });
    await chrome.scripting.insertCSS({ target: dove, files: ["pagina.css"] });
    await chrome.scripting.executeScript({ target: dove, files: ["prepara.js", "natale.js"] });
    return "acceso";
  } catch (errore) {
    // Pagine dove un'estensione non può entrare (chrome://, il Web Store, i PDF).
    return "non permesso: " + (errore && errore.message);
  }
}
chrome.action.onClicked.addListener(avvia);
// Tolto il permesso su tutti i siti dalle impostazioni del browser: il tema torna manuale.
chrome.permissions.onRemoved.addListener(async () => {
  try {
    if (await chrome.permissions.contains({ origins: ["<all_urls>"] })) return;
    await chrome.scripting.unregisterContentScripts({ ids: ["ps-auto"] });
    await chrome.storage.local.set({ "ps-sempre": "off" });
  } catch (errore) { /* non era registrato */ }
});
"""
ICONA_FIOCCO = ('<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">'
                '<path d="M12 2.5v19M3.8 7.2l16.4 9.6M20.2 7.2L3.8 16.8"/>'
                '<path d="M9.6 4.4L12 6.6l2.4-2.2M9.6 19.6L12 17.4l2.4 2.2M4.2 10.4l3-.8-.8-3M19.8 13.6l-3 .8.8 3M19.8 10.4l-3-.8.8-3M4.2 13.6l3 .8-.8 3"/></svg>')
NATALE_STILE = """
*, *::before, *::after { box-sizing: border-box; }
.natale-tela { position: fixed; top: 0; left: 0; display: block; pointer-events: none; }
.barretta { position: fixed; right: 12px; bottom: 68px; pointer-events: auto; }
button {
  width: 44px; height: 44px; border-radius: 50%; border: 1px solid #d4d0c8; background: #ffffff; color: #6b6660;
  cursor: pointer; display: grid; place-items: center; padding: 0; box-shadow: 0 6px 18px rgba(0, 0, 0, .18); opacity: .8;
}
button:hover { opacity: 1; }
button[aria-pressed="true"] { background: #c8102e; border-color: #c8102e; color: #ffffff; opacity: 1; }
@media (prefers-color-scheme: dark) { button { background: #1c1b1a; color: #bdb9b3; border-color: #3a3835; } }
@media print { :host { display: none; } }
"""
NATALE_PREPARA = """/* GENERATO da estensione/costruisci.py: non modificare a mano.
 *
 * Prepara la pagina per il tema di Natale: uno shadow DOM che tiene il
 * canvas della neve (`natale.js` ce lo mette da sé) e il tasto col fiocco
 * per spegnere e riaccendere.
 */
(function () {
  "use strict";
  if (window.top !== window || window.__nataleEstensione) return;
  // Caricato da solo (scelta «su tutti i siti») parte spento e guarda se l'utente l'aveva spento;
  // caricato da un clic sull'icona parte acceso.
  var daSolo = !window.__nataleAvvio;
  var ospite = document.createElement("div");
  ospite.id = "page-snow";
  ospite.style.cssText = "all: initial; position: fixed; inset: 0; z-index: 2147483645; pointer-events: none;";
  var radice = ospite.attachShadow({ mode: "open" });
  radice.innerHTML = __HTML__;
  try {
    var foglio = new CSSStyleSheet();
    foglio.replaceSync(__STILE__);
    radice.adoptedStyleSheets = [foglio];
  } catch (e) {
    var stile = document.createElement("style");
    stile.textContent = __STILE__;
    radice.appendChild(stile);
  }
  document.documentElement.appendChild(ospite);
  var tasto = radice.querySelector("button"), titolo = "";
  try { titolo = chrome.i18n.getMessage("titolo"); } catch (e) { /* niente titolo */ }
  tasto.title = titolo; tasto.setAttribute("aria-label", titolo);
  function mostra(acceso) { tasto.setAttribute("aria-pressed", acceso ? "true" : "false"); }
  mostra(!daSolo);
  window.__nataleEstensione = {
    radice: radice, ospite: ospite, acceso: !daSolo,
    // Dal tasto o da un altro clic sull'icona: spegne o riaccende. Con «su tutti i siti» la scelta vale ovunque.
    alterna: function () {
      var nuovo = !window.__natale.acceso();
      window.__natale.imposta(nuovo); mostra(nuovo);
      if (daSolo) { try { chrome.storage.local.set({ "ps-spento": nuovo ? "off" : "on" }); } catch (e) { /* solo per questa pagina */ } }
    },
  };
  tasto.addEventListener("click", function () { window.__nataleEstensione.alterna(); });
  if (daSolo) {
    try {
      chrome.storage.local.get("ps-spento").then(function (dati) {
        var su = dati["ps-spento"] !== "on";
        if (su && window.__natale) window.__natale.imposta(true);
        mostra(su);
      });
    } catch (e) { /* resta spento */ }
  }
})();
"""
NATALE_OPZIONI_JS = OPZIONI_JS.replace('ID = "pb-tasto"', 'ID = "ps-auto"').replace(
    '{ id: ID, js: ["tasto.js"], matches: ["<all_urls>"], runAt: "document_idle" }',
    '{ id: ID, js: ["prepara.js", "natale.js"], css: ["pagina.css"], matches: ["<all_urls>"], runAt: "document_idle" }'
).replace('"pb-sempre"', '"ps-sempre"').replace(
    "La pagina delle opzioni: una sola scelta, il tasto di accensione su tutti i\n * siti. Accenderla fa chiedere al browser il permesso (facoltativo) su tutti\n * i siti e registra lo script del tasto; spegnerla toglie l'uno e l'altro.",
    "La pagina delle opzioni: una sola scelta, il tema di Natale acceso da solo\n * su tutti i siti. Accenderla fa chiedere al browser il permesso (facoltativo)\n * su tutti i siti e registra gli script del tema; spegnerla toglie tutto.")


def icona_natale(lato: int) -> bytes:
    """Un fiocco di neve bianco su fondo rosso, disegnato qui."""
    import io
    import math
    from PIL import Image, ImageDraw
    k = 4
    n = lato * k
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, n - 1, n - 1], radius=n * 0.22, fill=(200, 16, 46, 255))
    c, r, w = n / 2, n * 0.34, max(2, round(n * 0.07))
    for i in range(6):
        a = math.pi / 2 + i * math.pi / 3
        x, y = c + math.cos(a) * r, c + math.sin(a) * r
        d.line([c, c, x, y], fill=(255, 255, 255, 255), width=w)
        mx, my = c + math.cos(a) * r * 0.62, c + math.sin(a) * r * 0.62
        for lato_barba in (0.8, -0.8):
            d.line([mx, my, mx + math.cos(a + lato_barba) * r * 0.32, my + math.sin(a + lato_barba) * r * 0.32], fill=(255, 255, 255, 255), width=max(2, w - 2))
    d.ellipse([c - w, c - w, c + w, c + w], fill=(255, 255, 255, 255))
    uscita = io.BytesIO()
    img.resize((lato, lato), Image.LANCZOS).save(uscita, format="PNG", optimize=True)
    return uscita.getvalue()


def file_natale() -> dict:
    html = '<div class="barretta"><button type="button" aria-pressed="true">' + ICONA_FIOCCO + "</button></div>"
    attesi = {
        "manifest.json": json.dumps(NATALE_MANIFEST, ensure_ascii=False, indent=2) + "\n",
        "sfondo.js": NATALE_SFONDO + SFONDO_GUIDA,
        "benvenuto.html": pagina_guida(NATALE_NOME, 4, ["guidaS1", "guidaS2"]),
        "benvenuto.css": GUIDA_CSS.replace("--tinta: #1f7a5a", "--tinta: #c8102e").replace("--tinta: #46c291; --su-tinta: #10201a", "--tinta: #ff6b81; --su-tinta: #2a0a10"),
        "benvenuto.js": GUIDA_JS,
        "prepara.js": (NATALE_PREPARA.replace("__HTML__", json.dumps(html)).replace("__STILE__", json.dumps(NATALE_STILE))),
        "natale.js": (RADICE / "web/static/natale.js").read_text(encoding="utf-8"),
        "pagina.css": NATALE_PAGINA_CSS,
        "opzioni.html": OPZIONI_HTML.replace("<title>Page Brawl</title>", "<title>Page Snow</title>"),
        "opzioni.css": OPZIONI_CSS, "opzioni.js": NATALE_OPZIONI_JS,
    }
    for lingua, testi in NATALE_MESSAGGI.items():
        if set(testi) != set(NATALE_MESSAGGI["en"]):
            raise SystemExit(f"messaggi di Natale {lingua}: chiavi diverse dall'inglese")
        if len(testi["descrizione"]) > 132:
            raise SystemExit(f"descrizione di Natale {lingua} troppo lunga per lo store: {len(testi['descrizione'])} caratteri")
        messaggi = {"nome": {"message": NATALE_NOME}}
        messaggi.update({chiave: {"message": testo} for chiave, testo in testi.items()})
        attesi[f"_locales/{lingua}/messages.json"] = json.dumps(messaggi, ensure_ascii=False, indent=2) + "\n"
    return attesi


# Le cartelle che si costruiscono: i file attesi, l'icona, il nome dello zip.
PRODOTTI = {
    "pacchetto": (lambda: file_attesi("pacchetto"), icona, f"page-brawl-{VERSIONE}-prova.zip"),
    "store": (lambda: file_attesi("store"), icona, f"page-brawl-{VERSIONE}-store.zip"),
    "natale": (file_natale, icona_natale, f"page-snow-{NATALE_VERSIONE}.zip"),
}


def main() -> int:
    verifica = "--verifica" in sys.argv
    vecchi = []
    for cartella, (attesi_di, icona_di, _zip) in PRODOTTI.items():
        uscita = QUI / cartella
        attesi = attesi_di()
        if verifica:
            vecchi += [f"{cartella}/{nome}" for nome, testo in attesi.items()
                       if not (uscita / nome).exists() or (uscita / nome).read_text(encoding="utf-8") != testo]
            continue
        for nome, testo in attesi.items():
            (uscita / nome).parent.mkdir(parents=True, exist_ok=True)
            (uscita / nome).write_text(testo, encoding="utf-8")
        (uscita / "icone").mkdir(parents=True, exist_ok=True)
        for lato in (16, 48, 128):
            percorso = uscita / "icone" / f"{lato}.png"
            if not percorso.exists():
                percorso.write_bytes(icona_di(lato))
        print("scritto " + str(uscita))
    if not verifica and premium()["sbloccoGratis"]:
        print("Premium si sblocca gratis anche in store/ (sblocco_gratis: true in premium.json).")
    elif not verifica and premium()["premium"] and not premium()["urlAcquisto"]:
        print("ATTENZIONE: Premium è chiuso ma manca l'indirizzo di acquisto: in store/ le funzioni Premium "
              "non si possono sbloccare. Prima di pubblicare metti url_acquisto in premium.json, "
              "oppure sblocco_gratis: true (si apre con un clic) o premium_attivo: false (niente lucchetti).")
    if "--zip" in sys.argv and not verifica:
        import zipfile
        (QUI / "zip").mkdir(exist_ok=True)
        for cartella, (_attesi, _icona, nome_zip) in PRODOTTI.items():
            nome = QUI / "zip" / nome_zip
            with zipfile.ZipFile(nome, "w", zipfile.ZIP_DEFLATED) as z:
                # I file stanno alla RADICE dello zip: lo vuole lo store, e così la
                # cartella estratta si carica a mano senza scendere di un livello.
                for f in sorted((QUI / cartella).rglob("*")):
                    if f.is_file():
                        z.write(f, f.relative_to(QUI / cartella).as_posix())
            print("zip " + str(nome))
    if verifica:
        if vecchi:
            print("estensione vecchia: " + ", ".join(vecchi) + " (rigenera con python3 estensione/costruisci.py)")
            return 1
        print("estensioni aggiornate (pacchetto/, store/ e natale/)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
