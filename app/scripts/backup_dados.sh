#!/usr/bin/env bash
set -euo pipefail

PROJETO=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
DESTINO=${BACKUP_DIR:-"$PROJETO/../atendimento_whatsapp-backups"}
DIAS=${BACKUP_KEEP_DAYS:-30}
mkdir -p "$DESTINO"

docker run --rm --user 0 \
  --mount type=volume,source=atendimento_whatsapp_atendimento_data,target=/data \
  --mount "type=bind,source=$DESTINO,target=/backups" \
  --mount "type=bind,source=$PROJETO/app/scripts/backup_dados.py,target=/backup_dados.py,readonly" \
  atendimento_whatsapp-app python /backup_dados.py \
  --source /data/atendimento.db --media /data/media --dest /backups --keep-days "$DIAS"

docker run --rm --user 0 \
  --mount "type=bind,source=$DESTINO,target=/backups" \
  atendimento_whatsapp-app chown -R "$(id -u):$(id -g)" /backups
