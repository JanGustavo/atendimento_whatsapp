"""Entrada HTTP da Evolution; o trabalho de banco roda após o 200."""
import hmac
import logging
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.core.config import get_settings
from app.core.database import get_session_maker
from app.providers import EvolutionProvider, provider_atual
from app.services.atendimento import receber_mensagem

router = APIRouter()
logger = logging.getLogger(__name__)
logger.setLevel(get_settings().app_log_level.upper())
_primeiro_payload = False

async def processar_entrada(entrada, maker: async_sessionmaker):
    try:
        async with maker() as db:
            await receber_mensagem(db, provider_atual(), entrada)
    except Exception:
        logger.exception("Falha ao processar mensagem recebida")

@router.post('/webhook/whatsapp')
async def webhook(request: Request, tarefas: BackgroundTasks,
                  segredo: str | None = Header(default=None, alias='X-Webhook-Secret'),
                  maker: async_sessionmaker = Depends(get_session_maker)):
    config = get_settings()
    if not config.evolution_webhook_secret or not hmac.compare_digest(segredo or '', config.evolution_webhook_secret):
        raise HTTPException(status_code=401, detail='Segredo inválido')
    payload = await request.json()
    global _primeiro_payload
    if not _primeiro_payload:
        logger.debug('Primeiro payload Evolution: %s', payload)
        _primeiro_payload = True
    provider = EvolutionProvider(config.evolution_base_url, config.evolution_api_key, config.evolution_instancia)
    entrada = provider.parse_webhook(payload)
    if entrada and not entrada.de_mim and '@g.us' not in entrada.numero:
        tarefas.add_task(processar_entrada, entrada, maker)
    return {'ok': True}
