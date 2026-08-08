"""
Modelo de `src/dados_cliente.py` — copie este arquivo e preencha.

    cp src/dados_cliente.example.py src/dados_cliente.py

O arquivo real (`dados_cliente.py`) é ignorado pelo git de propósito:
concentra os dados que identificam o prestador (CNPJ, razão social,
endereço, telefone, e-mail) e o repositório é público. Manter isso fora
do versionamento é o que permite o código ficar aberto sem expor dados de
um terceiro real.

Todos os valores abaixo saem dos PDFs (DANFSe) de notas já emitidas pelo
cliente, exceto onde indicado.
"""

# ---------------------------------------------------------------------------
# EMITENTE (prestador) — fixo, é sempre a mesma empresa que emite.
# ---------------------------------------------------------------------------
# Só dígitos, 14 posições. Usado também pelo validador para barrar tomador
# igual ao prestador — sem isso a nota poderia sair para a própria empresa
# emitente (erro de cadastro real já encontrado numa planilha).
CNPJ_PRESTADOR = "00000000000000"

RAZAO_SOCIAL_PRESTADOR = "RAZAO SOCIAL DO PRESTADOR LTDA"
INSCRICAO_MUNICIPAL_PRESTADOR = "00000000"
TELEFONE_PRESTADOR = "(00) 00000-0000"
EMAIL_PRESTADOR = "contato@exemplo.com.br"
MUNICIPIO_PRESTADOR = "Município"
UF_PRESTADOR = "UF"

# Série da DPS — ver campo "Série da DPS" no DANFSe.
SERIE_DPS = "00000"

# ---------------------------------------------------------------------------
# SERVIÇO — igual em todas as notas de um mesmo cliente.
# ---------------------------------------------------------------------------
# Código de Tributação Nacional (ex.: "17.01.01" para assessoria/consultoria).
CODIGO_TRIBUTACAO_NACIONAL = "00.00.00"

# Aparece no DANFSe em "Informações Complementares" como "NBS: <código>".
NBS_CODIGO = "000000000"

DESCRICAO_SERVICO_PADRAO = "DESCRICAO PADRAO DO SERVICO PRESTADO"

# Total de parcelas do contrato, conforme o padrão de nome dos PDFs que o
# cliente já salva hoje (ex.: "... 07 DE 12" -> 12).
TOTAL_PARCELAS_CONTRATO = 12
