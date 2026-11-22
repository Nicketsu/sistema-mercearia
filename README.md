# Sistema de Mercearia — Supabase

Este projeto conecta o Python diretamente ao PostgreSQL do Supabase e usa as tabelas
já existentes. Ele NÃO cria, altera ou remove tabelas.

## Arquivos
- `app.py`: telas e funcionalidades do sistema.
- `banco.py`: conexão com o Supabase.
- `requirements.txt`: bibliotecas Python.

## 1. Instalar dependências
No terminal do VS Code, dentro desta pasta:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Configurar a conexão
No Windows (PowerShell), configure a URI do Supabase na sessão atual:

```powershell
$env:SUPABASE_DB_URL="postgresql://postgres:SUA_SENHA@db.SEUPROJETO.supabase.co:5432/postgres?sslmode=require"
```

Substitua `SUA_SENHA` e `SEUPROJETO` pelos dados do seu projeto. Não compartilhe essa URI,
pois ela contém a senha do banco.

Use a URI de conexão direta do Supabase. Se sua rede não permitir conexão direta,
use a opção Session pooler exibida em Connect no Supabase.

## 3. Executar
```bash
python app.py
```

Abra no navegador:
http://localhost:8080

## Observações importantes
- O sistema usa as tabelas existentes: `categoria`, `unidade_medida`, `produto`,
  `pedido`, `item_pedido` e `movimentacao_estoque`.
- O cadastro de cliente e login não foram incluídos porque o banco atual não possui
  tabelas `cliente` e `usuario`, e o projeto foi mantido sem alterações.
- O estoque inicial de um produto é registrado como movimentação de entrada.
- Ao confirmar um pedido, o sistema registra as saídas em `movimentacao_estoque`;
  o gatilho já existente no banco atualiza o estoque.
- Faça primeiro um teste com poucos dados. Não execute novamente entradas de estoque
  que já foram registradas.
