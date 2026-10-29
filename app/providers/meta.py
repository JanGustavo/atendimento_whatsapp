"""WhatsApp Cloud API oficial da Meta; apenas mensagens de texto saem daqui."""
import httpx

from app.providers.base import MensagemEntrada


class MetaProvider:
    def __init__(self, graph_version: str, phone_number_id: str, access_token: str):
        self.graph_version = graph_version
        self.phone_number_id = phone_number_id
        self.access_token = access_token

    @property
    def _url(self) -> str:
        if not self.graph_version.startswith("v") or not self.phone_number_id.isdigit() or not self.access_token:
            raise ValueError("Configure META_GRAPH_VERSION, META_PHONE_NUMBER_ID e META_ACCESS_TOKEN")
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
                json={"messaging_product": "whatsapp", "recipient_type": "individual",
                      "to": numero, "type": "text", "text": {"body": texto}},
            )
            resposta.raise_for_status()
            dados = resposta.json()
            identidade = (dados.get("messages") or [{}])[0].get("id")
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
                    if isinstance(status, dict) and status.get("id") and status.get("status") in {"sent", "delivered", "read", "failed"}:
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
                for mensagem in valor.get("messages") or []:
                    if not isinstance(mensagem, dict):
                        continue
                    identidade = str(mensagem.get("id") or "")
                    numero = str(mensagem.get("from") or "")
                    if not identidade or not numero.isdigit():
                        continue
                    tipo = str(mensagem.get("type") or "")
                    if tipo == "text":
                        texto = (mensagem.get("text") or {}).get("body")
                        if not isinstance(texto, str) or not texto.strip():
                            continue
                        entradas.append(MensagemEntrada(identidade, numero, texto))
                    elif tipo:
                        entradas.append(MensagemEntrada(identidade, numero, "[Mídia recebida]", tipo="midia"))
        return entradas

    def parse_webhook(self, payload: dict) -> MensagemEntrada | None:
        entradas = self.parse_webhook_mensagens(payload)
        return entradas[0] if entradas else None

    async def status(self) -> str:
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                resposta = await client.get(self._url, headers={"Authorization": f"Bearer {self.access_token}"})
                resposta.raise_for_status()
            return "conectado"
        except (httpx.HTTPError, ValueError):
            return "desconectado"
