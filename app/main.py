import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.frontend import router as frontend_router
from app.api.chamados import router as chamados_router
from app.api.webhook import router as webhook_router
from app.api.painel import router
from app.api.simulador import router as simulador_router
from app.core.database import async_session_maker
from app.providers import provider_atual
from app.services.atendimento import verificar_timers

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
    try:
        yield
    finally:
        tarefa.cancel()
        with suppress(asyncio.CancelledError):
            await tarefa


app = FastAPI(title="Atendimento WhatsApp — Alpha", lifespan=lifespan)
web_dir = Path(__file__).resolve().parent / "web"
if not web_dir.exists():
    web_dir = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if (web_dir / "assets").exists():
    app.mount("/assets", StaticFiles(directory=web_dir / "assets"), name="web-assets")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(frontend_router)
app.include_router(chamados_router)
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
    return FileResponse(index)


@app.get("/favicon.svg", include_in_schema=False)
async def favicon():
    arquivo = web_dir / "favicon.svg"
    if not arquivo.exists():
        raise HTTPException(status_code=404)
    return FileResponse(arquivo)


app.include_router(router)
app.include_router(simulador_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
