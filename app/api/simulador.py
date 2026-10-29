from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import UsuarioAtual, somente_gestor
from app.api._shared import form
from app.core.database import get_db
from app.providers import CLIENTES, simulador_provider
from app.services.atendimento import receber_mensagem
from app.models import SimuladorEstado

router = APIRouter(prefix="/api/simulador")


@router.post("")
async def simulador_enviar(request: Request, db: AsyncSession = Depends(get_db), user: UsuarioAtual = Depends(somente_gestor)):
    estado = await db.get(SimuladorEstado, 1)
    if estado is None or not estado.ativo:
        raise HTTPException(status_code=403, detail="Simulador desativado")
    dados = await form(request)
    cliente = dados.get("cliente", "")
    texto = dados.get("texto", "").strip()
    if cliente not in CLIENTES or not texto or len(texto) > 4000:
        raise HTTPException(status_code=422)
    entrada = simulador_provider.parse_webhook({"id": str(uuid4()), "numero": CLIENTES[cliente][1], "texto": texto})
    await receber_mensagem(db, simulador_provider, entrada)
    return {"ok": True}
