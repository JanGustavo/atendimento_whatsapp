"""Read-only MeshCentral event stream consumer.

Events are emitted by MeshCentral's authenticated /control.ashx websocket.
Only relaylog protocol 2, msgid 15 (connected) / 11 (disconnected) count.
This module never requests a tunnel or grants remote-control rights.
"""
import asyncio
import base64
import json
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from websockets.asyncio.client import connect

from app.core.config import get_settings
from app.core.database import async_session_maker
from app.core.utils import now
from app.models import AcessoRemoto, Computador, SessaoMeshCentral, Usuario

log = logging.getLogger(__name__)
_monitor_conectado = False

INICIO_DESKTOP = 15
FIM_DESKTOP = 11
LIMITE_REPLAY = 2000


def monitor_conectado() -> bool:
    return _monitor_conectado


def websocket_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.path not in ("", "/") or parsed.query
            or parsed.fragment):
        raise ValueError("MESHCENTRAL_URL deve ser uma origem HTTPS sem credenciais ou caminho")
    return f"wss://{parsed.netloc}/control.ashx"


def parse_horario(valor) -> datetime | None:
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        # Os timestamps Unix podem chegar em segundos ou milissegundos.
        if not 0 < valor < 1e15:
            return None
        try:
            return datetime.fromtimestamp(valor / (1000 if valor > 1e11 else 1), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(valor, str):
        try:
            data = datetime.fromisoformat(valor.replace("Z", "+00:00"))
            return data.replace(tzinfo=timezone.utc) if data.tzinfo is None else data.astimezone(timezone.utc)
        except ValueError:
            return None
    return None


def interpretar_relay(evento: dict):
    """Reject unknown, uncorrelated or non-desktop relay events."""
    if not isinstance(evento, dict):
        return None
    if evento.get("etype") != "relay" or evento.get("action") != "relaylog":
        return None
    if str(evento.get("protocol")) != "2" or evento.get("msgid") not in (INICIO_DESKTOP, FIM_DESKTOP):
        return None
    args = evento.get("msgArgs")
    if not isinstance(args, list) or not args or not isinstance(args[0], str):
        return None
    sessao = args[0]
    nodeid = evento.get("nodeid")
    userid = evento.get("userid")
    if (not isinstance(nodeid, str) or not nodeid.startswith("node/")
            or not isinstance(userid, str) or not userid.startswith("user/")
            or not 1 <= len(sessao) <= 255 or len(nodeid) > 255 or len(userid) > 255):
        return None
    horario = parse_horario(evento.get("time"))
    if horario is None:
        # Nunca usar horario inventado ao restaurar eventos antigos.
        return None
    return {
        "id": sessao, "nodeid": nodeid, "userid": userid,
        "username": str(evento.get("username") or userid)[:120],
        "inicio": evento["msgid"] == INICIO_DESKTOP, "horario": horario,
    }


async def registrar_evento(db: AsyncSession, evento: dict) -> bool:
    """Idempotent by (MeshCentral session ID, MeshCentral node ID).

    Orphaned sessions remain recorded, even if no FortGiro consent matches.
    """
    dados = interpretar_relay(evento)
    if dados is None:
        return False

    computador = (await db.execute(
        select(Computador).where(Computador.mesh_node_id == dados["nodeid"])
    )).scalars().first()
    if computador is None:
        # O banco de atendimentos só audita os nós cadastrados.
        return False

    registro = (await db.execute(
        select(SessaoMeshCentral).where(
            SessaoMeshCentral.mesh_node_id == dados["nodeid"],
            SessaoMeshCentral.mesh_session_id == dados["id"],
        )
    )).scalar_one_or_none()

    if registro is None:
        registro = SessaoMeshCentral(
            mesh_node_id=dados["nodeid"], mesh_session_id=dados["id"],
            mesh_user_id=dados["userid"], mesh_username=dados["username"],
            computador_id=computador.id, estado="desconhecida",
        )
        db.add(registro)

    momento = dados["horario"]
    if dados["inicio"]:
        if registro.inicio_em is None or momento < registro.inicio_em:
            registro.inicio_em = momento
        # Replay de início não reabre uma sessão já encerrada.
        if registro.fim_em is None:
            registro.estado = "ativa"
        if registro.acesso_id is None:
            operador = (await db.execute(
                select(Usuario).where(
                    Usuario.mesh_user_id == dados["userid"],
                    Usuario.ativo.is_(True),
                )
            )).scalar_one_or_none()
            if operador is not None:
                acesso = (await db.execute(
                    select(AcessoRemoto)
                    .where(
                        AcessoRemoto.computador_id == computador.id,
                        AcessoRemoto.solicitante_id == operador.id,
                        AcessoRemoto.resultado == "autorizado",
                        AcessoRemoto.autorizado_em.is_not(None),
                        AcessoRemoto.fim_em.is_(None),
                    )
                    .order_by(AcessoRemoto.autorizado_em.desc())
                )).scalars().first()
                if acesso is not None:
                    autorizado = acesso.autorizado_em
                    if autorizado.tzinfo is None:
                        autorizado = autorizado.replace(tzinfo=timezone.utc)
                    if autorizado <= momento <= autorizado + timedelta(minutes=30):
                        registro.acesso_id = acesso.id
    else:
        if registro.fim_em is None or momento > registro.fim_em:
            registro.fim_em = momento
        registro.estado = "encerrada"
    # Handle both an out-of-order end and duplicate events without reopening.
    registro.observado_em = now()
    await db.flush()
    return True


async def consumir_mensagem(payload: dict, maker=async_session_maker) -> int:
    """Accept only MeshCentral's events stream and historical events response."""
    eventos = []
    if not isinstance(payload, dict):
        return 0
    if payload.get("action") == "event" and isinstance(payload.get("event"), dict):
        eventos = [payload["event"]]
    elif payload.get("action") == "events" and payload.get("responseid") == "fortgiro-replay":
        if isinstance(payload.get("events"), list):
            eventos = payload["events"][:LIMITE_REPLAY]
    # Chronological replay and idempotency handle reversed history results.
    eventos.sort(key=lambda x: str(x.get("time", "")) if isinstance(x, dict) else "")
    count = 0
    for evento in eventos:
        async with maker() as db:
            if await registrar_evento(db, evento):
                await db.commit()
                count += 1
    return count


async def acompanhar_meshcentral():
    """Reconnect and replay events after a connection failure.

    Strict TLS certificate validation; credentials never appear in URL/logs.
    """
    global _monitor_conectado
    config = get_settings()
    if not config.meshcentral_event_monitor:
        return
    if not config.meshcentral_audit_username or not config.meshcentral_audit_password:
        log.error("Monitor MeshCentral desligado: credenciais nao configuradas")
        return
    try:
        url = websocket_url(config.meshcentral_url)
    except ValueError as exc:
        log.error("Monitor MeshCentral desligado: %s", exc)
        return

    auth = ",".join(
        base64.b64encode(parte.encode()).decode("ascii")
        for parte in (config.meshcentral_audit_username, config.meshcentral_audit_password)
    )
    retry = 3
    while True:
        try:
            async with connect(
                url, additional_headers={"x-meshauth": auth},
                open_timeout=12, ping_interval=20, ping_timeout=20,
                max_size=2**20,
            ) as socket:
                _monitor_conectado = True
                retry = 3
                await socket.send(json.dumps(
                    {"action": "events", "limit": LIMITE_REPLAY, "responseid": "fortgiro-replay"}
                ))
                async for raw in socket:
                    try:
                        await consumir_mensagem(json.loads(raw))
                    except (ValueError, TypeError):
                        log.warning("Mensagem MeshCentral invalida ignorada")
                    except Exception:
                        log.exception("Erro ao registrar evento MeshCentral")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("Monitor MeshCentral desconectado (%s)", type(exc).__name__)
        finally:
            _monitor_conectado = False
        await asyncio.sleep(retry)
        retry = min(retry * 2, 30)
