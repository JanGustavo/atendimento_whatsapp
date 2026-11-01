"""Comunicação interna simples, restrita a usuários autenticados."""

import re

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.requests import Request
from fastapi.responses import FileResponse
from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api._shared import form
from app.api.deps import UsuarioAtual, get_current_user
from app.core.database import get_db
from app.core.utils import now
from app.models import LeituraInterna, MensagemGrupo, MensagemInterna, SetorInterno, Usuario
from app.services.media import caminho_media, foto_url, guardar_audio, guardar_webp
from app.services.presenca import esta_conectado

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
            "icone": grupo.icone,
            "total_pessoas": sum(pessoa.setor_interno_id == grupo.id for pessoa in pessoas),
            "membros_ativos": sum(pessoa.ativo and pessoa.setor_interno_id == grupo.id for pessoa in pessoas),
            "grupo_ativo": sum(
                pessoa.ativo and pessoa.setor_interno_id == grupo.id for pessoa in pessoas
            )
            >= 2
            and (user.role == "gestor" or any(
                pessoa.id == user.user_id and pessoa.setor_interno_id == grupo.id for pessoa in pessoas
            )),
            "pessoas": [
                {
                    "id": pessoa.id,
                    "nome": pessoa.nome,
                    "role": pessoa.role,
                    "ativo": pessoa.ativo,
                    "online": esta_conectado(pessoa),
                    "foto_url": foto_url(pessoa),
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
    if setor is None or atual is None or not atual.ativo or (user.role != "gestor" and atual.setor_interno_id != setor_id):
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


@router.get("/conversas")
async def listar_conversas(db: AsyncSession = Depends(get_db),
                           user: UsuarioAtual = Depends(get_current_user)):
    """Prévia e não lidas por conversa, inclusive grupos do setor."""
    peer = case(
        (MensagemInterna.remetente_id == user.user_id, MensagemInterna.destinatario_id),
        else_=MensagemInterna.remetente_id,
    )
    ultimas_diretas = (select(peer.label("peer_id"), func.max(MensagemInterna.id).label("mensagem_id"))
                      .where(or_(MensagemInterna.remetente_id == user.user_id,
                                 MensagemInterna.destinatario_id == user.user_id))
                      .group_by(peer).subquery())
    diretas = (await db.execute(select(Usuario, MensagemInterna)
                .join(ultimas_diretas, Usuario.id == ultimas_diretas.c.peer_id)
                .join(MensagemInterna, MensagemInterna.id == ultimas_diretas.c.mensagem_id)
                .where(Usuario.ativo.is_(True)))).all()
    nao_lidas_diretas = dict((await db.execute(select(
        MensagemInterna.remetente_id, func.count(MensagemInterna.id)
    ).outerjoin(LeituraInterna, and_(
        LeituraInterna.usuario_id == user.user_id, LeituraInterna.tipo == "direta",
        LeituraInterna.alvo_id == MensagemInterna.remetente_id,
    )).where(
        MensagemInterna.destinatario_id == user.user_id,
        MensagemInterna.id > func.coalesce(LeituraInterna.ultima_mensagem_id, 0),
    ).group_by(MensagemInterna.remetente_id))).all())

    grupos_disponiveis = (await db.execute(select(
        SetorInterno.id, SetorInterno.nome
    ).join(Usuario, Usuario.setor_interno_id == SetorInterno.id)
     .where(Usuario.ativo.is_(True), *(
         [] if user.role == "gestor" else [SetorInterno.id == (
             select(Usuario.setor_interno_id).where(Usuario.id == user.user_id).scalar_subquery()
         )]
     )).group_by(SetorInterno.id, SetorInterno.nome)
     .having(func.count(Usuario.id) >= 2))).all()
    grupos_ids = [item.id for item in grupos_disponiveis]
    ultimas_grupos = {}
    nao_lidas_grupos = {}
    if grupos_ids:
        ids = (select(func.max(MensagemGrupo.id))
               .where(MensagemGrupo.setor_id.in_(grupos_ids))
               .group_by(MensagemGrupo.setor_id))
        ultimas_grupos = {item.setor_id: item for item in (
            await db.execute(select(MensagemGrupo).where(MensagemGrupo.id.in_(ids))
                             )).scalars().all()}
        nao_lidas_grupos = dict((await db.execute(select(
            MensagemGrupo.setor_id, func.count(MensagemGrupo.id)
        ).outerjoin(LeituraInterna, and_(
            LeituraInterna.usuario_id == user.user_id, LeituraInterna.tipo == "grupo",
            LeituraInterna.alvo_id == MensagemGrupo.setor_id,
        )).where(
            MensagemGrupo.setor_id.in_(grupos_ids), MensagemGrupo.remetente_id != user.user_id,
            MensagemGrupo.id > func.coalesce(LeituraInterna.ultima_mensagem_id, 0),
        ).group_by(MensagemGrupo.setor_id))).all())

    conversas = []
    for colega, ultima in diretas:
        conversas.append({
            "tipo": "direta", "alvo_id": colega.id, "nome": colega.nome,
            "foto_url": foto_url(colega), "online": esta_conectado(colega),
            "ultimo_remetente": "Você" if ultima.remetente_id == user.user_id else colega.nome,
            "ultima_previa": "Mensagem apagada" if ultima.apagada_em else ultima.texto[:120] if ultima.texto else "Áudio" if ultima.audio_chave else "Imagem",
            "ultima_em": ultima.criada_em.isoformat(),
            "nao_lidas": nao_lidas_diretas.get(colega.id, 0),
        })
    for setor in grupos_disponiveis:
        ultima = ultimas_grupos.get(setor.id)
        remetente = await db.get(Usuario, ultima.remetente_id) if ultima else None
        conversas.append({
            "tipo": "grupo", "alvo_id": setor.id, "nome": setor.nome,
            "foto_url": None, "online": None,
            "ultimo_remetente": ("Você" if ultima.remetente_id == user.user_id else remetente.nome)
                                if ultima and remetente else None,
            "ultima_previa": ("Mensagem apagada" if ultima.apagada_em else ultima.texto[:120] if ultima.texto else "Áudio" if ultima.audio_chave else "Imagem") if ultima else None,
            "ultima_em": ultima.criada_em.isoformat() if ultima else None,
            "nao_lidas": nao_lidas_grupos.get(setor.id, 0),
        })
    conversas.sort(key=lambda item: item["ultima_em"] or "", reverse=True)
    return {"conversas": conversas, "nao_lidas": sum(item["nao_lidas"] for item in conversas)}


@router.post("/conversas/{tipo}/{alvo_id}/leitura")
async def marcar_leitura(tipo: str, alvo_id: int, db: AsyncSession = Depends(get_db),
                         user: UsuarioAtual = Depends(get_current_user)):
    if tipo == "direta":
        colega = await db.get(Usuario, alvo_id)
        if colega is None or not colega.ativo or colega.id == user.user_id:
            raise HTTPException(status_code=404, detail="Conversa não encontrada")
        ultimo = (await db.execute(select(func.max(MensagemInterna.id)).where(
            MensagemInterna.remetente_id == alvo_id,
            MensagemInterna.destinatario_id == user.user_id,
        ))).scalar() or 0
    elif tipo == "grupo":
        await grupo_visivel(db, alvo_id, user)
        ultimo = (await db.execute(select(func.max(MensagemGrupo.id)).where(
            MensagemGrupo.setor_id == alvo_id,
            MensagemGrupo.remetente_id != user.user_id,
        ))).scalar() or 0
    else:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    if ultimo:
        insercao = sqlite_insert(LeituraInterna).values(
            usuario_id=user.user_id, tipo=tipo, alvo_id=alvo_id,
            ultima_mensagem_id=ultimo, lida_em=now(),
        )
        await db.execute(insercao.on_conflict_do_update(
            index_elements=[LeituraInterna.usuario_id, LeituraInterna.tipo, LeituraInterna.alvo_id],
            set_={"ultima_mensagem_id": ultimo, "lida_em": now()},
            where=LeituraInterna.ultima_mensagem_id < ultimo,
        ))
        await db.commit()
    return {"ultima_mensagem_id": ultimo}


@router.get("/grupos/{setor_id}/mensagens")
async def mensagens_grupo(
    setor_id: int,
    antes: int | None = Query(None, ge=1),
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(get_current_user),
):
    await grupo_visivel(db, setor_id, user)
    consulta = (
        select(MensagemGrupo, Usuario.nome, Usuario.foto_chave)
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
            "remetente_foto_url": (
                f"/api/usuarios/{item.remetente_id}/foto?v={foto_chave}"
                if foto_chave
                else None
            ),
            "texto": item.texto,
            "imagem_url": f"/api/interno/imagens/{item.imagem_chave}"
            if item.imagem_chave
            else None,
            "audio_url": f"/api/interno/audios/{item.audio_chave}" if item.audio_chave else None,
            "apagada": item.apagada_em is not None,
            "editada_em": item.editada_em.isoformat() if item.editada_em else None,
            "criada_em": item.criada_em.isoformat(),
        }
        for item, nome, foto_chave in reversed(linhas)
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
            "audio_url": f"/api/interno/audios/{item.audio_chave}" if item.audio_chave else None,
            "apagada": item.apagada_em is not None,
            "editada_em": item.editada_em.isoformat() if item.editada_em else None,
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


@router.post("/mensagens/{colega_id}/imagem")
async def enviar_imagem(
    colega_id: int,
    request: Request,
    texto: str = Query("", max_length=4000),
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(get_current_user),
):
    colega = await db.get(Usuario, colega_id)
    if colega is None or not colega.ativo or colega.id == user.user_id:
        raise HTTPException(status_code=404, detail="Colega indisponível")
    chave, arquivo = await guardar_webp(request)
    try:
        mensagem = MensagemInterna(
            remetente_id=user.user_id,
            destinatario_id=colega_id,
            texto=texto.strip(),
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
    texto: str = Query("", max_length=4000),
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(get_current_user),
):
    await grupo_visivel(db, setor_id, user)
    chave, arquivo = await guardar_webp(request)
    try:
        mensagem = MensagemGrupo(
            setor_id=setor_id,
            remetente_id=user.user_id,
            texto=texto.strip(),
            imagem_chave=chave,
            criada_em=now(),
        )
        db.add(mensagem)
        await db.commit()
        return {"id": mensagem.id}
    except Exception:
        arquivo.unlink(missing_ok=True)
        raise


@router.post("/mensagens/{colega_id}/audio")
async def enviar_audio_direto(
    colega_id: int, request: Request, db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(get_current_user),
):
    colega = await db.get(Usuario, colega_id)
    if colega is None or not colega.ativo or colega.id == user.user_id:
        raise HTTPException(status_code=404, detail="Colega indisponível")
    chave, arquivo = await guardar_audio(request)
    try:
        mensagem = MensagemInterna(
            remetente_id=user.user_id, destinatario_id=colega_id,
            texto="", audio_chave=chave, criada_em=now(),
        )
        db.add(mensagem)
        await db.commit()
        return {"id": mensagem.id}
    except Exception:
        arquivo.unlink(missing_ok=True)
        raise


@router.post("/grupos/{setor_id}/audios")
async def enviar_audio_grupo(
    setor_id: int, request: Request, db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(get_current_user),
):
    await grupo_visivel(db, setor_id, user)
    chave, arquivo = await guardar_audio(request)
    try:
        mensagem = MensagemGrupo(
            setor_id=setor_id, remetente_id=user.user_id,
            texto="", audio_chave=chave, criada_em=now(),
        )
        db.add(mensagem)
        await db.commit()
        return {"id": mensagem.id}
    except Exception:
        arquivo.unlink(missing_ok=True)
        raise


@router.patch("/mensagens/{colega_id}/{mensagem_id}")
async def editar_mensagem_direta(
    colega_id: int, mensagem_id: int, request: Request,
    db: AsyncSession = Depends(get_db), user: UsuarioAtual = Depends(get_current_user),
):
    texto = (await form(request)).get("texto", "").strip()
    if not 1 <= len(texto) <= 4000:
        raise HTTPException(status_code=422, detail="Mensagem inválida")
    resultado = await db.execute(update(MensagemInterna).where(
        MensagemInterna.id == mensagem_id,
        MensagemInterna.remetente_id == user.user_id,
        MensagemInterna.destinatario_id == colega_id,
        MensagemInterna.apagada_em.is_(None),
        MensagemInterna.imagem_chave.is_(None),
        MensagemInterna.audio_chave.is_(None),
    ).values(texto=texto, editada_em=now()))
    if resultado.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=404, detail="Mensagem de texto não encontrada")
    await db.commit()
    return {"id": mensagem_id, "texto": texto, "editada": True}


@router.patch("/grupos/{setor_id}/mensagens/{mensagem_id}")
async def editar_mensagem_grupo(
    setor_id: int, mensagem_id: int, request: Request,
    db: AsyncSession = Depends(get_db), user: UsuarioAtual = Depends(get_current_user),
):
    await grupo_visivel(db, setor_id, user)
    texto = (await form(request)).get("texto", "").strip()
    if not 1 <= len(texto) <= 4000:
        raise HTTPException(status_code=422, detail="Mensagem inválida")
    resultado = await db.execute(update(MensagemGrupo).where(
        MensagemGrupo.id == mensagem_id,
        MensagemGrupo.setor_id == setor_id,
        MensagemGrupo.remetente_id == user.user_id,
        MensagemGrupo.apagada_em.is_(None),
        MensagemGrupo.imagem_chave.is_(None),
        MensagemGrupo.audio_chave.is_(None),
    ).values(texto=texto, editada_em=now()))
    if resultado.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=404, detail="Mensagem de texto não encontrada")
    await db.commit()
    return {"id": mensagem_id, "texto": texto, "editada": True}


