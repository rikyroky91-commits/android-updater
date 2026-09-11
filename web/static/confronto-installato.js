/* Confronto locale: i dati digitati non vengono inviati ad altri servizi. */
function confrontaInstallato(fonte, android, build, varianteConfermata) {
  var a = /^\d{1,2}$/.test(android) ? Number(android) : null;
  var b = /^\d{1,2}$/.test(String(fonte.android)) ? Number(fonte.android) : null;
  var installata = build.trim().toUpperCase();
  var trovata = String(fonte.build || '').trim().toUpperCase();
  if (!android && !installata) return 'Inserisci Android o build dalle impostazioni del telefono.';
  if (android && a === null) return 'Inserisci solo il numero Android, per esempio 15.';
  if (fonte.tipo !== 'current') return 'Non confrontabile: la fonte non conferma un firmware attuale.';
  if (!varianteConfermata) return 'Non confrontabile: verifica nella fonte che modello, variante e regione coincidano.';
  if (installata && trovata && installata === trovata) {
    if (a !== null && b !== null && a !== b) return 'Dati discordanti: la build coincide ma la versione Android è diversa. Controlla i dati inseriti e la fonte.';
    return 'La build installata coincide con quella trovata. Questo non esclude aggiornamenti non ancora presenti nella fonte.';
  }
  if (a !== null && b !== null && b > a) return 'Possibile aggiornamento: la fonte riporta Android ' + b + '. Verifica la disponibilità nelle impostazioni del telefono.';
  if (a !== null && b !== null && b < a) return 'La versione installata è più recente di quella trovata: la fonte potrebbe essere arretrata.';
  return 'Non confrontabile: Android uguale o dati insufficienti. Build diverse non indicano da sole quale sia più recente.';
}
if (typeof module !== 'undefined') module.exports = { confrontaInstallato };
if (typeof document !== 'undefined') {
  document.addEventListener('submit', function (event) {
    var form = event.target.closest('[data-confronto-installato]');
    if (!form) return;
    event.preventDefault();
    var fonte = JSON.parse(form.dataset.confrontoInstallato);
    form.querySelector('[role="status"]').textContent = confrontaInstallato(
      fonte, form.elements.android.value.trim(), form.elements.build.value,
      form.elements.variante.checked);
  });
  document.addEventListener('click', async function (event) {
    var button = event.target.closest('[data-copia-riepilogo]');
    if (!button) return;
    try {
      await navigator.clipboard.writeText(button.dataset.copiaRiepilogo);
      button.textContent = 'Riepilogo copiato';
    } catch (_) {
      var testo = document.createElement('textarea');
      testo.value = button.dataset.copiaRiepilogo;
      testo.setAttribute('aria-label', 'Riepilogo da copiare manualmente');
      button.after(testo); testo.focus(); testo.select();
      button.textContent = 'Copia il testo selezionato';
    }
  });
}
