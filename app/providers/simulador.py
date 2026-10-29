"""Provider simulado para testes locais sem WhatsApp real."""
from app.providers.base import MensagemEntrada, WhatsAppProvider  # noqa: F401

# Clientes fictícios usados pelo simulador de conversas
CLIENTES: dict[str, tuple[str, str]] = {
    "cliente1": ("Cliente 1", "5511999000001"),
    "cliente2": ("Cliente 2", "5511999000002"),
    "cliente3": ("Cliente 3", "5511999000003"),
}


class SimuladorProvider:
    async def enviar_texto(self, numero: str, texto: str) -> str | None:
        return None

    def parse_webhook(self, payload: dict) -> MensagemEntrada | None:
        try:
            return MensagemEntrada(
                str(payload["id"]),
                str(payload["numero"]),
                str(payload["texto"]),
                bool(payload.get("de_mim", False)),
                str(payload.get("tipo", "texto")),
            )
        except KeyError:
            return None

    async def status(self) -> str:
        return "simulado"


# Instância global reutilizável (sem estado mutável)
simulador_provider = SimuladorProvider()
