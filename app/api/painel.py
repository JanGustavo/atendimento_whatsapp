from datetime import timedelta
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import UsuarioAtual, get_current_user, somente_gestor
from app.core.config import get_settings
from app.core.database import get_db
from app.models import Atribuicao, Conversa, Mensagem, Setor, Usuario
from app.providers import provider_atual, provider_para_numero
from app.services.atendimento import now
from app.services.auth_service import create_access_token, get_password_hash, verify_password

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


async def form(request: Request) -> dict[str, str]:
    body = (await request.body()).decode("utf-8")
    return {key: values[-1] for key, values in parse_qs(body, keep_blank_values=True).items()}


def redirect(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=303)


@router.get("/", include_in_schema=False)
async def inicio():
    return redirect("/atendimentos")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
async def login(request: Request, db: AsyncSession = Depends(get_db)):
    dados = await form(request)
    email = dados.get("email", "").strip().lower()
    usuario = (await db.execute(select(Usuario).where(Usuario.email == email))).scalar_one_or_none()
    if usuario is None or not usuario.ativo or not verify_password(dados.get("senha", ""), usuario.senha_hash):
        return templates.TemplateResponse("login.html", {"request": request, "erro": "Login inválido"}, status_code=401)
    resposta = redirect("/gestor" if usuario.role == "gestor" else "/atendimentos")
    resposta.set_cookie("acesso", create_access_token(usuario.id, usuario.role), httponly=True, samesite="lax", secure=request.url.scheme == "https")
    return resposta


@router.post("/sair")
async def sair():
    resposta = redirect("/login")
    resposta.delete_cookie("acesso")
    return resposta


def escopo(user: UsuarioAtual):
    if user.role == "gestor":
        return True
    return Conversa.atribuido_id == user.user_id


async def conversa_visivel(db: AsyncSession, conversa_id: int, user: UsuarioAtual) -> Conversa:
    stmt = select(Conversa).where(Conversa.id == conversa_id, escopo(user))
    conversa = (await db.execute(stmt)).scalar_one_or_none()
    if conversa is None:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    return conversa


@router.get("/atendimentos", response_class=HTMLResponse)
async def atendimentos(request: Request, db: AsyncSession = Depends(get_db), user: UsuarioAtual = Depends(get_current_user)):
    stmt = select(Conversa).where(Conversa.atribuido_id == user.user_id).order_by(Conversa.id.desc())
    busca = request.query_params.get("q", "").strip()
    if busca:
        stmt = stmt.where(Conversa.numero.contains(busca))
    conversas = (await db.execute(stmt)).scalars().all()
    nome_template = "_lista.html" if request.headers.get("HX-Request") else "atendimentos.html"
    return templates.TemplateResponse(nome_template, {"request": request, "user": user, "conversas": conversas, "busca": busca})


@router.get("/atendimentos/{conversa_id}", response_class=HTMLResponse)
async def detalhe(conversa_id: int, request: Request, db: AsyncSession = Depends(get_db), user: UsuarioAtual = Depends(get_current_user)):
    conversa = await conversa_visivel(db, conversa_id, user)
    mensagens = (await db.execute(select(Mensagem).where(Mensagem.conversa_id == conversa_id).order_by(Mensagem.id))).scalars().all()
    nome_template = "_mensagens.html" if request.headers.get("HX-Request") else "conversa.html"
    return templates.TemplateResponse(nome_template, {"request": request, "user": user, "conversa": conversa, "mensagens": mensagens})


