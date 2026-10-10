/* LA SCELTA DELLA LINGUA (02/10/2026, su richiesta).
 *
 * Il sito nasce in italiano: le pagine le scrive il server. Qui sopra c'è
 * un velo di traduzione che gira nel browser: ogni testo dell'interfaccia
 * che compare nel dizionario viene sostituito con la sua versione nella
 * lingua scelta (inglese, spagnolo, francese, tedesco). La scelta resta nel
 * browser (`mut-lingua`).
 *
 * COSA SI TRADUCE: l'interfaccia (testata, ricerca, home, novità, accesso e
 * registrazione, le etichette delle schede, la striscia e la tendina del
 * ring). COSA NO: i dati (nomi dei modelli, build, titoli delle notizie
 * delle fonti) e le pagine di amministrazione. Un testo che non è nel
 * dizionario resta in italiano: meglio una frase non tradotta che una
 * tradotta male.
 *
 * I testi cambiati dopo (l'esito di una scommessa, un titolo aggiornato da
 * uno script) li segue un MutationObserver.
 */
(function () {
  "use strict";

  var CHIAVE = "mut-lingua";
  var CODICI = ["it", "en", "es", "fr", "de"];
  var radice = document.documentElement;

  // Ordine delle traduzioni: inglese, spagnolo, francese, tedesco.
  var T = {
    // --- Testata e piede
    "Cerca": ["Search", "Buscar", "Rechercher", "Suchen"],
    "Novità": ["News", "Novedades", "Nouveautés", "Neuigkeiten"],
    "Parco di test": ["Test fleet", "Parque de pruebas", "Parc de test", "Testgeräte"],
    "Catalogo": ["Catalogue", "Catálogo", "Catalogue", "Katalog"],
    "Accedi": ["Sign in", "Acceder", "Connexion", "Anmelden"],
    "Esci": ["Sign out", "Salir", "Déconnexion", "Abmelden"],
    "nessuna scansione ancora": ["no scan yet", "aún sin escaneos", "aucune analyse pour l'instant", "noch kein Scan"],
    "I dati vengono dalle fonti dei produttori. Le lacune sono dichiarate, non riempite.": [
      "Data comes from the manufacturers' sources. Gaps are declared, not filled in.",
      "Los datos proceden de las fuentes de los fabricantes. Las lagunas se declaran, no se rellenan.",
      "Les données viennent des sources des fabricants. Les lacunes sont déclarées, pas comblées.",
      "Die Daten stammen aus den Quellen der Hersteller. Lücken werden benannt, nicht aufgefüllt."],
    "Tema scuro": ["Dark theme", "Tema oscuro", "Thème sombre", "Dunkles Design"],
    "Passa al tema scuro": ["Switch to dark theme", "Cambiar al tema oscuro", "Passer au thème sombre", "Zum dunklen Design wechseln"],
    "Passa al tema chiaro": ["Switch to light theme", "Cambiar al tema claro", "Passer au thème clair", "Zum hellen Design wechseln"],
    "Tema natalizio": ["Christmas theme", "Tema navideño", "Thème de Noël", "Weihnachtsdesign"],
    "Accendi il tema natalizio": ["Turn on the Christmas theme", "Activar el tema navideño", "Activer le thème de Noël", "Weihnachtsdesign einschalten"],
    "Spegni il tema natalizio": ["Turn off the Christmas theme", "Desactivar el tema navideño", "Désactiver le thème de Noël", "Weihnachtsdesign ausschalten"],
    "Lingua": ["Language", "Idioma", "Langue", "Sprache"],
    "Cambia lingua": ["Change language", "Cambiar idioma", "Changer de langue", "Sprache ändern"],

    // --- Home e ricerca
    "Quale aggiornamento è arrivato, su quale modello, quando?": [
      "Which update has arrived, on which model, and when?",
      "¿Qué actualización ha llegado, en qué modelo y cuándo?",
      "Quelle mise à jour est arrivée, sur quel modèle, et quand ?",
      "Welches Update ist angekommen, auf welchem Modell, und wann?"],
    "il mio sito lo fa": ["my site does that", "mi sitio lo hace", "mon site le fait", "meine Seite kann das"],
    "Cerca un modello": ["Search for a model", "Buscar un modelo", "Rechercher un modèle", "Modell suchen"],
    "Recenti": ["Recent", "Recientes", "Récents", "Zuletzt"],
    "Scrivi un nome («Galaxy S24»), un codice modello («SM-S921B») o un IMEI, e premi Invio. Va bene com'è: 15 cifre, le prime 14 senza la cifra di controllo, o le 16 dell'IMEISV che molti telefoni mostrano con": [
      "Type a name (“Galaxy S24”), a model code (“SM-S921B”) or an IMEI, and press Enter. Any form works: 15 digits, the first 14 without the check digit, or the 16 of the IMEISV that many phones show with",
      "Escribe un nombre («Galaxy S24»), un código de modelo («SM-S921B») o un IMEI y pulsa Intro. Vale tal cual: 15 cifras, las 14 primeras sin el dígito de control, o las 16 del IMEISV que muchos teléfonos muestran con",
      "Saisissez un nom (« Galaxy S24 »), un code modèle (« SM-S921B ») ou un IMEI, puis appuyez sur Entrée. Tel quel, ça marche : 15 chiffres, les 14 premiers sans le chiffre de contrôle, ou les 16 de l'IMEISV que beaucoup de téléphones affichent avec",
      "Gib einen Namen („Galaxy S24“), einen Modellcode („SM-S921B“) oder eine IMEI ein und drücke Enter. So wie sie ist: 15 Ziffern, die ersten 14 ohne Prüfziffer oder die 16 der IMEISV, die viele Telefone anzeigen mit"],
    "dispositivi": ["devices", "dispositivos", "appareils", "Geräte"],
    "dispositivo": ["device", "dispositivo", "appareil", "Gerät"],
    "aggiornamenti": ["updates", "actualizaciones", "mises à jour", "Updates"],
    "aggiornamento": ["update", "actualización", "mise à jour", "Update"],
    "ultima scansione": ["last scan", "último escaneo", "dernière analyse", "letzter Scan"],
    "Modello, codice o IMEI": ["Model, code or IMEI", "Modelo, código o IMEI", "Modèle, code ou IMEI", "Modell, Code oder IMEI"],
    "Le ultime ricerche, di tutti": ["Latest searches, by everyone", "Las últimas búsquedas, de todos", "Les dernières recherches, de tous", "Die letzten Suchen, von allen"],
    "sorriso furbo": ["sly smile", "sonrisa pícara", "sourire malin", "verschmitztes Lächeln"],
    "Forse cercavi:": ["Did you mean:", "Quizá buscabas:", "Vouliez-vous dire :", "Meintest du:"],

    // --- Striscia delle notizie
    "Ultim'ora": ["Breaking", "Última hora", "Dernière heure", "Eilmeldung"],
    "Tutte le novità": ["All news", "Todas las novedades", "Toutes les nouveautés", "Alle Neuigkeiten"],
    "Ultime notizie di aggiornamento": ["Latest update news", "Últimas noticias de actualizaciones", "Dernières nouvelles de mises à jour", "Neueste Update-Meldungen"],
    "Firmware verificato": ["Verified firmware", "Firmware verificado", "Firmware vérifié", "Firmware verifiziert"],
    "firmware verificato": ["verified firmware", "firmware verificado", "firmware vérifié", "Firmware verifiziert"],
    "Ferma o riprendi lo scorrimento": ["Pause or resume scrolling", "Pausar o reanudar el desplazamiento", "Mettre en pause ou reprendre le défilement", "Lauftext anhalten oder fortsetzen"],
    "Opzioni del combattimento: scommesse, armi, imprevisti": ["Fight options: bets, weapons, surprises", "Opciones del combate: apuestas, armas, imprevistos", "Options du combat : paris, armes, imprévus", "Kampfoptionen: Wetten, Waffen, Überraschungen"],
    "Opzioni del combattimento": ["Fight options", "Opciones del combate", "Options du combat", "Kampfoptionen"],
    "Controller: scegli il personaggio e fagli fare le sue mosse": ["Controller: pick a fighter and trigger their moves", "Mando: elige el personaje y haz que use sus movimientos",
      "Manette : choisissez le personnage et lancez ses coups", "Controller: Figur wählen und ihre Angriffe auslösen"],
    "Cambia personaggio": ["Switch fighter", "Cambiar de personaje", "Changer de personnage", "Figur wechseln"],
    "Buco nero": ["Black hole", "Agujero negro", "Trou noir", "Schwarzes Loch"],
    "Colpo finale": ["Finishing move", "Golpe final", "Coup final", "Finaler Schlag"],
    "COLPO FINALE!": ["FINISHING MOVE!", "¡GOLPE FINAL!", "COUP FINAL !", "FINALER SCHLAG!"],
    "Cavallina": ["Leapfrog", "Salto de pídola", "Saute-mouton", "Bocksprung"],
    "Cambio di lato": ["Switch sides", "Cambio de lado", "Changement de côté", "Seitenwechsel"],
    "Colpo insieme": ["Strike together", "Golpe conjunto", "Frappe à deux", "Gemeinsamer Schlag"],
    "Palla di cannone": ["Cannonball", "Bala de cañón", "Boulet de canon", "Kanonenkugel"],
    "SLURP!": ["SLURP!", "¡SLURP!", "SLURP !", "SCHLÜRF!"],
    "PTUI!": ["PTOOEY!", "¡PUAJ!", "PTOUI !", "PFUI!"],
    "SPIAT!": ["SPLAT!", "¡PLAF!", "SPLATCH !", "PLATSCH!"],
    "OPLÀ!": ["HUP!", "¡HOP!", "HOP !", "HOPP!"],
    "CAMBIO!": ["SWITCH!", "¡CAMBIO!", "ON CHANGE !", "WECHSEL!"],
    "ORA!": ["NOW!", "¡AHORA!", "MAINTENANT !", "JETZT!"],
    "VAI!": ["GO!", "¡VAMOS!", "VAS-Y !", "LOS!"],
    "Pugno": ["Punch", "Puñetazo", "Coup de poing", "Schlag"],
    "Calcio": ["Kick", "Patada", "Coup de pied", "Tritt"],
    "Montante": ["Uppercut", "Gancho", "Uppercut", "Aufwärtshaken"],
    "Presa": ["Grab", "Agarre", "Prise", "Griff"],
    "Parata": ["Block", "Bloqueo", "Parade", "Block"],
    "Salto": ["Jump", "Salto", "Saut", "Sprung"],
    "Jetpack": ["Jetpack", "Jetpack", "Jetpack", "Jetpack"],
    "Lancia un oggetto": ["Throw an object", "Lanzar un objeto", "Lancer un objet", "Gegenstand werfen"],
    "Raffica di sfere": ["Sphere barrage", "Ráfaga de esferas", "Rafale de sphères", "Kugelhagel"],
    "Raffica di pugni": ["Punch flurry", "Ráfaga de puñetazos", "Rafale de coups", "Schlaghagel"],
    "Fendente": ["Slash", "Tajo", "Taille", "Hieb"],
    "Affondo": ["Thrust", "Estocada", "Estoc", "Stoß"],
    "Rovescio": ["Backhand", "Revés", "Revers", "Rückhandhieb"],
    "Chiudi le opzioni": ["Close options", "Cerrar opciones", "Fermer les options", "Optionen schließen"],
    "Lotte accese o spente": ["Fights on or off", "Peleas activadas o desactivadas", "Combats activés ou désactivés", "Kämpfe an oder aus"],
    "Spegni le lotte e lascia solo le notizie": ["Turn off the fights and keep only the news", "Apaga las peleas y deja solo las noticias", "Désactiver les combats et ne garder que les nouvelles", "Kämpfe ausschalten, nur die Meldungen behalten"],
    "Accendi le lotte": ["Turn on the fights", "Enciende las peleas", "Activer les combats", "Kämpfe einschalten"],
    "Nessuna novità in archivio per ora: la prossima scansione riempie questa striscia.": [
      "No news in the archive yet: the next scan will fill this strip.",
      "Aún no hay novedades en el archivo: el próximo escaneo llenará esta franja.",
      "Aucune nouveauté dans l'archive pour l'instant : la prochaine analyse remplira ce bandeau.",
      "Noch keine Neuigkeiten im Archiv: Der nächste Scan füllt diese Leiste."],

    // --- Tendina del ring
    "Il ring": ["The ring", "El ring", "Le ring", "Der Ring"],
    "Modalità": ["Modes", "Modos", "Modes", "Modi"],
    "Barre della vita": ["Health bars", "Barras de vida", "Barres de vie", "Lebensbalken"],
    "Super guerrieri": ["Super warriors", "Superguerreros", "Super guerriers", "Superkrieger"],
    // I personaggi nuovi (02/10/2026): maghi e duellanti, con le loro mosse.
    "Personaggi": ["Characters", "Personajes", "Personnages", "Figuren"],
    "Maghi": ["Wizards", "Magos", "Mages", "Zauberer"],
    "Duellanti": ["Duelists", "Duelistas", "Duellistes", "Duellanten"],
    "Scegli i personaggi per vedere le loro mosse.": ["Pick the characters to see their moves.", "Elige los personajes para ver sus movimientos.",
      "Choisissez les personnages pour voir leurs coups.", "Wähle die Figuren, um ihre Angriffe zu sehen."],
    "Trasformazione": ["Transformation", "Transformación", "Transformation", "Verwandlung"],
    "Trasforma i due": ["Transform both", "Transformar a los dos", "Transformer les deux", "Beide verwandeln"],
    "Bazooka": ["Bazooka", "Bazuca", "Bazooka", "Bazooka"],
    "Lanciafiamme": ["Flamethrower", "Lanzallamas", "Lance-flammes", "Flammenwerfer"],
    "Dardi magici": ["Magic bolts", "Dardos mágicos", "Traits magiques", "Zauberpfeile"],
    "Raggio": ["Beam", "Rayo", "Rayon", "Strahl"],
    "Gelo": ["Freeze", "Hielo", "Gel", "Frost"],
    "Rimpicciolisci": ["Shrink", "Encoger", "Rétrécir", "Schrumpfen"],
    "Fulmine": ["Lightning", "Relámpago", "Foudre", "Blitz"],
    "Levitazione": ["Levitation", "Levitación", "Lévitation", "Schweben"],
    "Scudo magico": ["Magic shield", "Escudo mágico", "Bouclier magique", "Zauberschild"],
    "Sparizione": ["Vanish", "Desaparición", "Disparition", "Verschwinden"],
    "Scatto tagliente": ["Dash slash", "Tajo relámpago", "Ruée tranchante", "Blitzschnitt"],
    "Lama lanciata": ["Thrown blade", "Hoja lanzada", "Lame lancée", "Klingenwurf"],
    "Incrocio di lame": ["Blade lock", "Cruce de hojas", "Lames croisées", "Klingenkreuzen"],
    "SOVRACCARICO!": ["OVERDRIVE!", "¡SOBRECARGA!", "SURCHARGE !", "ÜBERLADUNG!"],
    "COLOSSO!": ["COLOSSUS!", "¡COLOSO!", "COLOSSE !", "KOLOSS!"],
    "GRANDE ALBERO!": ["GREAT TREE!", "¡GRAN ÁRBOL!", "GRAND ARBRE !", "GROSSER BAUM!"],
    "CAVALIERE!": ["KNIGHT!", "¡CABALLERO!", "CHEVALIER !", "RITTER!"],
    "MULINELLO!": ["WHIRLWIND!", "¡REMOLINO!", "TOURBILLON !", "WIRBELWIND!"],
    "CREPA!": ["CRACK THE FLOOR!", "¡GRIETA!", "FISSURE !", "RISS!"],
    "KRAK!": ["KRAK!", "¡CRAC!", "KRAK !", "KRACK!"],
    "SBAM!": ["SLAM!", "¡PUM!", "SBAM !", "RUMMS!"],
    "SFERA FINALE!": ["FINAL SPHERE!", "¡ESFERA FINAL!", "SPHÈRE FINALE !", "FINALE SPHÄRE!"],
    "METEORA!": ["METEOR!", "¡METEORO!", "MÉTÉORE !", "METEOR!"],
    "FIUU!": ["FWEEE!", "¡FIU!", "FIOU !", "FIUU!"],
    "KABOOM!": ["KABOOM!", "¡KABUM!", "KABOUM !", "KAWUMM!"],
    "FWOOSH!": ["FWOOSH!", "¡FUUM!", "FWOUSH !", "WUSCH!"],
    "CLONK!": ["CLONK!", "¡CLONC!", "CLONK !", "KLONK!"],
    "SOVRACCARICO II!": ["OVERDRIVE II!", "¡SOBRECARGA II!", "SURCHARGE II !", "ÜBERLADUNG II!"],
    "Mira e spara": ["Aim and fire", "Apunta y dispara", "Viser et tirer", "Zielen und feuern"],
    "MIRA!": ["AIM!", "¡APUNTA!", "VISE !", "ZIELEN!"],
    "PRESO!": ["HIT!", "¡ACERTADO!", "TOUCHÉ !", "TREFFER!"],
    "MANCATO!": ["MISS!", "¡FALLADO!", "RATÉ !", "VERFEHLT!"],
    "Audio": ["Sound", "Sonido", "Son", "Ton"],
    // La corsa infinita (09/10/2026).
    // La corsa che cresce: gemme, armi, forzieri, bottega (09/10/2026, sera).
    "Più monete a terra": ["More coins on the ground", "Más monedas en el suelo", "Plus de pièces au sol", "Mehr Münzen am Boden"],
    "Raccogli da più lontano": ["Pick up from farther away", "Recoge desde más lejos", "Ramasse de plus loin", "Sammle aus größerer Entfernung"],
    "Armi più rapide": ["Faster weapons", "Armas más rápidas", "Armes plus rapides", "Schnellere Waffen"],
    "Armi più grandi": ["Bigger weapons", "Armas más grandes", "Armes plus grandes", "Größere Waffen"],
    "Liv.": ["Lv.", "Niv.", "Niv.", "St."],
    "Bottega": ["Workshop", "Taller", "Boutique", "Werkstatt"],
    "Evoluzione!": ["Evolution!", "¡Evolución!", "Évolution !", "Evolution!"],
    "Al massimo, e oltre": ["Maxed out, and beyond", "Al máximo, y más allá", "Au maximum, et au-delà", "Am Maximum, und darüber hinaus"],
    "Arma nuova": ["New weapon", "Arma nueva", "Nouvelle arme", "Neue Waffe"],
    "Monete": ["Coins", "Monedas", "Pièces", "Münzen"],
    "Forziere!": ["Chest!", "¡Cofre!", "Coffre !", "Truhe!"],
    "Monete in banca": ["Coins in the bank", "Monedas en el banco", "Pièces en banque", "Münzen auf der Bank"],
    "Al massimo": ["Maxed", "Al máximo", "Au max", "Maximal"],
    "in banca": ["in the bank", "en el banco", "en banque", "auf der Bank"],
    "Calamita": ["Magnet", "Imán", "Aimant", "Magnet"],
    "Ricarica": ["Cooldown", "Recarga", "Recharge", "Abklingzeit"],
    "Area": ["Area", "Área", "Zone", "Fläche"],
    "Telefoni in orbita": ["Orbiting phones", "Teléfonos en órbita", "Téléphones en orbite", "Kreisende Handys"],
    "Onda d'urto": ["Shockwave", "Onda expansiva", "Onde de choc", "Druckwelle"],
    "Aura di fuoco": ["Fire aura", "Aura de fuego", "Aura de feu", "Feueraura"],
    "Dardi": ["Darts", "Dardos", "Dards", "Pfeile"],
    "Lama rotante": ["Spinning blade", "Hoja giratoria", "Lame tournoyante", "Drehende Klinge"],
    "Più vita": ["More life", "Más vida", "Plus de vie", "Mehr Leben"],
    "Più forza": ["More strength", "Más fuerza", "Plus de force", "Mehr Kraft"],
    "Corazza": ["Armour", "Coraza", "Cuirasse", "Panzer"],
    "Fortuna": ["Luck", "Suerte", "Chance", "Glück"],
    "Avidità": ["Greed", "Avaricia", "Avidité", "Gier"],
    "Rinascita": ["Rebirth", "Renacer", "Renaissance", "Wiedergeburt"],
    "Tira a te tutte le gemme": ["Pulls every gem to you", "Atrae todas las gemas", "Attire toutes les gemmes", "Zieht alle Edelsteine an"],
    "+10 vita all'inizio": ["+10 life at the start", "+10 de vida al empezar", "+10 de vie au départ", "+10 Leben zu Beginn"],
    "+6% danni": ["+6% damage", "+6% de daño", "+6% de dégâts", "+6% Schaden"],
    "-5% danni presi": ["-5% damage taken", "-5% de daño recibido", "-5% de dégâts subis", "-5% erlittener Schaden"],
    "Forzieri più ricchi, più oggetti": ["Richer chests, more items", "Cofres más ricos, más objetos", "Coffres plus riches, plus d'objets", "Reichere Truhen, mehr Gegenstände"],
    "+10% monete": ["+10% coins", "+10% de monedas", "+10% de pièces", "+10% Münzen"],
    "Si parte con una vita in più": ["Start with one extra life", "Empiezas con una vida más", "On part avec une vie de plus", "Start mit einem Extraleben"],
    "Stormo di telefoni": ["Phone swarm", "Enjambre de teléfonos", "Nuée de téléphones", "Handyschwarm"],
    "Onda gigante": ["Giant wave", "Onda gigante", "Onde géante", "Riesenwelle"],
    "Tempesta": ["Storm", "Tempestad", "Tempête", "Sturm"],
    "Inferno": ["Inferno", "Infierno", "Enfer", "Inferno"],
    "Pioggia di dardi": ["Dart rain", "Lluvia de dardos", "Pluie de dards", "Pfeilregen"],
    "Doppia lama": ["Twin blade", "Doble hoja", "Double lame", "Doppelklinge"],
    "Telefoni che girano intorno e colpiscono": ["Phones circle around you and hit", "Teléfonos que giran a tu alrededor y golpean", "Des téléphones tournent autour de toi et frappent", "Handys kreisen um dich und treffen"],
    "+1 telefono": ["+1 phone", "+1 teléfono", "+1 téléphone", "+1 Handy"],
    "Più veloci": ["Faster", "Más rápidos", "Plus rapides", "Schneller"],
    "Più larghi e più forti": ["Wider and stronger", "Más amplios y más fuertes", "Plus larges et plus forts", "Weiter und stärker"],
    "Un'onda parte da te e spinge via tutti": ["A wave bursts from you and pushes everyone away", "Una onda sale de ti y aparta a todos", "Une onde part de toi et repousse tout le monde", "Eine Welle geht von dir aus und stößt alle weg"],
    "Più spesso": ["More often", "Más a menudo", "Plus souvent", "Öfter"],
    "Più larga": ["Wider", "Más amplia", "Plus large", "Weiter"],
    "Più forte": ["Stronger", "Más fuerte", "Plus fort", "Stärker"],
    "Più spesso e più larga": ["More often and wider", "Más a menudo y más amplia", "Plus souvent et plus large", "Öfter und weiter"],
    "Un fulmine cade su un nemico": ["Lightning strikes an enemy", "Un rayo cae sobre un enemigo", "La foudre frappe un ennemi", "Ein Blitz trifft einen Gegner"],
    "+1 fulmine": ["+1 bolt", "+1 rayo", "+1 éclair", "+1 Blitz"],
    "+2 fulmini": ["+2 bolts", "+2 rayos", "+2 éclairs", "+2 Blitze"],
    "Brucia chi ti sta vicino": ["Burns whoever is close to you", "Quema a quien está cerca de ti", "Brûle ceux qui sont près de toi", "Verbrennt alle in deiner Nähe"],
    "Più forte e più rapida": ["Stronger and faster", "Más fuerte y más rápida", "Plus forte et plus rapide", "Stärker und schneller"],
    "Dardi che cercano il nemico più vicino": ["Darts that seek the nearest enemy", "Dardos que buscan al enemigo más cercano", "Des dards qui cherchent l'ennemi le plus proche", "Pfeile, die den nächsten Gegner suchen"],
    "+1 dardo": ["+1 dart", "+1 dardo", "+1 dard", "+1 Pfeil"],
    "Passano attraverso": ["They pierce through", "Atraviesan", "Ils transpercent", "Sie durchbohren"],
    "Una lama lanciata che torna indietro": ["A thrown blade that comes back", "Una hoja lanzada que vuelve", "Une lame lancée qui revient", "Eine geworfene Klinge, die zurückkehrt"],
    "Più lontano": ["Farther", "Más lejos", "Plus loin", "Weiter weg"],
    "Più grande": ["Bigger", "Más grande", "Plus grande", "Größer"],
    "vita massima": ["max life", "vida máxima", "vie max", "max. Leben"],
    "Vita al massimo": ["Full life", "Vida al máximo", "Vie au maximum", "Volles Leben"],
    "vita": ["life", "vida", "vie", "Leben"],
    "danni": ["damage", "daño", "dégâts", "Schaden"],
    "velocità": ["speed", "velocidad", "vitesse", "Tempo"],
    "danni presi": ["damage taken", "daño recibido", "dégâts subis", "erlittener Schaden"],
    "Colpo finale più in fretta": ["Final move charges faster", "El golpe final carga más rápido", "Le coup final se charge plus vite", "Finale lädt schneller"],
    "La mira gira più piano": ["The aim turns slower", "La mira gira más despacio", "La visée tourne plus lentement", "Das Zielen dreht langsamer"],
    "vita per ogni nemico": ["life per enemy", "vida por enemigo", "vie par ennemi", "Leben pro Gegner"],
    "moneta per ogni nemico": ["coin per enemy", "moneda por enemigo", "pièce par ennemi", "Münze pro Gegner"],
    "Il tuo nome": ["Your name", "Tu nombre", "Ton nom", "Dein Name"],
    "Il tuo nome per la classifica": ["Your name for the leaderboard", "Tu nombre para la clasificación", "Ton nom pour le classement", "Dein Name für die Rangliste"],
    "Invia": ["Send", "Enviar", "Envoyer", "Senden"],
    "punti": ["points", "puntos", "points", "Punkte"],
    "Round": ["Round", "Ronda", "Manche", "Runde"],
    "Esci?": ["Quit?", "¿Salir?", "Quitter ?", "Beenden?"],
    "Pronti…": ["Ready…", "Listos…", "Prêts…", "Bereit…"],
    "Fatto!": ["Done!", "¡Hecho!", "Fait !", "Geschafft!"],
    "Mandalo K.O.": ["Knock them out", "Déjalo K.O.", "Mets-le K.O.", "Schick ihn K.O."],
    "Il capo": ["The boss", "El jefe", "Le chef", "Der Boss"],
    "Nuovo nemico": ["New enemy", "Nuevo enemigo", "Nouvel ennemi", "Neuer Gegner"],
    "Corvaccio": ["Ghoul crow", "Cuervo zombi", "Corbeau zombie", "Zombiekrähe"],
    "Tastiera": ["Keyboard", "Teclado", "Clavier", "Tastatur"],
    "Tema di Halloween": ["Halloween theme", "Tema de Halloween", "Thème d'Halloween", "Halloween-Design"],
    "Accendi il tema di Halloween": ["Turn on the Halloween theme", "Activar el tema de Halloween", "Activer le thème d'Halloween", "Halloween-Design einschalten"],
    "Spegni il tema di Halloween": ["Turn off the Halloween theme", "Desactivar el tema de Halloween", "Désactiver le thème d'Halloween", "Halloween-Design ausschalten"],
    "Comandi da tastiera": ["Keyboard controls", "Controles de teclado", "Commandes au clavier", "Tastatursteuerung"],
    "Tasti predefiniti": ["Default keys", "Teclas predeterminadas", "Touches par défaut", "Standardtasten"],
    "Clicca un tasto e premi quello nuovo (Esc annulla).": ["Click a key, then press the new one (Esc cancels).", "Haz clic en una tecla y pulsa la nueva (Esc cancela).", "Cliquez sur une touche puis appuyez sur la nouvelle (Échap annule).", "Klicke auf eine Taste und drücke die neue (Esc bricht ab)."],
    "Premi un tasto…": ["Press a key…", "Pulsa una tecla…", "Appuyez sur une touche…", "Drücke eine Taste…"],
    "Cammina a sinistra": ["Walk left", "Caminar a la izquierda", "Marcher à gauche", "Nach links gehen"],
    "Cammina a destra": ["Walk right", "Caminar a la derecha", "Marcher à droite", "Nach rechts gehen"],
    "Vola / atterra": ["Fly / land", "Volar / aterrizar", "Voler / atterrir", "Fliegen / landen"],
    "Cambia personaggio": ["Switch fighter", "Cambiar personaje", "Changer de personnage", "Figur wechseln"],
    "Apri il controller": ["Open the controller", "Abrir el mando", "Ouvrir la manette", "Controller öffnen"],
    "Colpo finale / mira": ["Final move / aim", "Golpe final / apuntar", "Coup final / viser", "Finalschlag / zielen"],
    "Oggetto": ["Item", "Objeto", "Objet", "Gegenstand"],
    "Spazio": ["Space", "Espacio", "Espace", "Leertaste"],
    "Invio": ["Enter", "Intro", "Entrée", "Eingabe"],
    "Strisciante": ["Crawler", "Reptante", "Rampant", "Kriecher"],
    "Botto": ["Boomer", "Petardo", "Pétard", "Knaller"],
    "Gonfio": ["Bloater", "Hinchado", "Gonflé", "Aufgeblähter"],
    "Saltatore": ["Leaper", "Saltador", "Sauteur", "Springer"],
    "Corazzato": ["Armored", "Acorazado", "Cuirassé", "Gepanzerter"],
    "Gelido": ["Frosty", "Gélido", "Glacial", "Eisiger"],
    "Bestione": ["Brute", "Bestia", "Brute", "Koloss"],
    "Sputatore": ["Spitter", "Escupidor", "Cracheur", "Spucker"],
    "Rabbioso": ["Rager", "Rabioso", "Enragé", "Rasender"],
    "Draghetto di fuoco": ["Fire drakeling", "Dragoncito de fuego", "Dragonnet de feu", "Feuerdrachling"],
    "Draghetto elettrico": ["Storm drakeling", "Dragoncito eléctrico", "Dragonnet électrique", "Blitzdrachling"],
    "Draghetto velenoso": ["Venom drakeling", "Dragoncito venenoso", "Dragonnet venimeux", "Giftdrachling"],
    "Finale": ["Final", "Final", "Final", "Finale"],
    "Contro": ["Against", "Contra", "Contre", "Gegen"],
    "Round superato!": ["Round cleared!", "¡Ronda superada!", "Manche réussie !", "Runde geschafft!"],
    "Senza un graffio!": ["Without a scratch!", "¡Sin un rasguño!", "Sans une égratignure !", "Ohne einen Kratzer!"],
    "Corsa infinita": ["Endless run", "Carrera infinita", "Course infinie", "Endloslauf"],
    "Combattimento libero": ["Free combat", "Combate libre", "Combat libre", "Freier Kampf"],
    "Scegli come giocare": ["Choose how to play", "Elige cómo jugar", "Choisis comment jouer", "Wähle, wie du spielst"],
    "Sopravvivi a ondate sempre più grandi: armi, livelli, draghetti, capi.": ["Survive ever bigger waves: weapons, levels, drakelings, bosses.", "Sobrevive a oleadas cada vez mayores: armas, niveles, dragoncitos, jefes.", "Survis à des vagues toujours plus grandes : armes, niveaux, dragonnets, boss.", "Überlebe immer größere Wellen: Waffen, Stufen, Drachlinge, Bosse."],
    "Due lottatori, i personaggi che vuoi, oggetti e imprevisti dalla tendina.": ["Two fighters, any characters you like, items and surprises from the menu.", "Dos luchadores, los personajes que quieras, objetos e imprevistos desde el menú.", "Deux combattants, les personnages de ton choix, objets et imprévus depuis le menu.", "Zwei Kämpfer, beliebige Figuren, Gegenstände und Überraschungen aus dem Menü."],
    "Personaggi, oggetti e imprevisti sono del combattimento libero.": ["Characters, items and surprises belong to free combat.", "Personajes, objetos e imprevistos son del combate libre.", "Personnages, objets et imprévus font partie du combat libre.", "Figuren, Gegenstände und Überraschungen gehören zum freien Kampf."],
    "Scegli chi lotta. Round dopo round, finché hai vite.": ["Pick your fighter. Round after round, while you have lives.", "Elige quién lucha. Ronda tras ronda, mientras tengas vidas.", "Choisis qui se bat. Manche après manche, tant qu'il te reste des vies.", "Wähle, wer kämpft. Runde um Runde, solange du Leben hast."],
    "Gioca con": ["Play as", "Jugar con", "Jouer avec", "Spielen mit"],
    "Il tuo record": ["Your best", "Tu récord", "Ton record", "Dein Rekord"],
    "Classifica": ["Leaderboard", "Clasificación", "Classement", "Rangliste"],
    "Scegli un premio": ["Pick a reward", "Elige un premio", "Choisis une récompense", "Wähle eine Belohnung"],
    "Livello": ["Level", "Nivel", "Niveau", "Stufe"],
    "Nuovo": ["New", "Nuevo", "Nouveau", "Neu"],
    "Negozio": ["Shop", "Tienda", "Boutique", "Laden"],
    "Comprato": ["Bought", "Comprado", "Acheté", "Gekauft"],
    "I tuoi oggetti": ["Your items", "Tus objetos", "Tes objets", "Deine Gegenstände"],
    "Avanti": ["Next", "Siguiente", "Suivant", "Weiter"],
    "La corsa è finita": ["The run is over", "La carrera ha terminado", "La course est finie", "Der Lauf ist vorbei"],
    "nemici": ["enemies", "enemigos", "ennemis", "Gegner"],
    "Nuovo record!": ["New record!", "¡Nuevo récord!", "Nouveau record !", "Neuer Rekord!"],
    "Sei in classifica, posizione": ["You're on the leaderboard, position", "Estás en la clasificación, puesto", "Tu es au classement, position", "Du bist in der Rangliste, Platz"],
    "Inviato!": ["Sent!", "¡Enviado!", "Envoyé !", "Gesendet!"],
    "Invio…": ["Sending…", "Enviando…", "Envoi…", "Wird gesendet…"],
    "La classifica globale è sul sito.": ["The global leaderboard is on the website.", "La clasificación global está en el sitio web.", "Le classement mondial est sur le site.", "Die globale Rangliste ist auf der Website."],
    "Ancora": ["Again", "Otra vez", "Encore", "Nochmal"],
    "Classifica globale": ["Global leaderboard", "Clasificación global", "Classement mondial", "Globale Rangliste"],
    "Chiudi": ["Close", "Cerrar", "Fermer", "Schließen"],
    "Classifica non raggiungibile": ["Leaderboard unavailable", "Clasificación no disponible", "Classement indisponible", "Rangliste nicht erreichbar"],
    "Carico la classifica…": ["Loading the leaderboard…", "Cargando la clasificación…", "Chargement du classement…", "Rangliste wird geladen…"],
    "Nessuno ancora: sii il primo!": ["Nobody yet: be the first!", "Nadie todavía: ¡sé el primero!", "Personne encore : sois le premier !", "Noch niemand: sei der Erste!"],
    "SALVO!": ["SAVED!", "¡A SALVO!", "SAUVÉ !", "GERETTET!"],
    "ULTIMA POSSIBILITÀ!": ["LAST CHANCE!", "¡ÚLTIMA OPORTUNIDAD!", "DERNIÈRE CHANCE !", "LETZTE CHANCE!"],
    "K.O.!": ["K.O.!", "¡K.O.!", "K.-O. !", "K.O.!"],
    "Non ancora carico": ["Not charged yet", "Aún no está cargado", "Pas encore chargé", "Noch nicht geladen"],
    "BOOM!": ["BOOM!", "¡BUM!", "BOUM !", "BUMM!"],
    "Cuore d'acciaio": ["Steel heart", "Corazón de acero", "Cœur d'acier", "Stahlherz"],
    "Rimessa a nuovo": ["Good as new", "Como nuevo", "Remis à neuf", "Wie neu"],
    "Una vita in più": ["One more life", "Una vida más", "Une vie de plus", "Ein Leben mehr"],
    "Pugni pesanti": ["Heavy fists", "Puños pesados", "Poings lourds", "Schwere Fäuste"],
    "Passo svelto": ["Quick step", "Paso rápido", "Pas rapide", "Flinker Schritt"],
    "Armeria": ["Armoury", "Armería", "Armurerie", "Waffenkammer"],
    "Pelle dura": ["Thick skin", "Piel dura", "Peau dure", "Dicke Haut"],
    "Energia": ["Energy", "Energía", "Énergie", "Energie"],
    "Occhio fermo": ["Steady eye", "Ojo firme", "Œil sûr", "Ruhiges Auge"],
    "Sete": ["Thirst", "Sed", "Soif", "Durst"],
    "Tasche piene": ["Full pockets", "Bolsillos llenos", "Poches pleines", "Volle Taschen"],
    "Pozione": ["Potion", "Poción", "Potion", "Trank"],
    "Scudo": ["Shield", "Escudo", "Bouclier", "Schild"],
    "Carica": ["Charge", "Carga", "Charge", "Ladung"],
    "Metà vita subito": ["Half your life back, now", "La mitad de la vida al instante", "La moitié de la vie tout de suite", "Sofort das halbe Leben zurück"],
    "Niente danni per sei secondi": ["No damage for six seconds", "Sin daño durante seis segundos", "Aucun dégât pendant six secondes", "Sechs Sekunden lang kein Schaden"],
    "Scoppia intorno a te": ["Explodes around you", "Explota a tu alrededor", "Explose autour de toi", "Explodiert um dich herum"],
    "Ferma tutti i nemici": ["Freezes every enemy", "Congela a todos los enemigos", "Fige tous les ennemis", "Hält alle Gegner an"],
    "Due razzi": ["Two rockets", "Dos cohetes", "Deux roquettes", "Zwei Raketen"],
    "Tre fiammate": ["Three bursts of fire", "Tres llamaradas", "Trois jets de flammes", "Drei Feuerstöße"],
    "Colpo finale pronto": ["Final move ready", "Golpe final listo", "Coup final prêt", "Finale bereit"],
    "Duello": ["Duel", "Duelo", "Duel", "Duell"],
    "Sopravvivenza": ["Survival", "Supervivencia", "Survie", "Überleben"],
    "Gravità lunare": ["Moon gravity", "Gravedad lunar", "Gravité lunaire", "Mondschwerkraft"],
    "Temporale": ["Thunderstorm", "Tormenta", "Orage", "Gewitter"],
    "Jetpack impazziti": ["Crazy jetpacks", "Jetpacks locos", "Jetpacks fous", "Verrückte Jetpacks"],
    "Classici": ["Classics", "Clásicos", "Classiques", "Klassiker"],
    "Pistola a ogni round": ["Pistol every round", "Pistola en cada ronda", "Pistolet à chaque manche", "Pistole in jeder Runde"],
    "Bazooka a ogni round": ["Bazooka every round", "Bazuca en cada ronda", "Bazooka à chaque manche", "Bazooka in jeder Runde"],
    "Lanciafiamme a ogni round": ["Flamethrower every round", "Lanzallamas en cada ronda", "Lance-flammes à chaque manche", "Flammenwerfer in jeder Runde"],
    "furioso": ["furious", "furioso", "furieux", "wütend"],
    "furiosa": ["furious", "furiosa", "furieuse", "wütend"],
    "armato": ["armed", "armado", "armé", "bewaffnet"],
    "armata": ["armed", "armada", "armée", "bewaffnet"],
    "gigante": ["giant", "gigante", "géant", "riesig"],
    "Robot": ["Robot", "Robot", "Robot", "Roboter"],
    "Non è andata": ["That didn't work", "No ha funcionado", "Ça n'a pas marché", "Hat nicht geklappt"],
    "Nome non valido": ["Invalid name", "Nombre no válido", "Nom invalide", "Ungültiger Name"],
    "Punteggio non valido": ["Invalid score", "Puntuación no válida", "Score invalide", "Ungültige Punktzahl"],
    "Troppe corse di fila: riprova fra qualche minuto": ["Too many runs in a row: try again in a few minutes", "Demasiadas carreras seguidas: inténtalo dentro de unos minutos", "Trop de courses d'affilée : réessaie dans quelques minutes", "Zu viele Läufe hintereinander: versuch es in ein paar Minuten"],
    "Troppo lungo": ["Too long", "Demasiado largo", "Trop long", "Zu lang"],
    "Onda energetica": ["Energy wave", "Onda de energía", "Onde d'énergie", "Energiewelle"],
    "Scontro di energie": ["Energy clash", "Choque de energías", "Choc d'énergies", "Energieduell"],
    "Scontro di raggi": ["Beam clash", "Choque de rayos", "Choc de rayons", "Strahlenduell"],
    "Carica l'aura": ["Charge aura", "Cargar el aura", "Charger l'aura", "Aura aufladen"],
    "Teletrasporto": ["Teleport", "Teletransporte", "Téléportation", "Teleport"],
    "Sfera gigante": ["Giant sphere", "Esfera gigante", "Sphère géante", "Riesenkugel"],
    "Disco tagliente": ["Cutting disc", "Disco cortante", "Disque tranchant", "Schneidscheibe"],
    "Lampo accecante": ["Blinding flash", "Destello cegador", "Éclair aveuglant", "Blendblitz"],
    "Barriera": ["Barrier", "Barrera", "Barrière", "Barriere"],
    "Autodistruzione": ["Self-destruct", "Autodestrucción", "Autodestruction", "Selbstzerstörung"],
    "Presa a distanza": ["Remote grip", "Agarre a distancia", "Prise à distance", "Ferngriff"],
    "Scommetti": ["Bet", "Apostar", "Parier", "Wetten"],
    "Gettoni:": ["Tokens:", "Fichas:", "Jetons :", "Chips:"],
    "Ricarica 100": ["Refill 100", "Recargar 100", "Recharger 100", "100 aufladen"],
    "Puntata": ["Stake", "Apuesta", "Mise", "Einsatz"],
    "Tutto": ["All", "Todo", "Tout", "Alles"],
    "Mela": ["Apple", "Manzana", "Pomme", "Apfel"],
    "Punta su chi vince il prossimo K.O.": ["Bet on who wins the next K.O.", "Apuesta por quién gana el próximo K.O.", "Pariez sur le vainqueur du prochain K.O.", "Wette, wer den nächsten K.o. gewinnt."],
    "Gettoni finiti.": ["Out of tokens.", "Sin fichas.", "Plus de jetons.", "Keine Chips mehr."],
    "Gettoni ricaricati.": ["Tokens refilled.", "Fichas recargadas.", "Jetons rechargés.", "Chips aufgeladen."],
    "Metti in campo": ["Put in play", "Poner en juego", "Mettre en jeu", "Ins Spiel bringen"],
    "Telefono": ["Phone", "Teléfono", "Téléphone", "Telefon"],
    "Tablet": ["Tablet", "Tableta", "Tablette", "Tablet"],
    "Portatile": ["Laptop", "Portátil", "Ordinateur portable", "Laptop"],
    "Pistola": ["Pistol", "Pistola", "Pistolet", "Pistole"],
    "Spada": ["Sword", "Espada", "Épée", "Schwert"],
    "Bomba": ["Bomb", "Bomba", "Bombe", "Bombe"],
    "Pieghevole": ["Foldable", "Plegable", "Pliable", "Faltbares"],
    "Imprevisti": ["Surprises", "Imprevistos", "Imprévus", "Überraschungen"],
    "Gravità": ["Gravity", "Gravedad", "Gravité", "Schwerkraft"],
    "Terra": ["Earth", "Tierra", "Terre", "Erde"],
    "Luna": ["Moon", "Luna", "Lune", "Mond"],
    "Spazio": ["Space", "Espacio", "Espace", "Weltraum"],
    "Giove": ["Jupiter", "Júpiter", "Jupiter", "Jupiter"],
    "Sottosopra (verso il tetto)": ["Upside down (towards the ceiling)", "Al revés (hacia el techo)", "À l'envers (vers le plafond)", "Kopfüber (zur Decke)"],
    "Pioggia": ["Rain", "Lluvia", "Pluie", "Regen"],
    "Uragano": ["Hurricane", "Huracán", "Ouragan", "Wirbelsturm"],
    "Al rallentatore": ["Slow motion", "A cámara lenta", "Au ralenti", "Zeitlupe"],
    "Terremoto": ["Earthquake", "Terremoto", "Séisme", "Erdbeben"],
    "Meteoriti": ["Meteorites", "Meteoritos", "Météorites", "Meteoriten"],
    "Orda di zombie": ["Zombie horde", "Horda de zombis", "Horde de zombies", "Zombiehorde"],
    "Jetpack a tutti": ["Jetpacks for all", "Jetpacks para todos", "Jetpacks pour tous", "Jetpacks für alle"],
    "Pioggia di telefoni": ["Phone shower", "Lluvia de teléfonos", "Pluie de téléphones", "Telefonregen"],
    "Pioggia di oggetti": ["Item shower", "Lluvia de objetos", "Pluie d'objets", "Gegenstandsregen"],
    "Fumogeno": ["Smoke bomb", "Bomba de humo", "Fumigène", "Rauchbombe"],
    "Barattolo di fuoco": ["Fire jar", "Tarro de fuego", "Bocal de feu", "Feuerglas"],
    "Barattolo di fulmini": ["Lightning jar", "Tarro de rayos", "Bocal de foudre", "Blitzglas"],
    "Barattolo d'acqua": ["Water jar", "Tarro de agua", "Bocal d'eau", "Wasserglas"],
    "VINCE!": ["WINS!", "¡GANA!", "GAGNE !", "GEWINNT!"],
    "FUORI DAL RING!": ["OUT OF THE RING!", "¡FUERA DEL RING!", "HORS DU RING !", "RAUS AUS DEM RING!"],
    "NUOVA PARTITA!": ["NEW MATCH!", "¡NUEVA PARTIDA!", "NOUVELLE PARTIE !", "NEUES SPIEL!"],
    "ROBOT": ["ROBOT", "ROBOT", "ROBOT", "ROBOTER"],
    "MELA": ["APPLE", "MANZANA", "POMME", "APFEL"],
    "Furia": ["Fury", "Furia", "Furie", "Raserei"],
    "Esplodi il robot": ["Blow up the robot", "Explota el robot", "Faire exploser le robot", "Roboter sprengen"],
    "Esplodi la mela": ["Blow up the apple", "Explota la manzana", "Faire exploser la pomme", "Apfel sprengen"],
    "Imprevisti a sorpresa": ["Random surprises", "Imprevistos por sorpresa", "Imprévus surprises", "Zufällige Überraschungen"],
    "Schizzi e arti staccati": ["Splashes and severed limbs", "Salpicaduras y miembros cortados", "Éclaboussures et membres arrachés", "Spritzer und abgetrennte Glieder"],
    "Ricomincia il round": ["Restart the round", "Reiniciar el asalto", "Recommencer le round", "Runde neu starten"],

    // --- Estensione del browser e Premium
    "Spegni le lotte": ["Turn off the fights", "Apaga las peleas", "Désactiver les combats", "Kämpfe ausschalten"],
    "Premium attivo.": ["Premium is active.", "Premium activo.", "Premium actif.", "Premium ist aktiv."],
    "Questa funzione fa parte di Premium.": ["This feature is part of Premium.", "Esta función forma parte de Premium.", "Cette fonction fait partie de Premium.", "Diese Funktion gehört zu Premium."],
    "Premium sblocca i personaggi (super guerrieri, maghi e duellanti) con le loro mosse, le armi e le bombe, il meteo, i meteoriti, il buco nero, l'orda di zombie e la gravità.": [
      "Premium unlocks the characters (super warriors, wizards and duelists) with their moves, weapons and bombs, weather, meteorites, the black hole, the zombie horde and gravity.",
      "Premium desbloquea los personajes (superguerreros, magos y duelistas) con sus movimientos, las armas y las bombas, el clima, los meteoritos, el agujero negro, la horda de zombis y la gravedad.",
      "Premium débloque les personnages (super guerriers, mages et duellistes) et leurs coups, les armes et les bombes, la météo, les météorites, le trou noir, la horde de zombies et la gravité.",
      "Premium schaltet die Figuren (Superkrieger, Zauberer und Duellanten) mit ihren Angriffen, Waffen und Bomben, Wetter, Meteoriten, das Schwarze Loch, die Zombiehorde und Schwerkraft frei."],
    "Per ora è gratis: un clic qui sotto e si apre tutto.": ["For now it is free: one click below unlocks everything.", "Por ahora es gratis: un clic aquí abajo y se abre todo.",
      "Pour l'instant c'est gratuit : un clic ci-dessous et tout s'ouvre.", "Im Moment ist es gratis: ein Klick hier unten schaltet alles frei."],
    "Sblocca Premium gratis": ["Unlock Premium for free", "Desbloquear Premium gratis", "Débloquer Premium gratuitement", "Premium gratis freischalten"],
    // Le scritte disegnate nel ring (i versi restano uguali in ogni lingua).
    "AHIA!": ["OUCH!", "¡AY!", "AÏE !", "AUA!"],
    "OPS!": ["OOPS!", "¡UPS!", "OUPS !", "UPS!"],
    "PARATO!": ["BLOCKED!", "¡PARADO!", "PARÉ !", "GEBLOCKT!"],
    "SCIVOLONE!": ["SLIPPED!", "¡RESBALÓN!", "GLISSADE !", "AUSGERUTSCHT!"],
    "SCOTTA!": ["HOT!", "¡QUEMA!", "ÇA BRÛLE !", "HEISS!"],
    "DAI!": ["GO!", "¡VAMOS!", "ALLEZ !", "LOS!"],
    "TREGUA!": ["TRUCE!", "¡TREGUA!", "TRÊVE !", "WAFFENRUHE!"],
    "Ondata": ["Wave", "Oleada", "Vague", "Welle"],
    "CINQUE!": ["HIGH FIVE!", "¡CHOCA!", "TOPE LÀ !", "HIGH FIVE!"],
    "SU!": ["UP!", "¡ARRIBA!", "DEBOUT !", "AUF!"],
    "TIÈ!": ["TAKE THAT!", "¡TOMA!", "TIENS !", "NIMM DAS!"],
    "VOLA!": ["FLY!", "¡A VOLAR!", "VOLE !", "FLIEG!"],
    "NOTIFICA!": ["PING!", "¡AVISO!", "NOTIF !", "PLING!"],
    "CTRL+ALT+CANC!": ["CTRL+ALT+DEL!", "¡CTRL+ALT+SUPR!", "CTRL+ALT+SUPPR !", "STRG+ALT+ENTF!"],
    "Come funziona": ["How it works", "Cómo funciona", "Comment ça marche", "So funktioniert es"],
    "Tasto di accensione su tutti i siti": ["Power button on every site", "Botón de encendido en todos los sitios", "Bouton de mise en marche sur tous les sites", "Einschaltknopf auf allen Websites"],
    "Sblocca Premium": ["Unlock Premium", "Desbloquear Premium", "Débloquer Premium", "Premium freischalten"],
    "Premium arriva presto": ["Premium is coming soon", "Premium llegará pronto", "Premium arrive bientôt", "Premium kommt bald"],
    "Premium di prova (solo in questa versione)": ["Trial Premium (this build only)", "Premium de prueba (solo en esta versión)", "Premium d'essai (cette version uniquement)", "Premium zum Testen (nur in dieser Version)"],

    // --- Novità
    "Cerca fra le novità": ["Search the news", "Buscar en las novedades", "Rechercher dans les nouveautés", "In den Neuigkeiten suchen"],
    "Cerca fra le novità: modello, build…": ["Search the news: model, build…", "Buscar en las novedades: modelo, build…", "Rechercher dans les nouveautés : modèle, build…", "In den Neuigkeiten suchen: Modell, Build…"],
    "Firmware verificati": ["Verified firmware", "Firmware verificados", "Firmwares vérifiés", "Verifizierte Firmware"],
    "Notizie": ["Articles", "Noticias", "Articles", "Meldungen"],
    "Tutte le marche": ["All brands", "Todas las marcas", "Toutes les marques", "Alle Marken"],
    "Tipo di novità": ["Type of news", "Tipo de novedad", "Type de nouveauté", "Art der Neuigkeit"],
    "Periodo": ["Period", "Periodo", "Période", "Zeitraum"],
    "Ieri": ["Yesterday", "Ayer", "Hier", "Gestern"],
    "Oggi": ["Today", "Hoy", "Aujourd'hui", "Heute"],
    "Leggi": ["Read", "Leer", "Lire", "Lesen"],
    "Nessuna novità": ["No news", "Sin novedades", "Aucune nouveauté", "Keine Neuigkeiten"],

    // --- Schede dei risultati
    "Aggiungi al parco di test": ["Add to the test fleet", "Añadir al parque de pruebas", "Ajouter au parc de test", "Zu den Testgeräten hinzufügen"],
    "Anno": ["Year", "Año", "Année", "Jahr"],
    "Archiviazione": ["Storage", "Almacenamiento", "Stockage", "Speicher"],
    "Batteria": ["Battery", "Batería", "Batterie", "Akku"],
    "Carica anche il firmware": ["Load the firmware too", "Cargar también el firmware", "Charger aussi le firmware", "Auch die Firmware laden"],
    "Cerco il firmware più recente…": ["Looking for the latest firmware…", "Buscando el firmware más reciente…", "Recherche du firmware le plus récent…", "Suche die neueste Firmware…"],
    "Codice modello": ["Model code", "Código de modelo", "Code modèle", "Modellcode"],
    "Confronta con un altro modello": ["Compare with another model", "Comparar con otro modelo", "Comparer avec un autre modèle", "Mit einem anderen Modell vergleichen"],
    "Confronto fra le fonti IMEI": ["Comparison of IMEI sources", "Comparación entre fuentes IMEI", "Comparaison des sources IMEI", "Vergleich der IMEI-Quellen"],
    "Controlla lo stesso IMEI su un'altra fonte:": ["Check the same IMEI on another source:", "Comprueba el mismo IMEI en otra fuente:", "Vérifiez le même IMEI sur une autre source :", "Dieselbe IMEI bei einer anderen Quelle prüfen:"],
    "Cosa è successo": ["What happened", "Qué ha pasado", "Ce qui s'est passé", "Was passiert ist"],
    "Data": ["Date", "Fecha", "Date", "Datum"],
    "Fonte": ["Source", "Fuente", "Source", "Quelle"],
    "IMEI riconosciuto:": ["IMEI recognised:", "IMEI reconocido:", "IMEI reconnu :", "IMEI erkannt:"],
    "Il modello è sbagliato? Correggilo": ["Wrong model? Fix it", "¿Modelo equivocado? Corrígelo", "Mauvais modèle ? Corrigez-le", "Falsches Modell? Korrigiere es"],
    "Marca": ["Brand", "Marca", "Marque", "Marke"],
    "Modello": ["Model", "Modelo", "Modèle", "Modell"],
    "Non è il nome giusto?": ["Not the right name?", "¿No es el nombre correcto?", "Ce n'est pas le bon nom ?", "Nicht der richtige Name?"],
    "Processore": ["Processor", "Procesador", "Processeur", "Prozessor"],
    "Rete": ["Network", "Red", "Réseau", "Netz"],
    "Salva questo modello": ["Save this model", "Guardar este modelo", "Enregistrer ce modèle", "Dieses Modell speichern"],
    "Salva questo nome": ["Save this name", "Guardar este nombre", "Enregistrer ce nom", "Diesen Namen speichern"],
    "Scheda completa del dispositivo in archivio": ["Full device sheet in the archive", "Ficha completa del dispositivo en el archivo", "Fiche complète de l'appareil dans l'archive", "Vollständiges Gerätedatenblatt im Archiv"],
    "Tipo": ["Type", "Tipo", "Type", "Typ"],
    "Versione": ["Version", "Versión", "Version", "Version"],
    "non dichiarato": ["not declared", "no declarado", "non déclaré", "nicht angegeben"],
    "MAJOR (nuova release OS)": ["MAJOR (new OS release)", "MAJOR (nueva versión del SO)", "MAJEURE (nouvelle version de l'OS)", "MAJOR (neue OS-Version)"],
    "Su": ["Up", "Arriba", "Haut", "Nach oben"],
    "dal catalogo per questo nome": ["from the catalogue for this name", "del catálogo para este nombre", "du catalogue pour ce nom", "aus dem Katalog für diesen Namen"],
    "Questa fonte non riporta il codice modello": ["This source does not give the model code", "Esta fuente no indica el código de modelo", "Cette source n'indique pas le code modèle", "Diese Quelle nennt den Modellcode nicht"],
    "Le fonti ufficiali e le notizie rispondono in qualche secondo. Il nome e le specifiche disponibili sono già mostrati qui sopra.": [
      "Official sources and news answer in a few seconds. The name and the available specs are already shown above.",
      "Las fuentes oficiales y las noticias responden en unos segundos. El nombre y las especificaciones disponibles ya se muestran arriba.",
      "Les sources officielles et les actualités répondent en quelques secondes. Le nom et les caractéristiques disponibles sont déjà affichés ci-dessus.",
      "Offizielle Quellen und Meldungen antworten in wenigen Sekunden. Name und verfügbare Daten stehen bereits oben."],
    "Scheda tecnica non disponibile per questo modello: il telefono è identificato, mancano solo le specifiche hardware.": [
      "No spec sheet available for this model: the phone is identified, only the hardware specs are missing.",
      "Ficha técnica no disponible para este modelo: el teléfono está identificado, solo faltan las especificaciones de hardware.",
      "Fiche technique indisponible pour ce modèle : le téléphone est identifié, seules les caractéristiques matérielles manquent.",
      "Kein Datenblatt für dieses Modell: Das Telefon ist erkannt, es fehlen nur die Hardwaredaten."],
    "La prima riga è la risposta che l'app usa: l'ordine è la precedenza, non la fortuna.": [
      "The first row is the answer the app uses: the order is precedence, not luck.",
      "La primera fila es la respuesta que usa la app: el orden es la prioridad, no la suerte.",
      "La première ligne est la réponse utilisée par l'appli : l'ordre est la priorité, pas le hasard.",
      "Die erste Zeile ist die Antwort, die die App verwendet: Die Reihenfolge ist Vorrang, kein Zufall."],

    // --- Accesso e registrazione
    "Nome utente": ["Username", "Nombre de usuario", "Nom d'utilisateur", "Benutzername"],
    "Password dimenticata?": ["Forgot your password?", "¿Has olvidado la contraseña?", "Mot de passe oublié ?", "Passwort vergessen?"],
    "Password dimenticata": ["Forgotten password", "Contraseña olvidada", "Mot de passe oublié", "Passwort vergessen"],
    "Solo per il parco di test. Non hai ancora un account?": ["Only for the test fleet. Don't have an account yet?", "Solo para el parque de pruebas. ¿Aún no tienes cuenta?", "Uniquement pour le parc de test. Pas encore de compte ?", "Nur für die Testgeräte. Noch kein Konto?"],
    "Richiedine uno": ["Request one", "Solicita una", "Demandez-en un", "Eines anfordern"],
    "Richiedi un account per il parco di test": ["Request an account for the test fleet", "Solicitar una cuenta para el parque de pruebas", "Demander un compte pour le parc de test", "Konto für die Testgeräte anfordern"],
    "Richiedi un account": ["Request an account", "Solicitar una cuenta", "Demander un compte", "Konto anfordern"],
    "Password (almeno 10 caratteri)": ["Password (at least 10 characters)", "Contraseña (al menos 10 caracteres)", "Mot de passe (au moins 10 caractères)", "Passwort (mindestens 10 Zeichen)"],
    "Conferma password": ["Confirm password", "Confirmar contraseña", "Confirmer le mot de passe", "Passwort bestätigen"],
    "Invia richiesta": ["Send request", "Enviar solicitud", "Envoyer la demande", "Anfrage senden"],
    "Hai già un account approvato? Accedi": ["Already have an approved account? Sign in", "¿Ya tienes una cuenta aprobada? Accede", "Vous avez déjà un compte approuvé ? Connectez-vous", "Schon ein freigegebenes Konto? Anmelden"],
    "Hai già un account approvato?": ["Already have an approved account?", "¿Ya tienes una cuenta aprobada?", "Vous avez déjà un compte approuvé ?", "Schon ein freigegebenes Konto?"],
    "L'account nasce subito ma resta in attesa finché l'amministratore non lo approva: nessuno entra nel parco di test senza una decisione presa da una persona.": [
      "The account is created at once but stays pending until the administrator approves it: nobody enters the test fleet without a decision made by a person.",
      "La cuenta se crea al instante, pero queda pendiente hasta que el administrador la apruebe: nadie entra en el parque de pruebas sin una decisión tomada por una persona.",
      "Le compte est créé tout de suite mais reste en attente jusqu'à l'approbation de l'administrateur : personne n'entre dans le parc de test sans une décision prise par une personne.",
      "Das Konto entsteht sofort, bleibt aber in Wartestellung, bis der Administrator es freigibt: Niemand kommt ohne die Entscheidung eines Menschen zu den Testgeräten."],
    "Inserisci l'indirizzo email dell'account. Se il recupero via email non è attivo, l'amministratore può generarti un link a mano.": [
      "Enter the account's email address. If email recovery is not enabled, the administrator can generate a link for you by hand.",
      "Introduce el correo electrónico de la cuenta. Si la recuperación por correo no está activa, el administrador puede generarte un enlace a mano.",
      "Saisissez l'adresse e-mail du compte. Si la récupération par e-mail n'est pas active, l'administrateur peut vous générer un lien à la main.",
      "Gib die E-Mail-Adresse des Kontos ein. Ist die Wiederherstellung per E-Mail nicht aktiv, kann der Administrator dir von Hand einen Link erzeugen."],
    "Mandami il link": ["Send me the link", "Envíame el enlace", "Envoyez-moi le lien", "Link senden"],
    "Torna all'accesso": ["Back to sign-in", "Volver al acceso", "Retour à la connexion", "Zurück zur Anmeldung"],
    "Password": ["Password", "Contraseña", "Mot de passe", "Passwort"],
    "Email": ["Email", "Correo electrónico", "E-mail", "E-Mail"],
    "va approvato da un amministratore prima di poter essere usato.": [
      "must be approved by an administrator before it can be used.",
      "debe ser aprobada por un administrador antes de poder usarse.",
      "doit être approuvé par un administrateur avant de pouvoir être utilisé.",
      "muss von einem Administrator freigegeben werden, bevor es benutzt werden kann."],

    // --- Confronto e firmware
    "Confronta con il software installato": ["Compare with the installed software", "Comparar con el software instalado", "Comparer avec le logiciel installé", "Mit der installierten Software vergleichen"],
    "Confronta versioni": ["Compare versions", "Comparar versiones", "Comparer les versions", "Versionen vergleichen"],
    "Forse cercavi anche:": ["You may also mean:", "Quizá también buscabas:", "Vous cherchiez peut-être aussi :", "Vielleicht meintest du auch:"],
    "Trova un telefono con hardware simile": ["Find a phone with similar hardware", "Buscar un teléfono con hardware similar", "Trouver un téléphone au matériel similaire", "Telefon mit ähnlicher Hardware finden"],
    "Il modello è riconosciuto, ma nessuna fonte ne pubblica la versione firmware attuale.": [
      "The model is recognised, but no source publishes its current firmware version.",
      "El modelo está reconocido, pero ninguna fuente publica su versión de firmware actual.",
      "Le modèle est reconnu, mais aucune source ne publie sa version de firmware actuelle.",
      "Das Modell ist erkannt, aber keine Quelle veröffentlicht seine aktuelle Firmware-Version."],
    "Ho verificato nella fonte che modello, variante e regione corrispondono al mio telefono.": [
      "I have checked in the source that model, variant and region match my phone.",
      "He comprobado en la fuente que el modelo, la variante y la región coinciden con mi teléfono.",
      "J'ai vérifié dans la source que le modèle, la variante et la région correspondent à mon téléphone.",
      "Ich habe in der Quelle geprüft, dass Modell, Variante und Region zu meinem Telefon passen."],

    // --- Correzione del nome
    "Nome commerciale, scritto a mano": ["Commercial name, typed by hand", "Nombre comercial, escrito a mano", "Nom commercial, saisi à la main", "Handelsname, von Hand eingegeben"],
    "Non trovi il nome giusto? Scrivilo tu": ["Can't find the right name? Type it yourself", "¿No encuentras el nombre correcto? Escríbelo tú", "Vous ne trouvez pas le bon nom ? Saisissez-le", "Richtiger Name nicht dabei? Gib ihn selbst ein"],
    "altre varianti:": ["other variants:", "otras variantes:", "autres variantes :", "weitere Varianten:"],
    "Vale per ogni ricerca futura di questo codice, con qualsiasi dei suoi nomi — non solo con quello scritto ora.": [
      "It applies to every future search for this code, under any of its names, not only the one typed now.",
      "Vale para todas las búsquedas futuras de este código, con cualquiera de sus nombres, no solo con el escrito ahora.",
      "Cela vaut pour toute recherche future de ce code, sous n'importe lequel de ses noms, pas seulement celui saisi maintenant.",
      "Gilt für jede künftige Suche nach diesem Code, unter jedem seiner Namen, nicht nur dem jetzt eingegebenen."],
    "Usalo solo se nessuna delle forme sopra è quella giusta: a differenza di quelle — verificate dal dataset o costruite dalla marca nota — un nome scritto qui non è garantito trovare una scheda tecnica.": [
      "Use it only if none of the forms above is right: unlike those (verified by the dataset or built from the known brand), a name typed here is not guaranteed to find a spec sheet.",
      "Úsalo solo si ninguna de las formas de arriba es la correcta: a diferencia de aquellas (verificadas por el conjunto de datos o construidas a partir de la marca conocida), un nombre escrito aquí no garantiza encontrar una ficha técnica.",
      "À utiliser seulement si aucune des formes ci-dessus n'est la bonne : contrairement à celles-ci (vérifiées par le jeu de données ou construites à partir de la marque connue), un nom saisi ici ne garantit pas de trouver une fiche technique.",
      "Nur verwenden, wenn keine der Formen oben stimmt: Anders als diese (vom Datensatz geprüft oder aus der bekannten Marke gebildet) findet ein hier eingegebener Name nicht sicher ein Datenblatt."],
  };

  // Pezzi di frase dentro righe che contengono anche dati (codici, SoC).
  var FRAMMENTI = [
    ["Controllo versione ufficiale (endpoint FOTA)", ["Official version check (FOTA endpoint)", "Comprobación de versión oficial (endpoint FOTA)", "Vérification de version officielle (endpoint FOTA)", "Offizielle Versionsprüfung (FOTA-Endpunkt)"]],
    ["(ricerca diretta)", ["(direct lookup)", "(búsqueda directa)", "(recherche directe)", "(Direktsuche)"]],
    ["nuova release OS", ["new OS release", "nueva versión del SO", "nouvelle version de l'OS", "neue OS-Version"]],
  ];

  // «N unità fa», nelle quattro lingue.
  var UNITA = {
    secondo: [["second", "seconds"], ["segundo", "segundos"], ["seconde", "secondes"], ["Sekunde", "Sekunden"]],
    min: [["min", "min"], ["min", "min"], ["min", "min"], ["Min.", "Min."]],
    minuto: [["minute", "minutes"], ["minuto", "minutos"], ["minute", "minutes"], ["Minute", "Minuten"]],
    ora: [["hour", "hours"], ["hora", "horas"], ["heure", "heures"], ["Stunde", "Stunden"]],
    giorno: [["day", "days"], ["día", "días"], ["jour", "jours"], ["Tag", "Tagen"]],
    settimana: [["week", "weeks"], ["semana", "semanas"], ["semaine", "semaines"], ["Woche", "Wochen"]],
    mese: [["month", "months"], ["mes", "meses"], ["mois", "mois"], ["Monat", "Monaten"]],
    anno: [["year", "years"], ["año", "años"], ["an", "ans"], ["Jahr", "Jahren"]],
  };
  var PLURALI = { secondi: "secondo", minuti: "minuto", ore: "ora", giorni: "giorno", settimane: "settimana", mesi: "mese", anni: "anno" };
  function fa(n, unita, li) {
    var chiave = PLURALI[unita] || unita, u = UNITA[chiave];
    if (!u) return null;
    var nome = u[li][Number(n) === 1 ? 0 : 1];
    return li === 0 ? n + " " + nome + " ago" : li === 1 ? "hace " + n + " " + nome : li === 2 ? "il y a " + n + " " + nome : "vor " + n + " " + nome;
  }
  var CHI = { "il robot": ["the robot", "el robot", "le robot", "der Roboter"], "la mela": ["the apple", "la manzana", "la pomme", "der Apfel"] };
  var SU_CHI = { "sul robot": ["on the robot", "al robot", "sur le robot", "auf den Roboter"], "sulla mela": ["on the apple", "a la manzana", "sur la pomme", "auf den Apfel"] };
  // I personaggi inventati hanno un nome proprio, uguale in ogni lingua.
  function suChi(testo, li) { return SU_CHI[testo] ? SU_CHI[testo][li] : ["on ", "por ", "sur ", "auf "][li] + testo.slice(3); }
  var FINITI = [" Out of tokens: you can refill them.", " Sin fichas: puedes recargarlas.", " Plus de jetons : vous pouvez les recharger.", " Keine Chips mehr: Du kannst sie aufladen."];

  var REGOLE = [
    [/^(\d+) (secondo|secondi|min|minuto|minuti|ora|ore|giorno|giorni|settimana|settimane|mese|mesi|anno|anni) fa$/, function (m, li) { return fa(m[1], m[2], li); }],
    [/^rilevato (\d+) (\S+) fa$/, function (m, li) {
      var t = fa(m[1], m[2], li);
      return t && [ "detected ", "detectado ", "détecté ", "erkannt " ][li] + t;
    }],
    [/^(\d+) giorni$/, function (m, li) { return m[1] + " " + ["days", "días", "jours", "Tage"][li]; }],
    [/^(\d+)\/(\d+) fonti attive$/, function (m, li) { return m[1] + "/" + m[2] + " " + ["sources active", "fuentes activas", "sources actives", "Quellen aktiv"][li]; }],
    [/^Aggiornamenti di (.+)$/, function (m, li) { return ["Updates for ", "Actualizaciones de ", "Mises à jour de ", "Updates für "][li] + m[1]; }],
    [/^e altre (\d+)$/, function (m, li) { return ["and " + m[1] + " more", "y otras " + m[1], "et " + m[1] + " autres", "und " + m[1] + " weitere"][li]; }],
    [/^Puntati (\d+) gettoni (sul robot|sulla mela|su [A-Z][a-z]+) \(×([\d.]+)\): si decide al prossimo K\.O\.$/, function (m, li) {
      var su = suChi(m[2], li);
      return ["Staked " + m[1] + " tokens " + su + " (×" + m[3] + "): decided at the next K.O.",
              "Apostadas " + m[1] + " fichas " + su + " (×" + m[3] + "): se decide en el próximo K.O.",
              m[1] + " jetons misés " + su + " (×" + m[3] + ") : décision au prochain K.O.",
              m[1] + " Chips " + su + " gesetzt (×" + m[3] + "): Entscheidung beim nächsten K.o."][li];
    }],
    [/^Vinto! Ha vinto (il robot|la mela|[A-Z][a-z]+): \+(\d+) gettoni\.( Gettoni finiti: puoi ricaricarli\.)?$/, function (m, li) {
      var chi = CHI[m[1]] ? CHI[m[1]][li] : m[1];
      return ["You won! Winner: " + chi + ". +" + m[2] + " tokens.", "¡Has ganado! Gana " + chi + ": +" + m[2] + " fichas.",
              "Gagné ! Vainqueur : " + chi + ". +" + m[2] + " jetons.", "Gewonnen! Sieger: " + chi + ". +" + m[2] + " Chips."][li] + (m[3] ? FINITI[li] : "");
    }],
    [/^Perso: ha vinto (il robot|la mela|[A-Z][a-z]+)\. Meno (\d+) gettoni\.( Gettoni finiti: puoi ricaricarli\.)?$/, function (m, li) {
      var chi = CHI[m[1]] ? CHI[m[1]][li] : m[1];
      return ["You lost: " + chi + " won. −" + m[2] + " tokens.", "Has perdido: ha ganado " + chi + ". −" + m[2] + " fichas.",
              "Perdu : " + chi + " a gagné. −" + m[2] + " jetons.", "Verloren: Sieger ist " + chi + ". −" + m[2] + " Chips."][li] + (m[3] ? FINITI[li] : "");
    }],
  ];

  // --- Il motore --------------------------------------------------------
  var PREFISSO = /^([^A-Za-zÀ-ÿ0-9«(]+)([\s\S]+)$/;
  function cerca(corpo, li) {
    if (Object.prototype.hasOwnProperty.call(T, corpo)) return T[corpo][li];
    for (var i = 0; i < REGOLE.length; i++) {
      var m = corpo.match(REGOLE[i][0]);
      if (m) { var r = REGOLE[i][1](m, li); if (r) return r; }
    }
    return null;
  }
  function traduci(testo, lingua) {
    var li = CODICI.indexOf(lingua) - 1;
    if (li < 0 || !testo) return null;
    var m = testo.match(/^(\s*)([\s\S]*?)(\s*)$/), corpo = m[2].replace(/\s+/g, " ");
    if (!corpo) return null;
    var r = cerca(corpo, li);
    if (r === null) {
      // Un simbolo o una faccina davanti («🕓 Recenti», «· 4 mesi fa»), una freccia in fondo («Leggi →»).
      var coda = "", centro = corpo, testa = "";
      var f = centro.match(/^([\s\S]*?)(\s*[→›»]+)$/);
      if (f && f[1]) { centro = f[1]; coda = f[2]; }
      var p = centro.match(PREFISSO);
      if (p && p[2]) { testa = p[1]; centro = p[2]; }
      if (testa || coda) { var r2 = cerca(centro, li); if (r2 !== null) r = testa + r2 + coda; }
    }
    if (r === null) {
      var cambiato = corpo, trovato = false;
      for (var i = 0; i < FRAMMENTI.length; i++) if (cambiato.indexOf(FRAMMENTI[i][0]) >= 0) { cambiato = cambiato.split(FRAMMENTI[i][0]).join(FRAMMENTI[i][1][li]); trovato = true; }
      if (trovato) r = cambiato;
    }
    return r === null ? null : m[1] + r + m[3];
  }

  // FUORI DAL SITO (l'estensione del browser) questo file serve solo come
  // dizionario: `window.__lingueSoloDizionario` dice di non toccare la pagina
  // (né la lingua salvata, né il menu, né `<html lang>`); chi lo carica usa
  // `window.__lingue.copri(radice, lingua)` sulla propria radice.
  var soloDizionario = !!window.__lingueSoloDizionario;
  var lingua = "it";
  if (!soloDizionario) {
    try { var salvata = window.localStorage.getItem(CHIAVE); if (CODICI.indexOf(salvata) >= 0) lingua = salvata; } catch (e) { /* italiano */ }
  }

  var originali = new WeakMap(), scritti = new WeakMap(), attributi = new WeakMap();
  var ATTRIBUTI = ["title", "placeholder", "aria-label"];
  var titoloOriginale = null, titoloScritto = null;

  function daSaltare(el) {
    return !el || (el.closest && el.closest("script, style, noscript, code, pre, textarea, [data-notrad]"));
  }
  function trattaTesto(nodo) {
    if (daSaltare(nodo.parentElement)) return;
    var ora = nodo.nodeValue;
    // Un testo cambiato da qualcun altro (non da qui) è un nuovo originale.
    if (!originali.has(nodo) || scritti.get(nodo) !== ora) originali.set(nodo, ora);
    var originale = originali.get(nodo);
    var nuovo = lingua === "it" ? originale : (traduci(originale, lingua) || originale);
    if (nuovo !== ora) nodo.nodeValue = nuovo;
    scritti.set(nodo, nuovo);
  }
  function trattaAttributi(el) {
    if (!el.getAttribute || daSaltare(el)) return;
    var memoria = attributi.get(el);
    for (var i = 0; i < ATTRIBUTI.length; i++) {
      var a = ATTRIBUTI[i], ora = el.getAttribute(a);
      if (ora === null) continue;
      if (!memoria) { memoria = {}; attributi.set(el, memoria); }
      var voce = memoria[a];
      if (!voce || voce.scritto !== ora) voce = memoria[a] = { originale: ora, scritto: ora };
      var nuovo = lingua === "it" ? voce.originale : (traduci(voce.originale, lingua) || voce.originale);
      if (nuovo !== ora) el.setAttribute(a, nuovo);
      voce.scritto = nuovo;
    }
  }
  function percorri(da) {
    if (!da) return;
    if (da.nodeType === 3) { trattaTesto(da); return; }
    if (da.nodeType !== 1 && da.nodeType !== 11) return;       // 11: una radice shadow
    if (da.nodeType === 1) trattaAttributi(da);
    var giro = document.createTreeWalker(da, 1 | 4 /* elementi e testi */), nodo;
    while ((nodo = giro.nextNode())) {
      if (nodo.nodeType === 3) trattaTesto(nodo); else trattaAttributi(nodo);
    }
  }
  function trattaTitolo() {
    var ora = document.title;
    if (titoloOriginale === null || titoloScritto !== ora) titoloOriginale = ora;
    var nuovo = titoloOriginale;
    if (lingua !== "it") {
      var m = titoloOriginale.match(/^(.*?)( · M\.U\.T)$/);
      var t = m ? traduci(m[1], lingua) : traduci(titoloOriginale, lingua);
      if (t) nuovo = m ? t + m[2] : t;
    }
    if (nuovo !== ora) document.title = nuovo;
    titoloScritto = nuovo;
  }

  function aggiornaTasto() {
    var tasti = document.querySelectorAll("[data-lingua-tasto] [data-lingua-codice]");
    for (var i = 0; i < tasti.length; i++) tasti[i].textContent = lingua.toUpperCase();
    var voci = document.querySelectorAll("[data-lingua-scelta]");
    for (i = 0; i < voci.length; i++) voci[i].setAttribute("aria-checked", voci[i].getAttribute("data-lingua-scelta") === lingua ? "true" : "false");
  }
  function applica() {
    radice.setAttribute("lang", lingua);
    percorri(document.body);
    trattaTitolo();
    aggiornaTasto();
    radice.classList.remove("lingua-attesa");
  }
  function imposta(nuova) {
    if (CODICI.indexOf(nuova) < 0) return;
    lingua = nuova;
    try { window.localStorage.setItem(CHIAVE, lingua); } catch (e) { /* solo per questa pagina */ }
    applica();
    try { window.dispatchEvent(new CustomEvent("mut:lingua", { detail: { lingua: lingua } })); } catch (e) { /* pazienza */ }
  }

  function chiudiMenu() {
    var menu = document.querySelectorAll("[data-lingua-menu]"), tasti = document.querySelectorAll("[data-lingua-tasto]");
    for (var i = 0; i < menu.length; i++) menu[i].hidden = true;
    for (i = 0; i < tasti.length; i++) tasti[i].setAttribute("aria-expanded", "false");
  }

  function avvia() {
    applica();
    document.addEventListener("click", function (e) {
      var scelta = e.target.closest && e.target.closest("[data-lingua-scelta]");
      if (scelta) { imposta(scelta.getAttribute("data-lingua-scelta")); chiudiMenu(); return; }
      var tasto = e.target.closest && e.target.closest("[data-lingua-tasto]");
      if (tasto) {
        var menu = tasto.parentNode.querySelector("[data-lingua-menu]"), apri = menu.hidden;
        chiudiMenu();
        menu.hidden = !apri; tasto.setAttribute("aria-expanded", apri ? "true" : "false");
        return;
      }
      chiudiMenu();
    });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") chiudiMenu(); });
    osserva(document.body);
  }
  // I testi che cambiano dopo: l'esito di una scommessa, un titolo aggiornato, una scheda caricata.
  function osserva(nodo) {
    if (!window.MutationObserver || !nodo) return;
    new MutationObserver(function (cambi) {
      if (lingua === "it") return;
      for (var i = 0; i < cambi.length; i++) {
        var c = cambi[i];
        if (c.type === "characterData") trattaTesto(c.target);
        else if (c.type === "attributes") trattaAttributi(c.target);
        else for (var k = 0; k < c.addedNodes.length; k++) percorri(c.addedNodes[k]);
      }
    }).observe(nodo, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRIBUTI });
  }
  // Traduce una radice a scelta (anche uno shadow DOM) e la tiene tradotta.
  function copri(nodo, nuova) {
    if (CODICI.indexOf(nuova) >= 0) lingua = nuova;
    percorri(nodo);
    osserva(nodo);
  }

  window.__lingue = { imposta: imposta, lingua: function () { return lingua; }, traduci: traduci, codici: CODICI.slice(),
                      chiavi: function () { return Object.keys(T); }, copri: copri };
  if (soloDizionario) return;
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", avvia);
  else avvia();
})();
