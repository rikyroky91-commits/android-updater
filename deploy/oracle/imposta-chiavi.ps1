# Inserisce le chiavi del sito in ~/sito.env sul VPS Oracle e riavvia.
#
#   powershell -ExecutionPolicy Bypass -File deploy\oracle\imposta-chiavi.ps1
#
# Chiede ogni valore (schermo pulito alla fine); INVIO a vuoto lascia
# quello attuale.
# I valori viaggiano solo dentro SSH (stdin), mai sulla riga di comando.
param(
    [string]$Server = "ubuntu@158.180.233.181",
    [string]$Chiave = "$HOME\.ssh\oracle_sito"
)

# Le stesse variabili segrete di render.yaml (`sync: false`), nell'ordine
# in cui contano. SESSION_SECRET non c'è: la genera setup.sh sul server.
$nomi = @(
    # Backup: da qui tornano account, password e parco. La chiave di
    # cifratura DEVE essere la stessa di Render, o i backup non si leggono.
    "BACKUP_GIST_ID", "BACKUP_GITHUB_TOKEN", "BACKUP_ENCRYPTION_KEY",
    # Amministratore: nasce da queste tre solo se il backup non ne porta uno.
    "ADMIN_USERNAME", "ADMIN_PASSWORD", "ADMIN_EMAIL",
    "GEMINI_API_KEY",
    "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID",
    # Email: qui SMTP non è bloccato come su Render gratuito; Brevo va
    # comunque, ed è preferito se impostato.
    "SMTP_USERNAME", "SMTP_PASSWORD", "BREVO_API_KEY", "BREVO_MITTENTE",
    "TAC_API_KEY", "TAC_API_KEY_2", "TAC_API_PROVIDER_2", "TAC_API_KEY_3",
    "OXYGEN_USER_AGENT",
    # Facoltativo: un modello Gemini preciso. Vuoto = l'elenco di modelli
    # flash in core/aiquery.py, che basta e costa meno.
    "AI_QUERY_MODEL"
)
Write-Host "Copia i valori da Render -> servizio -> Environment. INVIO per saltare quelli che non hai.`n"
$righe = @()
foreach ($nome in $nomi) {
    # Input VISIBILE di proposito: con -AsSecureString, in alcune console
    # Ctrl+V incolla un solo carattere e si vede un asterisco solo, senza
    # modo di accorgersene. Lo schermo si pulisce subito dopo.
    $v = Read-Host "$nome (INVIO = lascia com'e')"
    if ($v) { $righe += "$nome=$($v.Trim())"; Write-Host "  ok, $($v.Trim().Length) caratteri" }
}
Clear-Host
if (-not $righe) { Write-Host "Nessun valore inserito."; exit }

# Sul server: sostituisce le righe esistenti con lo stesso nome, poi riavvia.
$remoto = @'
set -e
f=~/sito.env
while IFS= read -r riga; do
  k=${riga%%=*}
  grep -v "^$k=" "$f" > "$f.nuovo" || true
  printf '%s\n' "$riga" >> "$f.nuovo"
  mv "$f.nuovo" "$f"
done
chmod 600 "$f"
cd ~/app && docker compose -f deploy/oracle/docker-compose.yml up -d >/dev/null 2>&1
echo "Chiavi salvate e sito riavviato."
'@ -replace "`r", ""

($righe -join "`n") + "`n" | ssh -i $Chiave $Server $remoto
