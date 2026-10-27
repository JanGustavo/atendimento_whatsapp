"""Leitura simples de formulários URL-encoded enviados pelo React."""
from urllib.parse import parse_qs

async def form(request) -> dict[str, str]:
    body = (await request.body()).decode("utf-8")
    return {key: values[-1] for key, values in parse_qs(body, keep_blank_values=True).items()}
