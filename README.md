# Sistema de Mercearia — Supabase

Aplicação web em Python/Flask, com interface responsiva, conectada ao banco Supabase existente.

## Funcionalidades
- Painel inicial com indicadores.
- Listagem e cadastro de categorias.
- Listagem e cadastro de produtos.
- Entrada e saída de estoque por `movimentacao_estoque`.
- Criação e confirmação de pedidos.
- Relatório geral de estoque e vendas.
- Verificação da conexão em `/health`.

## Importante: banco de dados
O projeto foi preparado para utilizar as tabelas existentes:
`categoria`, `unidade_medida`, `produto`, `pedido`, `item_pedido`,
`movimentacao_estoque` e `historico_preco`.

O sistema não cria, apaga ou altera tabelas. O estoque é movimentado inserindo registros em
`movimentacao_estoque`, para respeitar o gatilho já existente no banco.

O fluxo de pedido implementado cria pedido com um item por vez. O pedido fica pendente até
ser confirmado. Na confirmação, o sistema registra a saída no estoque.

## Publicar no GitHub e Render
1. Envie os arquivos desta pasta para o repositório GitHub.
2. No Render, crie um Web Service conectado ao repositório.
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `gunicorn app:app --bind 0.0.0.0:$PORT`
5. Em Environment, crie:
   - Key: `SUPABASE_DB_URL`
   - Value: URI completa do banco no Supabase (`postgresql://...`)
   - Key: `FLASK_SECRET_KEY`
   - Value: uma chave aleatória longa.
6. Salve e faça deploy.

**Não coloque a URI, senha ou chaves no GitHub.**

## Rodar localmente
Windows PowerShell:
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:SUPABASE_DB_URL="SUA_URI_DO_SUPABASE"
python app.py
```
Acesse `http://localhost:8080`.

## Nota
O sistema não inclui autenticação/login. Antes de usar com dados reais ou expor operações ao público,
adicione autenticação e regras de acesso adequadas. O serviço Render gratuito pode suspender após
inatividade.
