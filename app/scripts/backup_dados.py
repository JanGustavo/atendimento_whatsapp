"""Backup consistente do SQLite e dos arquivos de mídia do volume Docker."""

import argparse
import hashlib
import json
import shutil
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


def digest(path: Path) -> str:
    hash_ = hashlib.sha256()
    with path.open("rb") as arquivo:
        for parte in iter(lambda: arquivo.read(1024 * 1024), b""):
            hash_.update(parte)
    return hash_.hexdigest()


def arquivos(pasta: Path) -> dict[str, str]:
    return {
        str(path.relative_to(pasta)): digest(path)
        for path in sorted(pasta.rglob("*")) if path.is_file()
    }


def verificar(backup: Path) -> None:
    """Restaura em pasta temporária e confere banco e mídia sem tocar produção."""
    with tempfile.TemporaryDirectory(prefix="restauracao-") as temp:
        destino = Path(temp)
        shutil.copy2(backup / "atendimento.db", destino / "atendimento.db")
        shutil.copytree(backup / "media", destino / "media")
        with sqlite3.connect(destino / "atendimento.db") as db:
            assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        manifesto = json.loads((backup / "manifesto.json").read_text())
        assert digest(destino / "atendimento.db") == manifesto["banco_sha256"]
        assert arquivos(destino / "media") == manifesto["arquivos"]
    print(f"Restauração verificada: {backup.name}")


def criar(origem: Path, media: Path, destino: Path, dias: int) -> Path:
    if dias < 1 or not origem.is_file():
        raise ValueError("Banco ausente ou prazo de retenção inválido")
    destino.mkdir(parents=True, exist_ok=True)
    agora = datetime.now(timezone.utc)
    nome = "backup-" + agora.strftime("%Y%m%dT%H%M%SZ")
    final = destino / nome
    if final.exists():
        raise FileExistsError(final)
    with tempfile.TemporaryDirectory(prefix=".backup-temporario-", dir=destino) as temp:
        temporario = Path(temp)
        with sqlite3.connect(f"file:{origem}?mode=ro", uri=True) as fonte:
            with sqlite3.connect(temporario / "atendimento.db") as copia:
                fonte.backup(copia)
        shutil.copytree(media, temporario / "media") if media.is_dir() else (temporario / "media").mkdir()
        manifesto = {
            "criado_em_utc": agora.isoformat(),
            "banco_sha256": digest(temporario / "atendimento.db"),
            "arquivos": arquivos(temporario / "media"),
        }
        (temporario / "manifesto.json").write_text(json.dumps(manifesto, indent=2))
        shutil.move(str(temporario), str(final))
    verificar(final)
    limite = agora - timedelta(days=dias)
    for antigo in destino.glob("backup-*"):
        if antigo.is_dir() and antigo != final:
            try:
                data = datetime.strptime(antigo.name, "backup-%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if data < limite:
                shutil.rmtree(antigo)
    return final


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--media", type=Path)
    parser.add_argument("--dest", type=Path)
    parser.add_argument("--keep-days", type=int, default=30)
    parser.add_argument("--verify", type=Path)
    argumentos = parser.parse_args()
    if argumentos.verify:
        verificar(argumentos.verify)
    else:
        print(criar(argumentos.source, argumentos.media, argumentos.dest, argumentos.keep_days))
