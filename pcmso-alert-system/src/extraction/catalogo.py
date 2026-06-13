"""
Normalização do catálogo de exames (Fase 2, item 1).

O extrator preserva o texto cru das tabelas CONTROLE MÉDICO (congelado pelos
golden files). A convergência de grafias acontece aqui, na gravação do catálogo:

1. `_limpar`  — junta quebras de linha embutidas, colapsa espaços, tira ":" final.
2. `_chave`   — versão casefold + sem acento do nome limpo. É a CHAVE de lookup:
                grafias que diferem só em caixa/acento convergem para o mesmo
                `TipoExame` automaticamente (ex.: "Acuidade Visual" == "Acuidade visual").
3. `SINONIMOS`— tabela editável {chave: nome_de_exibição_preferido}. Só refina o
                display quando há divergência de caixa; o lookup já é por chave.

`normalizar_exame(nome)` devolve `(nome_exibicao, chave)`.

NÃO faz fusões semânticas (ex.: unir "Hemograma Completo e Plaquetas" com
"...e Contagem de Plaquetas e Reticulócitos") — isso é decisão clínica do
analista. Candidatos ficam comentados em SINONIMOS para curadoria manual.
"""
import re
import unicodedata

# {chave casefold/sem-acento: nome de exibição preferido}
# Edite à vontade: a chave é o resultado de _chave(); o valor é como o catálogo exibe.
SINONIMOS: dict[str, str] = {
    "acuidade visual": "Acuidade Visual",
    "audiometria tonal": "Audiometria Tonal",
    # --- Candidatos a FUSÃO SEMÂNTICA (requer decisão clínica; descomente p/ unir) ---
    # Unir exigiria mapear chaves DISTINTAS ao mesmo exame — hoje cada uma vira um
    # TipoExame próprio. Mantidos separados de propósito (reticulócitos ≠ só plaquetas):
    #   "hemograma completo com contagem de plaquetas"
    #   "hemograma completo e contagem de plaquetas e reticulocitos"
    #   "hemograma completo e plaquetas"
}


def _limpar(nome: str) -> str:
    """Junta \\n embutido, colapsa espaços, remove ':' final e espaços nas pontas."""
    return re.sub(r"\s+", " ", (nome or "").replace("\n", " ")).strip().rstrip(":").strip()


def _chave(nome: str) -> str:
    """Chave de convergência: limpo -> casefold -> sem acentos."""
    limpo = _limpar(nome).casefold()
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", limpo) if not unicodedata.combining(c)
    )
    return re.sub(r"\s+", " ", sem_acento).strip()


def normalizar_exame(nome: str) -> tuple[str, str]:
    """
    Devolve (nome_exibicao, chave) para um nome cru de exame.

    - `chave` é estável a variações de caixa/acento/espaço/\\n → use no lookup único.
    - `nome_exibicao` é o display: a grafia preferida da tabela, ou o nome limpo.
    """
    limpo = _limpar(nome)
    chave = _chave(limpo)
    return SINONIMOS.get(chave, limpo), chave
