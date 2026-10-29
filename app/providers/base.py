"""Tipos base e protocolo do provider WhatsApp."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class MensagemEntrada:
    id: str
    numero: str
    texto: str
    de_mim: bool = False
    tipo: str = "texto"


class WhatsAppProvider(Protocol):
    async def enviar_texto(self, numero: str, texto: str) -> str | None: ...
    def parse_webhook(self, payload: dict) -> MensagemEntrada | None: ...
    async def status(self) -> str: ...
