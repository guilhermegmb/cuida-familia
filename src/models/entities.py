from __future__ import annotations

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.session import Base
from src.models.enums import (
    CanalInteracaoEnum,
    FrequenciaRotinaEnum,
    GeneroEnum,
    GravidadeEnum,
    PapelInteracaoEnum,
    ParentescoEnum,
    PrioridadeAlertaEnum,
    StatusAlertaEnum,
    StatusConsultaEnum,
    StatusLembreteEnum,
    StatusMedicamentoEnum,
    StatusPlanoEnum,
    StatusRotinaEnum,
    TipoAlertaEnum,
    TipoConsultaEnum,
    TipoEventoSaudeEnum,
    TipoInteracaoEnum,
    TipoLembreteEnum,
    TipoRotinaEnum,
    ViaAdministracaoEnum,
    ViaAgendamentoEnum,
)


def enum_col(enum_cls: type, name: str):
    return Enum(enum_cls, name=name, native_enum=True, create_type=False)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Cuidador(TimestampMixin, Base):
    __tablename__ = "cuidadores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome_completo: Mapped[str] = mapped_column(String(150), nullable=False)
    telefone_whatsapp: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    data_nascimento: Mapped[date | None] = mapped_column(Date)
    genero: Mapped[GeneroEnum | None] = mapped_column(enum_col(GeneroEnum, "genero_enum"))
    parentesco: Mapped[ParentescoEnum] = mapped_column(enum_col(ParentescoEnum, "parentesco_enum"), nullable=False)
    idioma_preferido: Mapped[str] = mapped_column(String(10), nullable=False, default="pt-BR")
    fuso_horario: Mapped[str] = mapped_column(String(60), nullable=False, default="America/Sao_Paulo")
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    preferencias_notificacao: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    observacoes: Mapped[str | None] = mapped_column(Text)


class PessoaCuidada(TimestampMixin, Base):
    __tablename__ = "pessoas_cuidadas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cuidador_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cuidadores.id", ondelete="RESTRICT"), nullable=False)
    nome_completo: Mapped[str] = mapped_column(String(150), nullable=False)
    data_nascimento: Mapped[date | None] = mapped_column(Date)
    genero: Mapped[GeneroEnum | None] = mapped_column(enum_col(GeneroEnum, "genero_enum"))
    grau_dependencia: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)
    comorbidades: Mapped[str | None] = mapped_column(Text)
    alergias: Mapped[str | None] = mapped_column(Text)
    condicoes_clinicas: Mapped[str | None] = mapped_column(Text)
    contato_emergencia_nome: Mapped[str | None] = mapped_column(String(150))
    contato_emergencia_telefone: Mapped[str | None] = mapped_column(String(20))
    observacoes: Mapped[str | None] = mapped_column(Text)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class PlanoCuidado(TimestampMixin, Base):
    __tablename__ = "planos_cuidado"
    __table_args__ = (
        CheckConstraint("fim_previsto_em IS NULL OR fim_previsto_em >= inicio_em", name="ck_planos_cuidado_periodo"),
        UniqueConstraint("pessoa_cuidada_id", "versao", name="uq_planos_cuidado_versao"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pessoa_cuidada_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pessoas_cuidadas.id", ondelete="CASCADE"), nullable=False)
    cuidador_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cuidadores.id", ondelete="RESTRICT"), nullable=False)
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    objetivo_geral: Mapped[str] = mapped_column(Text, nullable=False)
    detalhes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[StatusPlanoEnum] = mapped_column(enum_col(StatusPlanoEnum, "status_plano_enum"), nullable=False, default=StatusPlanoEnum.rascunho)
    inicio_em: Mapped[date] = mapped_column(Date, nullable=False)
    fim_previsto_em: Mapped[date | None] = mapped_column(Date)
    versao: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    gerado_por_ia: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Rotina(TimestampMixin, Base):
    __tablename__ = "rotinas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plano_cuidado_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("planos_cuidado.id", ondelete="CASCADE"), nullable=False)
    pessoa_cuidada_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pessoas_cuidadas.id", ondelete="CASCADE"), nullable=False)
    medicamento_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("medicamentos.id", ondelete="SET NULL"))
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)
    tipo: Mapped[TipoRotinaEnum] = mapped_column(enum_col(TipoRotinaEnum, "tipo_rotina_enum"), nullable=False)
    frequencia: Mapped[FrequenciaRotinaEnum] = mapped_column(
        enum_col(FrequenciaRotinaEnum, "frequencia_rotina_enum"), nullable=False
    )
    regra_personalizada_cron: Mapped[str | None] = mapped_column(String(120))
    horario_padrao: Mapped[time | None] = mapped_column(Time)
    dia_semana: Mapped[int | None] = mapped_column(SmallInteger)
    dia_mes: Mapped[int | None] = mapped_column(SmallInteger)
    status: Mapped[StatusRotinaEnum] = mapped_column(enum_col(StatusRotinaEnum, "status_rotina_enum"), nullable=False, default=StatusRotinaEnum.ativa)
    inicio_em: Mapped[date] = mapped_column(Date, nullable=False)
    fim_em: Mapped[date | None] = mapped_column(Date)


