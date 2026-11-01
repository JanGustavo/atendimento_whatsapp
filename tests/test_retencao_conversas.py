from datetime import datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models import Conversa, Mensagem
from app.scripts.retencao_conversas import limpar


def test_retencao_apaga_so_encerradas_antigas_e_preserva_midia_em_uso(tmp_path):
    banco = tmp_path / "atendimento.db"
    media = tmp_path / "media"
    media.mkdir()
    (media / "unica.webp").write_bytes(b"imagem antiga")
    (media / "compartilhada.webp").write_bytes(b"imagem em uso")
    engine = create_engine(f"sqlite:///{banco}")
    Base.metadata.create_all(engine)
    agora = datetime(2026, 11, 1)
    with Session(engine) as db:
        db.add_all([
            Conversa(id=1, numero="551100000001", status="encerrada", etapa="encerrada",
                     encerrada_em=agora - timedelta(days=181)),
            Conversa(id=2, numero="551100000002", status="encerrada", etapa="encerrada",
                     encerrada_em=agora - timedelta(days=179), foto_chave="compartilhada.webp"),
            Conversa(id=3, numero="551100000003", status="aberta", etapa="atribuida",
                     encerrada_em=None),
        ])
        db.add_all([
            Mensagem(conversa_id=1, origem="cliente", texto="antiga", imagem_chave="unica.webp"),
            Mensagem(conversa_id=1, origem="cliente", texto="antiga 2", audio_chave="compartilhada.webp"),
        ])
        db.commit()
    assert limpar(banco, media, 180, agora) == 1
    with Session(engine) as db:
        assert [c.id for c in db.scalars(select(Conversa).order_by(Conversa.id))] == [2, 3]
        assert db.scalars(select(Mensagem)).all() == []
    assert not (media / "unica.webp").exists()
    assert (media / "compartilhada.webp").exists()
    assert limpar(banco, media, 180, agora) == 0
    engine.dispose()
