const {test} = require('node:test');
const assert = require('node:assert/strict');
const {confrontaInstallato: compare} = require('../web/static/confronto-installato.js');
const source = {tipo: 'current', android: 16, build: 'C.42'};
test('same build only after variant verification', () => {
  assert.match(compare(source, '16', 'C.42', false), /Non confrontabile/);
  assert.match(compare(source, '16', 'c.42', true), /coincide/);
});
test('factory and reported data never imply an available update', () => {
  for (const tipo of ['factory', 'support', 'reported', ''])
    assert.match(compare({...source, tipo}, '15', 'B.9', true), /Non confrontabile/);
});
test('different builds cannot be sorted lexically', () => {
  assert.match(compare(source, '16', 'C.9', true), /Non confrontabile/);
  assert.match(compare(source, '15', 'B.9', true), /Possibile aggiornamento/);
  assert.match(compare(source, '17', 'D.1', true), /più recente/);
});
test('contradictions and missing values', () => {
  assert.match(compare(source, '15', 'C.42', true), /discordanti/);
  assert.match(compare(source, '', '', true), /Inserisci/);
  assert.match(compare(source, 'foo', 'C.42', true), /solo il numero/);
  assert.match(compare({...source, android: ''}, '15', 'B.9', true), /Non confrontabile/);
});
