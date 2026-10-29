"""Comunicação interna simples, restrita a usuários autenticados."""

import re
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.requests import Request
from fastapi.responses import FileResponse
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api._shared import form
from app.api.deps import UsuarioAtual, get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.core.utils import now
from app.models import MensagemGrupo, MensagemInterna, SetorInterno, Usuario

router = APIRouter(prefix="/api/interno")


@router.get("/setores")
async def setores(
    db: AsyncSession = Depends(get_db), user: UsuarioAtual = Depends(get_current_user)
):
    grupos = (await db.execute(select(SetorInterno).order_by(SetorInterno.nome))).scalars().all()
    pessoas = (await db.execute(select(Usuario).order_by(Usuario.nome))).scalars().all()
    return [
        {
            "id": grupo.id,
            "nome": grupo.nome,
            "total_pessoas": sum(pessoa.setor_interno_id == grupo.id for pessoa in pessoas),
            "grupo_ativo": sum(
                pessoa.ativo and pessoa.setor_interno_id == grupo.id for pessoa in pessoas
            )
            >= 2
            and any(
                pessoa.id == user.user_id and pessoa.setor_interno_id == grupo.id
                for pessoa in pessoas
            ),
            "pessoas": [
                {
                    "id": pessoa.id,
                    "nome": pessoa.nome,
                    "role": pessoa.role,
                    "ativo": pessoa.ativo,
                    "online": pessoa.online,
                }
                for pessoa in pessoas
                if pessoa.id != user.user_id and pessoa.setor_interno_id == grupo.id
            ],
        }
        for grupo in grupos
    ]


async def grupo_visivel(db: AsyncSession, setor_id: int, user: UsuarioAtual) -> SetorInterno:
    setor = await db.get(SetorInterno, setor_id)
    atual = await db.get(Usuario, user.user_id)
    if setor is None or atual is None or not atual.ativo or atual.setor_interno_id != setor_id:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    quantidade = (
        await db.execute(
            select(func.count(Usuario.id)).where(
                Usuario.setor_interno_id == setor_id, Usuario.ativo.is_(True)
            )
        )
    ).scalar_one()
    if quantidade < 2:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    return setor


@router.get("/grupos/{setor_id}/mensagens")
async def mensagens_grupo(
    setor_id: int,
    antes: int | None = Query(None, ge=1),
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(get_current_user),
):
    await grupo_visivel(db, setor_id, user)
    consulta = (
        select(MensagemGrupo, Usuario.nome)
        .join(Usuario, Usuario.id == MensagemGrupo.remetente_id)
        .where(MensagemGrupo.setor_id == setor_id)
    )
    if antes is not None:
        consulta = consulta.where(MensagemGrupo.id < antes)
    linhas = (await db.execute(consulta.order_by(MensagemGrupo.id.desc()).limit(50))).all()
    return [
        {
            "id": item.id,
            "remetente_id": item.remetente_id,
            "remetente_nome": nome,
            "texto": item.texto,
            "imagem_url": f"/api/interno/imagens/{item.imagem_chave}"
            if item.imagem_chave
            else None,
            "criada_em": item.criada_em.isoformat(),
        }
        for item, nome in reversed(linhas)
    ]


@router.post("/grupos/{setor_id}/mensagens")
async def enviar_grupo(
    setor_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(get_current_user),
):
    await grupo_visivel(db, setor_id, user)
    texto = (await form(request)).get("texto", "").strip()
    if not 1 <= len(texto) <= 4000:
        raise HTTPException(status_code=422, detail="Mensagem inválida")
    mensagem = MensagemGrupo(
        setor_id=setor_id, remetente_id=user.user_id, texto=texto, criada_em=now()
    )
    db.add(mensagem)
    await db.commit()
    return {"id": mensagem.id}


@router.get("/mensagens/{colega_id}")
async def mensagens(
    colega_id: int,
    antes: int | None = Query(None, ge=1),
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(get_current_user),
):
    colega = await db.get(Usuario, colega_id)
    if colega is None or not colega.ativo or colega.id == user.user_id:
        raise HTTPException(status_code=404, detail="Colega não encontrado")
    consulta = select(MensagemInterna).where(
        or_(
            and_(
                MensagemInterna.remetente_id == user.user_id,
                MensagemInterna.destinatario_id == colega_id,
            ),
            and_(
                MensagemInterna.remetente_id == colega_id,
                MensagemInterna.destinatario_id == user.user_id,
            ),
        )
    )
    if antes is not None:
        consulta = consulta.where(MensagemInterna.id < antes)
    registros = (
        (await db.execute(consulta.order_by(MensagemInterna.id.desc()).limit(50))).scalars().all()
    )
    return [
        {
            "id": item.id,
            "remetente_id": item.remetente_id,
            "texto": item.texto,
            "imagem_url": f"/api/interno/imagens/{item.imagem_chave}"
            if item.imagem_chave
            else None,
            "criada_em": item.criada_em.isoformat(),
        }
        for item in reversed(registros)
    ]


