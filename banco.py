import os
import psycopg2


def conectar_supabase():
    """
    Conecta ao PostgreSQL do Supabase.
    Configure a variável de ambiente SUPABASE_DB_URL com a URI do projeto.
    Exemplo:
    postgresql://postgres:SENHA@db.PROJETO.supabase.co:5432/postgres?sslmode=require
    """
    url = os.getenv("SUPABASE_DB_URL")
    if not url:
        raise RuntimeError(
            "A variável SUPABASE_DB_URL não foi configurada. "
            "Configure a URI do banco do Supabase antes de iniciar."
        )

    return psycopg2.connect(url, sslmode="require")


def testar_conexao():
    conexao = conectar_supabase()
    try:
        with conexao.cursor() as cur:
            cur.execute("SELECT current_database(), current_user;")
            return cur.fetchone()
    finally:
        conexao.close()
