"""
Popula o banco com dados de teste realistas para desenvolvimento.
Cria 2 empresas, 12 colaboradores, tipos de exames, mapeamentos cargo×exame
e exames com vencimentos variados (incluindo alguns em 10-15 dias).

Uso:
    python scripts/seed_test_data.py
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from config.database import get_db_context
from src.database.models import (
    CargoExame, Colaborador, CriticidadeExame, Empresa,
    Exame, StatusExame, TipoExame,
)


EMPRESAS = [
    {
        "razao_social": "Metalúrgica São Paulo Ltda",
        "nome_fantasia": "MetalSP",
        "cnpj": "12.345.678/0001-90",
        "email_sso": "sso@metalsp.com.br",
        "whatsapp_sso": "+5511999990001",
        "senha_dashboard": "senha123",
    },
    {
        "razao_social": "Construções Norte S/A",
        "nome_fantasia": "ConstNorte",
        "cnpj": "98.765.432/0001-10",
        "email_sso": "seguranca@constnorte.com.br",
        "whatsapp_sso": "+5592999990002",
        "senha_dashboard": "senha123",
    },
]

TIPOS_EXAMES = [
    ("Audiometria",           12, CriticidadeExame.ALTA),
    ("Acuidade Visual",       12, CriticidadeExame.NORMAL),
    ("Hemograma Completo",    12, CriticidadeExame.NORMAL),
    ("Espirometria",          12, CriticidadeExame.ALTA),
    ("Avaliação Clínica",     12, CriticidadeExame.NORMAL),
    ("Raio-X de Tórax",       24, CriticidadeExame.NORMAL),
    ("Glicemia em Jejum",     12, CriticidadeExame.BAIXA),
    ("Eletrocardiograma",     24, CriticidadeExame.NORMAL),
    ("Toxicológico",          12, CriticidadeExame.ALTA),
]

COLABORADORES_EMP1 = [
    ("João Carlos Silva",    "123.456.789-09", "Operador de Máquinas", "Produção"),
    ("Maria Aparecida Santos", "987.654.321-00", "Analista de Qualidade", "Qualidade"),
    ("Pedro Henrique Costa", "456.789.123-87", "Soldador", "Fabricação"),
    ("Ana Paula Ferreira",   "321.654.987-65", "Supervisora de Produção", "Produção"),
    ("Carlos Eduardo Lima",  "654.321.098-43", "Técnico de Manutenção", "Manutenção"),
    ("Fernanda Oliveira",    "789.123.456-21", "Auxiliar Administrativo", "Administrativo"),
]

COLABORADORES_EMP2 = [
    ("Roberto Alves Nunes",  "111.222.333-96", "Pedreiro", "Obras"),
    ("Juliana Costa Melo",   "444.555.666-30", "Engenheira Civil", "Engenharia"),
    ("Marcos Vinicius Rocha","777.888.999-74", "Mestre de Obras", "Obras"),
    ("Lúcia Helena Barros",  "222.333.444-18", "Técnica de Segurança", "SSO"),
    ("Anderson Lima Souza",  "555.666.777-52", "Eletricista", "Elétrica"),
    ("Patrícia Almeida",     "888.999.000-85", "Auxiliar de Obras", "Obras"),
]

CARGO_EXAMES_EMP1 = [
    ("Operador de Máquinas",   "Produção",  "Ruído",      "Audiometria",        12),
    ("Operador de Máquinas",   "Produção",  "Ruído",      "Acuidade Visual",    12),
    ("Operador de Máquinas",   "Produção",  "Vibração",   "Avaliação Clínica",  12),
    ("Soldador",               "Fabricação","Químico",    "Espirometria",       12),
    ("Soldador",               "Fabricação","Químico",    "Hemograma Completo", 12),
    ("Soldador",               "Fabricação","Químico",    "Raio-X de Tórax",    24),
    ("Técnico de Manutenção",  "Manutenção","Elétrico",   "Avaliação Clínica",  12),
    ("Analista de Qualidade",  "Qualidade", "",           "Avaliação Clínica",  12),
    ("Supervisora de Produção","Produção",  "",           "Avaliação Clínica",  12),
]

CARGO_EXAMES_EMP2 = [
    ("Pedreiro",         "Obras",      "Ergonômico", "Avaliação Clínica",  12),
    ("Pedreiro",         "Obras",      "Físico",     "Raio-X de Tórax",    24),
    ("Mestre de Obras",  "Obras",      "Ergonômico", "Avaliação Clínica",  12),
    ("Eletricista",      "Elétrica",   "Elétrico",   "Avaliação Clínica",  12),
    ("Eletricista",      "Elétrica",   "Elétrico",   "Acuidade Visual",    12),
    ("Engenheira Civil", "Engenharia", "",           "Avaliação Clínica",  12),
]


def seed() -> None:
    print("=== Seed de dados de teste ===\n")
    hoje = date.today()

    with get_db_context() as db:
        # --- Tipos de exames ---
        tipos: dict[str, TipoExame] = {}
        for nome, periodo, crit in TIPOS_EXAMES:
            from sqlalchemy import select
            t = db.scalar(select(TipoExame).where(TipoExame.nome == nome))
            if not t:
                t = TipoExame(nome=nome, periodicidade_meses=periodo, criticidade=crit)
                db.add(t)
                db.flush()
            tipos[nome] = t
        print(f"✓ {len(tipos)} tipos de exame")

        # --- Empresas + colaboradores + cargo_exames + exames ---
        for i, emp_data in enumerate(EMPRESAS):
            from sqlalchemy import select
            emp = db.scalar(select(Empresa).where(Empresa.cnpj == emp_data["cnpj"]))
            if not emp:
                emp = Empresa(**emp_data)
                db.add(emp)
                db.flush()
            print(f"✓ Empresa: {emp.razao_social}")

            colaboradores_data = COLABORADORES_EMP1 if i == 0 else COLABORADORES_EMP2
            cargo_exames_data  = CARGO_EXAMES_EMP1  if i == 0 else CARGO_EXAMES_EMP2

            # Colaboradores
            cols: dict[str, Colaborador] = {}
            for nome, cpf, cargo, setor in colaboradores_data:
                c = db.scalar(select(Colaborador).where(Colaborador.cpf == cpf))
                if not c:
                    c = Colaborador(
                        empresa_id=emp.id,
                        nome_completo=nome,
                        cpf=cpf,
                        cargo=cargo,
                        setor=setor,
                        data_admissao=hoje - timedelta(days=365 * 2),
                        ativo=True,
                    )
                    db.add(c)
                    db.flush()
                cols[nome] = c
            print(f"  ✓ {len(cols)} colaboradores")

            # Mapeamentos cargo × exames
            for cargo, setor, risco, tipo_nome, periodo in cargo_exames_data:
                tipo = tipos.get(tipo_nome)
                if not tipo:
                    continue
                existe = db.scalar(select(CargoExame).where(
                    CargoExame.empresa_id == emp.id,
                    CargoExame.cargo == cargo,
                    CargoExame.tipo_exame_id == tipo.id,
                ))
                if not existe:
                    db.add(CargoExame(
                        empresa_id=emp.id,
                        cargo=cargo, setor=setor, risco=risco,
                        tipo_exame_id=tipo.id,
                        periodicidade_meses=periodo,
                    ))
            print(f"  ✓ {len(cargo_exames_data)} mapeamentos cargo-exame")

            # Exames com datas variadas (para testar alertas)
            exame_configs = [
                # (colaborador_index, tipo_nome, dias_para_vencimento)
                (0, "Audiometria",        12),   # vence em 12 dias (ALERTA)
                (0, "Acuidade Visual",    30),
                (0, "Avaliação Clínica",  14),   # vence em 14 dias (ALERTA)
                (1, "Avaliação Clínica",  10),   # vence em 10 dias (ALERTA)
                (1, "Hemograma Completo", 60),
                (2, "Espirometria",       11),   # vence em 11 dias (ALERTA)
                (2, "Hemograma Completo", -5),   # VENCIDO
                (2, "Raio-X de Tórax",    90),
                (3, "Avaliação Clínica",  45),
                (4, "Avaliação Clínica",  13),   # vence em 13 dias (ALERTA)
                (5, "Avaliação Clínica",  120),
            ]

            col_list = list(cols.values())
            for col_idx, tipo_nome, dias in exame_configs:
                if col_idx >= len(col_list):
                    continue
                col = col_list[col_idx]
                tipo = tipos.get(tipo_nome)
                if not tipo:
                    continue

                data_proximo = hoje + timedelta(days=dias)
                data_ultimo  = data_proximo - timedelta(days=tipo.periodicidade_meses * 30)
                status = StatusExame.VENCIDO if dias < 0 else StatusExame.PENDENTE

                from sqlalchemy import select as sel
                existe_exame = db.scalar(sel(Exame).where(
                    Exame.colaborador_id == col.id,
                    Exame.tipo_exame_id == tipo.id,
                ))
                if not existe_exame:
                    db.add(Exame(
                        colaborador_id=col.id,
                        tipo_exame_id=tipo.id,
                        data_ultimo_exame=data_ultimo,
                        data_proximo_exame=data_proximo,
                        status=status,
                    ))

            alertas_count = sum(1 for _, _, d in exame_configs if 10 <= d <= 15)
            print(f"  ✓ {len(exame_configs)} exames ({alertas_count} vencendo em 10-15 dias)")

        print("\n✅ Seed concluído!")
        print("\n📋 Credenciais de acesso ao dashboard:")
        for emp_data in EMPRESAS:
            print(f"   CNPJ: {emp_data['cnpj']} | Senha: {emp_data['senha_dashboard']}")

        print("\nPróximo passo:")
        print("  uvicorn src.validation_interface.web_validator:app --reload --port 5000")
        print("  streamlit run src/dashboard/app.py")


if __name__ == "__main__":
    seed()