@router.post("/atendimentos/{conversa_id}/mensagens")
async def enviar(conversa_id: int, request: Request, db: AsyncSession = Depends(get_db), user: UsuarioAtual = Depends(get_current_user)):
    conversa = await conversa_visivel(db, conversa_id, user)
    dados = await form(request)
    texto = dados.get("texto", "").strip()
    if not texto or len(texto) > 4000:
        raise HTTPException(status_code=422, detail="Texto inválido")
    if conversa.status != "aberta":
        raise HTTPException(status_code=409, detail="Conversa encerrada")
    condicoes = [Conversa.id == conversa.id, Conversa.status == "aberta"]
    if user.role != "gestor":
        condicoes.append(Conversa.atribuido_id == user.user_id)
    resultado = await db.execute(update(Conversa).where(*condicoes).values(status="aberta"))
    if resultado.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    mensagem = Mensagem(conversa_id=conversa.id, autor_id=user.user_id, origem="humano",
                        texto=texto, envio_status="pendente", criada_em=now())
    db.add(mensagem)
    await db.flush()
    try:
        await provider_para_numero(conversa.numero).enviar_texto(conversa.numero, texto)
    except Exception:
        mensagem.envio_status = "falhou"
        await db.commit()
        raise HTTPException(status_code=502, detail="Envio ao WhatsApp falhou. A mensagem ficou marcada como falhou; tente enviá-la novamente.")
    mensagem.envio_status = "enviada"
    if user.role == "vendedor":
        await db.execute(update(Conversa).where(*condicoes).values(
            primeira_resposta_em=func.coalesce(Conversa.primeira_resposta_em, now()),
            timer_prazo_em=None, etapa="atribuida"))
    await db.commit()
    return redirect(f"/atendimentos/{conversa.id}")


@router.post("/atendimentos/{conversa_id}/encerrar")
async def encerrar(conversa_id: int, db: AsyncSession = Depends(get_db), user: UsuarioAtual = Depends(get_current_user)):
    conversa = await conversa_visivel(db, conversa_id, user)
    condicoes = [Conversa.id == conversa.id, Conversa.status == "aberta"]
    if user.role != "gestor":
        condicoes.append(Conversa.atribuido_id == user.user_id)
    resultado = await db.execute(update(Conversa).where(*condicoes).values(
        status="encerrada", etapa="encerrada", timer_prazo_em=None))
    if resultado.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    await db.commit()
    return redirect("/atendimentos")


@router.get("/gestor", response_class=HTMLResponse)
async def gestor(request: Request, db: AsyncSession = Depends(get_db), user: UsuarioAtual = Depends(somente_gestor)):
    vendedor = request.query_params.get("vendedor", "")
    stmt = select(Conversa).order_by(Conversa.id.desc())
    if vendedor.isdecimal():
        stmt = stmt.where(Conversa.atribuido_id == int(vendedor))
    conversas = (await db.execute(stmt)).scalars().all()
    usuarios = (await db.execute(select(Usuario).order_by(Usuario.id))).scalars().all()
    setores = (await db.execute(select(Setor).order_by(Setor.ordem))).scalars().all()
    whatsapp_status = await provider_atual().status()
    return templates.TemplateResponse("gestor.html", {"request": request, "user": user, "conversas": conversas, "usuarios": usuarios, "setores": setores, "filtro": vendedor, "whatsapp_status": whatsapp_status})


@router.post("/gestor/usuarios")
async def criar_usuario(request: Request, db: AsyncSession = Depends(get_db), user: UsuarioAtual = Depends(somente_gestor)):
    dados = await form(request)
    role = dados.get("role", "")
    if role not in {"vendedor", "responsavel", "gestor"} or len(dados.get("senha", "")) < 8:
        raise HTTPException(status_code=422, detail="Papel ou senha inválidos")
    email = dados.get("email", "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=422, detail="Email inválido")
    if (await db.execute(select(Usuario.id).where(Usuario.email == email))).first():
        raise HTTPException(status_code=409, detail="Email já existe")
    db.add(Usuario(nome=dados.get("nome", "").strip(), email=email, senha_hash=get_password_hash(dados["senha"]), role=role, ativo=True, online=True))
    await db.commit()
    return redirect("/gestor")


@router.post("/gestor/usuarios/{usuario_id}")
async def editar_usuario(usuario_id: int, request: Request, db: AsyncSession = Depends(get_db), user: UsuarioAtual = Depends(somente_gestor)):
    usuario = await db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=404)
    dados = await form(request)
    role = dados.get("role", usuario.role)
    if role not in {"vendedor", "responsavel", "gestor"}:
        raise HTTPException(status_code=422)
    email = dados.get("email", usuario.email).strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=422, detail="Email inválido")
    if email != usuario.email and (await db.execute(select(Usuario.id).where(Usuario.email == email))).first():
        raise HTTPException(status_code=409, detail="Email já existe")
    usuario.nome = dados.get("nome", usuario.nome).strip()
    usuario.email = email
    usuario.role = role
    usuario.ativo = dados.get("ativo") == "on"
    usuario.online = dados.get("online") == "on"
    if dados.get("senha"):
        if len(dados["senha"]) < 8:
            raise HTTPException(status_code=422)
        usuario.senha_hash = get_password_hash(dados["senha"])
    await db.commit()
    return redirect("/gestor")


