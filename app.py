import os
from decimal import Decimal, InvalidOperation
from functools import wraps

from flask import Flask, flash, redirect, render_template, request, url_for
from psycopg2.extras import RealDictCursor

from banco import conectar_supabase

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "troque-esta-chave-no-render")


def db_connection():
    return conectar_supabase()


def query(sql, params=None, one=False):
    conn = db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params or ())
            result = cur.fetchone() if one else cur.fetchall()
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def execute(sql, params=None):
    conn = db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def decimal_value(raw, label, minimum=None):
    try:
        value = Decimal(str(raw).replace(",", "."))
    except (InvalidOperation, TypeError):
        raise ValueError(f"Informe um valor válido para {label}.")
    if minimum is not None and value < Decimal(str(minimum)):
        raise ValueError(f"{label} deve ser maior ou igual a {minimum}.")
    return value


@app.template_filter("brl")
def brl(value):
    try:
        value = Decimal(str(value or 0))
        formatted = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {formatted}"
    except Exception:
        return "R$ 0,00"


@app.template_filter("qty")
def qty(value):
    try:
        return f"{Decimal(str(value or 0)):,.3f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return value


@app.template_filter("datetime_br")
def datetime_br(value):
    return value.strftime("%d/%m/%Y %H:%M") if value else "—"


@app.context_processor
def inject_globals():
    return {"current_endpoint": request.endpoint or ""}


@app.route("/")
def dashboard():
    stats = query("""
        SELECT
          (SELECT COUNT(*) FROM public.produto WHERE situacao = 'ativo') AS produtos_ativos,
          (SELECT COUNT(*) FROM public.categoria) AS categorias,
          (SELECT COUNT(*) FROM public.pedido WHERE status = 'pendente') AS pedidos_pendentes,
          (SELECT COALESCE(SUM(valor_total), 0) FROM public.pedido WHERE status = 'confirmado'
             AND data_hora::date = CURRENT_DATE) AS vendas_hoje
    """, one=True)
    low_stock = query("""
        SELECT p.id_produto, p.nome_produto, p.estoque_atual, u.sigla_unidade
        FROM public.produto p
        LEFT JOIN public.unidade_medida u ON u.id_unidade = p.id_unidade
        WHERE p.situacao = 'ativo' AND p.estoque_atual <= 5
        ORDER BY p.estoque_atual ASC, p.nome_produto
        LIMIT 6
    """)
    recent_orders = query("""
        SELECT id_pedido, valor_total, data_hora, status
        FROM public.pedido ORDER BY data_hora DESC LIMIT 6
    """)
    return render_template("dashboard.html", stats=stats, low_stock=low_stock, recent_orders=recent_orders)


@app.route("/produtos")
def produtos():
    items = query("""
        SELECT p.id_produto, p.nome_produto, p.estoque_atual, p.situacao,
               p.preco_venda, p.preco_custo, c.nome_categoria, u.sigla_unidade
        FROM public.produto p
        LEFT JOIN public.categoria c ON c.id_categoria = p.id_categoria
        LEFT JOIN public.unidade_medida u ON u.id_unidade = p.id_unidade
        ORDER BY p.nome_produto
    """)
    return render_template("produtos.html", items=items)


