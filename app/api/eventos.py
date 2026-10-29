"""Eventos leves para avisos na tela, consultados pelo painel a cada 3 s."""
from fastapi import APIRouter, Depends, Query
from datetime import timedelta
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import UsuarioAtual, get_current_user
from app.core.database import get_db
from app.core.utils import now
from app.models import Conversa, LeituraConversa, Mensagem, MensagemInterna, Usuario

router = APIRouter(prefix="/api/eventos")


@router.get("")
async def eventos(
    inicio: bool = False,
    whatsapp_apos: int = Query(0, ge=0),
    interno_apos: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(get_current_user),
):
    whatsapp_base = select(Mensagem).join(Conversa, Conversa.id == Mensagem.conversa_id).outerjoin(
        LeituraConversa, and_(LeituraConversa.conversa_id == Conversa.id,
                              LeituraConversa.usuario_id == user.user_id)).where(
        Mensagem.origem == "cliente", Mensagem.id > func.coalesce(LeituraConversa.ultima_mensagem_id, 0),
    )
    if user.role != "gestor":
        whatsapp_base = whatsapp_base.where(Conversa.atribuido_id == user.user_id)
    interno_base = select(MensagemInterna).where(MensagemInterna.destinatario_id == user.user_id)
    if inicio:
        # Primeiro acesso: trazer as últimas 24 h e avançar o cursor até o fim do banco.
        # Isso também funciona quando dados históricos são importados depois de mensagens novas.
        limite_antigo = now() - timedelta(hours=24)
        ultimo_whatsapp = (await db.execute(select(func.max(Mensagem.id)).join(
            Conversa, Conversa.id == Mensagem.conversa_id,
        ).where(Mensagem.origem == "cliente", *(
            [] if user.role == "gestor" else [Conversa.atribuido_id == user.user_id]
        )))).scalar() or 0
        ultimo_interno = (await db.execute(select(func.max(MensagemInterna.id)).where(
            MensagemInterna.destinatario_id == user.user_id,
        ))).scalar() or 0
        whatsapp = list(reversed((await db.execute(whatsapp_base.where(
            Mensagem.criada_em >= limite_antigo,
        ).order_by(Mensagem.id.desc()).limit(100))).scalars().all()))
        interno = list(reversed((await db.execute(interno_base.where(
            MensagemInterna.criada_em >= limite_antigo,
        ).order_by(MensagemInterna.id.desc()).limit(100))).scalars().all()))
    else:
        whatsapp = (await db.execute(whatsapp_base.where(
            Mensagem.id > whatsapp_apos,
        ).order_by(Mensagem.id).limit(100))).scalars().all()
        interno = (await db.execute(interno_base.where(
            MensagemInterna.id > interno_apos,
        ).order_by(MensagemInterna.id).limit(100))).scalars().all()
    numeros = {}
    for item in whatsapp:
        if item.conversa_id not in numeros:
            conversa = await db.get(Conversa, item.conversa_id)
            numeros[item.conversa_id] = conversa.numero
    nomes = {}
    for item in interno:
        if item.remetente_id not in nomes:
            remetente = await db.get(Usuario, item.remetente_id)
            nomes[item.remetente_id] = remetente.nome if remetente else "Colega"
    return {
        "whatsapp": [{"id": item.id, "conversa_id": item.conversa_id,
                      "numero": numeros[item.conversa_id], "texto": item.texto[:160]} for item in whatsapp],
        "interno": [{"id": item.id, "remetente_id": item.remetente_id,
                    "nome": nomes[item.remetente_id], "texto": item.texto[:160]} for item in interno],
        "ultimo_whatsapp": ultimo_whatsapp if inicio else (whatsapp[-1].id if whatsapp else whatsapp_apos),
        "ultimo_interno": ultimo_interno if inicio else (interno[-1].id if interno else interno_apos),
    }
