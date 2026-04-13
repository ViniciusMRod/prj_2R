"""
Inicializa o schema do banco de dados via SQLAlchemy.
Execute uma vez após subir o PostgreSQL com docker-compose.

Uso:
    python scripts/init_database.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from config.database import Base, engine, test_connection
import src.database.models  # noqa — registra todos os models


def main() -> None:
    print("=== PCMSO Alert System — Inicialização do Banco ===\n")

    if not test_connection():
        print("❌ Falha na conexão com PostgreSQL. Verifique o .env e se o container está rodando.")
        sys.exit(1)

    print("✓ Conexão com PostgreSQL estabelecida.")
    print("Criando tabelas...\n")

    Base.metadata.create_all(bind=engine)

    # Listar tabelas criadas
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tabelas = inspector.get_table_names()
    for t in sorted(tabelas):
        print(f"  ✓ {t}")

    print(f"\n✅ {len(tabelas)} tabela(s) criada(s) com sucesso.")
    print("\nPróximo passo: python scripts/seed_test_data.py")


if __name__ == "__main__":
    main()
