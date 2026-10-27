from app.core.config import Settings


def test_configuracao_do_env_para_timer_e_provider(tmp_path, monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("WHATSAPP_PROVIDER", raising=False)
    for nome in ("TIMER_ESPERA_SEGUNDOS", "TIMER_AVISO_SEGUNDOS", "TIMER_MAXIMO_SEGUNDOS"):
        monkeypatch.delenv(nome, raising=False)
    arquivo = tmp_path / ".env"
    arquivo.write_text(
        "JWT_SECRET=segredo-do-arquivo\n"
        "WHATSAPP_PROVIDER=simulador\n"
        "TIMER_ESPERA_SEGUNDOS=61\n"
        "TIMER_AVISO_SEGUNDOS=31\n"
        "TIMER_MAXIMO_SEGUNDOS=151\n",
        encoding="utf-8",
    )
    config = Settings(_env_file=arquivo)
    assert config.jwt_secret == "segredo-do-arquivo"
    assert config.whatsapp_provider == "simulador"
    assert (config.timer_espera_segundos, config.timer_aviso_segundos, config.timer_maximo_segundos) == (61, 31, 151)
