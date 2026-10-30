"""Armazenamento privado de WebP no volume persistente."""

from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, Request

from app.core.config import get_settings


def foto_url(usuario) -> str | None:
    return f"/api/usuarios/{usuario.id}/foto?v={usuario.foto_chave}" if usuario.foto_chave else None


def caminho_media(chave: str) -> Path:
    return Path(get_settings().media_dir) / chave


async def guardar_webp(request: Request) -> tuple[str, Path]:
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
    pasta = Path(get_settings().media_dir)
    pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
    chave = f"{uuid4().hex}.webp"
    arquivo = pasta / chave
    with arquivo.open("xb") as destino:
        destino.write(dados)
    return chave, arquivo
