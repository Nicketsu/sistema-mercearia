from decimal import Decimal, InvalidOperation
from pywebio import start_server
from pywebio.input import input, input_group, select, FLOAT, NUMBER
from pywebio.output import (
    clear, put_markdown, put_table, put_success, put_error,
    put_warning, put_text, put_buttons
)
from banco import conectar_supabase


def executar_consulta(sql, parametros=None, retornar=False):
    conexao = conectar_supabase()
    try:
        with conexao.cursor() as cur:
            cur.execute(sql, parametros or ())
            resultado = cur.fetchall() if retornar else None
        conexao.commit()
        return resultado
    except Exception:
        conexao.rollback()
        raise
    finally:
        conexao.close()


def cabecalho(titulo):
    clear()
    put_markdown("# Sistema de Mercearia")
    put_markdown(f"## {titulo}")


def listar_categorias():
    cabecalho("Categorias")
    dados = executar_consulta(
        "SELECT id_categoria, nome_categoria, descricao "
        "FROM public.categoria ORDER BY nome_categoria",
        retornar=True
    )
    if dados:
        put_table([["ID", "Categoria", "Descrição"]] + [list(x) for x in dados])
    else:
        put_warning("Nenhuma categoria cadastrada.")
    put_buttons(["Voltar"], onclick=lambda _: menu_principal())


def cadastrar_categoria():
    cabecalho("Cadastrar categoria")
    dados = input_group("Nova categoria", [
        input("Nome da categoria", name="nome", required=True),
        input("Descrição (opcional)", name="descricao")
    ])
    executar_consulta(
        "INSERT INTO public.categoria (nome_categoria, descricao) VALUES (%s, %s)",
        (dados["nome"].strip(), dados["descricao"].strip() or None)
    )
    put_success("Categoria cadastrada!")
    put_buttons(["Voltar ao menu"], onclick=lambda _: menu_principal())


def listar_produtos():
    cabecalho("Produtos")
    dados = executar_consulta("""
        SELECT p.id_produto, p.nome_produto, c.nome_categoria,
               u.sigla_unidade, p.estoque_atual, p.preco_venda,
               p.preco_custo, p.situacao
        FROM public.produto p
        LEFT JOIN public.categoria c ON c.id_categoria = p.id_categoria
        LEFT JOIN public.unidade_medida u ON u.id_unidade = p.id_unidade
        ORDER BY p.nome_produto
    """, retornar=True)
    if dados:
        put_table([["ID", "Produto", "Categoria", "Unidade", "Estoque",
                    "Preço venda", "Preço custo", "Situação"]] +
                  [list(x) for x in dados])
    else:
        put_warning("Nenhum produto cadastrado.")
    put_buttons(["Voltar"], onclick=lambda _: menu_principal())


def cadastrar_produto():
    cabecalho("Cadastrar produto")
    categorias = executar_consulta(
        "SELECT id_categoria, nome_categoria FROM public.categoria ORDER BY nome_categoria",
        retornar=True
    )
    unidades = executar_consulta(
        "SELECT id_unidade, nome_unidade FROM public.unidade_medida ORDER BY nome_unidade",
        retornar=True
    )
    if not categorias or not unidades:
        put_error("Cadastre pelo menos uma categoria e uma unidade de medida primeiro.")
        put_buttons(["Voltar"], onclick=lambda _: menu_principal())
        return

    dados = input_group("Dados do produto", [
        input("Nome do produto", name="nome", required=True),
        select("Categoria", name="categoria",
               options=[{"label": nome, "value": ident} for ident, nome in categorias]),
        select("Unidade de medida", name="unidade",
               options=[{"label": nome, "value": ident} for ident, nome in unidades]),
        input("Preço de venda", name="venda", type=FLOAT, required=True),
        input("Preço de custo", name="custo", type=FLOAT, required=True),
        input("Estoque inicial (use 0 se não houver)", name="estoque", type=FLOAT, value=0)
    ])
    if dados["venda"] < 0 or dados["custo"] < 0 or dados["estoque"] < 0:
        put_error("Preços e estoque não podem ser negativos.")
        put_buttons(["Voltar"], onclick=lambda _: menu_principal())
        return

    executar_consulta("""
        INSERT INTO public.produto
            (nome_produto, preco_venda, preco_custo, id_categoria, id_unidade, estoque_atual, situacao)
        VALUES (%s, %s, %s, %s, %s, 0, 'ativo')
    """, (dados["nome"].strip(), dados["venda"], dados["custo"],
          dados["categoria"], dados["unidade"]))

    # O estoque inicial é lançado como movimentação para acionar o gatilho já existente.
    if dados["estoque"] > 0:
        produto = executar_consulta(
            "SELECT id_produto FROM public.produto WHERE nome_produto = %s ORDER BY id_produto DESC LIMIT 1",
            (dados["nome"].strip(),), retornar=True
        )
        executar_consulta("""
            INSERT INTO public.movimentacao_estoque
                (id_produto, quantidade, tipo_operacao)
            VALUES (%s, %s, 'entrada')
        """, (produto[0][0], dados["estoque"]))

    put_success("Produto cadastrado!")
    put_buttons(["Voltar ao menu"], onclick=lambda _: menu_principal())