@router.post("/mensagens/{colega_id}")
async def enviar(
    colega_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(get_current_user),
):
    colega = await db.get(Usuario, colega_id)
    if colega is None or not colega.ativo or colega.id == user.user_id:
        raise HTTPException(status_code=404, detail="Colega indisponível")
    dados = await form(request)
    texto = dados.get("texto", "").strip()
    if not 1 <= len(texto) <= 4000:
        raise HTTPException(status_code=422, detail="Mensagem inválida")
    mensagem = MensagemInterna(
        remetente_id=user.user_id,
        destinatario_id=colega.id,
        texto=texto,
        criada_em=now(),
    )
    db.add(mensagem)
    await db.commit()
    return {"id": mensagem.id}


async def _webp(request: Request) -> bytes:
    if request.headers.get("content-type", "").split(";")[0].lower() != "image/webp":
        raise HTTPException(status_code=415, detail="Envie uma imagem WebP")
    partes = []
    tamanho = 0
    async for parte in request.stream():
        tamanho += len(parte)
        if tamanho > 2 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Imagem acima de 2 MB")
        partes.append(parte)
    dados = b"".join(partes)
    if (
        len(dados) < 20
        or dados[:4] != b"RIFF"
        or dados[8:12] != b"WEBP"
        or int.from_bytes(dados[4:8], "little") != len(dados) - 8
    ):
        raise HTTPException(status_code=422, detail="Arquivo WebP inválido")
    return dados


async def _guardar_imagem(request: Request) -> tuple[str, Path]:
    dados = await _webp(request)
    pasta = Path(get_settings().media_dir)
    pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
    chave = f"{uuid4().hex}.webp"
    arquivo = pasta / chave
    with arquivo.open("xb") as destino:
        destino.write(dados)
    return chave, arquivo


@router.post("/mensagens/{colega_id}/imagem")
async def enviar_imagem(
    colega_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(get_current_user),
):
    colega = await db.get(Usuario, colega_id)
    if colega is None or not colega.ativo or colega.id == user.user_id:
        raise HTTPException(status_code=404, detail="Colega indisponível")
    chave, arquivo = await _guardar_imagem(request)
    try:
        mensagem = MensagemInterna(
            remetente_id=user.user_id,
            destinatario_id=colega_id,
            texto="",
            imagem_chave=chave,
            criada_em=now(),
        )
        db.add(mensagem)
        await db.commit()
        return {"id": mensagem.id}
    except Exception:
        arquivo.unlink(missing_ok=True)
        raise


@router.post("/grupos/{setor_id}/imagens")
async def enviar_imagem_grupo(
    setor_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(get_current_user),
):
    await grupo_visivel(db, setor_id, user)
    chave, arquivo = await _guardar_imagem(request)
    try:
        mensagem = MensagemGrupo(
            setor_id=setor_id,
            remetente_id=user.user_id,
            texto="",
            imagem_chave=chave,
            criada_em=now(),
        )
        db.add(mensagem)
        await db.commit()
        return {"id": mensagem.id}
    except Exception:
        arquivo.unlink(missing_ok=True)
        raise


@router.get("/imagens/{chave}")
async def ler_imagem(
    chave: str,
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(get_current_user),
):
    if not re.fullmatch(r"[0-9a-f]{32}\.webp", chave):
        raise HTTPException(status_code=404, detail="Imagem não encontrada")
    direta = (
        await db.execute(
            select(MensagemInterna).where(
                MensagemInterna.imagem_chave == chave,
                or_(
                    MensagemInterna.remetente_id == user.user_id,
                    MensagemInterna.destinatario_id == user.user_id,
                ),
            )
        )
    ).scalar_one_or_none()
    if direta is None:
        atual = await db.get(Usuario, user.user_id)
        grupo = (
            await db.execute(
                select(MensagemGrupo).where(
                    MensagemGrupo.imagem_chave == chave,
                    MensagemGrupo.setor_id == atual.setor_interno_id,
                )
            )
        ).scalar_one_or_none()
        if grupo is None:
            raise HTTPException(status_code=404, detail="Imagem não encontrada")
    arquivo = Path(get_settings().media_dir) / chave
    if not arquivo.is_file():
        raise HTTPException(status_code=404, detail="Imagem não encontrada")
    return FileResponse(
        arquivo,
        media_type="image/webp",
        headers={"Cache-Control": "private, max-age=3600"},
    )
