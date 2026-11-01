"""Armazenamento privado de mídia no volume persistente."""

import asyncio
import tempfile
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


async def guardar_audio(request: Request) -> tuple[str, Path]:
    tipo = request.headers.get("content-type", "").split(";")[0].lower()
    if tipo not in {"audio/mpeg", "audio/ogg", "audio/webm"}:
        raise HTTPException(status_code=415, detail="Envie áudio MP3, OGG Opus ou gravação WebM")
    partes = []
    tamanho = 0
    async for parte in request.stream():
        tamanho += len(parte)
        if tamanho > 16 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Áudio acima de 16 MB")
        partes.append(parte)
    dados = b"".join(partes)
    valido = (
        (tipo == "audio/mpeg" and (dados.startswith(b"ID3") or (len(dados) > 2 and dados[0] == 0xff and dados[1] & 0xe0 == 0xe0)))
        or (tipo == "audio/ogg" and dados.startswith(b"OggS") and b"OpusHead" in dados[:128])
        or (tipo == "audio/webm" and dados.startswith(b"\x1a\x45\xdf\xa3"))
    )
    if not valido:
        raise HTTPException(status_code=422, detail="Áudio inválido; use MP3 ou OGG Opus")
    if tipo == "audio/webm":
        with tempfile.TemporaryDirectory() as pasta_temporaria:
            origem = Path(pasta_temporaria) / "gravacao.webm"
            destino = Path(pasta_temporaria) / "gravacao.ogg"
            origem.write_bytes(dados)
            processo = await asyncio.create_subprocess_exec(
                "ffmpeg", "-nostdin", "-v", "error", "-i", str(origem),
                "-vn", "-ac", "1", "-ar", "48000", "-c:a", "libopus", "-application", "voip",
                "-b:a", "24k", "-f", "ogg", str(destino),
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
            )
            try:
                _, erro = await asyncio.wait_for(processo.communicate(), timeout=30)
            except TimeoutError:
                processo.kill()
                await processo.communicate()
                raise HTTPException(status_code=422, detail="Tempo de conversão do áudio excedido")
            if processo.returncode != 0 or not destino.is_file():
                raise HTTPException(status_code=422, detail="Não foi possível converter a gravação")
            dados = destino.read_bytes()
            if len(dados) > 16 * 1024 * 1024 or not dados.startswith(b"OggS") or b"OpusHead" not in dados[:128]:
                raise HTTPException(status_code=422, detail="Gravação convertida inválida")
            tipo = "audio/ogg"
    pasta = Path(get_settings().media_dir)
    pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
    chave = f"{uuid4().hex}.{'mp3' if tipo == 'audio/mpeg' else 'ogg'}"
    arquivo = pasta / chave
    with arquivo.open("xb") as destino:
        destino.write(dados)
    return chave, arquivo
