from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./atendimento.db"
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    whatsapp_provider: Literal["simulador", "meta"] = "simulador"
    meta_graph_version: str = "v24.0"
    meta_phone_number_id: str = ""
    meta_access_token: str = ""
    meta_verify_token: str = ""
    meta_app_secret: str = ""
    aviso_transferencia_ativo: bool = True
    aviso_transferencia_texto: str = "Seu atendimento foi transferido para {nome}."
    app_log_level: str = "INFO"
    chamado_install_token: str = ""
    panel_https_host: str = ""
    media_dir: str = "./media"
    timer_espera_segundos: int = 90
    timer_aviso_segundos: int = 60
    timer_maximo_segundos: int = 210
    expediente_inicio: str = "07:00"
    expediente_fim: str = "18:30"
    expediente_fuso: str = "America/Sao_Paulo"
    mensagem_fora_expediente: str = (
        "Estamos fora do horário de atendimento. Voltaremos no próximo expediente."
    )
    mensagem_reabertura: str = "Estamos de volta. Vamos iniciar seu atendimento."
    mensagem_standby: str = "Ainda não conseguimos um atendente. Seu pedido ficou em espera; nossa equipe responderá assim que possível."
    seed_gestor_password: str = ""
    seed_vendedor_password: str = ""
    seed_responsavel_password: str = ""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