@router.post("/gestor/setores/{setor_id}")
async def configurar_setor(setor_id: int, request: Request, db: AsyncSession = Depends(get_db), user: UsuarioAtual = Depends(somente_gestor)):
    setor = await db.get(Setor, setor_id)
    if setor is None:
        raise HTTPException(status_code=404)
    dados = await form(request)
    nome = dados.get("nome", setor.nome).strip()
    if not nome or len(nome) > 80:
        raise HTTPException(status_code=422, detail="Nome do setor inválido")
    if nome != setor.nome and (await db.execute(select(Setor.id).where(Setor.nome == nome))).first():
        raise HTTPException(status_code=409, detail="Setor já existe")
    responsavel_id = dados.get("responsavel_id", "")
    responsavel = await db.get(Usuario, int(responsavel_id)) if responsavel_id.isdecimal() else None
    if setor.ordem != 1 and (responsavel is None or responsavel.role != "responsavel" or not responsavel.ativo):
        raise HTTPException(status_code=422, detail="Responsável inválido")
    setor.nome = nome
    setor.responsavel_id = responsavel.id if responsavel else None
    await db.commit()
    return redirect("/gestor")


@router.post("/gestor/conversas/{conversa_id}/transferir")
async def transferir(conversa_id: int, request: Request, db: AsyncSession = Depends(get_db), user: UsuarioAtual = Depends(somente_gestor)):
    conversa = await conversa_visivel(db, conversa_id, user)
    dados = await form(request)
    alvo_id = dados.get("usuario_id", "")
    alvo = await db.get(Usuario, int(alvo_id)) if alvo_id.isdecimal() else None
    setor = await db.get(Setor, conversa.setor_id) if conversa.setor_id else None
    vendas = setor is not None and setor.ordem == 1
    papel_esperado = "vendedor" if vendas else "responsavel"
    if alvo is None or not alvo.ativo or alvo.role != papel_esperado:
        raise HTTPException(status_code=422, detail="Destino inválido")
    antigo = conversa.atribuido_id
    if antigo == alvo.id:
        raise HTTPException(status_code=409, detail="Conversa já atribuída a este usuário")
    instante = now()
    resultado = await db.execute(update(Conversa).where(
        Conversa.id == conversa_id, Conversa.atribuido_id == antigo, Conversa.status == "aberta",
    ).values(atribuido_id=alvo.id, etapa="atribuida", primeira_resposta_em=None,
             timer_inicio_em=instante if vendas else None,
             timer_prazo_em=instante + timedelta(seconds=get_settings().timer_espera_segundos) if vendas else None,
             timer_aviso_em=None, timer_extensoes=0))
    if resultado.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Conversa já transferida")
    db.add(Atribuicao(conversa_id=conversa_id, de_usuario_id=antigo, para_usuario_id=alvo.id, motivo="gestor", criada_em=instante))
    alvo.ultima_atribuicao_em = instante
    config = get_settings()
    if config.aviso_transferencia_ativo:
        texto = config.aviso_transferencia_texto.replace("{nome}", alvo.nome)
        mensagem = Mensagem(conversa_id=conversa.id, origem="bot", texto=texto,
                            envio_status="pendente", criada_em=now())
        db.add(mensagem)
        await db.flush()
        try:
            await provider_para_numero(conversa.numero).enviar_texto(conversa.numero, texto)
        except Exception:
            mensagem.envio_status = "falhou"
            await db.commit()
            raise HTTPException(status_code=502, detail="Transferência salva, mas o aviso ao cliente falhou.")
        mensagem.envio_status = "enviada"
    await db.commit()
    return redirect("/gestor")