@app.route("/produtos/novo", methods=["GET", "POST"])
def novo_produto():
    categorias = query("SELECT id_categoria, nome_categoria FROM public.categoria ORDER BY nome_categoria")
    unidades = query("SELECT id_unidade, nome_unidade, sigla_unidade FROM public.unidade_medida ORDER BY nome_unidade")
    if request.method == "POST":
        try:
            nome = request.form.get("nome_produto", "").strip()
            if not nome:
                raise ValueError("Informe o nome do produto.")
            preco_venda = decimal_value(request.form.get("preco_venda"), "Preço de venda", 0)
            preco_custo = decimal_value(request.form.get("preco_custo"), "Preço de custo", 0)
            estoque = decimal_value(request.form.get("estoque_atual", "0"), "Estoque inicial", 0)
            categoria = int(request.form["id_categoria"])
            unidade = int(request.form["id_unidade"])
            conn = db_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO public.produto
                          (nome_produto, estoque_atual, situacao, preco_venda, preco_custo, id_categoria, id_unidade)
                        VALUES (%s, 0, 'ativo', %s, %s, %s, %s)
                        RETURNING id_produto
                    """, (nome, preco_venda, preco_custo, categoria, unidade))
                    product_id = cur.fetchone()[0]
                    if estoque > 0:
                        cur.execute("""
                            INSERT INTO public.movimentacao_estoque
                              (id_produto, quantidade, tipo_operacao)
                            VALUES (%s, %s, 'entrada')
                        """, (product_id, estoque))
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
            flash("Produto cadastrado com sucesso.", "success")
            return redirect(url_for("produtos"))
        except Exception as exc:
            flash(f"Não foi possível cadastrar: {exc}", "danger")
    return render_template("produto_form.html", categorias=categorias, unidades=unidades)


@app.route("/categorias", methods=["GET", "POST"])
def categorias():
    if request.method == "POST":
        nome = request.form.get("nome_categoria", "").strip()
        descricao = request.form.get("descricao", "").strip()
        if not nome:
            flash("Informe o nome da categoria.", "warning")
        else:
            try:
                execute("INSERT INTO public.categoria (nome_categoria, descricao) VALUES (%s, %s)", (nome, descricao or None))
                flash("Categoria cadastrada.", "success")
                return redirect(url_for("categorias"))
            except Exception as exc:
                flash(f"Não foi possível cadastrar a categoria: {exc}", "danger")
    items = query("""
        SELECT c.id_categoria, c.nome_categoria, c.descricao, COUNT(p.id_produto) AS total_produtos
        FROM public.categoria c
        LEFT JOIN public.produto p ON p.id_categoria = c.id_categoria
        GROUP BY c.id_categoria ORDER BY c.nome_categoria
    """)
    return render_template("categorias.html", items=items)


@app.route("/estoque", methods=["GET", "POST"])
def estoque():
    if request.method == "POST":
        try:
            product_id = int(request.form["id_produto"])
            amount = decimal_value(request.form.get("quantidade"), "Quantidade", "0.001")
            operation = request.form.get("tipo_operacao")
            if operation not in ("entrada", "saida"):
                raise ValueError("Tipo de movimentação inválido.")
            execute("""
                INSERT INTO public.movimentacao_estoque (id_produto, quantidade, tipo_operacao)
                VALUES (%s, %s, %s)
            """, (product_id, amount, operation))
            flash("Movimentação registrada. O estoque é atualizado pelo banco de dados.", "success")
            return redirect(url_for("estoque"))
        except Exception as exc:
            flash(f"Não foi possível registrar a movimentação: {exc}", "danger")
    products = query("""
        SELECT id_produto, nome_produto, estoque_atual
        FROM public.produto WHERE situacao = 'ativo' ORDER BY nome_produto
    """)
    movements = query("""
        SELECT m.id_movimentacao, m.quantidade, m.tipo_operacao, m.data_hora,
               p.nome_produto
        FROM public.movimentacao_estoque m
        JOIN public.produto p ON p.id_produto = m.id_produto
        ORDER BY m.data_hora DESC LIMIT 30
    """)
    return render_template("estoque.html", products=products, movements=movements)


@app.route("/pedidos")
def pedidos():
    items = query("""
        SELECT id_pedido, valor_total, data_hora, status
        FROM public.pedido ORDER BY data_hora DESC LIMIT 100
    """)
    products = query("""
        SELECT id_produto, nome_produto, preco_venda, estoque_atual
        FROM public.produto WHERE situacao = 'ativo' ORDER BY nome_produto
    """)
    return render_template("pedidos.html", items=items, products=products)


@app.route("/pedidos/novo", methods=["POST"])
def criar_pedido():
    try:
        product_id = int(request.form["id_produto"])
        amount = decimal_value(request.form.get("quantidade"), "Quantidade", "0.001")
        conn = db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT preco_venda FROM public.produto
                    WHERE id_produto = %s AND situacao = 'ativo'
                """, (product_id,))
                product = cur.fetchone()
                if not product:
                    raise ValueError("Produto não encontrado ou inativo.")
                price = Decimal(str(product[0]))
                total = price * amount
                cur.execute("""
                    INSERT INTO public.pedido (valor_total, status)
                    VALUES (%s, 'pendente') RETURNING id_pedido
                """, (total,))
                order_id = cur.fetchone()[0]
                cur.execute("""
                    INSERT INTO public.item_pedido (id_pedido, id_produto, quantidade, preco_unitario)
                    VALUES (%s, %s, %s, %s)
                """, (order_id, product_id, amount, price))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        flash(f"Pedido #{order_id} criado como pendente. Confirme-o para dar baixa no estoque.", "success")
    except Exception as exc:
        flash(f"Não foi possível criar o pedido: {exc}", "danger")
    return redirect(url_for("pedidos"))


@app.route("/pedidos/<int:order_id>/confirmar", methods=["POST"])
def confirmar_pedido(order_id):
    conn = db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM public.pedido WHERE id_pedido = %s FOR UPDATE", (order_id,))
            order = cur.fetchone()
            if not order:
                raise ValueError("Pedido não encontrado.")
            if order[0] != "pendente":
                raise ValueError("Somente pedidos pendentes podem ser confirmados.")
            cur.execute("""
                SELECT id_produto, quantidade FROM public.item_pedido WHERE id_pedido = %s
            """, (order_id,))
            order_items = cur.fetchall()
            if not order_items:
                raise ValueError("O pedido não possui itens.")
            for product_id, amount in order_items:
                cur.execute("""
                    INSERT INTO public.movimentacao_estoque
                      (id_produto, id_pedido, quantidade, tipo_operacao)
                    VALUES (%s, %s, %s, 'saida')
                """, (product_id, order_id, amount))
            cur.execute("UPDATE public.pedido SET status = 'confirmado' WHERE id_pedido = %s", (order_id,))
        conn.commit()
        flash(f"Pedido #{order_id} confirmado e movimentação de estoque registrada.", "success")
    except Exception as exc:
        conn.rollback()
        flash(f"Não foi possível confirmar o pedido: {exc}", "danger")
    finally:
        conn.close()
    return redirect(url_for("pedidos"))


@app.route("/relatorios")
def relatorios():
    sales = query("""
        SELECT COUNT(*) AS pedidos_confirmados, COALESCE(SUM(valor_total), 0) AS total_vendido
        FROM public.pedido WHERE status = 'confirmado'
    """, one=True)
    stock = query("""
        SELECT p.nome_produto, p.estoque_atual, p.preco_custo, p.preco_venda,
               c.nome_categoria, u.sigla_unidade
        FROM public.produto p
        LEFT JOIN public.categoria c ON c.id_categoria = p.id_categoria
        LEFT JOIN public.unidade_medida u ON u.id_unidade = p.id_unidade
        WHERE p.situacao = 'ativo'
        ORDER BY p.nome_produto
    """)
    return render_template("relatorios.html", sales=sales, stock=stock)


@app.route("/health")
def health():
    try:
        query("SELECT 1", one=True)
        return {"status": "ok", "database": "connected"}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}, 500


@app.errorhandler(500)
def internal_error(error):
    return render_template("erro.html"), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=False)
