"""Única fronteira entre o atendimento e o WhatsApp."""
from dataclasses import dataclass
from typing import Protocol
import httpx
from app.core.config import get_settings

@dataclass(frozen=True)
class MensagemEntrada:
    id: str
    numero: str
    texto: str
    de_mim: bool = False
    tipo: str = "texto"

class WhatsAppProvider(Protocol):
    async def enviar_texto(self, numero: str, texto: str) -> None: ...
    def parse_webhook(self, payload: dict) -> MensagemEntrada | None: ...
    async def status(self) -> str: ...

class SimuladorProvider:
    async def enviar_texto(self, numero: str, texto: str) -> None:
        return None

    def parse_webhook(self, payload: dict) -> MensagemEntrada | None:
        try:
            return MensagemEntrada(str(payload["id"]), str(payload["numero"]), str(payload["texto"]),
                                   bool(payload.get("de_mim", False)), str(payload.get("tipo", "texto")))
        except KeyError:
            return None

    async def status(self) -> str:
        return "simulado"

class EvolutionProvider:
    def __init__(self, base_url: str, api_key: str, instancia: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.instancia = instancia

    async def enviar_texto(self, numero: str, texto: str) -> None:
        numero = "".join(c for c in numero if c.isdigit())
        if not numero:
            raise ValueError("Número inválido")
        async with httpx.AsyncClient(timeout=5) as client:
            resposta = await client.post(f"{self.base_url}/message/sendText/{self.instancia}",
                                        headers={"apikey": self.api_key}, json={"number": numero, "text": texto})
            resposta.raise_for_status()

    def parse_webhook(self, payload: dict) -> MensagemEntrada | None:
        if str(payload.get("event", "")).upper().replace(".", "_") != "MESSAGES_UPSERT":
            return None
        data = payload.get("data")
        if isinstance(data, list):
            data = data[0] if data else None
        if not isinstance(data, dict):
            return None
        chave = data.get("key") or {}
        jid = str(chave.get("remoteJid") or "")
        if jid.endswith("@g.us") or not jid:
            return None
        numero = jid.split("@", 1)[0]
        if not numero.isdigit():
            return None
        mensagem = data.get("message") or {}
        for envelope in ("ephemeralMessage", "viewOnceMessage", "viewOnceMessageV2"):
            if envelope in mensagem:
                mensagem = (mensagem[envelope] or {}).get("message") or {}
        texto = mensagem.get("conversation") or (mensagem.get("extendedTextMessage") or {}).get("text")
        tipo = "texto"
        if not isinstance(texto, str) or not texto.strip():
            if not any(chave.endswith("Message") for chave in mensagem):
                return None
            texto, tipo = "[Mídia recebida]", "midia"
        identidade = str(chave.get("id") or "")
        if not identidade:
            return None
        return MensagemEntrada(identidade, numero, texto, bool(chave.get("fromMe")), tipo)

    async def status(self) -> str:
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                resposta = await client.get(f"{self.base_url}/instance/connectionState/{self.instancia}",
                                           headers={"apikey": self.api_key})
                resposta.raise_for_status()
                return "conectado" if resposta.json().get("instance", {}).get("state") == "open" else "desconectado"
        except (httpx.HTTPError, ValueError, KeyError):
            return "desconectado"

simulador_provider = SimuladorProvider()
CLIENTES = {
    "cliente1": ("Cliente 1", "5511999000001"),
    "cliente2": ("Cliente 2", "5511999000002"),
    "cliente3": ("Cliente 3", "5511999000003"),
}

def provider_atual() -> WhatsAppProvider:
    config = get_settings()
    if config.whatsapp_provider == "simulador":
        return simulador_provider
    return EvolutionProvider(config.evolution_base_url, config.evolution_api_key, config.evolution_instancia)

def provider_para_numero(numero: str) -> WhatsAppProvider:
    return simulador_provider if numero in {valor[1] for valor in CLIENTES.values()} else provider_atual()
