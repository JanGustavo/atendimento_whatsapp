"""Presença calculada a partir da última atividade do painel."""

from datetime import timedelta

from app.core.config import get_settings
from app.core.utils import now
from app.models import Usuario


def esta_conectado(usuario: Usuario) -> bool:
    visto = usuario.ultima_atividade_em
    return bool(
        usuario.ativo
        and visto is not None
        and visto >= now() - timedelta(seconds=get_settings().presenca_limite_segundos)
    )
