# Guia do desenvolvedor — Ambiente n8n PCMSO

> Este guia descreve como o desenvolvedor acessa, importa e testa os workflows
> do PCMSO no n8n. Pré-requisito: serviços Python de pé (veja `manual_admin.md §10`).

---

## 1. Acessar o editor n8n

O n8n PCMSO roda no container `n8n-editor-ftr` (projeto `ftr_pos_agentes_e_automacao`).

```
http://localhost:5678
```

Faça login com as credenciais configuradas no `docker-compose` desse projeto.
Se o container estiver parado: `docker start n8n-editor-ftr`.

---

## 2. Por que `host.docker.internal` (e não `localhost`)

O n8n roda dentro de um container Docker. Quando um nó HTTP Request aponta
para `localhost`, ele alcança **o próprio container**, não o Windows host.
Os apps Python (porta 8000 e 5000) rodam no host — por isso os workflows usam
`host.docker.internal` como hostname:

| App | URL nos workflows |
|---|---|
| API de extração | `http://host.docker.internal:8000` |
| web_validator   | `http://host.docker.internal:5000` |

> No Linux sem Docker Desktop, `host.docker.internal` pode não estar disponível.
> Alternativa: `--add-host=host.docker.internal:host-gateway` no `docker run`,
> ou usar o IP da interface `docker0` (`172.17.0.1`).

---

## 3. Importar os 4 workflows

1. Abra `http://localhost:5678`.
2. Menu lateral → **Workflows** → botão **⊕ Add Workflow** → **Import from file**.
3. Importe cada JSON na ordem abaixo (a ordem não afeta o funcionamento):

| Arquivo | O que faz |
|---|---|
| `n8n_workflows/workflow_upload_pcmso.json` | Upload do lote de PDFs → Excel para o analista |
| `n8n_workflows/workflow_daily_alerts.json` | Alertas diários (05h00) |
| `n8n_workflows/workflow_monthly_report.json` | Relatório mensal (dia 1, 08h00) |
| `n8n_workflows/workflow_limpeza_staging.json` | Limpeza de staging TTL (segunda, 04h00) |

4. Após importar cada um, **ative o workflow** (toggle no canto superior direito
   do editor do workflow).

> O workflow de limpeza usa `Execute Command` — só funciona se o n8n estiver no
> mesmo host que o app. Em container separado, desative-o e use cron de sistema.

---

## 4. Testar o workflow de upload manualmente (sem esperar o cron)

### 4a. Via trigger de teste no editor n8n

1. Abra o workflow **PCMSO - Lote assíncrono**.
2. Clique no nó **Gatilho manual (webhook)** → **Listen for Test Event**.
3. Em outro terminal, dispare via `curl` ou PowerShell (veja abaixo).
4. Acompanhe a execução nos nós em tempo real.

### 4b. Via PowerShell (simula o analista)

```powershell
# Certifique-se de que há PDFs em data/pcmso_raw/ antes de disparar
python -c "
import urllib.request, json, os

def post_multipart(url, files):
    boundary = b'----BoundaryPCMSO'
    parts = []
    for name, path in files:
        with open(path, 'rb') as f:
            data = f.read()
        parts.append(b'--' + boundary + b'\r\n')
        parts.append(f'Content-Disposition: form-data; name=\"{name}\"; filename=\"{os.path.basename(path)}\"\r\n'.encode())
        parts.append(b'Content-Type: application/pdf\r\n\r\n')
        parts.append(data + b'\r\n')
    parts.append(b'--' + boundary + b'--\r\n')
    body = b''.join(parts)
    req = urllib.request.Request(url, data=body)
    req.add_header('Content-Type', f'multipart/form-data; boundary={boundary.decode()}')
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

pdfs = [('files', f) for f in __import__('glob').glob('data/pcmso_raw/*.pdf')]
r = post_multipart('http://localhost:8000/extrair-lote', pdfs)
print(json.dumps(r, indent=2))
"
```

Resposta esperada (HTTP 202):
```json
{ "job_uuid": "...", "total_pdfs": 2, "status": "pendente" }
```

### 4c. Acompanhar o status do job

```powershell
$uuid = "COLE-O-UUID-AQUI"
Invoke-RestMethod "http://localhost:8000/lote/$uuid"
```

Campos importantes: `status` (`pendente → processando → concluido | falhou`),
`processados`, `total_pdfs`, `com_erro`, `erro_detalhe`.

### 4d. Baixar o Excel gerado

```powershell
$uuid = "COLE-O-UUID-AQUI"
Invoke-WebRequest "http://localhost:8000/lote/$uuid/excel" -OutFile "data/pcmso_lote/resultado.xlsx"
```

---

## 5. Monitorar execuções no n8n

- **Execuções recentes:** Menu lateral → **Executions** → filtre pelo workflow.
- **Ver detalhes de um nó:** clique na execução → clique em qualquer nó para ver
  input/output JSON.
- **Erros:** execuções com falha aparecem em vermelho; o nó onde parou fica
  destacado. O campo `erro_detalhe` no nó `Consultar status do job` traz o
  motivo quando o job `falhou`.

---

## 6. Disparar alertas e relatório manualmente (fora do cron)

```powershell
# Alertas diários
Invoke-RestMethod -Uri 'http://localhost:5000/api/processar-alertas' -Method Post

# Relatório mensal
Invoke-RestMethod -Uri 'http://localhost:5000/api/relatorio-mensal' -Method Get
```

---

## 7. Checklist antes de testar com dados reais do analista

- [ ] `data/pcmso_raw/` contém os PDFs do analista (limpar os PDFs de teste antes)
- [ ] API de extração de pé: `Invoke-RestMethod http://localhost:8000/docs`
- [ ] web_validator de pé: `Invoke-RestMethod http://localhost:5000/docs`
- [ ] Worker rodando (janela PowerShell aberta com `python scripts/worker_lote.py`)
- [ ] n8n editor acessível: `http://localhost:5678`
- [ ] 4 workflows importados e **ativos** no n8n
- [ ] Banco com dados limpos (se for teste novo): `python scripts/raio_x_banco.py`

---

## 8. Parar os serviços

Feche as janelas PowerShell dos 3 processos, ou:

```powershell
# Matar por porta (cuidado para não derrubar outros processos)
Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process
Get-Process -Id (Get-NetTCPConnection -LocalPort 5000).OwningProcess | Stop-Process
```

O n8n (Docker) continua rodando independente — pare apenas se necessário:
```powershell
docker stop n8n-editor-ftr
```
