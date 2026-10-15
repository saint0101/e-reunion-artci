#!/bin/bash
# Sauvegarde nocturne chiffrée de QR Meeting (P7.1 / R7).
# À lancer par cron sur l'hôte (root), jamais depuis l'interface web :
#   30 2 * * * /home/e-reunion-artci/scripts/backup_cron.sh >> /var/log/qrmeeting_backup.log 2>&1
#
# Prérequis :
#   - /root/.qrmeeting_backup_pass : phrase secrète (chmod 600), conservée aussi par la DSI
#   - BACKUP_DEST : destination hors serveur (ex. user@srv-backup:/sauvegardes/qrmeeting/)
#
# Restauration : gpg -d backup_XXXX.tar.gz.gpg > backup_XXXX.tar.gz
set -euo pipefail

APP_DIR="${APP_DIR:-/home/e-reunion-artci}"
CONTAINER="${CONTAINER:-artci_e_reunion}"
PASS_FILE="${PASS_FILE:-/root/.qrmeeting_backup_pass}"
BACKUP_DEST="${BACKUP_DEST:-}"
KEEP_LOCAL_DAYS="${KEEP_LOCAL_DAYS:-2}"

LOCAL_DIR="$APP_DIR/db_backup"

echo "[$(date '+%F %T')] Début de la sauvegarde"

[ -s "$PASS_FILE" ] || { echo "Phrase secrète absente : $PASS_FILE"; exit 1; }

# 1. Archive en clair créée dans le conteneur (montée sur $LOCAL_DIR)
docker exec "$CONTAINER" python /app/gestion_reunions/manage.py backup_create --keep 1

ARCHIVE=$(ls -1t "$LOCAL_DIR"/backup_*.tar.gz | head -n 1)

# 2. Chiffrement, puis suppression immédiate de l'archive en clair
gpg --batch --yes --pinentry-mode loopback --passphrase-file "$PASS_FILE" \
    --symmetric --cipher-algo AES256 -o "$ARCHIVE.gpg" "$ARCHIVE"
shred -u "$ARCHIVE" 2>/dev/null || rm -f "$ARCHIVE"
chmod 600 "$ARCHIVE.gpg"

# 3. Copie hors serveur
if [ -n "$BACKUP_DEST" ]; then
    scp -q "$ARCHIVE.gpg" "$BACKUP_DEST"
    echo "Copié vers $BACKUP_DEST"
else
    echo "ATTENTION : BACKUP_DEST non défini, la sauvegarde reste sur le serveur"
fi

# 4. Rotation locale : on ne garde que quelques jours sur le serveur applicatif
find "$LOCAL_DIR" -name 'backup_*.tar.gz.gpg' -mtime +"$KEEP_LOCAL_DAYS" -delete

echo "[$(date '+%F %T')] Fin : $(basename "$ARCHIVE").gpg"
