#!/usr/bin/env bash
# Prepara una VM Oracle Cloud (Ubuntu) a ospitare il sito. Si lancia UNA
# volta sulla VM appena creata (il repository è privato, quindi il file ci
# arriva copiato, non scaricato):
#
#   scp -i chiave.key deploy/oracle/setup.sh ubuntu@IP:
#   ssh -i chiave.key ubuntu@IP 'bash setup.sh'
#
# Fa tre cose: installa Docker, apre le porte 80/443 nel firewall della
# VM, crea ~/sito.env da compilare.
set -euo pipefail

# 1. DOCKER, dallo script ufficiale: supporta sia x86 sia ARM (Ampere A1).
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sudo sh
fi
sudo usermod -aG docker "$USER"

# 2. IL FIREWALL DELLA VM. Le immagini Ubuntu di Oracle hanno regole
# iptables che rifiutano tutto tranne SSH, ANCHE dopo aver aperto le porte
# nella Security List della rete virtuale: servono entrambe le cose, ed è
# l'errore più comune in assoluto su Oracle («la porta è aperta ma non
# risponde»). Le regole vanno inserite PRIMA del REJECT finale, la cui
# posizione cambia da un'immagine all'altra: si cerca, non si indovina.
apri() {
  sudo iptables -C INPUT -m state --state NEW -p "$1" --dport "$2" -j ACCEPT 2>/dev/null && return
  pos=$(sudo iptables -L INPUT --line-numbers -n | awk '$2=="REJECT"{print $1; exit}')
  sudo iptables -I INPUT "${pos:-1}" -m state --state NEW -p "$1" --dport "$2" -j ACCEPT
}
apri tcp 80
apri tcp 443
apri udp 443
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y netfilter-persistent iptables-persistent
sudo netfilter-persistent save

# 3. IL FILE DEI SEGRETI, fuori dalla cartella del codice.
if [ ! -f "$HOME/sito.env" ]; then
  ip=$(curl -fsS https://ifconfig.me || echo "IP-PUBBLICO")
  cat > "$HOME/sito.env" <<EOF
# Dominio del sito. Senza un dominio proprio: l'IP con i trattini + .sslip.io
SITE_DOMAIN=${ip//./-}.sslip.io

GEMINI_API_KEY=
TELEGRAM_TOKEN=
TELEGRAM_CHAT_ID=
BACKUP_GIST_ID=
BACKUP_GITHUB_TOKEN=
EOF
  chmod 600 "$HOME/sito.env"
fi

mkdir -p "$HOME/app"
echo
echo "Fatto. Ora:"
echo "  1. compila i valori in ~/sito.env  (nano ~/sito.env)"
echo "  2. esci e rientra via SSH, perché il gruppo docker abbia effetto"
echo "  3. lancia il workflow «deploy-oracle» da GitHub"
