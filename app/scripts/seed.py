import asyncio

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import async_session_maker
from app.models import Computador, Setor, SetorInterno, Usuario
from app.services.auth_service import get_password_hash


async def seed():
    settings = get_settings()
    passwords = {
        "gestor": settings.seed_gestor_password,
        "colaborador": settings.seed_vendedor_password,
        "supervisor": settings.seed_responsavel_password,
    }
    if any(len(value) < 8 for value in passwords.values()):
        raise RuntimeError("Defina SEED_*_PASSWORD com pelo menos 8 caracteres no .env")
    pessoas = [
        ("Gestor", "gestor@demo.local", "gestor"),
        ("Vendedor 1", "vendedor1@demo.local", "colaborador"),
        ("Vendedor 2", "vendedor2@demo.local", "colaborador"),
        ("Vendedor 3", "vendedor3@demo.local", "colaborador"),
        ("Responsável 1", "responsavel1@demo.local", "supervisor"),
        ("Responsável 2", "responsavel2@demo.local", "supervisor"),
    ]
    async with async_session_maker() as db:
        for identificador, nome, icone in [
            (1, "Vendas", "vendas"),
            (2, "Estoque", "estoque"),
            (3, "Garantia", "garantia"),
            (4, "Administração", "administracao"),
        ]:
            if not await db.get(SetorInterno, identificador):
                db.add(SetorInterno(id=identificador, nome=nome, icone=icone))
        await db.flush()
        for nome, email, role in pessoas:
            if not (await db.execute(select(Usuario.id).where(Usuario.email == email))).first():
                setor_interno_id = {"colaborador": 1, "supervisor": 3, "gestor": 4}[role]
                db.add(
                    Usuario(
                        nome=nome,
                        email=email,
                        role=role,
                        senha_hash=get_password_hash(passwords[role]),
                        ativo=True,
                        online=True,
                        setor_interno_id=setor_interno_id,
                    )
                )
        await db.flush()
        responsaveis = (
            (
                await db.execute(
                    select(Usuario).where(Usuario.role == "supervisor").order_by(Usuario.id)
                )
            )
            .scalars()
            .all()
        )
        setores = [
            (1, "Vendas/Compra", None),
            (2, "Devolução", responsaveis[0].id),
            (3, "Garantia", responsaveis[1].id),
            (4, "Outro", responsaveis[0].id),
        ]
        for ordem, nome, responsavel_id in setores:
            if not (await db.execute(select(Setor.id).where(Setor.ordem == ordem))).first():
                icone = {1: "vendas", 2: "devolucao", 3: "garantia", 4: "equipe"}[ordem]
                db.add(Setor(ordem=ordem, nome=nome, icone=icone, responsavel_id=responsavel_id))
        usuarios = {
            item.email: item for item in (await db.execute(select(Usuario))).scalars().all()
        }
        computadores = [
            ("PC Vendedor 1", "vendedor1@demo.local", "empresa"),
            ("PC Vendedor 2", "vendedor2@demo.local", "empresa"),
            ("PC Vendedor 3", "vendedor3@demo.local", "empresa"),
            ("PC Dono", "gestor@demo.local", "dono"),
        ]
        for nome, email, grupo in computadores:
            if not (await db.execute(select(Computador.id).where(Computador.nome == nome))).first():
                db.add(Computador(nome=nome, dono_id=usuarios[email].id, grupo=grupo))
        await db.commit()


if __name__ == "__main__":
    asyncio.run(seed())