def movimentar_estoque():
    cabecalho("Movimentação de estoque")
    produtos = executar_consulta(
        "SELECT id_produto, nome_produto FROM public.produto WHERE situacao = 'ativo' ORDER BY nome_produto",
        retornar=True
    )
    if not produtos:
        put_warning("Cadastre um produto primeiro.")
        put_buttons(["Voltar"], onclick=lambda _: menu_principal())
        return

    dados = input_group("Registrar movimentação", [
        select("Produto", name="produto",
               options=[{"label": nome, "value": ident} for ident, nome in produtos]),
        select("Operação", name="tipo", options=[
            {"label": "Entrada", "value": "entrada"},
            {"label": "Saída", "value": "saida"}
        ]),
        input("Quantidade", name="quantidade", type=FLOAT, required=True)
    ])
    if dados["quantidade"] <= 0:
        put_error("A quantidade deve ser maior que zero.")
    else:
        executar_consulta("""
            INSERT INTO public.movimentacao_estoque
                (id_produto, quantidade, tipo_operacao)
            VALUES (%s, %s, %s)
        """, (dados["produto"], dados["quantidade"], dados["tipo"]))
        put_success("Movimentação registrada. O gatilho do banco atualizou o estoque.")
    put_buttons(["Voltar ao menu"], onclick=lambda _: menu_principal())


def criar_pedido():
    cabecalho("Criar pedido")
    produtos = executar_consulta("""
        SELECT id_produto, nome_produto, preco_venda, estoque_atual
        FROM public.produto
        WHERE situacao = 'ativo'
        ORDER BY nome_produto
    """, retornar=True)
    if not produtos:
        put_warning("Não há produtos ativos.")
        put_buttons(["Voltar"], onclick=lambda _: menu_principal())
        return

    escolha = input_group("Item do pedido", [
        select("Produto", name="produto",
               options=[{"label": f"{nome} — R$ {preco} (estoque: {estoque})",
                         "value": ident}
                        for ident, nome, preco, estoque in produtos]),
        input("Quantidade", name="quantidade", type=FLOAT, required=True)
    ])
    if escolha["quantidade"] <= 0:
        put_error("A quantidade deve ser maior que zero.")
        put_buttons(["Voltar"], onclick=lambda _: menu_principal())
        return

    selecionado = next(p for p in produtos if p[0] == escolha["produto"])
    if Decimal(str(escolha["quantidade"])) > Decimal(str(selecionado[3])):
        put_error("Quantidade maior que o estoque disponível.")
        put_buttons(["Voltar"], onclick=lambda _: menu_principal())
        return

    conexao = conectar_supabase()
    try:
        with conexao.cursor() as cur:
            cur.execute("""
                INSERT INTO public.pedido (valor_total, status)
                VALUES (0, 'pendente')
                RETURNING id_pedido
            """)
            id_pedido = cur.fetchone()[0]
            cur.execute("""
                INSERT INTO public.item_pedido
                    (id_pedido, id_produto, quantidade, preco_unitario)
                VALUES (%s, %s, %s, %s)
            """, (id_pedido, escolha["produto"], escolha["quantidade"], selecionado[2]))
            cur.execute("""
                UPDATE public.pedido
                SET valor_total = (
                    SELECT COALESCE(SUM(subtotal), 0)
                    FROM public.item_pedido WHERE id_pedido = %s
                )
                WHERE id_pedido = %s
            """, (id_pedido, id_pedido))
        conexao.commit()
        put_success(f"Pedido #{id_pedido} criado como pendente.")
        put_text("O estoque ainda não foi alterado. Confirme o pedido no menu.")
    except Exception as erro:
        conexao.rollback()
        put_error(f"Não foi possível criar o pedido: {erro}")
    finally:
        conexao.close()
    put_buttons(["Voltar ao menu"], onclick=lambda _: menu_principal())


