"""Solicitação remota e link para o desktop no MeshCentral."""

from typing import Protocol
from urllib.parse import urlencode, urlparse

from fastapi import HTTPException

from app.core.config import get_settings
from app.models import Computador


class RemotoProvider(Protocol):
    async def solicitar_acesso(self, computador: Computador) -> str: ...
    def link_acesso(self, computador: Computador) -> str | None: ...


class RemotoSimulado:
    async def solicitar_acesso(self, computador: Computador) -> str:
        return "simulado"

    def link_acesso(self, computador: Computador) -> str | None:
        return None


class RemotoMeshCentral:
    def __init__(self, url: str):
        parsed = urlparse(url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
            raise HTTPException(status_code=503, detail="Endereço HTTPS do MeshCentral não configurado")
        self.url = url.rstrip("/")

    async def solicitar_acesso(self, computador: Computador) -> str:
        if not computador.mesh_node_id:
            raise HTTPException(status_code=409, detail="Cadastre o Mesh node ID deste computador")
        return "aceito"

    def link_acesso(self, computador: Computador) -> str | None:
        if not computador.mesh_node_id:
            return None
        return f"{self.url}/?{urlencode({'node': computador.mesh_node_id, 'viewmode': 11})}"


remoto_provider: RemotoProvider = RemotoSimulado()


def provider_remoto_atual() -> RemotoProvider:
    config = get_settings()
    if config.remoto_provider == "meshcentral":
        return RemotoMeshCentral(config.meshcentral_url)
    return remoto_provider
