
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
