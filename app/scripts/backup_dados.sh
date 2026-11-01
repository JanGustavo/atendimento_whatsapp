#!/usr/bin/env bash
set -euo pipefail

PROJETO=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
DESTINO=${BACKUP_DIR:-"$PROJETO/../atendimento_whatsapp-backups"}
DIAS=${BACKUP_KEEP_DAYS:-30}
RETENCAO=$(awk -F= '$1 == "RETENCAO_CONVERSAS_DIAS" {print $2}' "$PROJETO/.env")
RETENCAO=${RETENCAO:-180}
[[ $RETENCAO =~ ^[1-9][0-9]*$ ]] || { echo 'RETENCAO_CONVERSAS_DIAS inválido'; exit 1; }
mkdir -p "$DESTINO"

docker run --rm --user 0 \
  --mount type=volume,source=atendimento_whatsapp_atendimento_data,target=/data \
  --mount "type=bind,source=$DESTINO,target=/backups" \
  --mount "type=bind,source=$PROJETO/app/scripts/backup_dados.py,target=/backup_dados.py,readonly" \
  atendimento_whatsapp-app python /backup_dados.py \
  --source /data/atendimento.db --media /data/media --dest /backups --keep-days "$DIAS"

docker run --rm --user 0 \
  --mount type=volume,source=atendimento_whatsapp_atendimento_data,target=/data \
  --mount "type=bind,source=$PROJETO/app/scripts/retencao_conversas.py,target=/retencao.py,readonly" \
  atendimento_whatsapp-app python /retencao.py \
  --database /data/atendimento.db --media /data/media --days "$RETENCAO"

docker run --rm --user 0 \
  --mount "type=bind,source=$DESTINO,target=/backups" \
  atendimento_whatsapp-app chown -R "$(id -u):$(id -g)" /backups