@router.delete("/mensagens/{colega_id}/{mensagem_id}")
async def apagar_mensagem_direta(
    colega_id: int, mensagem_id: int, db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(get_current_user),
):
    mensagem = (await db.execute(select(MensagemInterna).where(
        MensagemInterna.id == mensagem_id,
        MensagemInterna.remetente_id == user.user_id,
        MensagemInterna.destinatario_id == colega_id,
        MensagemInterna.apagada_em.is_(None),
    ))).scalar_one_or_none()
    if mensagem is None:
        raise HTTPException(status_code=404, detail="Mensagem não encontrada")
    arquivos = [chave for chave in (mensagem.imagem_chave, mensagem.audio_chave) if chave]
    await db.execute(update(MensagemInterna).where(
        MensagemInterna.id == mensagem_id, MensagemInterna.apagada_em.is_(None),
    ).values(texto="", imagem_chave=None, audio_chave=None, apagada_em=now()))
    await db.commit()
    for chave in arquivos:
        caminho_media(chave).unlink(missing_ok=True)
    return {"apagada": True}


@router.delete("/grupos/{setor_id}/mensagens/{mensagem_id}")
async def apagar_mensagem_grupo(
    setor_id: int, mensagem_id: int, db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(get_current_user),
):
    await grupo_visivel(db, setor_id, user)
    mensagem = (await db.execute(select(MensagemGrupo).where(
        MensagemGrupo.id == mensagem_id,
        MensagemGrupo.setor_id == setor_id,
        MensagemGrupo.remetente_id == user.user_id,
        MensagemGrupo.apagada_em.is_(None),
    ))).scalar_one_or_none()
    if mensagem is None:
        raise HTTPException(status_code=404, detail="Mensagem não encontrada")
    arquivos = [chave for chave in (mensagem.imagem_chave, mensagem.audio_chave) if chave]
    await db.execute(update(MensagemGrupo).where(
        MensagemGrupo.id == mensagem_id, MensagemGrupo.apagada_em.is_(None),
    ).values(texto="", imagem_chave=None, audio_chave=None, apagada_em=now()))
    await db.commit()
    for chave in arquivos:
        caminho_media(chave).unlink(missing_ok=True)
    return {"apagada": True}


