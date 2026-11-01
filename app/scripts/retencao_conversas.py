"""Exclui conversas encerradas há mais de N dias e suas mídias sem referências."""

import argparse
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


REFERENCIAS = (
    ("conversas", "foto_chave"),
    ("mensagens", "imagem_chave"),
    ("mensagens", "audio_chave"),
    ("mensagens_internas", "imagem_chave"),
    ("mensagens_internas", "audio_chave"),
    ("mensagens_grupo", "imagem_chave"),
    ("mensagens_grupo", "audio_chave"),
    ("usuarios", "foto_chave"),
)


def limpar(banco: Path, media: Path, dias: int, instante: datetime | None = None) -> int:
    if dias < 1:
        raise ValueError("Prazo de retenção inválido")
    agora = instante or datetime.now(timezone.utc)
    limite = (agora - timedelta(days=dias)).replace(tzinfo=None)
    chaves: set[str] = set()
    with sqlite3.connect(banco, timeout=30) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=30000")
        db.execute("BEGIN IMMEDIATE")
        conversas = db.execute(
            "SELECT id, foto_chave FROM conversas "
            "WHERE status='encerrada' AND encerrada_em IS NOT NULL AND encerrada_em < ?",
            (limite.isoformat(sep=" "),),
        ).fetchall()
        for conversa_id, foto_chave in conversas:
            if foto_chave:
                chaves.add(foto_chave)
            for imagem, audio in db.execute(
                "SELECT imagem_chave, audio_chave FROM mensagens WHERE conversa_id=?", (conversa_id,)
            ):
                chaves.update(chave for chave in (imagem, audio) if chave)
            for tabela in ("leituras_conversas", "atribuicoes", "mensagens"):
                db.execute(f"DELETE FROM {tabela} WHERE conversa_id=?", (conversa_id,))
            db.execute("DELETE FROM conversas WHERE id=?", (conversa_id,))
        db.commit()
        # A mesma mídia pode estar referenciada em outra conversa ou no chat interno.
        for chave in chaves:
            if Path(chave).name != chave or chave in {"", ".", ".."}:
                continue
            if any(
                db.execute(f"SELECT 1 FROM {tabela} WHERE {coluna}=? LIMIT 1", (chave,)).fetchone()
                for tabela, coluna in REFERENCIAS
            ):
                continue
            arquivo = media / chave
            if arquivo.is_file() and arquivo.resolve().parent == media.resolve():
                arquivo.unlink()
    return len(conversas)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--media", type=Path, required=True)
    parser.add_argument("--days", type=int, default=180)
    argumentos = parser.parse_args()
    print(f"Conversas encerradas removidas: {limpar(argumentos.database, argumentos.media, argumentos.days)}")
