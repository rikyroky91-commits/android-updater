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
 * I testi cambiati dopo (un titolo aggiornato da
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
    "Opzioni del combattimento: personaggi, armi, imprevisti": ["Fight options: characters, weapons, surprises", "Opciones del combate: personajes, armas, imprevistos", "Options du combat : personnages, armes, imprévus", "Kampfoptionen: Figuren, Waffen, Überraschungen"],
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
    "Sciame di falene": ["Moth swarm", "Enjambre de polillas", "Nuée de phalènes", "Mottenschwarm"],
    "Catene di rune": ["Rune chains", "Cadenas de runas", "Chaînes de runes", "Runenketten"],
    "Pioggia di stelle": ["Star shower", "Lluvia de estrellas", "Pluie d'étoiles", "Sternenregen"],
    "Maledizione di smeraldo": ["Emerald curse", "Maldición esmeralda", "Malédiction d'émeraude", "Smaragdfluch"],
    "MALEDIZIONE DI SMERALDO!": ["EMERALD CURSE!", "¡MALDICIÓN ESMERALDA!", "MALÉDICTION D'ÉMERAUDE !", "SMARAGDFLUCH!"],
    "SMERALDO!": ["EMERALD!", "¡ESMERALDA!", "ÉMERAUDE !", "SMARAGD!"],
    "LEGATO!": ["BOUND!", "¡ATADO!", "ENCHAÎNÉ !", "GEFESSELT!"],
    "STELLE!": ["STARS!", "¡ESTRELLAS!", "ÉTOILES !", "STERNE!"],
    "Scatto tagliente": ["Dash slash", "Tajo relámpago", "Ruée tranchante", "Blitzschnitt"],
    "Lama lanciata": ["Thrown blade", "Hoja lanzada", "Lame lancée", "Klingenwurf"],
    "Incrocio di lame": ["Blade lock", "Cruce de hojas", "Lames croisées", "Klingenkreuzen"],
    // Il Limit Break (16/10/2026, Riccardo: «il sovraccarico da oggi si chiamerà limit break») ha lo stesso nome in ogni lingua.
    "LIMIT BREAK!": ["LIMIT BREAK!", "¡LIMIT BREAK!", "LIMIT BREAK !", "LIMIT BREAK!"],
    "Limit Break": ["Limit Break", "Limit Break", "Limit Break", "Limit Break"],
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
    "Respinta": ["Repulse", "Repulsión", "Répulsion", "Rückstoß"],
    // Le missioni e il rimescolo della corsa infinita (16/10/2026).
    "Missioni": ["Missions", "Misiones", "Missions", "Missionen"],
    "MISSIONE COMPIUTA!": ["MISSION COMPLETE!", "¡MISIÓN CUMPLIDA!", "MISSION ACCOMPLIE !", "MISSION ERFÜLLT!"],
    "Arriva al round": ["Reach round", "Llega a la ronda", "Atteins la manche", "Erreiche Runde"],
    "Abbatti": ["Defeat", "Derrota a", "Abats", "Besiege"],
    "nemici in una corsa": ["enemies in one run", "enemigos en una partida", "ennemis en une partie", "Gegner in einem Lauf"],
    "Sconfiggi": ["Beat", "Vence a", "Bats", "Besiege"],
    "capo": ["boss", "jefe", "boss", "Boss"],
    "capi in una corsa": ["bosses in one run", "jefes en una partida", "boss en une partie", "Bosse in einem Lauf"],
    "Evolvi": ["Evolve", "Evoluciona", "Fais évoluer", "Entwickle"],
    "armi in una corsa": ["weapons in one run", "armas en una partida", "armes en une partie", "Waffen in einem Lauf"],
    "Evolvi un'arma": ["Evolve a weapon", "Evoluciona un arma", "Fais évoluer une arme", "Entwickle eine Waffe"],
    "Vinci": ["Win", "Gana", "Gagne", "Gewinne"],
    "round senza danni": ["rounds without damage", "rondas sin daño", "manches sans dégâts", "Runden ohne Schaden"],
    "Fai": ["Score", "Haz", "Marque", "Erziele"],
    "Rimescola": ["Reroll", "Barajar", "Relancer", "Neu mischen"],
    "in una corsa": ["in one run", "en una partida", "en une partie", "in einem Lauf"],
    "Premio della corsa": ["Run reward", "Premio de la partida", "Prime de la partie", "Laufprämie"],
    "raccolte": ["collected", "recogidas", "ramassées", "gesammelt"],
    "Crediti": ["Credits", "Créditos", "Crédits", "Credits"],
    "Allena": ["Train", "Entrenar", "Entraîner", "Trainieren"],
    "PERSONAGGI": ["FIGHTERS", "PERSONAJES", "PERSONNAGES", "KÄMPFER"],
    "OSPITE": ["GUEST", "INVITADO", "INVITÉ", "GAST"],
    "Salvali": ["Save them", "Guárdalos", "Sauvegarde", "Sichern"],
    "salvato nell'account": ["saved to your account", "guardado en tu cuenta", "sauvegardé dans ton compte", "im Konto gespeichert"],
    "Ospite: i progressi restano solo su questo dispositivo": ["Guest: progress stays on this device only", "Invitado: el progreso queda solo aquí", "Invité : progrès sur cet appareil seulement", "Gast: Fortschritt nur auf diesem Gerät"],
    "Sei dentro: crediti, potenziamenti dei personaggi, missioni e record sono salvati nel tuo account e li ritrovi su ogni dispositivo.": ["You're in: credits, fighter upgrades, missions and records are saved to your account and follow you to every device.", "Has entrado: créditos, mejoras de los personajes, misiones y récords se guardan en tu cuenta y los encuentras en cualquier dispositivo.", "Tu es connecté : crédits, améliorations, missions et records sont sauvegardés dans ton compte et te suivent partout.", "Du bist angemeldet: Credits, Upgrades, Missionen und Rekorde sind in deinem Konto gespeichert und auf jedem Gerät da."],
    "Stai giocando come ospite: crediti, potenziamenti e record restano solo su questo dispositivo e si perdono se cancelli i dati del browser. Con un account (nick, email e password) li conservi e li ritrovi ovunque.": ["You're playing as a guest: credits, upgrades and records stay on this device only and are lost if you clear browser data. With an account (nickname, email and password) you keep them everywhere.", "Juegas como invitado: créditos, mejoras y récords quedan solo en este dispositivo y se pierden si borras los datos del navegador. Con una cuenta (nick, email y contraseña) los conservas en todas partes.", "Tu joues en invité : crédits, améliorations et records restent sur cet appareil et disparaissent si tu effaces les données du navigateur. Avec un compte (pseudo, e-mail et mot de passe), tu les gardes partout.", "Du spielst als Gast: Credits, Upgrades und Rekorde bleiben nur auf diesem Gerät und gehen verloren, wenn du die Browserdaten löschst. Mit einem Konto (Nick, E-Mail und Passwort) behältst du sie überall."],
    "Crediti insufficienti": ["Not enough credits", "Créditos insuficientes", "Crédits insuffisants", "Nicht genug Credits"],
    "Allenamento": ["Training", "Entrenamiento", "Entraînement", "Training"],
    "Per sempre, solo per questo personaggio": ["Forever, for this fighter only", "Para siempre, solo para este personaje", "Pour toujours, pour ce personnage seulement", "Für immer, nur für diese Figur"],
    "Spendi i crediti in «Allena» prima della prossima corsa: arriverai più lontano.": ["Spend your credits in “Train” before the next run: you will get further.", "Gasta los créditos en «Entrenar» antes de la próxima partida: llegarás más lejos.", "Dépense tes crédits dans « Entraîner » avant la prochaine partie : tu iras plus loin.", "Gib deine Credits vor dem nächsten Lauf unter „Trainieren“ aus: Du kommst weiter."],
    "Tempra": ["Toughness", "Temple", "Endurance", "Zähigkeit"],
    "+12 vita all'inizio": ["+12 starting health", "+12 de vida al empezar", "+12 vie au départ", "+12 Leben zu Beginn"],
    "Colpo": ["Strike", "Golpe", "Frappe", "Schlag"],
    "+8% danni": ["+8% damage", "+8% de daño", "+8% de dégâts", "+8% Schaden"],
    "Riflessi": ["Reflexes", "Reflejos", "Réflexes", "Reflexe"],
    "Parry più facile, contrattacco più forte": ["Easier parry, stronger counter", "Parry más fácil, contraataque más fuerte", "Parry plus facile, contre plus fort", "Leichterer Parry, stärkerer Konter"],
    "Arsenale": ["Arsenal", "Arsenal", "Arsenal", "Arsenal"],
    "L'arma di partenza parte un livello più su": ["Your starting weapon begins one level higher", "El arma inicial empieza un nivel más arriba", "L'arme de départ commence un niveau plus haut", "Die Startwaffe beginnt eine Stufe höher"],
    "Seconda arma": ["Second weapon", "Segunda arma", "Deuxième arme", "Zweite Waffe"],
    "Si parte con una seconda arma": ["Start with a second weapon", "Empiezas con una segunda arma", "On commence avec une deuxième arme", "Start mit einer zweiten Waffe"],
    "Premi": ["Press", "Pulsa", "Appuie sur", "Drücke"],
    "al momento giusto": ["at the right moment", "en el momento justo", "au bon moment", "im richtigen Moment"],
    "rimandala": ["send it back", "devuélvela", "renvoie-la", "schick sie zurück"],
    "RIMANDATA!": ["SENT BACK!", "¡DEVUELTA!", "RENVOYÉE !", "ZURÜCK!"],
    "Fucile-sega": ["Saw rifle", "Rifle sierra", "Fusil-scie", "Sägegewehr"],
    "Bruto armato": ["Armed brute", "Bruto armado", "Brute armée", "Bewaffneter Rohling"],
    "Spara da lontano, sega da vicino": ["Shoots from afar, saws up close", "Dispara de lejos, sierra de cerca", "Tire de loin, scie de près", "Schießt von weitem, sägt aus der Nähe"],
    "Spara da lontano; con la parata, il primo che arriva lo tagli in due (poi si rompe)": ["Shoots from afar; guard with it and the first enemy that comes close is cut in two (then it breaks)", "Dispara de lejos; en guardia, el primero que llega lo partes en dos (luego se rompe)", "Tire de loin ; en garde, le premier qui arrive est coupé en deux (puis elle casse)", "Schießt von weitem; in Deckung wird der Erste, der kommt, zweigeteilt (dann bricht sie)"],
    "CONTRO LETALE!": ["LETHAL COUNTER!", "¡CONTRA LETAL!", "CONTRE LÉTAL !", "TÖDLICHER KONTER!"],
    "CONTRO!": ["COUNTER!", "¡CONTRA!", "CONTRE !", "KONTER!"],
    "mancavano": ["missing", "faltaban", "il manquait", "es fehlten"],
    "Dadi": ["Dice", "Dados", "Dés", "Würfel"],
    "Un rimescolo di carte in più a corsa": ["One more card reroll per run", "Un barajado de cartas más por partida", "Une relance de cartes en plus par partie", "Ein Karten-Neumischen mehr pro Lauf"],
    "LIMIT BREAK II!": ["LIMIT BREAK II!", "¡LIMIT BREAK II!", "LIMIT BREAK II !", "LIMIT BREAK II!"],
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
    // L'arena di lava dell'app Android (12/10/2026)
    "LAVA!": ["LAVA!", "¡LAVA!", "LAVE !", "LAVA!"],
    "SALVO!": ["SAVED!", "¡A SALVO!", "SAUVÉ !", "GERETTET!"],
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
    "Mela": ["Apple", "Manzana", "Pomme", "Apfel"],
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
    // Il menu, la guida e le impostazioni (17/10/2026).
    "A fine corsa metti un nome e finisci nella classifica globale.": ["At the end of a run, enter a name and join the global leaderboard.", "Al final de una partida pon un nombre y entra en la clasificación mundial.", "À la fin d'une course, mets un nom et entre dans le classement mondial.", "Gib am Ende eines Laufs einen Namen ein und komm in die weltweite Bestenliste."],
    "ADESSO!": ["NOW!", "¡AHORA!", "MAINTENANT !", "JETZT!"],
    "Accesa": ["On", "Activado", "Activé", "An"],
    "Acceso": ["On", "Activado", "Activé", "An"],
    "Aggancio, cariche e granate": ["Lock-on, charges and grenades", "Fijar, cargas y granadas", "Verrouillage, charges et grenades", "Anvisieren, Angriffe und Granaten"],
    "Aiuto al parry": ["Parry assist", "Ayuda al parry", "Aide au parry", "Parry-Hilfe"],
    "Alto": ["High", "Alto", "Élevé", "Hoch"],
    "Anello del parry": ["Parry ring", "Anillo del parry", "Anneau du parry", "Parry-Ring"],
    "Audio e volume, dettaglio grafico, aiuti al parry, rallentatore, scossa dello schermo, difficoltà della corsa, tasti.": ["Audio and volume, graphics detail, parry assists, slow motion, screen shake, run difficulty, keys.", "Audio y volumen, detalle gráfico, ayudas al parry, cámara lenta, temblor de pantalla, dificultad, teclas.", "Son et volume, détails graphiques, aides au parry, ralenti, tremblement de l'écran, difficulté, touches.", "Ton und Lautstärke, Grafikdetails, Parry-Hilfen, Zeitlupe, Bildschirmwackeln, Schwierigkeit, Tasten."],
    "Audio, grafica, aiuti al parry, difficoltà, tasti.": ["Audio, graphics, parry assists, difficulty, keys.", "Audio, gráficos, ayudas al parry, dificultad, teclas.", "Son, graphismes, aides au parry, difficulté, touches.", "Ton, Grafik, Parry-Hilfen, Schwierigkeit, Tasten."],
    "Aura, raffica di pugni, onda energetica (super guerrieri; aura e onda anche i maghi).": ["Aura, punch flurry, energy wave (super warriors; mages have aura and wave too).", "Aura, ráfaga de puñetazos, onda de energía (súper guerreros; los magos también tienen aura y onda).", "Aura, rafale de coups, onde d'énergie (super guerriers ; les mages ont aussi l'aura et l'onde).", "Aura, Schlaghagel, Energiewelle (Superkrieger; Magier haben auch Aura und Welle)."],
    "Basso": ["Low", "Bajo", "Faible", "Niedrig"],
    "Basso: meno particelle e niente ombre sfumate, per i computer lenti.": ["Low: fewer particles and no soft shadows, for slow computers.", "Bajo: menos partículas y sin sombras suaves, para ordenadores lentos.", "Faible : moins de particules et pas d'ombres douces, pour les ordinateurs lents.", "Niedrig: weniger Partikel und keine weichen Schatten, für langsame Computer."],
    "Para al momento giusto. A tempo di musica.": ["Parry on time. On the beat.", "Para en el momento justo. Al ritmo de la música.", "Pare au bon moment. En rythme.", "Pariere im richtigen Moment. Im Takt."],
    "1 contro 1": ["1 vs 1", "1 contra 1", "1 contre 1", "1 gegen 1"],
    "Tu contro un lottatore, sulla piattaforma sopra la lava. Para i suoi colpi, buttalo giù, non cadere.": ["You against one fighter, on the platform above the lava. Parry their hits, knock them off, don't fall.", "Tú contra un luchador, en la plataforma sobre la lava. Para sus golpes, tíralo abajo, no caigas.", "Toi contre un combattant, sur la plateforme au-dessus de la lave. Pare ses coups, fais-le tomber, ne tombe pas.", "Du gegen einen Kämpfer, auf der Plattform über der Lava. Pariere seine Schläge, stoß ihn hinunter, fall nicht."],
    "Benvenuto in": ["Welcome to", "Bienvenido a", "Bienvenue dans", "Willkommen bei"],
    "Benvenuto in Page Brawl": ["Welcome to Page Brawl", "Bienvenido a Page Brawl", "Bienvenue dans Page Brawl", "Willkommen bei Page Brawl"],
    "Bottega: potenziamenti per tutti. Allena: caratteristiche per un personaggio solo.": ["Shop: upgrades for everyone. Train: traits for one character.", "Tienda: mejoras para todos. Entrenar: rasgos para un solo personaje.", "Boutique : améliorations pour tous. Entraîner : traits pour un seul personnage.", "Laden: Verbesserungen für alle. Training: Eigenschaften für eine Figur."],
    "Cambia": ["Change", "Cambiar", "Changer", "Ändern"],
    "Cambia il tasto": ["Change key", "Cambiar tecla", "Changer la touche", "Taste ändern"],
    "Camminare.": ["Walk.", "Caminar.", "Marcher.", "Gehen."],
    "Clic su un nemico: lo agganci (mirino rosso) e il tuo eroe pensa prima a lui. Clic di nuovo, o sul vuoto, per sganciare.": ["Click an enemy to lock on (red crosshair): your hero goes for it first. Click again, or on empty space, to release.", "Haz clic en un enemigo para fijarlo (mira roja): tu héroe va primero a por él. Clic de nuevo, o en el vacío, para soltarlo.", "Clique sur un ennemi pour le verrouiller (viseur rouge) : ton héros s'en occupe d'abord. Clique à nouveau, ou dans le vide, pour libérer.", "Klick auf einen Gegner, um ihn anzuvisieren (rotes Fadenkreuz): dein Held kümmert sich zuerst um ihn. Nochmal klicken oder ins Leere, um zu lösen."],
    "Col mouse prendi e lanci lottatori e oggetti. Ogni tasto si cambia nelle impostazioni.": ["With the mouse you grab and throw fighters and objects. Every key can be changed in the settings.", "Con el ratón agarras y lanzas luchadores y objetos. Cada tecla se cambia en los ajustes.", "Avec la souris tu attrapes et lances combattants et objets. Chaque touche se change dans les réglages.", "Mit der Maus packst und wirfst du Kämpfer und Gegenstände. Jede Taste lässt sich in den Einstellungen ändern."],
    "Col parry non prendi danno, il tempo rallenta e parte il contrattacco.": ["A parry takes no damage, time slows down and the counterattack starts.", "Con el parry no recibes daño, el tiempo se ralentiza y sale el contraataque.", "Avec le parry tu ne prends aucun dégât, le temps ralentit et la contre-attaque part.", "Beim Parry nimmst du keinen Schaden, die Zeit wird langsamer und der Konter startet."],
    "Come si gioca": ["How to play", "Cómo se juega", "Comment jouer", "So wird gespielt"],
    "Conferma": ["Confirm", "Confirmar", "Confirmer", "Bestätigen"],
    "Crescere fra una corsa e l'altra": ["Growing between runs", "Crecer entre partidas", "Progresser entre deux courses", "Zwischen den Läufen stärker werden"],
    "Dettaglio grafico": ["Graphics detail", "Detalle gráfico", "Détails graphiques", "Grafikdetails"],
    "Difficile": ["Hard", "Difícil", "Difficile", "Schwer"],
    "Difficoltà della corsa": ["Run difficulty", "Dificultad de la partida", "Difficulté de la course", "Schwierigkeit des Laufs"],
    "Dopo un parry il tempo rallenta per mezzo secondo.": ["After a parry, time slows down for half a second.", "Tras un parry el tiempo se ralentiza medio segundo.", "Après un parry, le temps ralentit une demi-seconde.", "Nach einem Parry wird die Zeit eine halbe Sekunde langsamer."],
    "Due lottatori di pezza si picchiano da soli. Tu puoi comandarne uno, quando vuoi.": ["Two ragdoll fighters brawl on their own. You can take control of one whenever you like.", "Dos luchadores de trapo se pelean solos. Puedes controlar a uno cuando quieras.", "Deux combattants en chiffon se battent tout seuls. Tu peux en diriger un quand tu veux.", "Zwei Stoffpuppen-Kämpfer prügeln sich von selbst. Du kannst jederzeit einen steuern."],
    "Due lottatori sulla pagina che si picchiano da soli. Comandi chi vuoi, scegli i personaggi, lanci oggetti e scateni imprevisti dalla tendina.": ["Two fighters brawling on the page by themselves. Control whoever you want, pick the characters, throw objects and trigger surprises from the menu panel.", "Dos luchadores en la página que se pelean solos. Controla a quien quieras, elige personajes, lanza objetos y desata imprevistos desde el panel.", "Deux combattants sur la page qui se battent tout seuls. Dirige qui tu veux, choisis les personnages, lance des objets et déclenche des imprévus depuis le panneau.", "Zwei Kämpfer auf der Seite, die sich von selbst prügeln. Steuere, wen du willst, wähle Figuren, wirf Gegenstände und löse Überraschungen im Menü aus."],
    "Facile": ["Easy", "Fácil", "Facile", "Leicht"],
    "Ho capito!": ["Got it!", "¡Entendido!", "Compris !", "Verstanden!"],
    "I migliori della corsa infinita, da tutto il mondo.": ["The best endless runs from around the world.", "Las mejores partidas infinitas de todo el mundo.", "Les meilleures courses infinies du monde entier.", "Die besten Endlosläufe aus aller Welt."],
    "INIZIA QUI": ["START HERE", "EMPIEZA AQUÍ", "COMMENCE ICI", "HIER STARTEN"],
    "Il bruto armato tira granate: al lampo bianco premi S e gliela rimandi. Morendo lascia il fucile-sega.": ["The armed brute throws grenades: press S at the white flash to send them back. When it dies it drops the saw rifle.", "El bruto armado lanza granadas: pulsa S en el destello blanco y se la devuelves. Al morir deja el rifle sierra.", "La brute armée lance des grenades : appuie sur S au flash blanc pour la renvoyer. En mourant, elle lâche le fusil-scie.", "Der bewaffnete Rohling wirft Granaten: drück beim weißen Blitz S und schick sie zurück. Stirbt er, lässt er das Sägegewehr fallen."],
    "Il colpo finale, quando la barra è piena. X C V usano gli oggetti raccolti.": ["The finishing move, when the bar is full. X C V use the items you picked up.", "El golpe final, cuando la barra está llena. X C V usan los objetos recogidos.", "Le coup final, quand la barre est pleine. X C V utilisent les objets ramassés.", "Der Finisher, wenn die Leiste voll ist. X C V benutzen die eingesammelten Gegenstände."],
    "Il cuore del gioco: un'orda che cresce senza fermarsi. Para al momento giusto, sali di livello, scegli armi e poteri, batti un capo ogni cinque livelli di minaccia.": ["The heart of the game: a horde that keeps growing. Parry at the right moment, level up, pick weapons and powers, beat a boss every five threat levels.", "El corazón del juego: una horda que no deja de crecer. Para en el momento justo, sube de nivel, elige armas y poderes, vence a un jefe cada cinco niveles de amenaza.", "Le cœur du jeu : une horde qui grandit sans arrêt. Pare au bon moment, monte de niveau, choisis armes et pouvoirs, bats un boss tous les cinq niveaux de menace.", "Das Herz des Spiels: eine Horde, die immer weiter wächst. Pariere im richtigen Moment, steig auf, wähle Waffen und Kräfte, besiege alle fünf Bedrohungsstufen einen Boss."],
    "Il ring è la pagina che stai guardando.": ["The ring is the page you're looking at.", "El ring es la página que estás mirando.", "Le ring, c'est la page que tu regardes.", "Der Ring ist die Seite, die du gerade ansiehst."],
    "Il «!» sopra chi sta per colpire. Premuto troppo presto o troppo tardi, te lo dice il gioco.": ["The «!» above whoever is about to strike. Pressed too early or too late? The game tells you.", "El «!» sobre quien va a golpear. Si pulsas demasiado pronto o tarde, el juego te lo dice.", "Le « ! » au-dessus de celui qui va frapper. Trop tôt ou trop tard ? Le jeu te le dit.", "Das «!» über dem, der gleich zuschlägt. Zu früh oder zu spät gedrückt? Das Spiel sagt es dir."],
    "Impostazioni": ["Settings", "Ajustes", "Réglages", "Einstellungen"],
    "Indietro": ["Back", "Atrás", "Retour", "Zurück"],
    "L'anello che si stringe intorno a te e diventa d'oro quando è il momento del parry.": ["The ring that closes in around you and turns gold when it's time to parry.", "El anillo que se cierra a tu alrededor y se vuelve dorado cuando es el momento del parry.", "L'anneau qui se resserre autour de toi et devient doré quand c'est le moment du parry.", "Der Ring, der sich um dich zusammenzieht und golden wird, wenn es Zeit für den Parry ist."],
    "La carica letale: scintilla rossa, poi la rincorsa. Col parry, contrattacco ad area.": ["The lethal charge: a red spark, then the run-up. Parry it for an area counterattack.", "La carga letal: chispa roja y luego la carrera. Con el parry, contraataque de área.", "La charge mortelle : étincelle rouge, puis l'élan. Avec le parry, contre-attaque de zone.", "Der tödliche Ansturm: roter Funke, dann der Anlauf. Mit Parry ein Flächenkonter."],
    "La corsa finisce qui: il premio in crediti e il riepilogo arrivano lo stesso.": ["The run ends here: you still get the credit reward and the summary.", "La partida termina aquí: el premio en créditos y el resumen llegan igual.", "La course s'arrête ici : la récompense en crédits et le récapitulatif arrivent quand même.", "Der Lauf endet hier: Die Credit-Belohnung und die Übersicht gibt es trotzdem."],
    "La corsa infinita": ["The endless run", "La partida infinita", "La course infinie", "Der Endloslauf"],
    "La finestra del parry dura quattro fotogrammi in più.": ["The parry window lasts four frames longer.", "La ventana del parry dura cuatro fotogramas más.", "La fenêtre du parry dure quatre images de plus.", "Das Parry-Fenster dauert vier Bilder länger."],
    "La guida, mentre la corsa aspetta.": ["The guide, while the run waits.", "La guía, mientras la partida espera.", "Le guide, pendant que la course attend.", "Die Anleitung, während der Lauf wartet."],
    "La minaccia cresce da sola: più nemici, tipi nuovi, un capo ogni cinque livelli.": ["The threat grows by itself: more enemies, new types, a boss every five levels.", "La amenaza crece sola: más enemigos, tipos nuevos, un jefe cada cinco niveles.", "La menace grandit toute seule : plus d'ennemis, de nouveaux types, un boss tous les cinq niveaux.", "Die Bedrohung wächst von selbst: mehr Gegner, neue Arten, alle fünf Stufen ein Boss."],
    "La pagina che stai guardando è il ring: titoli, tasti e immagini sono piattaforme su cui salire.": ["The page you're looking at is the ring: headings, buttons and images are platforms to climb.", "La página que estás mirando es el ring: títulos, botones e imágenes son plataformas.", "La page que tu regardes est le ring : titres, boutons et images sont des plateformes.", "Die Seite, die du ansiehst, ist der Ring: Überschriften, Knöpfe und Bilder sind Plattformen."],
    "Le altre mosse del controller, nell'ordine dei suoi spicchi. H apre il controller.": ["The other controller moves, in the order of its slices. H opens the controller.", "Los demás movimientos del mando, en el orden de sus sectores. H abre el mando.", "Les autres coups de la manette, dans l'ordre de ses parts. H ouvre la manette.", "Die übrigen Controller-Züge in der Reihenfolge der Segmente. H öffnet den Controller."],
    "Le gemme danno esperienza: a ogni livello una carta da scegliere (1 2 3, o frecce e Invio).": ["Gems give experience: each level lets you pick a card (1 2 3, or arrows and Enter).", "Las gemas dan experiencia: en cada nivel eliges una carta (1 2 3, o flechas e Intro).", "Les gemmes donnent de l'expérience : à chaque niveau, une carte à choisir (1 2 3, ou flèches et Entrée).", "Edelsteine geben Erfahrung: Auf jeder Stufe wählst du eine Karte (1 2 3 oder Pfeile und Enter)."],
    "Musica": ["Music", "Música", "Musique", "Musik"],
    "Una base ritmica: i colpi dei nemici cadono sul battito e un «tic» li annuncia un battito prima.": ["A rhythmic beat: enemy hits land on the beat and a \"tick\" warns you one beat earlier.", "Una base rítmica: los golpes enemigos caen en el pulso y un «tic» los anuncia un pulso antes.", "Une base rythmique : les coups ennemis tombent sur le temps et un « tic » les annonce un temps avant.", "Ein rhythmischer Beat: Gegnerangriffe landen auf dem Schlag, ein „Tick“ kündigt sie einen Schlag vorher an."],
    "Ritardo audio": ["Audio delay", "Retraso de audio", "Retard audio", "Audioverzögerung"],
    "Con cuffie o casse Bluetooth il suono arriva tardi: alzalo finché il «tic» e il colpo coincidono.": ["With Bluetooth headphones or speakers sound arrives late: raise it until the \"tick\" and the hit line up.", "Con auriculares o altavoces Bluetooth el sonido llega tarde: súbelo hasta que el «tic» y el golpe coincidan.", "Avec un casque ou une enceinte Bluetooth le son arrive en retard : augmente-le jusqu'à ce que le « tic » et le coup coïncident.", "Mit Bluetooth-Kopfhörern oder -Lautsprechern kommt der Ton zu spät: erhöhe ihn, bis „Tick“ und Treffer zusammenfallen."],
    "Mai": ["Never", "Nunca", "Jamais", "Nie"],
    "Medio": ["Medium", "Medio", "Moyen", "Mittel"],
    "Menu": ["Menu", "Menú", "Menu", "Menü"],
    "Gioca": ["Play", "Jugar", "Jouer", "Spielen"],
    "Menu, guida e impostazioni": ["Menu, guide and settings", "Menú, guía y ajustes", "Menu, guide et réglages", "Menü, Anleitung und Einstellungen"],
    "Missioni: tre alla volta, pagano crediti e salgono di gradino.": ["Missions: three at a time, they pay credits and step up.", "Misiones: tres a la vez, pagan créditos y suben de nivel.", "Missions : trois à la fois, elles rapportent des crédits et montent d'échelon.", "Missionen: drei gleichzeitig, sie bringen Credits und steigen auf."],
    "Monete e premio della corsa diventano crediti.": ["Coins and the run reward become credits.", "Las monedas y el premio de la partida se vuelven créditos.", "Les pièces et la récompense de la course deviennent des crédits.", "Münzen und die Laufbelohnung werden zu Credits."],
    "Muoversi e attaccare": ["Moving and attacking", "Moverse y atacar", "Se déplacer et attaquer", "Bewegen und angreifen"],
    "Nella corsa infinita affronti un'orda che non finisce mai: il segreto è parare al momento giusto.": ["In the endless run you face a horde that never ends: the secret is blocking at the right moment.", "En la partida infinita te enfrentas a una horda sin fin: el secreto es parar en el momento justo.", "Dans la course infinie tu affrontes une horde sans fin : le secret, c'est de parer au bon moment.", "Im Endloslauf triffst du auf eine Horde ohne Ende: Das Geheimnis ist, im richtigen Moment zu parieren."],
    "No": ["No", "No", "Non", "Nein"],
    "Normale": ["Normal", "Normal", "Normal", "Normal"],
    "Ogni azione e il suo tasto: Invio su una riga, poi il tasto nuovo.": ["Every action and its key: Enter on a row, then the new key.", "Cada acción y su tecla: Intro en una fila y luego la tecla nueva.", "Chaque action et sa touche : Entrée sur une ligne, puis la nouvelle touche.", "Jede Aktion und ihre Taste: Enter auf einer Zeile, dann die neue Taste."],
    "PAUSA": ["PAUSE", "PAUSA", "PAUSE", "PAUSE"],
    "Para. Tenuto è guardia: lo scudo davanti a te.": ["Blocks. Held, it's a guard: the shield in front of you.", "Para. Mantenido es guardia: el escudo delante de ti.", "Pare. Maintenu, c'est la garde : le bouclier devant toi.", "Pariert. Gehalten ist es Deckung: der Schild vor dir."],
    "Parata e parry": ["Block and parry", "Parada y parry", "Parade et parry", "Blocken und Parry"],
    "Piena": ["Full", "Completo", "Complet", "Voll"],
    "Quando arriva un colpo, un anello si stringe verso di te. Quando diventa d'oro, premi S: PARRY.": ["When a blow is coming, a ring closes in on you. When it turns gold, press S: PARRY.", "Cuando llega un golpe, un anillo se cierra hacia ti. Cuando se vuelve dorado, pulsa S: PARRY.", "Quand un coup arrive, un anneau se resserre vers toi. Quand il devient doré, appuie sur S : PARRY.", "Wenn ein Schlag kommt, zieht sich ein Ring zu dir zusammen. Wird er golden, drück S: PARRY."],
    "Quanto fanno male i colpi nella corsa: facile un terzo meno, difficile un terzo più.": ["How much hits hurt in the run: easy a third less, hard a third more.", "Cuánto duelen los golpes en la partida: fácil un tercio menos, difícil un tercio más.", "Combien les coups font mal pendant la course : facile un tiers de moins, difficile un tiers de plus.", "Wie sehr Treffer im Lauf wehtun: leicht ein Drittel weniger, schwer ein Drittel mehr."],
    "Questa guida si riapre dal menu (Esc) o dalla tendina, quando vuoi.": ["You can reopen this guide from the menu (Esc) or the panel, whenever you want.", "Esta guía se vuelve a abrir desde el menú (Esc) o el panel cuando quieras.", "Ce guide se rouvre depuis le menu (Échap) ou le panneau, quand tu veux.", "Diese Anleitung öffnest du jederzeit wieder über das Menü (Esc) oder das Bedienfeld."],
    "Rallentatore del parry": ["Parry slow motion", "Cámara lenta del parry", "Ralenti du parry", "Parry-Zeitlupe"],
    "Ridotta": ["Reduced", "Reducido", "Réduit", "Reduziert"],
    "Riprendi": ["Resume", "Continuar", "Reprendre", "Fortsetzen"],
    "Ripristina": ["Reset", "Restablecer", "Réinitialiser", "Zurücksetzen"],
    "Scegli": ["Select", "Elegir", "Choisir", "Wählen"],
    "Scossa dello schermo": ["Screen shake", "Temblor de pantalla", "Tremblement de l'écran", "Bildschirmwackeln"],
    "Sei pagine per imparare tutto: muoversi, attaccare, la parata e il parry col contrattacco, la corsa infinita, l'aggancio, crescere fra una corsa e l'altra.": ["Six pages to learn it all: moving, attacking, blocking and parrying with the counterattack, the endless run, lock-on, growing between runs.", "Seis páginas para aprenderlo todo: moverse, atacar, la parada y el parry con contraataque, la partida infinita, fijar objetivo, crecer entre partidas.", "Six pages pour tout apprendre : se déplacer, attaquer, la parade et le parry avec la contre-attaque, la course infinie, le verrouillage, progresser entre deux courses.", "Sechs Seiten, um alles zu lernen: bewegen, angreifen, blocken und parieren mit Konter, der Endloslauf, Anvisieren, stärker werden zwischen den Läufen."],
    "Sempre": ["Always", "Siempre", "Toujours", "Immer"],
    "Sfoglia": ["Browse", "Pasar", "Feuilleter", "Blättern"],
    "Si torna alla lotta da dove si era rimasti.": ["Back to the fight where you left off.", "Vuelves a la pelea donde lo dejaste.", "Retour au combat là où tu l'avais laissé.", "Zurück zum Kampf, wo du aufgehört hast."],
    "Sicuro? Premi ancora": ["Sure? Press again", "¿Seguro? Pulsa otra vez", "Sûr ? Appuie encore", "Sicher? Nochmal drücken"],
    "Abbandona la corsa": ["Quit the run", "Abandonar la partida", "Abandonner la course", "Lauf abbrechen"],
    "Solo nella corsa": ["Only in the run", "Solo en la partida", "Seulement en course", "Nur im Lauf"],
    "Spenta": ["Off", "Desactivado", "Désactivé", "Aus"],
    "Spento": ["Off", "Desactivado", "Désactivé", "Aus"],
    "Sì": ["Yes", "Sí", "Oui", "Ja"],
    "Tasti": ["Keys", "Teclas", "Touches", "Tasten"],
    "Tre vite. Finite, l'ultima possibilità: un colpo finale a segno ti rimette in piedi.": ["Three lives. Once they're gone, a last chance: a finishing move that lands puts you back on your feet.", "Tres vidas. Al acabarse, la última oportunidad: un golpe final certero te vuelve a poner en pie.", "Trois vies. Une fois épuisées, une dernière chance : un coup final réussi te remet debout.", "Drei Leben. Sind sie weg, die letzte Chance: Ein Finisher, der trifft, bringt dich wieder auf die Beine."],
    "Volare o atterrare; passare all'altro lottatore.": ["Fly or land; switch to the other fighter.", "Volar o aterrizar; pasar al otro luchador.", "Voler ou atterrir ; passer à l'autre combattant.", "Fliegen oder landen; zum anderen Kämpfer wechseln."],
    "Volume": ["Volume", "Volumen", "Volume", "Lautstärke"],
    "SBILANCIATO!": ["STAGGERED!", "¡DESEQUILIBRADO!", "DÉSÉQUILIBRÉ !", "AUS DEM GLEICHGEWICHT!"],
    "GUARDIA ROTTA!": ["GUARD BROKEN!", "¡GUARDIA ROTA!", "GARDE BRISÉE !", "DECKUNG GEBROCHEN!"],
    "COLPO DI GRAZIA!": ["DEATHBLOW!", "¡GOLPE DE GRACIA!", "COUP DE GRÂCE !", "GNADENSTOSS!"],
    "PARRY PERFETTO!": ["PERFECT PARRY!", "¡PARRY PERFECTO!", "PARADE PARFAITE !", "PERFEKTE PARADE!"],
    "CONTRO TOTALE!": ["FULL COUNTER!", "¡CONTRA TOTAL!", "CONTRE TOTAL !", "VOLLER KONTER!"],
    "Equilibrio e guardia": ["Posture and guard", "Equilibrio y guardia", "Équilibre et garde", "Gleichgewicht und Deckung"],
    "Col parry non prendi danno, il tempo rallenta e parte il contrattacco. All'ultimo istante è un PARRY PERFETTO.": ["A parry takes no damage, time slows down and the counter starts. At the very last instant it's a PERFECT PARRY.", "Con el parry no recibes daño, el tiempo se ralentiza y llega el contraataque. En el último instante es un PARRY PERFECTO.", "Avec la parade parfaite tu ne prends aucun dégât, le temps ralentit et la contre-attaque part. Au tout dernier instant, c'est une PARADE PARFAITE.", "Beim Parry nimmst du keinen Schaden, die Zeit wird langsamer und der Konter startet. Im allerletzten Moment ist es eine PERFEKTE PARADE."],
    "Ogni parry toglie equilibrio a chi attacca (la barra sopra la testa). Piena: SBILANCIATO.": ["Every parry breaks the attacker's posture (the bar above the head). Full: STAGGERED.", "Cada parry quita equilibrio a quien ataca (la barra sobre la cabeza). Llena: DESEQUILIBRADO.", "Chaque parade fait perdre l'équilibre à l'attaquant (la barre au-dessus de la tête). Pleine : DÉSÉQUILIBRÉ.", "Jeder Parry nimmt dem Angreifer Gleichgewicht (der Balken über dem Kopf). Voll: AUS DEM GLEICHGEWICHT."],
    "Colpisci chi è sbilanciato: COLPO DI GRAZIA. I nemici normali cadono subito, il capo perde un terzo della vita.": ["Hit a staggered enemy: DEATHBLOW. Normal enemies drop at once, the boss loses a third of its health.", "Golpea a quien está desequilibrado: GOLPE DE GRACIA. Los enemigos normales caen al instante, el jefe pierde un tercio de la vida.", "Frappe celui qui est déséquilibré : COUP DE GRÂCE. Les ennemis normaux tombent aussitôt, le chef perd un tiers de sa vie.", "Triff, wer aus dem Gleichgewicht ist: GNADENSTOSS. Normale Gegner fallen sofort, der Boss verliert ein Drittel seiner Energie."],
    "Anello rosso e «!!»: attacco pericoloso. La parata non basta, serve il parry.": ["Red ring and «!!»: dangerous attack. Blocking isn't enough, you need the parry.", "Anillo rojo y «!!»: ataque peligroso. Bloquear no basta, hace falta el parry.", "Anneau rouge et « !! » : attaque dangereuse. Bloquer ne suffit pas, il faut la parade parfaite.", "Roter Ring und «!!»: gefährlicher Angriff. Blocken reicht nicht, du brauchst den Parry."],
    "Il capo colpisce tre volte di fila. Parale tutte e tre: CONTRO TOTALE.": ["The boss strikes three times in a row. Parry all three: FULL COUNTER.", "El jefe golpea tres veces seguidas. Para las tres: CONTRA TOTAL.", "Le chef frappe trois fois de suite. Pare les trois : CONTRE TOTAL.", "Der Boss schlägt dreimal hintereinander zu. Pariere alle drei: VOLLER KONTER."],
    "La guardia sotto i piedi si consuma a ogni parata. A zero si rompe e resti scoperto: alterna parry e attacchi.": ["The guard under your feet wears down with every block. At zero it breaks and you're open: mix parries and attacks.", "La guardia bajo tus pies se gasta con cada bloqueo. A cero se rompe y quedas al descubierto: alterna parry y ataques.", "La garde sous tes pieds s'use à chaque blocage. À zéro elle se brise et tu restes à découvert : alterne parades et attaques.", "Die Deckung unter deinen Füßen nutzt sich bei jedem Block ab. Bei null bricht sie und du bist offen: wechsle Parry und Angriffe ab."],
    "TROPPO PRESTO!": ["TOO EARLY!", "¡DEMASIADO PRONTO!", "TROP TÔT !", "ZU FRÜH!"],
    "TROPPO TARDI!": ["TOO LATE!", "¡DEMASIADO TARDE!", "TROP TARD !", "ZU SPÄT!"],
    "SQUARCIATO!": ["SLICED!", "¡REBANADO!", "TRANCHÉ !", "ZERTEILT!"],
    "Bruto di brace": ["Ember brute", "Bruto de brasas", "Brute de braise", "Glutbrocken"],
    "Enorme e muscoloso, con la maschera di ferro: tiene la distanza e se gli vai addosso balza via.": ["Huge and muscular, with an iron mask: keeps its distance and leaps away if you close in.", "Enorme y musculoso, con máscara de hierro: mantiene la distancia y salta lejos si te acercas.", "Énorme et musclé, avec un masque de fer : garde ses distances et bondit au loin si tu approches.", "Riesig und muskulös, mit Eisenmaske: hält Abstand und springt weg, wenn du näher kommst."],
    "Spara raffiche e tira granate a parabola; quando ringhia è scoperto.": ["Fires bursts and lobs grenades; when it growls it's open.", "Dispara ráfagas y lanza granadas en parábola; cuando gruñe queda al descubierto.", "Tire des rafales et lance des grenades en cloche ; quand il grogne, il est à découvert.", "Feuert Salven und wirft Granaten im Bogen; wenn er knurrt, ist er offen."],
    "Arriva uno zombie. Guarda le sue braccia: quando le alza, sta per morderti.": ["A zombie is coming. Watch its arms: when it raises them, it's about to bite.", "Llega un zombi. Mira sus brazos: cuando los levanta, va a morderte.", "Un zombie arrive. Regarde ses bras : quand il les lève, il va mordre.", "Ein Zombie kommt. Achte auf seine Arme: Hebt er sie, will er beißen."],
    "Così si ferma un colpo": ["That's how you stop a hit", "Así se detiene un golpe", "Voilà comment on arrête un coup", "So hält man einen Treffer auf"],
    "Ma la guardia si consuma: guarda lo scudo intorno al tasto.": ["But your guard wears down: watch the shield around the button.", "Pero la guardia se gasta: mira el escudo alrededor del botón.", "Mais ta garde s'use : regarde le bouclier autour du bouton.", "Aber die Deckung nutzt sich ab: Achte auf den Schild um die Taste."],
    "Premi {P} proprio quando il colpo arriva. Stavolta fermo il tempo io.": ["Press {P} right as the hit lands. This time I'll stop time for you.", "Pulsa {P} justo cuando llega el golpe. Esta vez detengo yo el tiempo.", "Appuie sur {P} pile quand le coup arrive. Cette fois, j'arrête le temps pour toi.", "Drück {P} genau, wenn der Treffer kommt. Diesmal halte ich die Zeit für dich an."],
    "Niente danni, il tempo rallenta e parte il contrattacco.": ["No damage, time slows down and the counter starts.", "Sin daño, el tiempo se ralentiza y llega el contraataque.", "Aucun dégât, le temps ralentit et la contre-attaque part.", "Kein Schaden, die Zeit wird langsam und der Konter startet."],
    "Adesso da solo": ["Now on your own", "Ahora tú solo", "À toi tout seul", "Jetzt allein"],
    "Quando l'anello intorno al tasto diventa d'oro, premi.": ["When the ring around the button turns gold, press.", "Cuando el anillo alrededor del botón se vuelva dorado, pulsa.", "Quand l'anneau autour du bouton devient doré, appuie.", "Wenn der Ring um die Taste golden wird, drück."],
    "PERFETTO!": ["PERFECT!", "¡PERFECTO!", "PARFAIT !", "PERFEKT!"],
    "Ti aiuto ancora una volta": ["I'll help you one more time", "Te ayudo una vez más", "Je t'aide encore une fois", "Ich helfe dir noch einmal"],
    "Tocca a te!": ["Your turn!", "¡Te toca!", "À toi !", "Du bist dran!"],
    "Arriva l'orda. Ogni nemico nuovo te lo presento quando arriva.": ["Here comes the horde. I'll introduce every new enemy when it shows up.", "Llega la horda. Cada enemigo nuevo te lo presento cuando aparezca.", "Voici la horde. Je te présente chaque nouvel ennemi quand il arrive.", "Die Horde kommt. Jeden neuen Gegner stelle ich dir vor, wenn er auftaucht."],
    "Tieni premuto {P}!": ["Hold {P}!", "¡Mantén {P}!", "Maintiens {P} !", "Halte {P}!"],
    "Premi {P}: agguato con la sega": ["Press {P}: ambush with the saw", "Pulsa {P}: emboscada con la sierra", "Appuie sur {P} : embuscade à la scie", "Drück {P}: Hinterhalt mit der Säge"],
    "Il tempo è fermo: aspetto te": ["Time is frozen: waiting for you", "El tiempo está parado: te espero", "Le temps est figé : je t'attends", "Die Zeit steht still: Ich warte auf dich"],
    "Tocca per continuare": ["Tap to continue", "Toca para continuar", "Touche pour continuer", "Tippen zum Fortfahren"],
    "Zombie": ["Zombie", "Zombi", "Zombie", "Zombie"],
    "Zombie svelto": ["Fast zombie", "Zombi rápido", "Zombie rapide", "Schneller Zombie"],
    "Zombie d'oro": ["Golden zombie", "Zombi de oro", "Zombie doré", "Goldener Zombie"],
    "Bestia armata": ["Armed beast", "Bestia armada", "Bête armée", "Bewaffnete Bestie"],
    "La carica rossa": ["The red charge", "La carga roja", "La charge rouge", "Der rote Ansturm"],
    "il tasto PARATA": ["the GUARD button", "el botón PARADA", "le bouton PARADE", "die PARADE-Taste"],
    "Cosa fa": ["What it does", "Qué hace", "Ce qu'il fait", "Was er tut"],
    "Attacco": ["Attack", "Ataque", "Attaque", "Angriff"],
    "Come fermarlo": ["How to stop it", "Cómo pararlo", "Comment l'arrêter", "So stoppst du ihn"],
    "Come si usa": ["How to use it", "Cómo se usa", "Comment l'utiliser", "So benutzt du sie"],
    "Attenzione": ["Careful", "Atención", "Attention", "Achtung"],
    "Guida": ["Guide", "Guía", "Guide", "Anleitung"],
    "Ho capito": ["Got it", "Entendido", "Compris", "Verstanden"],
    "Salta la guida": ["Skip the guide", "Saltar la guía", "Passer le guide", "Anleitung überspringen"],
    "La tua prima corsa": ["Your first run", "Tu primera carrera", "Ta première course", "Dein erster Lauf"],
    "Il tuo lottatore attacca da solo: tu pensi a difenderti.": ["Your fighter attacks on its own: you take care of defense.", "Tu luchador ataca solo: tú te ocupas de defenderte.", "Ton combattant attaque tout seul : toi, tu t'occupes de la défense.", "Dein Kämpfer greift von selbst an: Du kümmerst dich um die Abwehr."],
    "La difesa è {P}. Ti faccio vedere come si usa, un nemico alla volta.": ["Defense is {P}. I'll show you how to use it, one enemy at a time.", "La defensa es {P}. Te enseño a usarla, un enemigo cada vez.", "La défense, c'est {P}. Je te montre comment l'utiliser, un ennemi à la fois.", "Die Abwehr ist {P}. Ich zeige dir, wie sie geht, ein Gegner nach dem anderen."],
    "La parata": ["The guard", "La parada", "La parade", "Die Parade"],
    "Sta arrivando uno zombie. Quando alza le braccia per morderti, tieni premuto {P}.": ["A zombie is coming. When it raises its arms to bite you, hold {P}.", "Llega un zombi. Cuando levante los brazos para morderte, mantén pulsado {P}.", "Un zombie arrive. Quand il lève les bras pour te mordre, maintiens {P}.", "Ein Zombie kommt. Wenn er die Arme hebt, um zu beißen, halte {P} gedrückt."],
    "Il morso si ferma sulla guardia. Ma tenerla troppo a lungo la consuma.": ["The bite stops on your guard. But holding it too long wears it down.", "El mordisco se detiene en la guardia. Pero mantenerla demasiado la desgasta.", "La morsure s'arrête sur ta garde. Mais la tenir trop longtemps l'use.", "Der Biss prallt an der Deckung ab. Aber zu lange halten nutzt sie ab."],
    "Tieni premuto {P} quando ti morde": ["Hold {P} when it bites", "Mantén {P} cuando muerda", "Maintiens {P} quand il mord", "Halte {P}, wenn er beißt"],
    "PARATO! Così si ferma un colpo.": ["BLOCKED! That's how you stop a hit.", "¡PARADO! Así se detiene un golpe.", "PARÉ ! Voilà comment on arrête un coup.", "GEBLOCKT! So hält man einen Treffer auf."],
    "Troppo tardi: tieni premuto {P} prima del morso": ["Too late: hold {P} before the bite", "Demasiado tarde: mantén {P} antes del mordisco", "Trop tard : maintiens {P} avant la morsure", "Zu spät: halte {P} vor dem Biss"],
    "Il parry": ["The parry", "El parry", "La parade parfaite", "Der Parry"],
    "Il parry è la parata al momento giusto: premi {P} proprio quando il colpo arriva.": ["A parry is a guard at the right moment: press {P} just as the hit lands.", "El parry es la parada en el momento justo: pulsa {P} justo cuando llega el golpe.", "La parade parfaite, c'est parer au bon moment : appuie sur {P} pile quand le coup arrive.", "Der Parry ist die Parade im richtigen Moment: Drück {P} genau, wenn der Treffer kommt."],
    "L'anello intorno al tasto si stringe: quando diventa d'oro, è il momento.": ["The ring around the button closes in: when it turns gold, that's the moment.", "El anillo alrededor del botón se cierra: cuando se vuelve dorado, es el momento.", "L'anneau autour du bouton se resserre : quand il devient doré, c'est le moment.", "Der Ring um die Taste zieht sich zusammen: Wenn er golden wird, ist es so weit."],
    "Stavolta fermo il tempo io e ti dico quando.": ["This time I'll stop time and tell you when.", "Esta vez detengo yo el tiempo y te digo cuándo.", "Cette fois, j'arrête le temps et je te dis quand.", "Diesmal halte ich die Zeit an und sage dir, wann."],
    "Troppo presto: premi solo quando l'anello è d'oro": ["Too early: press only when the ring is gold", "Demasiado pronto: pulsa solo cuando el anillo sea dorado", "Trop tôt : appuie seulement quand l'anneau est doré", "Zu früh: drück erst, wenn der Ring golden ist"],
    "Quasi! Riproviamo": ["Almost! Let's try again", "¡Casi! Probemos otra vez", "Presque ! On recommence", "Fast! Noch einmal"],
    "ORA! Premi {P}": ["NOW! Press {P}", "¡AHORA! Pulsa {P}", "MAINTENANT ! Appuie sur {P}", "JETZT! Drück {P}"],
    "Aspetta che l'anello diventi d'oro…": ["Wait for the ring to turn gold…", "Espera a que el anillo se vuelva dorado…", "Attends que l'anneau devienne doré…", "Warte, bis der Ring golden wird…"],
    "Tocca a te": ["Your turn", "Te toca", "À toi de jouer", "Du bist dran"],
    "Ogni volta che arriva un nemico nuovo te lo presento: cosa fa e come fermarlo.": ["Every time a new enemy shows up I'll introduce it: what it does and how to stop it.", "Cada vez que llegue un enemigo nuevo te lo presento: qué hace y cómo pararlo.", "Chaque fois qu'un nouvel ennemi arrive, je te le présente : ce qu'il fait et comment l'arrêter.", "Jedes Mal, wenn ein neuer Gegner auftaucht, stelle ich ihn dir vor: was er tut und wie du ihn stoppst."],
    "Lento, va giù con due colpi.": ["Slow, goes down in two hits.", "Lento, cae con dos golpes.", "Lent, tombe en deux coups.", "Langsam, fällt nach zwei Treffern."],
    "Carica le braccia e morde da vicino.": ["Winds up its arms and bites up close.", "Carga los brazos y muerde de cerca.", "Arme ses bras et mord de près.", "Holt mit den Armen aus und beißt aus der Nähe."],
    "Tieni premuto {P} quando morde, o fai il parry quando l'anello diventa d'oro.": ["Hold {P} when it bites, or parry when the ring turns gold.", "Mantén {P} cuando muerda, o haz el parry cuando el anillo se vuelva dorado.", "Maintiens {P} quand il mord, ou fais la parade parfaite quand l'anneau devient doré.", "Halte {P}, wenn er beißt, oder pariere, wenn der Ring golden wird."],
    "Veloce e fragile: un colpo e va giù.": ["Fast and fragile: one hit and it's down.", "Rápido y frágil: un golpe y cae.", "Rapide et fragile : un coup et il tombe.", "Schnell und zerbrechlich: ein Treffer und er liegt."],
    "Morde in fretta: la carica è corta.": ["Bites quickly: the wind-up is short.", "Muerde rápido: la carga es corta.", "Mord vite : la préparation est courte.", "Beißt schnell: kurzes Ausholen."],
    "L'anello si chiude presto: premi {P} appena diventa d'oro.": ["The ring closes fast: press {P} as soon as it turns gold.", "El anillo se cierra pronto: pulsa {P} en cuanto se vuelva dorado.", "L'anneau se ferme vite : appuie sur {P} dès qu'il devient doré.", "Der Ring schließt sich schnell: Drück {P}, sobald er golden wird."],
    "Vola a stormi, da quote sempre diverse.": ["Flies in flocks, at ever-changing heights.", "Vuela en bandadas, a alturas siempre distintas.", "Vole en nuées, à des hauteurs toujours différentes.", "Fliegt in Schwärmen, immer in anderer Höhe."],
    "Scende in picchiata a beccare: la parata non lo ferma.": ["Dives down to peck: your guard won't stop it.", "Baja en picado a picotear: la parada no lo detiene.", "Pique pour donner des coups de bec : la parade ne l'arrête pas.", "Stürzt herab und hackt: Die Parade hält ihn nicht auf."],
    "Lascia fare alle armi automatiche e spostati quando scende su di te.": ["Let your automatic weapons handle it and move when it dives at you.", "Deja que actúen las armas automáticas y apártate cuando baje hacia ti.", "Laisse faire tes armes automatiques et écarte-toi quand il fonce sur toi.", "Lass die Automatikwaffen arbeiten und weich aus, wenn er auf dich herabstürzt."],
    "Striscia a terra: i pugni dritti gli passano sopra.": ["Crawls on the ground: straight punches go over it.", "Se arrastra por el suelo: los puñetazos rectos le pasan por encima.", "Rampe au sol : les coups droits passent au-dessus.", "Kriecht am Boden: gerade Schläge gehen drüber."],
    "Morde le gambe da sotto.": ["Bites your legs from below.", "Muerde las piernas desde abajo.", "Mord les jambes par en dessous.", "Beißt von unten in die Beine."],
    "Il morso si para come gli altri: {P} al momento giusto.": ["Its bite can be blocked like the others: {P} at the right moment.", "Su mordisco se para como los demás: {P} en el momento justo.", "Sa morsure se pare comme les autres : {P} au bon moment.", "Sein Biss lässt sich wie die anderen parieren: {P} im richtigen Moment."],
    "Ha una bomba sulla schiena e corre.": ["Carries a bomb on its back and runs.", "Lleva una bomba a la espalda y corre.", "Porte une bombe sur le dos et court.", "Trägt eine Bombe auf dem Rücken und rennt."],
    "Ti arriva addosso e scoppia.": ["Runs into you and explodes.", "Se te echa encima y explota.", "Te fonce dessus et explose.", "Rennt in dich hinein und explodiert."],
    "Abbattilo prima che arrivi: se scoppia in mezzo agli zombie, li fa saltare.": ["Take it down before it reaches you: if it blows up among zombies, it takes them out.", "Derríbalo antes de que llegue: si explota entre zombis, los hace volar.", "Abats-le avant qu'il arrive : s'il explose au milieu des zombies, il les fait sauter.", "Erledige ihn, bevor er ankommt: Explodiert er zwischen Zombies, sprengt er sie mit."],
    "Vola e ti gira intorno.": ["Flies and circles around you.", "Vuela y da vueltas a tu alrededor.", "Vole et tourne autour de toi.", "Fliegt und kreist um dich."],
    "Sputa fuoco dritto: la parata non lo ferma.": ["Breathes fire straight ahead: your guard won't stop it.", "Escupe fuego en línea recta: la parada no lo detiene.", "Crache du feu tout droit : la parade ne l'arrête pas.", "Speit Feuer geradeaus: Die Parade hält es nicht auf."],
    "Esci dalla linea del fuoco, poi colpiscilo quando scende in picchiata.": ["Get out of the line of fire, then hit it when it dives.", "Sal de la línea de fuego y golpéalo cuando baje en picado.", "Sors de la ligne de feu, puis frappe-le quand il pique.", "Raus aus der Feuerlinie, dann triff ihn, wenn er herabstürzt."],
    "Lento e pieno di gas.": ["Slow and full of gas.", "Lento y lleno de gas.", "Lent et plein de gaz.", "Langsam und voller Gas."],
    "Quando scoppia lascia una nube che stende gli zombie e ti fa tossire.": ["When it bursts it leaves a cloud that knocks zombies down and makes you cough.", "Al reventar deja una nube que tumba a los zombis y te hace toser.", "En éclatant, il laisse un nuage qui renverse les zombies et te fait tousser.", "Platzt er, bleibt eine Wolke, die Zombies umwirft und dich husten lässt."],
    "Abbattilo lontano da te, in mezzo agli altri zombie.": ["Take it down away from you, among the other zombies.", "Derríbalo lejos de ti, entre los otros zombis.", "Abats-le loin de toi, au milieu des autres zombies.", "Erledige ihn weit weg von dir, zwischen den anderen Zombies."],
    "Prende la rincorsa e salta da lontano.": ["Takes a run-up and leaps from afar.", "Coge carrerilla y salta desde lejos.", "Prend son élan et saute de loin.", "Nimmt Anlauf und springt von weitem."],
    "Ti piomba addosso e morde appena atterra.": ["Lands on you and bites as soon as it touches down.", "Te cae encima y muerde nada más aterrizar.", "Te tombe dessus et mord dès qu'il atterrit.", "Landet auf dir und beißt sofort."],
    "Guardalo in aria e premi {P} quando tocca terra.": ["Watch it in the air and press {P} when it lands.", "Míralo en el aire y pulsa {P} cuando toque el suelo.", "Suis-le en l'air et appuie sur {P} quand il touche le sol.", "Beobachte ihn in der Luft und drück {P}, wenn er landet."],
    "Vola alto.": ["Flies high.", "Vuela alto.", "Vole haut.", "Fliegt hoch."],
    "Una linea avvisa dove cadrà il fulmine: la parata non lo ferma.": ["A line warns where the lightning will strike: your guard won't stop it.", "Una línea avisa dónde caerá el rayo: la parada no lo detiene.", "Une ligne indique où la foudre tombera : la parade ne l'arrête pas.", "Eine Linie zeigt, wo der Blitz einschlägt: Die Parade hält ihn nicht auf."],
    "Quando vedi la linea, spostati da lì.": ["When you see the line, move away from it.", "Cuando veas la línea, apártate de ahí.", "Quand tu vois la ligne, éloigne-toi.", "Siehst du die Linie, geh da weg."],
    "Elmo e piastra: i colpi deboli gli fanno metà.": ["Helmet and plate: weak hits do half damage.", "Casco y placa: los golpes débiles le hacen la mitad.", "Casque et plastron : les coups faibles font moitié moins.", "Helm und Platte: Schwache Treffer machen nur halben Schaden."],
    "Morde come gli altri.": ["Bites like the others.", "Muerde como los demás.", "Mord comme les autres.", "Beißt wie die anderen."],
    "Fai il parry: il contrattacco e i colpi forti passano la corazza.": ["Parry it: the counter and strong hits get through the armor.", "Haz el parry: el contraataque y los golpes fuertes atraviesan la coraza.", "Fais la parade parfaite : la contre-attaque et les coups forts traversent l'armure.", "Pariere: Der Konter und starke Treffer gehen durch die Rüstung."],
    "Freddo e resistente.": ["Cold and tough.", "Frío y resistente.", "Froid et résistant.", "Kalt und zäh."],
    "Il suo morso ti rallenta.": ["Its bite slows you down.", "Su mordisco te ralentiza.", "Sa morsure te ralentit.", "Sein Biss verlangsamt dich."],
    "Non farti mordere: para o fai il parry con {P}.": ["Don't get bitten: block or parry with {P}.", "Que no te muerda: para o haz el parry con {P}.", "Ne te fais pas mordre : pare ou fais la parade parfaite avec {P}.", "Lass dich nicht beißen: Blocke oder pariere mit {P}."],
    "Enorme: ci vogliono sei colpi.": ["Huge: it takes six hits.", "Enorme: hacen falta seis golpes.", "Énorme : il faut six coups.", "Riesig: braucht sechs Treffer."],
    "Una manata che butta a terra e consuma molta guardia.": ["A slap that knocks you down and drains a lot of guard.", "Un manotazo que te tumba y gasta mucha guardia.", "Une gifle qui te met à terre et use beaucoup ta garde.", "Ein Schlag, der dich umwirft und viel Deckung kostet."],
    "Fai il parry: la parata regge, ma la guardia si svuota in fretta.": ["Parry it: a block holds, but your guard empties fast.", "Haz el parry: la parada aguanta, pero la guardia se vacía rápido.", "Fais la parade parfaite : la parade tient, mais ta garde se vide vite.", "Pariere: Blocken hält, aber die Deckung leert sich schnell."],
    "Vola e tira dall'alto.": ["Flies and attacks from above.", "Vuela y ataca desde arriba.", "Vole et attaque d'en haut.", "Fliegt und greift von oben an."],
    "Una palla di veleno ad arco che lascia una pozza.": ["An arcing poison ball that leaves a puddle.", "Una bola de veneno en arco que deja un charco.", "Une boule de poison en cloche qui laisse une flaque.", "Eine Giftkugel im Bogen, die eine Pfütze hinterlässt."],
    "Spostati da dove cade e non restare nella pozza.": ["Move away from where it lands and stay out of the puddle.", "Apártate de donde cae y no te quedes en el charco.", "Éloigne-toi de l'endroit où elle tombe et ne reste pas dans la flaque.", "Weich aus, wo sie landet, und bleib nicht in der Pfütze."],
    "Resta a distanza.": ["Keeps its distance.", "Se queda a distancia.", "Reste à distance.", "Hält Abstand."],
    "Sputa veleno ad arco: la parata non lo ferma.": ["Spits poison in an arc: your guard won't stop it.", "Escupe veneno en arco: la parada no lo detiene.", "Crache du poison en cloche : la parade ne l'arrête pas.", "Spuckt Gift im Bogen: Die Parade hält es nicht auf."],
    "Spostati quando sputa e vai a prenderlo da vicino.": ["Move when it spits and go get it up close.", "Apártate cuando escupa y ve a por él de cerca.", "Écarte-toi quand il crache et va le chercher de près.", "Weich aus, wenn er spuckt, und hol ihn dir aus der Nähe."],
    "Rosso e velocissimo.": ["Red and very fast.", "Rojo y rapidísimo.", "Rouge et très rapide.", "Rot und sehr schnell."],
    "Ti corre addosso e morde subito.": ["Runs at you and bites right away.", "Corre hacia ti y muerde enseguida.", "Te fonce dessus et mord tout de suite.", "Rennt auf dich zu und beißt sofort."],
    "Tieni il dito pronto: premi {P} appena l'anello diventa d'oro.": ["Keep your finger ready: press {P} as soon as the ring turns gold.", "Ten el dedo listo: pulsa {P} en cuanto el anillo se vuelva dorado.", "Garde le doigt prêt : appuie sur {P} dès que l'anneau devient doré.", "Halt den Finger bereit: Drück {P}, sobald der Ring golden wird."],
    "Muscolosa e agile: tiene la distanza e schiva saltando quando le vai addosso.": ["Muscular and agile: keeps its distance and leaps away when you close in.", "Musculosa y ágil: mantiene la distancia y esquiva saltando cuando te acercas.", "Musclée et agile : garde ses distances et esquive en sautant quand tu approches.", "Muskulös und wendig: hält Abstand und springt weg, wenn du näher kommst."],
    "Spara raffiche di colpi e tira granate a parabola.": ["Fires bursts of shots and lobs grenades.", "Dispara ráfagas y lanza granadas en parábola.", "Tire des rafales et lance des grenades en cloche.", "Feuert Salven und wirft Granaten im Bogen."],
    "Col parry rimandi colpi e granate a chi li ha tirati. Morendo lascia il fucile-sega.": ["A parry sends shots and grenades back at the shooter. It drops the saw rifle when it dies.", "Con el parry devuelves disparos y granadas a quien los lanzó. Al morir deja el rifle sierra.", "La parade parfaite renvoie tirs et grenades à l'envoyeur. En mourant, elle laisse le fusil-scie.", "Mit dem Parry schickst du Schüsse und Granaten zurück. Stirbt sie, lässt sie das Sägegewehr fallen."],
    "Enorme e lento, con tanta vita.": ["Huge and slow, with lots of health.", "Enorme y lento, con mucha vida.", "Énorme et lent, avec beaucoup de vie.", "Riesig und langsam, mit viel Leben."],
    "Tre manate di fila.": ["Three slaps in a row.", "Tres manotazos seguidos.", "Trois gifles d'affilée.", "Drei Schläge hintereinander."],
    "Parale tutte e tre col parry: CONTRO TOTALE e il capo va giù sbilanciato.": ["Parry all three: TOTAL COUNTER and the boss goes down off balance.", "Haz parry a los tres: CONTRA TOTAL y el jefe cae desequilibrado.", "Pare les trois avec la parade parfaite : CONTRE TOTAL et le chef tombe déséquilibré.", "Pariere alle drei: TOTALKONTER, und der Boss geht aus dem Gleichgewicht zu Boden."],
    "Non attacca: scappa carico di monete.": ["Doesn't attack: runs off loaded with coins.", "No ataca: huye cargado de monedas.", "N'attaque pas : s'enfuit chargé de pièces.", "Greift nicht an: flieht voller Münzen."],
    "Dopo otto secondi si rintana.": ["After eight seconds it burrows away.", "A los ocho segundos se esconde.", "Au bout de huit secondes, il se terre.", "Nach acht Sekunden verkriecht er sich."],
    "Prendilo prima che scappi: lascia tante monete.": ["Catch it before it escapes: it drops lots of coins.", "Atrápalo antes de que huya: deja muchas monedas.", "Attrape-le avant qu'il s'enfuie : il laisse plein de pièces.", "Schnapp ihn, bevor er flieht: Er lässt viele Münzen fallen."],
    "Una scintilla rossa, poi lo zombie parte di corsa verso di te.": ["A red spark, then the zombie charges at you.", "Una chispa roja y el zombi sale corriendo hacia ti.", "Une étincelle rouge, puis le zombie fonce sur toi.", "Ein roter Funke, dann stürmt der Zombie auf dich los."],
    "Una carica che la parata non regge: l'anello è rosso.": ["A charge your guard can't hold: the ring is red.", "Una carga que la parada no aguanta: el anillo es rojo.", "Une charge que la parade ne tient pas : l'anneau est rouge.", "Ein Ansturm, den die Parade nicht hält: Der Ring ist rot."],
    "Solo il parry la ferma: premi {P} quando arriva e stendi chi ti sta intorno.": ["Only a parry stops it: press {P} when it hits and knock down everyone around you.", "Solo el parry la detiene: pulsa {P} cuando llegue y tumba a quien te rodea.", "Seule la parade parfaite l'arrête : appuie sur {P} quand elle arrive et renverse ceux qui t'entourent.", "Nur ein Parry stoppt ihn: Drück {P}, wenn er ankommt, und wirf alle um dich herum um."],
    "Spara da solo da lontano.": ["Shoots on its own from afar.", "Dispara solo desde lejos.", "Tire tout seul de loin.", "Schießt von selbst aus der Ferne."],
    "Con {P} ti metti in agguato: il primo nemico che arriva lo tagli in due, a rallentatore.": ["With {P} you lie in wait: the first enemy that comes close gets cut in two, in slow motion.", "Con {P} te pones al acecho: al primer enemigo que llegue lo partes en dos, a cámara lenta.", "Avec {P} tu te mets à l'affût : le premier ennemi qui arrive est coupé en deux, au ralenti.", "Mit {P} gehst du auf der Lauer: Den ersten Gegner, der kommt, schneidest du in Zeitlupe entzwei."],
    "Si usa una volta sola: dopo il taglio la sega si rompe. Tienila per il nemico più pericoloso.": ["One use only: the saw breaks after the cut. Save it for the most dangerous enemy.", "Se usa una sola vez: tras el corte la sierra se rompe. Guárdala para el enemigo más peligroso.", "Un seul usage : après la coupe, la scie casse. Garde-la pour l'ennemi le plus dangereux.", "Nur einmal nutzbar: Nach dem Schnitt bricht die Säge. Heb sie dir für den gefährlichsten Gegner auf."],
    "SEGA ROTTA!": ["SAW BROKEN!", "¡SIERRA ROTA!", "SCIE CASSÉE !", "SÄGE KAPUTT!"],
    "Minaccia": ["Threat", "Amenaza", "Menace", "Bedrohung"],
    "Capo a": ["Boss at", "Jefe en", "Boss à", "Boss bei"],
    "Arriva alla minaccia": ["Reach threat", "Llega a la amenaza", "Atteins la menace", "Erreiche Bedrohung"],
    "Passa": ["Clear", "Supera", "Passe", "Schaffe"],
    "livelli di minaccia senza danni": ["threat levels without damage", "niveles de amenaza sin daño", "niveaux de menace sans dégâts", "Bedrohungsstufen ohne Schaden"],
    "Para al momento giusto": ["Block at the right moment", "Para en el momento justo", "Pare au bon moment", "Pariere im richtigen Moment"],
    "Arriva il capo!": ["The boss is coming!", "¡Llega el jefe!", "Le boss arrive !", "Der Boss kommt!"],
    "senza danni": ["no damage", "sin daño", "sans dégâts", "ohne Schaden"],
    "Tastiera: 1 2 3, oppure ← → e Invio": ["Keyboard: 1 2 3, or ← → and Enter", "Teclado: 1 2 3, o ← → e Intro", "Clavier : 1 2 3, ou ← → et Entrée", "Tastatur: 1 2 3 oder ← → und Enter"],
    "Ti piace Page Brawl? Dona quanto vuoi: nel messaggio della donazione puoi chiedere una funzione o un personaggio nuovo.": ["Enjoying Page Brawl? Donate what you like: in the donation message you can ask for a new feature or character.", "¿Te gusta Page Brawl? Dona lo que quieras: en el mensaje de la donación puedes pedir una función o un personaje nuevo.", "Page Brawl vous plaît ? Donnez ce que vous voulez : dans le message du don, vous pouvez demander une fonction ou un personnage nouveau.", "Gefällt dir Page Brawl? Spende, so viel du willst: In der Nachricht zur Spende kannst du dir eine neue Funktion oder Figur wünschen."],
    "Sostieni Page Brawl": ["Support Page Brawl", "Apoya Page Brawl", "Soutenir Page Brawl", "Page Brawl unterstützen"],
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
  // I testi che cambiano dopo: un titolo aggiornato, una scheda caricata.
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
