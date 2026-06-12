"""
Raio-x do banco: inspeciona (read-only) o que entrou no PostgreSQL após
aprovar lotes de PCMSO. Mostra contagem por tabela, destaques de cada uma
e checagens de integridade úteis na fase de testes.

Uso:
    python scripts/raio_x_banco.py            # panorama
    python scripts/raio_x_banco.py --detalhe  # + amostra de linhas por tabela

Não escreve nada — seguro rodar a qualquer momento.
"""
import sys
from pathlib import Path

# Console do Windows costuma vir em cp1252 — força UTF-8 para não quebrar acentos.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import func, select  # noqa: E402

from config.database import get_db_context  # noqa: E402
from src.database.models import (  # noqa: E402
    CargoExame, Colaborador, Empresa, Exame, PcmsoVersao,
    StatusValidacao, TipoExame, ValidacaoPendente,
)

DETALHE = "--detalhe" in sys.argv


def _linha(rotulo: str, valor) -> None:
    print(f"  {rotulo:<28}{valor}")


def panorama(db) -> None:
    print("\n" + "=" * 60)
    print("CONTAGEM POR TABELA")
    print("=" * 60)
    tabelas = [
        ("empresas", Empresa),
        ("colaboradores", Colaborador),
        ("tipos_exames", TipoExame),
        ("cargo_exames", CargoExame),
        ("exames", Exame),
        ("pcmso_versoes", PcmsoVersao),
        ("validacao_pendente", ValidacaoPendente),
    ]
    for nome, modelo in tabelas:
        total = db.scalar(select(func.count()).select_from(modelo))
        _linha(nome, total)


def versoes(db) -> None:
    print("\n" + "=" * 60)
    print("VERSIONAMENTO (pcmso_versoes)")
    print("=" * 60)
    rows = db.execute(
        select(PcmsoVersao.empresa_id, PcmsoVersao.ano_referencia,
               PcmsoVersao.versao, PcmsoVersao.hash_arquivo)
        .order_by(PcmsoVersao.empresa_id, PcmsoVersao.ano_referencia, PcmsoVersao.versao)
    ).all()
    if not rows:
        print("  (vazio — nenhuma versão registrada ainda)")
        return
    print(f"  {'EMPRESA':<9}{'ANO':<6}{'VER':<5}HASH")
    for emp, ano, ver, h in rows:
        print(f"  {emp:<9}{ano:<6}v{ver:<4}{(h or '')[:16]}…")


def cargo_exames_por_empresa(db) -> None:
    print("\n" + "=" * 60)
    print("CARGO × EXAME por empresa")
    print("=" * 60)
    rows = db.execute(
        select(CargoExame.empresa_id, func.count())
        .group_by(CargoExame.empresa_id)
        .order_by(CargoExame.empresa_id)
    ).all()
    if not rows:
        print("  (vazio)")
        return
    for emp, n in rows:
        _linha(f"empresa {emp}", f"{n} mapeamentos")


def integridade(db) -> None:
    print("\n" + "=" * 60)
    print("CHECAGENS DE INTEGRIDADE")
    print("=" * 60)
    avisos = []

    # Hashes duplicados em pcmso_versoes (não deveria existir — unique)
    dup_hash = db.execute(
        select(PcmsoVersao.hash_arquivo, func.count())
        .where(PcmsoVersao.hash_arquivo.is_not(None))
        .group_by(PcmsoVersao.hash_arquivo)
        .having(func.count() > 1)
    ).all()
    if dup_hash:
        avisos.append(f"{len(dup_hash)} hash(es) duplicado(s) em pcmso_versoes")

    # Versões sem hash (não dá pra detectar reenvio depois)
    sem_hash = db.scalar(
        select(func.count()).select_from(PcmsoVersao).where(PcmsoVersao.hash_arquivo.is_(None))
    )
    if sem_hash:
        avisos.append(f"{sem_hash} versão(ões) sem hash_arquivo")

    # cargo_exames órfãos (tipo_exame inexistente) — FK deveria impedir
    orf = db.scalar(
        select(func.count()).select_from(CargoExame)
        .outerjoin(TipoExame, CargoExame.tipo_exame_id == TipoExame.id)
        .where(TipoExame.id.is_(None))
    )
    if orf:
        avisos.append(f"{orf} cargo_exame(s) com tipo_exame inexistente")

    # Empresas sem CNPJ
    sem_cnpj = db.scalar(
        select(func.count()).select_from(Empresa)
        .where((Empresa.cnpj.is_(None)) | (Empresa.cnpj == ""))
    )
    if sem_cnpj:
        avisos.append(f"{sem_cnpj} empresa(s) sem CNPJ")

    if avisos:
        for a in avisos:
            print(f"  [!] {a}")
    else:
        print("  OK — nenhum problema detectado.")


def fila_validacao(db) -> None:
    print("\n" + "=" * 60)
    print("FILA DE VALIDAÇÃO (validacao_pendente)")
    print("=" * 60)
    for status in StatusValidacao:
        n = db.scalar(
            select(func.count()).select_from(ValidacaoPendente)
            .where(ValidacaoPendente.status == status)
        )
        _linha(status.value, n)


def detalhe(db) -> None:
    print("\n" + "=" * 60)
    print("AMOSTRA — empresas")
    print("=" * 60)
    for e in db.execute(select(Empresa.id, Empresa.cnpj, Empresa.razao_social).limit(20)).all():
        print(f"  #{e[0]:<4}{(e[1] or ''):<20}{(e[2] or '')[:40]}")

    print("\n" + "=" * 60)
    print("AMOSTRA — tipos_exames")
    print("=" * 60)
    for t in db.execute(select(TipoExame.nome, TipoExame.periodicidade_meses).limit(30)).all():
        print(f"  {(t[0] or '')[:40]:<42}{t[1]}m")


def main() -> None:
    with get_db_context() as db:
        panorama(db)
        versoes(db)
        cargo_exames_por_empresa(db)
        fila_validacao(db)
        integridade(db)
        if DETALHE:
            detalhe(db)
    print()


if __name__ == "__main__":
    main()
