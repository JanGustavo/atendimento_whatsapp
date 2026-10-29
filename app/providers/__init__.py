"""Única fronteira entre o atendimento e o WhatsApp.

Re-exporta tudo que o código externo importa de app.providers,
mantendo compatibilidade total de imports.
"""

from app.providers._factory import provider_atual, provider_para_numero
from app.providers.base import MensagemEntrada, WhatsAppProvider
from app.providers.meta import MetaProvider
from app.providers.simulador import CLIENTES, SimuladorProvider, simulador_provider

__all__ = [
    "MensagemEntrada",
    "WhatsAppProvider",
    "CLIENTES",
    "SimuladorProvider",
    "simulador_provider",
    "MetaProvider",
    "provider_atual",
    "provider_para_numero",
]