@router.get("/audios/{chave}")
async def ler_audio(
    chave: str, db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(get_current_user),
):
    if not re.fullmatch(r"[0-9a-f]{32}\.(mp3|ogg)", chave):
        raise HTTPException(status_code=404, detail="Áudio não encontrado")
    direta = (await db.execute(select(MensagemInterna.id).where(
        MensagemInterna.audio_chave == chave,
        or_(MensagemInterna.remetente_id == user.user_id,
            MensagemInterna.destinatario_id == user.user_id),
    ))).scalar_one_or_none()
    if direta is None:
        atual = await db.get(Usuario, user.user_id)
        grupo = (await db.execute(select(MensagemGrupo.id).where(
            MensagemGrupo.audio_chave == chave,
            *([] if user.role == "gestor" else [MensagemGrupo.setor_id == atual.setor_interno_id]),
        ))).scalar_one_or_none()
        if grupo is None:
            raise HTTPException(status_code=404, detail="Áudio não encontrado")
    arquivo = caminho_media(chave)
    if not arquivo.is_file():
        raise HTTPException(status_code=404, detail="Áudio não encontrado")
    return FileResponse(
        arquivo, media_type="audio/mpeg" if chave.endswith(".mp3") else "audio/ogg",
        headers={"Cache-Control": "private, no-store", "Accept-Ranges": "bytes"},
    )


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
                    *([] if user.role == "gestor" else [MensagemGrupo.setor_id == atual.setor_interno_id]),
                )
            )
        ).scalar_one_or_none()
        if grupo is None:
            raise HTTPException(status_code=404, detail="Imagem não encontrada")
    arquivo = caminho_media(chave)
    if not arquivo.is_file():
        raise HTTPException(status_code=404, detail="Imagem não encontrada")
    return FileResponse(
        arquivo,
        media_type="image/webp",
        headers={"Cache-Control": "private, max-age=3600"},
    )
