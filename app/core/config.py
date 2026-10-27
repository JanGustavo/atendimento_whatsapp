from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./atendimento.db"
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    whatsapp_provider: Literal["simulador", "evolution"] = "simulador"
    evolution_base_url: str = "http://evolution:8080"
    evolution_api_key: str = ""
    evolution_instancia: str = "fortgiro"
    evolution_webhook_secret: str = ""
    aviso_transferencia_ativo: bool = True
    aviso_transferencia_texto: str = "Seu atendimento foi transferido para {nome}."
    app_log_level: str = "INFO"
    chamado_install_token: str = ""
    timer_espera_segundos: int = 60
    timer_aviso_segundos: int = 30
    timer_maximo_segundos: int = 150
    seed_gestor_password: str = ""
    seed_vendedor_password: str = ""
    seed_responsavel_password: str = ""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
