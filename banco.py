import os
import psycopg2


def conectar_supabase():
    url = os.getenv("SUPABASE_DB_URL", "").strip()
    if not url:
        raise RuntimeError(
            "A variável SUPABASE_DB_URL não foi configurada. "
            "Cadastre a URI do Supabase nas Environment Variables do Render."
        )
    if url.startswith("$env:") or url.startswith("SUPABASE_DB_URL="):
        raise RuntimeError(
            "SUPABASE_DB_URL contém um comando em vez da URI. "
            "No Render, Key deve ser SUPABASE_DB_URL e Value deve ser a URI postgresql://..."
        )
    return psycopg2.connect(url, sslmode="require", connect_timeout=15)
