"""Contrato único do acesso remoto; MeshCentral poderá implementá-lo depois."""
from typing import Protocol

from app.models import Computador


class RemotoProvider(Protocol):
    async def solicitar_acesso(self, computador: Computador) -> str: ...


class RemotoSimulado:
    async def solicitar_acesso(self, computador: Computador) -> str:
        return "simulado"


remoto_provider: RemotoProvider = RemotoSimulado()