class Medicamento(TimestampMixin, Base):
    __tablename__ = "medicamentos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pessoa_cuidada_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pessoas_cuidadas.id", ondelete="CASCADE"), nullable=False)
    plano_cuidado_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("planos_cuidado.id", ondelete="SET NULL"))
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    principio_ativo: Mapped[str | None] = mapped_column(String(150))
    dosagem: Mapped[str] = mapped_column(String(80), nullable=False)
    via_administracao: Mapped[ViaAdministracaoEnum] = mapped_column(
        enum_col(ViaAdministracaoEnum, "via_administracao_enum"), nullable=False, default=ViaAdministracaoEnum.oral
    )
    intervalo_horas: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    orientacoes: Mapped[str | None] = mapped_column(Text)
    prescrito_por: Mapped[str | None] = mapped_column(String(150))
    inicio_em: Mapped[date] = mapped_column(Date, nullable=False)
    fim_em: Mapped[date | None] = mapped_column(Date)
    status: Mapped[StatusMedicamentoEnum] = mapped_column(
        enum_col(StatusMedicamentoEnum, "status_medicamento_enum"), nullable=False, default=StatusMedicamentoEnum.ativo
    )


class EventoSaude(TimestampMixin, Base):
    __tablename__ = "eventos_saude"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pessoa_cuidada_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pessoas_cuidadas.id", ondelete="CASCADE"), nullable=False)
    cuidador_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cuidadores.id", ondelete="SET NULL"))
    rotina_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rotinas.id", ondelete="SET NULL"))
    tipo: Mapped[TipoEventoSaudeEnum] = mapped_column(enum_col(TipoEventoSaudeEnum, "tipo_evento_saude_enum"), nullable=False)
    gravidade: Mapped[GravidadeEnum] = mapped_column(enum_col(GravidadeEnum, "gravidade_enum"), nullable=False, default=GravidadeEnum.baixa)
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)
    valor_numerico: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    unidade_medida: Mapped[str | None] = mapped_column(String(30))
    ocorreu_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    localizacao: Mapped[str | None] = mapped_column(String(150))
    requer_atencao_imediata: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadados: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class Alerta(TimestampMixin, Base):
    __tablename__ = "alertas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pessoa_cuidada_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pessoas_cuidadas.id", ondelete="CASCADE"), nullable=False)
    cuidador_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cuidadores.id", ondelete="CASCADE"), nullable=False)
    evento_saude_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("eventos_saude.id", ondelete="SET NULL"))
    rotina_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rotinas.id", ondelete="SET NULL"))
    tipo: Mapped[TipoAlertaEnum] = mapped_column(enum_col(TipoAlertaEnum, "tipo_alerta_enum"), nullable=False)
    prioridade: Mapped[PrioridadeAlertaEnum] = mapped_column(
        enum_col(PrioridadeAlertaEnum, "prioridade_alerta_enum"), nullable=False, default=PrioridadeAlertaEnum.media
    )
    status: Mapped[StatusAlertaEnum] = mapped_column(
        enum_col(StatusAlertaEnum, "status_alerta_enum"), nullable=False, default=StatusAlertaEnum.novo
    )
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    acao_recomendada: Mapped[str | None] = mapped_column(Text)
    gerado_por_ia: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    detectado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    resolvido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Interacao(TimestampMixin, Base):
    __tablename__ = "interacoes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cuidador_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cuidadores.id", ondelete="CASCADE"), nullable=False)
    pessoa_cuidada_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("pessoas_cuidadas.id", ondelete="SET NULL"))
    alerta_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("alertas.id", ondelete="SET NULL"))
    tipo: Mapped[TipoInteracaoEnum] = mapped_column(enum_col(TipoInteracaoEnum, "tipo_interacao_enum"), nullable=False, default=TipoInteracaoEnum.mensagem)
    papel_origem: Mapped[PapelInteracaoEnum] = mapped_column(
        enum_col(PapelInteracaoEnum, "papel_interacao_enum"), nullable=False
    )
    canal: Mapped[CanalInteracaoEnum] = mapped_column(enum_col(CanalInteracaoEnum, "canal_interacao_enum"), nullable=False, default=CanalInteracaoEnum.whatsapp)
    conteudo: Mapped[str] = mapped_column(Text, nullable=False)
    sentimento_detectado: Mapped[str | None] = mapped_column(String(50))
    confianca_sentimento: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    contexto_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    ocorreu_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Consulta(TimestampMixin, Base):
    __tablename__ = "consultas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pessoa_cuidada_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pessoas_cuidadas.id", ondelete="CASCADE"), nullable=False)
    cuidador_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cuidadores.id", ondelete="CASCADE"), nullable=False)
    tipo: Mapped[TipoConsultaEnum] = mapped_column(enum_col(TipoConsultaEnum, "tipo_consulta_enum"), nullable=False)
    status: Mapped[StatusConsultaEnum] = mapped_column(
        enum_col(StatusConsultaEnum, "status_consulta_enum"), nullable=False, default=StatusConsultaEnum.agendada
    )
    especialidade: Mapped[str | None] = mapped_column(String(120))
    profissional_saude: Mapped[str | None] = mapped_column(String(150))
    local_consulta: Mapped[str | None] = mapped_column(String(200))
    agendada_para: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duracao_minutos: Mapped[int | None] = mapped_column(SmallInteger)
    via_agendamento: Mapped[ViaAgendamentoEnum] = mapped_column(
        enum_col(ViaAgendamentoEnum, "via_agendamento_enum"), nullable=False, default=ViaAgendamentoEnum.manual
    )
    observacoes: Mapped[str | None] = mapped_column(Text)
    retorno_recomendado_em: Mapped[date | None] = mapped_column(Date)


class Lembrete(TimestampMixin, Base):
    __tablename__ = "lembretes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pessoa_cuidada_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pessoas_cuidadas.id", ondelete="CASCADE"), nullable=False)
    cuidador_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cuidadores.id", ondelete="CASCADE"), nullable=False)
    rotina_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rotinas.id", ondelete="SET NULL"))
    medicamento_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("medicamentos.id", ondelete="SET NULL"))
    consulta_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("consultas.id", ondelete="SET NULL"))
    tipo: Mapped[TipoLembreteEnum] = mapped_column(enum_col(TipoLembreteEnum, "tipo_lembrete_enum"), nullable=False)
    status: Mapped[StatusLembreteEnum] = mapped_column(
        enum_col(StatusLembreteEnum, "status_lembrete_enum"), nullable=False, default=StatusLembreteEnum.agendado
    )
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    mensagem: Mapped[str] = mapped_column(Text, nullable=False)
    agendado_para: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    enviado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    canais: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=lambda: ["whatsapp"])
    tentativas_envio: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
