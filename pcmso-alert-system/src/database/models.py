"""
Models SQLAlchemy — todas as 10 tabelas do PCMSO Alert System.
"""
from __future__ import annotations

import enum
from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Enum, ForeignKey,
    Index, Integer, String, Text, UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config.database import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class StatusExame(str, enum.Enum):
    PENDENTE = "pendente"
    AGENDADO = "agendado"
    REALIZADO = "realizado"
    VENCIDO = "vencido"


class StatusValidacao(str, enum.Enum):
    PENDENTE = "pendente"
    APROVADO = "aprovado"
    REJEITADO = "rejeitado"


class CanalAlerta(str, enum.Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"


class StatusEnvio(str, enum.Enum):
    ENVIADO = "enviado"
    FALHOU = "falhou"
    PENDENTE = "pendente"


class CriticidadeExame(str, enum.Enum):
    ALTA = "alta"
    NORMAL = "normal"
    BAIXA = "baixa"


class TipoMovimentacao(str, enum.Enum):
    ADMISSIONAL = "admissional"
    PERIODICO = "periodico"
    DEMISSIONAL = "demissional"
    RETORNO = "retorno"
    MUDANCA_FUNCAO = "mudanca_funcao"


class StatusDemanda(str, enum.Enum):
    PENDENTE = "pendente"
    AGENDADO = "agendado"
    CONCLUIDO = "concluido"
    CANCELADO = "cancelado"


class StatusLote(str, enum.Enum):
    PENDENTE = "pendente"
    PROCESSANDO = "processando"
    CONCLUIDO = "concluido"
    FALHOU = "falhou"


# ---------------------------------------------------------------------------
# Tabela 1: Empresas
# ---------------------------------------------------------------------------

class Empresa(Base):
    """Empresas clientes — cada uma tem seu próprio SSO (Serviço de Saúde Ocupacional)."""
    __tablename__ = "empresas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    razao_social: Mapped[str] = mapped_column(String(255), nullable=False)
    nome_fantasia: Mapped[Optional[str]] = mapped_column(String(255))
    cnpj: Mapped[str] = mapped_column(String(18), unique=True, nullable=False)
    email_sso: Mapped[str] = mapped_column(String(255), nullable=False)
    telefone_sso: Mapped[Optional[str]] = mapped_column(String(20))
    whatsapp_sso: Mapped[Optional[str]] = mapped_column(String(20))
    senha_dashboard: Mapped[Optional[str]] = mapped_column(String(255))  # hash bcrypt
    data_cadastro: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relacionamentos
    colaboradores: Mapped[list["Colaborador"]] = relationship("Colaborador", back_populates="empresa")
    alertas_enviados: Mapped[list["AlertaEnviado"]] = relationship("AlertaEnviado", back_populates="empresa")
    validacoes_pendentes: Mapped[list["ValidacaoPendente"]] = relationship("ValidacaoPendente", back_populates="empresa")
    pcmso_versoes: Mapped[list["PcmsoVersao"]] = relationship("PcmsoVersao", back_populates="empresa")
    cargo_exames: Mapped[list["CargoExame"]] = relationship("CargoExame", back_populates="empresa")
    demandas: Mapped[list["Demanda"]] = relationship("Demanda", back_populates="empresa")

    def __repr__(self) -> str:
        return f"<Empresa {self.cnpj} - {self.razao_social}>"


# ---------------------------------------------------------------------------
# Tabela 2: Colaboradores
# ---------------------------------------------------------------------------

class Colaborador(Base):
    """Colaboradores de cada empresa cliente."""
    __tablename__ = "colaboradores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    empresa_id: Mapped[int] = mapped_column(Integer, ForeignKey("empresas.id"), nullable=False)
    nome_completo: Mapped[str] = mapped_column(String(255), nullable=False)
    cpf: Mapped[str] = mapped_column(String(14), unique=True, nullable=False)
    cargo: Mapped[Optional[str]] = mapped_column(String(100))
    setor: Mapped[Optional[str]] = mapped_column(String(100))
    data_admissao: Mapped[Optional[date]] = mapped_column(Date)
    data_demissao: Mapped[Optional[date]] = mapped_column(Date)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relacionamentos
    empresa: Mapped["Empresa"] = relationship("Empresa", back_populates="colaboradores")
    exames: Mapped[list["Exame"]] = relationship("Exame", back_populates="colaborador")
    demandas: Mapped[list["Demanda"]] = relationship("Demanda", back_populates="colaborador")

    __table_args__ = (
        Index("idx_colaboradores_empresa", "empresa_id"),
    )

    def __repr__(self) -> str:
        return f"<Colaborador {self.cpf} - {self.nome_completo}>"


# ---------------------------------------------------------------------------
# Tabela 3: Tipos de Exames
# ---------------------------------------------------------------------------

class TipoExame(Base):
    """Catálogo de tipos de exames ocupacionais com periodicidade padrão."""
    __tablename__ = "tipos_exames"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    # Chave de convergência (casefold/sem-acento) — grafias equivalentes mapeiam aqui.
    nome_normalizado: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    descricao: Mapped[Optional[str]] = mapped_column(Text)
    periodicidade_meses: Mapped[int] = mapped_column(Integer, nullable=False)
    criticidade: Mapped[CriticidadeExame] = mapped_column(
        Enum(CriticidadeExame), default=CriticidadeExame.NORMAL
    )

    # Relacionamentos
    exames: Mapped[list["Exame"]] = relationship("Exame", back_populates="tipo_exame")
    cargo_exames: Mapped[list["CargoExame"]] = relationship("CargoExame", back_populates="tipo_exame")

    def __repr__(self) -> str:
        return f"<TipoExame {self.nome} ({self.periodicidade_meses}m)>"


# ---------------------------------------------------------------------------
# Tabela 4: Exames
# ---------------------------------------------------------------------------

class Exame(Base):
    """Exames realizados ou agendados por colaborador."""
    __tablename__ = "exames"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    colaborador_id: Mapped[int] = mapped_column(Integer, ForeignKey("colaboradores.id"), nullable=False)
    tipo_exame_id: Mapped[int] = mapped_column(Integer, ForeignKey("tipos_exames.id"), nullable=False)
    data_ultimo_exame: Mapped[Optional[date]] = mapped_column(Date)
    data_proximo_exame: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[StatusExame] = mapped_column(Enum(StatusExame), default=StatusExame.PENDENTE)
    observacoes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relacionamentos
    colaborador: Mapped["Colaborador"] = relationship("Colaborador", back_populates="exames")
    tipo_exame: Mapped["TipoExame"] = relationship("TipoExame", back_populates="exames")
    alertas: Mapped[list["AlertaEnviado"]] = relationship("AlertaEnviado", back_populates="exame")

    __table_args__ = (
        Index("idx_exames_data_proximo", "data_proximo_exame"),
        Index("idx_exames_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Exame col={self.colaborador_id} tipo={self.tipo_exame_id} vence={self.data_proximo_exame}>"


# ---------------------------------------------------------------------------
# Tabela 5: Alertas Enviados
# ---------------------------------------------------------------------------

class AlertaEnviado(Base):
    """Histórico de todos os alertas enviados (email e WhatsApp)."""
    __tablename__ = "alertas_enviados"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exame_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("exames.id"))
    empresa_id: Mapped[int] = mapped_column(Integer, ForeignKey("empresas.id"), nullable=False)
    canal: Mapped[CanalAlerta] = mapped_column(Enum(CanalAlerta), nullable=False)
    mensagem: Mapped[Optional[str]] = mapped_column(Text)
    status_envio: Mapped[StatusEnvio] = mapped_column(Enum(StatusEnvio), default=StatusEnvio.PENDENTE)
    erro_detalhe: Mapped[Optional[str]] = mapped_column(Text)
    data_envio: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relacionamentos
    exame: Mapped[Optional["Exame"]] = relationship("Exame", back_populates="alertas")
    empresa: Mapped["Empresa"] = relationship("Empresa", back_populates="alertas_enviados")

    __table_args__ = (
        Index("idx_alertas_data", "data_envio"),
        Index("idx_alertas_empresa", "empresa_id"),
    )

    def __repr__(self) -> str:
        return f"<AlertaEnviado empresa={self.empresa_id} canal={self.canal} status={self.status_envio}>"


# ---------------------------------------------------------------------------
# Tabela 6: Validação Pendente
# ---------------------------------------------------------------------------

class ValidacaoPendente(Base):
    """Fila de PCMSOs aguardando revisão e aprovação do técnico."""
    __tablename__ = "validacao_pendente"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pcmso_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    empresa_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("empresas.id"))
    dados_extraidos: Mapped[Optional[dict]] = mapped_column(JSONB)
    status: Mapped[StatusValidacao] = mapped_column(Enum(StatusValidacao), default=StatusValidacao.PENDENTE)
    observacoes_tecnico: Mapped[Optional[str]] = mapped_column(Text)
    validado_por: Mapped[Optional[str]] = mapped_column(String(100))
    data_upload: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    data_validacao: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Relacionamentos
    empresa: Mapped[Optional["Empresa"]] = relationship("Empresa", back_populates="validacoes_pendentes")

    def __repr__(self) -> str:
        return f"<ValidacaoPendente {self.pcmso_filename} status={self.status}>"


# ---------------------------------------------------------------------------
# Tabela 7: Versões PCMSO
# ---------------------------------------------------------------------------

class PcmsoVersao(Base):
    """Controle de versões dos PCMSOs carregados — detecta duplicatas por hash."""
    __tablename__ = "pcmso_versoes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    empresa_id: Mapped[int] = mapped_column(Integer, ForeignKey("empresas.id"), nullable=False)
    versao: Mapped[int] = mapped_column(Integer, nullable=False)
    ano_referencia: Mapped[int] = mapped_column(Integer, nullable=False)
    arquivo_path: Mapped[Optional[str]] = mapped_column(String(500))
    hash_arquivo: Mapped[Optional[str]] = mapped_column(String(64), unique=True)
    data_upload: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relacionamentos
    empresa: Mapped["Empresa"] = relationship("Empresa", back_populates="pcmso_versoes")

    __table_args__ = (
        UniqueConstraint("empresa_id", "ano_referencia", "versao", name="uq_pcmso_versao"),
    )

    def __repr__(self) -> str:
        return f"<PcmsoVersao empresa={self.empresa_id} ano={self.ano_referencia} v{self.versao}>"


# ---------------------------------------------------------------------------
# Tabela 8: Cargo × Exames (extraído do PCMSO)
# ---------------------------------------------------------------------------

class CargoExame(Base):
    """
    Mapeamento de cargo/setor/risco → exames obrigatórios.
    Populado durante a extração e validação do PCMSO.
    Base para geração automática de demandas.
    """
    __tablename__ = "cargo_exames"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    empresa_id: Mapped[int] = mapped_column(Integer, ForeignKey("empresas.id"), nullable=False)
    cargo: Mapped[str] = mapped_column(String(100), nullable=False)
    setor: Mapped[Optional[str]] = mapped_column(String(100))
    risco: Mapped[Optional[str]] = mapped_column(String(100))  # ruído, químico, ergonômico, etc.
    tipo_exame_id: Mapped[int] = mapped_column(Integer, ForeignKey("tipos_exames.id"), nullable=False)
    periodicidade_meses: Mapped[Optional[int]] = mapped_column(Integer)  # sobrescreve TipoExame.periodicidade_meses
    obrigatorio: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relacionamentos
    empresa: Mapped["Empresa"] = relationship("Empresa", back_populates="cargo_exames")
    tipo_exame: Mapped["TipoExame"] = relationship("TipoExame", back_populates="cargo_exames")

    __table_args__ = (
        UniqueConstraint("empresa_id", "cargo", "tipo_exame_id", name="uq_cargo_exame"),
        Index("idx_cargo_exames_empresa_cargo", "empresa_id", "cargo"),
    )

    def __repr__(self) -> str:
        return f"<CargoExame empresa={self.empresa_id} cargo={self.cargo} exame={self.tipo_exame_id}>"


# ---------------------------------------------------------------------------
# Tabela 9: Demandas de Movimentações
# ---------------------------------------------------------------------------

class Demanda(Base):
    """
    Demandas de movimentação de colaboradores recebidas pelos técnicos.
    Ao ser criada, gera automaticamente os exames obrigatórios via CargoExame.
    """
    __tablename__ = "demandas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    empresa_id: Mapped[int] = mapped_column(Integer, ForeignKey("empresas.id"), nullable=False)
    colaborador_id: Mapped[int] = mapped_column(Integer, ForeignKey("colaboradores.id"), nullable=False)
    cargo: Mapped[str] = mapped_column(String(100), nullable=False)
    tipo_movimentacao: Mapped[TipoMovimentacao] = mapped_column(Enum(TipoMovimentacao), nullable=False)
    status: Mapped[StatusDemanda] = mapped_column(Enum(StatusDemanda), default=StatusDemanda.PENDENTE)
    exames_gerados: Mapped[Optional[dict]] = mapped_column(JSONB)  # snapshot dos exames criados
    tecnico_responsavel: Mapped[Optional[str]] = mapped_column(String(100))
    observacoes: Mapped[Optional[str]] = mapped_column(Text)
    data_prazo: Mapped[Optional[date]] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relacionamentos
    empresa: Mapped["Empresa"] = relationship("Empresa", back_populates="demandas")
    colaborador: Mapped["Colaborador"] = relationship("Colaborador", back_populates="demandas")

    __table_args__ = (
        Index("idx_demandas_empresa_status", "empresa_id", "status"),
        Index("idx_demandas_prazo", "data_prazo"),
    )

    def __repr__(self) -> str:
        return f"<Demanda col={self.colaborador_id} tipo={self.tipo_movimentacao} status={self.status}>"


# ---------------------------------------------------------------------------
# Tabela 10: Jobs de lote (ingestão assíncrona de PDFs)
# ---------------------------------------------------------------------------

class LoteJob(Base):
    """Job de processamento assíncrono de um lote de PDFs de PCMSO."""
    __tablename__ = "lote_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_uuid: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    status: Mapped[StatusLote] = mapped_column(
        Enum(StatusLote), default=StatusLote.PENDENTE, nullable=False
    )
    total_pdfs: Mapped[int] = mapped_column(Integer, nullable=False)
    processados: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    com_erro: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    staging_dir: Mapped[str] = mapped_column(String(500), nullable=False)
    excel_path: Mapped[Optional[str]] = mapped_column(String(500))
    erro_detalhe: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    __table_args__ = (
        Index("idx_lote_jobs_status_created", "status", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<LoteJob {self.job_uuid} {self.status} {self.processados}/{self.total_pdfs}>"
