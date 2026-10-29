"""Insere um pequeno histórico fictício apenas entre contas de demonstração."""
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core.database import async_session_maker
from app.models import MensagemInterna, Usuario


async def seed_chat_demo():
    exemplos = [
        ("vendedor1@demo.local", "gestor@demo.local", "[Demonstração] Conferi o atendimento de ontem.", datetime(2026, 10, 26, 10, 15)),
        ("gestor@demo.local", "vendedor1@demo.local", "[Demonstração] Obrigado. Deixe o histórico registrado aqui.", datetime(2026, 10, 26, 10, 19)),
        ("vendedor1@demo.local", "gestor@demo.local", "[Demonstração] Nova atualização do atendimento.", datetime(2026, 10, 28, 9, 20)),
        ("gestor@demo.local", "vendedor1@demo.local", "[Demonstração] Recebido. Assim podemos consultar mensagens de dias diferentes.", datetime(2026, 10, 28, 9, 24)),
    ]
    async with async_session_maker() as db:
        usuarios = {item.email: item for item in (await db.execute(select(Usuario).where(
            Usuario.email.in_({email for origem, destino, _texto, _data in exemplos for email in (origem, destino)})
        ))).scalars()}
        if len(usuarios) != 2:
            raise RuntimeError("Rode o seed principal antes de inserir o histórico de demonstração")
        existentes = set((await db.execute(select(MensagemInterna.texto).where(
            MensagemInterna.texto.like("[Demonstração]%")
        ))).scalars())
        for origem, destino, texto, data in exemplos:
            if texto not in existentes:
                utc = data.replace(tzinfo=ZoneInfo("America/Sao_Paulo")).astimezone(ZoneInfo("UTC"))
                db.add(MensagemInterna(remetente_id=usuarios[origem].id, destinatario_id=usuarios[destino].id,
                                       texto=texto, criada_em=utc.replace(tzinfo=None)))
        await db.commit()


if __name__ == "__main__":
    asyncio.run(seed_chat_demo())
