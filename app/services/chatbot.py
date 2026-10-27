"""Transições do menu. Sem dependências de banco, rede ou relógio."""

MENU_SETOR = "Escolha o setor:\n1 - Vendas/Compra\n2 - Devolução\n3 - Garantia\n4 - Outro"


def processar_mensagem(estado_atual: str, texto: str) -> tuple[str, list[str], str | None]:
    escolha = texto.strip()
    if estado_atual == "menu_setor":
        if escolha == "1":
            return "menu_vendedor", [], "listar_vendedores"
        if escolha in {"2", "3", "4"}:
            return "atribuida", [], f"atribuir_setor:{escolha}"
        return "menu_setor", [MENU_SETOR], None
    if estado_atual == "menu_vendedor":
        if escolha.isdecimal():
            return "atribuida", [], f"escolher_vendedor:{int(escolha)}"
        return "menu_vendedor", [], "listar_vendedores"
    if estado_atual == "aviso_transferencia" and escolha == "1":
        return "aviso_transferencia", [], "estender_espera"
    return estado_atual, [], None
