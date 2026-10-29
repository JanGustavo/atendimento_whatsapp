"""Webhook da Meta: verificação GET, assinatura POST e processamento após o 200."""
import hashlib
import hmac
import json
import logging
import asyncio
from datetime import UTC, datetime
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy import select
from app.core.config import get_settings
from app.core.database import get_session_maker
from app.providers import MetaProvider
from app.services.atendimento import receber_mensagem
from app.core.utils import now
from app.models import Mensagem

router = APIRouter()
logger = logging.getLogger(__name__)
logger.setLevel(get_settings().app_log_level.upper())
_primeiro_payload = False

async def processar_entrada(entrada, provider: MetaProvider, maker: async_sessionmaker):
    try:
        async with maker() as db:
            await receber_mensagem(db, provider, entrada)
    except Exception:
        logger.exception("Falha ao processar mensagem recebida")


async def processar_status(status: dict, maker: async_sessionmaker):
    identidade = status["id"]
    ordem = {"pendente": 0, "enviada": 1, "entregue": 2, "lida": 3}
    novo = {"sent": "enviada", "delivered": "entregue", "read": "lida", "failed": "falhou"}[status["status"]]
    try:
        instante = datetime.fromtimestamp(int(status["timestamp"]), UTC).replace(tzinfo=None)
    except (KeyError, TypeError, ValueError, OverflowError):
        instante = now()
    for tentativa in range(5):
        async with maker() as db:
            mensagem = (await db.execute(select(Mensagem).where(
                Mensagem.provider_id == identidade, Mensagem.origem.in_(["humano", "bot"])
            ))).scalar_one_or_none()
            if mensagem is not None:
                atual = mensagem.envio_status or "pendente"
                if novo == "falhou":
                    if atual in {"pendente", "enviada"}:
                        mensagem.envio_status = "falhou"
                elif ordem.get(novo, 0) > ordem.get(atual, 0):
                    mensagem.envio_status = novo
                    if novo == "lida":
                        mensagem.lida_em = instante
                await db.commit()
                return
        if tentativa < 4:
            await asyncio.sleep(1)
    logger.debug("Status Meta sem mensagem correspondente: %s", identidade)


@router.get('/webhook/whatsapp', response_class=PlainTextResponse)
async def verificar_webhook(request: Request):
    config = get_settings()
    parametros = request.query_params
    if (parametros.get('hub.mode') != 'subscribe' or not config.meta_verify_token or
            not hmac.compare_digest(parametros.get('hub.verify_token', ''), config.meta_verify_token)):
        raise HTTPException(status_code=403, detail='Verificação inválida')
    return parametros.get('hub.challenge', '')


@router.post('/webhook/whatsapp')
async def webhook(request: Request, tarefas: BackgroundTasks,
                  assinatura: str | None = Header(default=None, alias='X-Hub-Signature-256'),
                  maker: async_sessionmaker = Depends(get_session_maker)):
    config = get_settings()
    corpo = await request.body()
    if not config.meta_app_secret:
        raise HTTPException(status_code=401, detail='Assinatura inválida')
    esperado = 'sha256=' + hmac.new(config.meta_app_secret.encode(), corpo, hashlib.sha256).hexdigest()
    if not assinatura or not hmac.compare_digest(assinatura, esperado):
        raise HTTPException(status_code=401, detail='Assinatura inválida')
    try:
        payload = json.loads(corpo)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail='JSON inválido') from None
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail='JSON inválido')
    global _primeiro_payload
    if not _primeiro_payload:
        logger.debug('Primeiro payload Meta: %s', payload)
        _primeiro_payload = True
    provider = MetaProvider(config.meta_graph_version, config.meta_phone_number_id, config.meta_access_token)
    for status in provider.parse_webhook_statuses(payload):
        tarefas.add_task(processar_status, status, maker)
    for entrada in provider.parse_webhook_mensagens(payload):
        tarefas.add_task(processar_entrada, entrada, provider, maker)
    return {'ok': True}