def confirmar_pedido():
    cabecalho("Confirmar pedido")
    pedidos = executar_consulta("""
        SELECT id_pedido, data_hora, valor_total
        FROM public.pedido
        WHERE status = 'pendente'
        ORDER BY data_hora
    """, retornar=True)
    if not pedidos:
        put_warning("Não existem pedidos pendentes.")
        put_buttons(["Voltar"], onclick=lambda _: menu_principal())
        return

    dados = input_group("Selecione o pedido", [
        select("Pedido", name="pedido",
               options=[{"label": f"#{i} — {data} — R$ {total}",
                         "value": i} for i, data, total in pedidos])
    ])
    conexao = conectar_supabase()
    try:
        with conexao.cursor() as cur:
            cur.execute("""
                SELECT id_produto, quantidade
                FROM public.item_pedido
                WHERE id_pedido = %s
            """, (dados["pedido"],))
            itens = cur.fetchall()
            if not itens:
                raise ValueError("O pedido não possui itens.")

            # O gatilho existente atualiza o estoque em cada saída.
            for id_produto, quantidade in itens:
                cur.execute("""
                    INSERT INTO public.movimentacao_estoque
                        (id_produto, id_pedido, quantidade, tipo_operacao)
                    VALUES (%s, %s, %s, 'saida')
                """, (id_produto, dados["pedido"], quantidade))

            cur.execute("""
                UPDATE public.pedido SET status = 'confirmado'
                WHERE id_pedido = %s AND status = 'pendente'
            """, (dados["pedido"],))
            if cur.rowcount != 1:
                raise ValueError("O pedido não está mais pendente.")
        conexao.commit()
        put_success(f"Pedido #{dados['pedido']} confirmado e estoque atualizado.")
    except Exception as erro:
        conexao.rollback()
        put_error(f"Confirmação cancelada: {erro}")
    finally:
        conexao.close()
    put_buttons(["Voltar ao menu"], onclick=lambda _: menu_principal())


def relatorio_vendas():
    cabecalho("Relatório de pedidos")
    dados = executar_consulta("""
        SELECT p.id_pedido, p.data_hora, p.status, p.valor_total,
               COUNT(ip.id_item) AS quantidade_de_itens
        FROM public.pedido p
        LEFT JOIN public.item_pedido ip ON ip.id_pedido = p.id_pedido
        GROUP BY p.id_pedido, p.data_hora, p.status, p.valor_total
        ORDER BY p.data_hora DESC
    """, retornar=True)
    if dados:
        put_table([["Pedido", "Data", "Status", "Total", "Nº de itens"]] +
                  [list(x) for x in dados])
    else:
        put_warning("Nenhum pedido registrado.")
    put_buttons(["Voltar"], onclick=lambda _: menu_principal())


def relatorio_estoque():
    cabecalho("Relatório de estoque")
    dados = executar_consulta("""
        SELECT p.id_produto, p.nome_produto, p.estoque_atual,
               p.preco_venda, p.situacao
        FROM public.produto p
        ORDER BY p.nome_produto
    """, retornar=True)
    if dados:
        put_table([["ID", "Produto", "Estoque", "Preço de venda", "Situação"]] +
                  [list(x) for x in dados])
    else:
        put_warning("Nenhum produto cadastrado.")
    put_buttons(["Voltar"], onclick=lambda _: menu_principal())


def menu_principal():
    cabecalho("Menu principal")
    opcoes = [
        "Listar categorias",
        "Cadastrar categoria",
        "Listar produtos",
        "Cadastrar produto",
        "Movimentar estoque",
        "Criar pedido",
        "Confirmar pedido",
        "Relatório de pedidos",
        "Relatório de estoque",
        "Testar conexão",
        "Sair"
    ]
    escolha = select("Escolha uma funcionalidade", options=opcoes)
    acoes = {
        "Listar categorias": listar_categorias,
        "Cadastrar categoria": cadastrar_categoria,
        "Listar produtos": listar_produtos,
        "Cadastrar produto": cadastrar_produto,
        "Movimentar estoque": movimentar_estoque,
        "Criar pedido": criar_pedido,
        "Confirmar pedido": confirmar_pedido,
        "Relatório de pedidos": relatorio_vendas,
        "Relatório de estoque": relatorio_estoque,
    }
    if escolha == "Testar conexão":
        try:
            resultado = executar_consulta(
                "SELECT current_database(), current_user", retornar=True
            )
            put_success(f"Conexão OK: banco {resultado[0][0]}, usuário {resultado[0][1]}")
        except Exception as erro:
            put_error(f"Falha na conexão: {erro}")
        put_buttons(["Voltar ao menu"], onclick=lambda _: menu_principal())
    elif escolha == "Sair":
        clear()
        put_text("Sistema encerrado. Você pode fechar esta aba.")
    else:
        acoes[escolha]()


if __name__ == "__main__":
    start_server(menu_principal, port=8080, debug=True)
