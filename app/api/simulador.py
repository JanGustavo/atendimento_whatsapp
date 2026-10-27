from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import UsuarioAtual, somente_gestor
from app.api.painel import form, templates
from app.core.database import get_db
from app.models import Conversa, Mensagem
from app.providers import CLIENTES, simulador_provider
from app.services.atendimento import receber_mensagem

router = APIRouter()


@router.get("/simulador", response_class=HTMLResponse)
async def simulador(request: Request, db: AsyncSession = Depends(get_db), user: UsuarioAtual = Depends(somente_gestor)):
    cliente = request.query_params.get("cliente", "cliente1")
    if cliente not in CLIENTES:
        raise HTTPException(status_code=404)
    numero = CLIENTES[cliente][1]
    conversa = (await db.execute(select(Conversa).where(Conversa.numero == numero).order_by(Conversa.id.desc()).limit(1))).scalar_one_or_none()
    mensagens = [] if conversa is None else (await db.execute(select(Mensagem).where(Mensagem.conversa_id == conversa.id).order_by(Mensagem.id))).scalars().all()
    nome_template = "_simulador_mensagens.html" if request.headers.get("HX-Request") else "simulador.html"
    return templates.TemplateResponse(nome_template, {"request": request, "user": user, "clientes": CLIENTES, "cliente": cliente, "mensagens": mensagens})


@router.post("/simulador")
async def simulador_enviar(request: Request, db: AsyncSession = Depends(get_db), user: UsuarioAtual = Depends(somente_gestor)):
    dados = await form(request)
    cliente = dados.get("cliente", "")
    texto = dados.get("texto", "").strip()
    if cliente not in CLIENTES or not texto or len(texto) > 4000:
        raise HTTPException(status_code=422)
    entrada = simulador_provider.parse_webhook({"id": str(uuid4()), "numero": CLIENTES[cliente][1], "texto": texto})
    await receber_mensagem(db, simulador_provider, entrada)
    return RedirectResponse(f"/simulador?cliente={cliente}", status_code=303)
