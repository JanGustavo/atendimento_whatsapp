"""Factory: escolhe o provider ativo com base nas configurações."""
from app.core.config import get_settings
from app.providers.base import WhatsAppProvider
from app.providers.evolution import EvolutionProvider
from app.providers.simulador import CLIENTES, simulador_provider


def provider_atual() -> WhatsAppProvider:
    config = get_settings()
    if config.whatsapp_provider == "simulador":
        return simulador_provider
    return EvolutionProvider(config.evolution_base_url, config.evolution_api_key, config.evolution_instancia)


def provider_para_numero(numero: str) -> WhatsAppProvider:
    """Retorna simulador se o número pertencer a um cliente de teste."""
    numeros_simulados = {v[1] for v in CLIENTES.values()}
    return simulador_provider if numero in numeros_simulados else provider_atual()
