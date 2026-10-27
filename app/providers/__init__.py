"""Única fronteira entre o atendimento e o WhatsApp.

Re-exporta tudo que o código externo importa de app.providers,
mantendo compatibilidade total de imports.
"""
from app.providers.base import MensagemEntrada, WhatsAppProvider
from app.providers.simulador import CLIENTES, SimuladorProvider, simulador_provider
from app.providers.evolution import EvolutionProvider
from app.providers._factory import provider_atual, provider_para_numero

__all__ = [
    "MensagemEntrada",
    "WhatsAppProvider",
    "CLIENTES",
    "SimuladorProvider",
    "simulador_provider",
    "EvolutionProvider",
    "provider_atual",
    "provider_para_numero",
]
