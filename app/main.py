import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.atendimentos import router as atendimentos_router
from app.api.auth import router as auth_router
from app.api.chamados import router as chamados_router
from app.api.eventos import router as eventos_router
from app.api.frontend import router as frontend_router
from app.api.gestor import router as gestor_router
from app.api.interno import router as interno_router
from app.api.simulador import router as simulador_router
from app.api.webhook import router as webhook_router
from app.core.config import get_settings
from app.core.database import async_session_maker
from app.providers import provider_atual
from app.services.atendimento import verificar_timers
from app.services.meshcentral_events import acompanhar_meshcentral

logger = logging.getLogger(__name__)


async def timer_loop() -> None:
    while True:
        try:
            async with async_session_maker() as db:
                await verificar_timers(db, provider_atual())
        except Exception:
            logger.exception("Falha ao verificar timers")
        await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    tarefa = asyncio.create_task(timer_loop())
    monitor = asyncio.create_task(acompanhar_meshcentral())
    try:
        yield
    finally:
        for task in (tarefa, monitor):
            task.cancel()
        for task in (tarefa, monitor):
            with suppress(asyncio.CancelledError):
                await task


app = FastAPI(title="Atendimento WhatsApp — Alpha", lifespan=lifespan)


@app.middleware("http")
async def exigir_origem_do_painel_https(request: Request, call_next):
    host = get_settings().panel_https_host
    if (
        host
        and request.url.hostname == host
        and request.method in {"POST", "PUT", "PATCH", "DELETE"}
        and request.url.path.startswith("/api/")
        and request.headers.get("origin") != f"https://{host}"
    ):
        return JSONResponse({"detail": "Origem inválida"}, status_code=403)
    return await call_next(request)


web_dir = Path(__file__).resolve().parent / "web"
if not web_dir.exists():
    web_dir = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if (web_dir / "assets").exists():
    app.mount("/assets", StaticFiles(directory=web_dir / "assets"), name="web-assets")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(frontend_router)
app.include_router(auth_router)
app.include_router(atendimentos_router)
app.include_router(gestor_router)
app.include_router(chamados_router)
app.include_router(interno_router)
app.include_router(eventos_router)
app.include_router(webhook_router)


@app.get("/", include_in_schema=False)
@app.get("/login", include_in_schema=False)
async def entrada_painel():
    return RedirectResponse("/painel", status_code=303)


@app.get("/painel", include_in_schema=False)
async def painel_react():
    index = web_dir / "index.html"
    if not index.exists():
        raise HTTPException(status_code=503, detail="Frontend ainda não compilado")
    return FileResponse(index, headers={"Cache-Control": "no-store"})


@app.get("/favicon.svg", include_in_schema=False)
async def favicon():
    arquivo = web_dir / "favicon.svg"
    if not arquivo.exists():
        raise HTTPException(status_code=404)
    return FileResponse(arquivo)


app.include_router(simulador_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    include_in_schema=False,
)
async def pagina_react(path: str, request: Request):
    if request.method != "GET" or path.startswith(("api/", "webhook/", "static/", "assets/")):
        raise HTTPException(status_code=404)
    return await painel_react()
