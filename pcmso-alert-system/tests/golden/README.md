# Golden files da extração

Snapshots completos de `extrair_pcmso` para os PDFs de exemplo da pasta `../PCMSO`.

Os `.json` desta pasta **não são versionados** (`*.json` está no `.gitignore` por LGPD —
contêm razão social, CNPJ e cargos extraídos dos PDFs). Eles existem apenas na máquina
local e servem de rede de regressão durante mudanças no extrator (Fase 2: normalização
do catálogo de exames).

## Gerar / regenerar

```bash
python scripts/gerar_golden_files.py                 # gera só os que faltam
python scripts/gerar_golden_files.py --sobrescrever  # regenera tudo
```

Só regenere após uma mudança **intencional** de comportamento — e confira o diff
do que mudou antes (ex.: rode `pytest tests/test_golden_files.py` antes de regenerar
e leia as divergências reportadas).

## Rodar os testes

```bash
python -m pytest tests/test_golden_files.py -q
```

Sem PDFs ou sem goldens (CI, clone limpo), os testes são pulados.
