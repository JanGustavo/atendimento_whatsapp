"""WhatsApp Cloud API oficial da Meta."""

import httpx

from app.providers.base import MensagemEntrada
from app.services.media import caminho_media


class MetaTokenExpirado(Exception):
    """A Graph API informou que o token de acesso expirou."""


class MetaEnvioRecusado(Exception):
    """A Graph API recusou o envio por um motivo diferente de token expirado."""


def _token_expirado(resposta: httpx.Response) -> bool:
    try:
        erro = resposta.json().get("error", {})
        return erro.get("code") == 190 and erro.get("error_subcode") == 463
    except (ValueError, AttributeError):
        return False


def _erro_envio(resposta: httpx.Response) -> str:
    try:
        erro = resposta.json().get("error", {})
        mensagem = erro.get("message")
        codigo = erro.get("code")
        if isinstance(mensagem, str) and mensagem:
            return f"Meta recusou o envio (HTTP {resposta.status_code}, código {codigo}): {mensagem}"
    except (ValueError, AttributeError):
        pass
    return f"Meta recusou o envio (HTTP {resposta.status_code})."


class MetaProvider:
    def __init__(self, graph_version: str, phone_number_id: str, access_token: str):
        self.graph_version = graph_version
        self.phone_number_id = phone_number_id
        self.access_token = access_token

    @property
    def _url(self) -> str:
        if (
            not self.graph_version.startswith("v")
            or not self.phone_number_id.isdigit()
            or not self.access_token
        ):
            raise ValueError(
                "Configure META_GRAPH_VERSION, META_PHONE_NUMBER_ID e META_ACCESS_TOKEN"
            )
        return f"https://graph.facebook.com/{self.graph_version}/{self.phone_number_id}"

    async def enviar_texto(self, numero: str, texto: str) -> str:
        numero = "".join(caractere for caractere in numero if caractere.isdigit())
        if not numero:
            raise ValueError("Número inválido")
        # O wa_id brasileiro pode chegar sem o nono dígito, embora o destino
        # cadastrado na Cloud API o inclua. Converta apenas celulares brasileiros.
        if numero.startswith("55") and len(numero) == 12 and numero[4] in "6789":
            numero = numero[:4] + "9" + numero[4:]
        async with httpx.AsyncClient(timeout=10) as client:
            resposta = await client.post(
                f"{self._url}/messages",
                headers={"Authorization": f"Bearer {self.access_token}"},
                json={
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": numero,
                    "type": "text",
                    "text": {"body": texto},
                },
            )
            if _token_expirado(resposta):
                raise MetaTokenExpirado("Token de acesso da Meta expirou")
            if resposta.is_error:
                raise MetaEnvioRecusado(_erro_envio(resposta))
            dados = resposta.json()
            identidade = (dados.get("messages") or [{}])[0].get("id")
            if not isinstance(identidade, str) or not identidade:
                raise ValueError("Meta não retornou o ID da mensagem")
            return identidade

    async def enviar_imagem(
        self, numero: str, imagem_chave: str, legenda: str | None = None
    ) -> str:
        numero = "".join(caractere for caractere in numero if caractere.isdigit())
        if not numero:
            raise ValueError("Número inválido")
        if numero.startswith("55") and len(numero) == 12 and numero[4] in "6789":
            numero = numero[:4] + "9" + numero[4:]
        caminho = caminho_media(imagem_chave)
        if not caminho.is_file():
            raise ValueError("Arquivo de imagem não encontrado")
        dados_arquivo = caminho.read_bytes()
        async with httpx.AsyncClient(timeout=20) as client:
            resposta_upload = await client.post(
                f"{self._url}/media",
                headers={"Authorization": f"Bearer {self.access_token}"},
                data={"messaging_product": "whatsapp", "type": "image/webp"},
                files={"file": (imagem_chave, dados_arquivo, "image/webp")},
            )
            if _token_expirado(resposta_upload):
                raise MetaTokenExpirado("Token de acesso da Meta expirou")
            if resposta_upload.is_error:
                raise MetaEnvioRecusado(_erro_envio(resposta_upload))
            media_id = (resposta_upload.json() or {}).get("id")
            if not isinstance(media_id, str) or not media_id:
                raise ValueError("Meta não retornou o ID da mídia enviada")
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": numero,
                "type": "image",
                "image": {"id": media_id},
            }
            if legenda:
                payload["image"]["caption"] = legenda
            resposta = await client.post(
                f"{self._url}/messages",
                headers={"Authorization": f"Bearer {self.access_token}"},
                json=payload,
            )
            if _token_expirado(resposta):
                raise MetaTokenExpirado("Token de acesso da Meta expirou")
            if resposta.is_error:
                raise MetaEnvioRecusado(_erro_envio(resposta))
            dados = resposta.json()
            identidade = (dados.get("messages") or [{}])[0].get("id")
            if not isinstance(identidade, str) or not identidade:
                raise ValueError("Meta não retornou o ID da mensagem")
            return identidade

    async def enviar_audio(self, numero: str, audio_chave: str) -> str:
        numero = "".join(c for c in numero if c.isdigit())
        if not numero:
            raise ValueError("Número inválido")
        if numero.startswith("55") and len(numero) == 12 and numero[4] in "6789":
            numero = numero[:4] + "9" + numero[4:]
        arquivo = caminho_media(audio_chave)
        if not arquivo.is_file() or arquivo.suffix not in {".mp3", ".ogg"}:
            raise ValueError("Áudio não encontrado")
        # A Cloud API não aceita o MIME genérico audio/ogg para voz.
        tipo = "audio/mpeg" if arquivo.suffix == ".mp3" else "audio/ogg; codecs=opus"
        async with httpx.AsyncClient(timeout=30) as client:
            upload = await client.post(
                f"{self._url}/media",
                headers={"Authorization": f"Bearer {self.access_token}"},
                data={"messaging_product": "whatsapp", "type": tipo},
                files={"file": (audio_chave, arquivo.read_bytes(), tipo)},
            )
            if _token_expirado(upload):
                raise MetaTokenExpirado("Token de acesso da Meta expirou")
            if upload.is_error:
                raise MetaEnvioRecusado(_erro_envio(upload))
            media_id = (upload.json() or {}).get("id")
            if not isinstance(media_id, str) or not media_id:
                raise ValueError("Meta não retornou o ID do áudio")
            audio = {"id": media_id}
            if arquivo.suffix == ".ogg":
                audio["voice"] = True
            resposta = await client.post(
                f"{self._url}/messages",
                headers={"Authorization": f"Bearer {self.access_token}"},
                json={"messaging_product": "whatsapp", "recipient_type": "individual", "to": numero,
                      "type": "audio", "audio": audio},
            )
            if _token_expirado(resposta):
                raise MetaTokenExpirado("Token de acesso da Meta expirou")
            if resposta.is_error:
                raise MetaEnvioRecusado(_erro_envio(resposta))
            identidade = (resposta.json().get("messages") or [{}])[0].get("id")
            if not isinstance(identidade, str) or not identidade:
                raise ValueError("Meta não retornou o ID da mensagem")
            return identidade

    async def enviar_template(self, numero: str, nome: str, idioma: str) -> str:
        numero = "".join(c for c in numero if c.isdigit())
        if not numero or not nome or not idioma:
            raise ValueError("Número, nome do template e idioma são obrigatórios")
        if numero.startswith("55") and len(numero) == 12 and numero[4] in "6789":
            numero = numero[:4] + "9" + numero[4:]
        async with httpx.AsyncClient(timeout=10) as client:
            resposta = await client.post(
                f"{self._url}/messages",
                headers={"Authorization": f"Bearer {self.access_token}"},
                json={"messaging_product": "whatsapp", "recipient_type": "individual", "to": numero,
                      "type": "template", "template": {"name": nome, "language": {"code": idioma}}},
            )
            if _token_expirado(resposta):
                raise MetaTokenExpirado("Token de acesso da Meta expirou")
            if resposta.is_error:
                raise MetaEnvioRecusado(_erro_envio(resposta))
            identidade = (resposta.json().get("messages") or [{}])[0].get("id")
            if not isinstance(identidade, str) or not identidade:
                raise ValueError("Meta não retornou o ID da mensagem")
            return identidade

    def parse_webhook_statuses(self, payload: dict) -> list[dict]:
        if payload.get("object") != "whatsapp_business_account":
            return []
        resultados = []
        for item in payload.get("entry") or []:
            if not isinstance(item, dict):
                continue
            for alteracao in item.get("changes") or []:
                if not isinstance(alteracao, dict):
                    continue
                if alteracao.get("field") != "messages":
                    continue
                valor = alteracao.get("value") or {}
                if not isinstance(valor, dict):
                    continue
                numero_destino = str((valor.get("metadata") or {}).get("phone_number_id") or "")
                if numero_destino and numero_destino != self.phone_number_id:
                    continue
                for status in valor.get("statuses") or []:
                    if (
                        isinstance(status, dict)
                        and status.get("id")
                        and status.get("status") in {"sent", "delivered", "read", "failed"}
                    ):
                        resultados.append(status)
        return resultados

    def parse_webhook_mensagens(self, payload: dict) -> list[MensagemEntrada]:
        if payload.get("object") != "whatsapp_business_account":
            return []
        entradas = []
        for item in payload.get("entry") or []:
            if not isinstance(item, dict):
                continue
            for alteracao in item.get("changes") or []:
                if not isinstance(alteracao, dict):
                    continue
                if alteracao.get("field") != "messages":
                    continue
                valor = alteracao.get("value") or {}
                if not isinstance(valor, dict):
                    continue
                numero_destino = str((valor.get("metadata") or {}).get("phone_number_id") or "")
                if numero_destino and numero_destino != self.phone_number_id:
                    continue
                nomes = {}
                for contato in valor.get("contacts") or []:
                    if not isinstance(contato, dict):
                        continue
                    perfil = contato.get("profile") or {}
                    nome = perfil.get("name") if isinstance(perfil, dict) else None
                    if isinstance(nome, str) and nome.strip():
                        nomes[str(contato.get("wa_id") or "")] = " ".join(nome.split())[:120]
                for mensagem in valor.get("messages") or []:
                    if not isinstance(mensagem, dict):
                        continue
                    identidade = str(mensagem.get("id") or "")
                    numero = str(mensagem.get("from") or "")
                    if not identidade or not numero.isdigit():
                        continue
                    nome_contato = nomes.get(numero)
                    tipo = str(mensagem.get("type") or "")
                    if tipo == "text":
                        texto = (mensagem.get("text") or {}).get("body")
                        if not isinstance(texto, str) or not texto.strip():
                            continue
                        entradas.append(MensagemEntrada(identidade, numero, texto, nome_contato=nome_contato))
                    elif tipo:
                        entradas.append(
                            MensagemEntrada(identidade, numero, "[Mídia recebida]", tipo="midia", nome_contato=nome_contato)
                        )
        return entradas

    def parse_webhook(self, payload: dict) -> MensagemEntrada | None:
        entradas = self.parse_webhook_mensagens(payload)
        return entradas[0] if entradas else None

    async def status(self) -> str:
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                resposta = await client.get(
                    self._url, headers={"Authorization": f"Bearer {self.access_token}"}
                )
                if _token_expirado(resposta):
                    return "token expirado"
                resposta.raise_for_status()
            return "conectado"
        except (httpx.HTTPError, ValueError):
            return "desconectado"
