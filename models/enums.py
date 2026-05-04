from enum import Enum


class StrEnum(str, Enum):
    pass


class GeneroEnum(StrEnum):
    feminino = "feminino"
    masculino = "masculino"
    nao_binario = "nao_binario"
    prefiro_nao_informar = "prefiro_nao_informar"


class ParentescoEnum(StrEnum):
    filho = "filho"
    filha = "filha"
    conjuge = "conjuge"
    irmao = "irmao"
    irma = "irma"
    neto = "neto"
    neta = "neta"
    sobrinho = "sobrinho"
    sobrinha = "sobrinha"
    amigo = "amigo"
    vizinho = "vizinho"
    cuidador_profissional = "cuidador_profissional"
    outro = "outro"


class StatusPlanoEnum(StrEnum):
    rascunho = "rascunho"
    ativo = "ativo"
    pausado = "pausado"
    encerrado = "encerrado"
    arquivado = "arquivado"


class TipoRotinaEnum(StrEnum):
    medicamento = "medicamento"
    atividade_fisica = "atividade_fisica"
    alimentacao = "alimentacao"
    hidratacao = "hidratacao"
    sono = "sono"
    monitoramento = "monitoramento"
    consulta = "consulta"
    exame = "exame"
    outro = "outro"


class FrequenciaRotinaEnum(StrEnum):
    diaria = "diaria"
    semanal = "semanal"
    mensal = "mensal"
    personalizada = "personalizada"


class StatusRotinaEnum(StrEnum):
    ativa = "ativa"
    pausada = "pausada"
    concluida = "concluida"
    cancelada = "cancelada"


class TipoEventoSaudeEnum(StrEnum):
    sintoma = "sintoma"
    crise = "crise"
    medicao = "medicao"
    queda = "queda"
    comportamento = "comportamento"
    sono = "sono"
    outro = "outro"


class GravidadeEnum(StrEnum):
    baixa = "baixa"
    moderada = "moderada"
    alta = "alta"
    critica = "critica"


class PapelInteracaoEnum(StrEnum):
    cuidador = "cuidador"
    agente = "agente"
    sistema = "sistema"


class CanalInteracaoEnum(StrEnum):
    whatsapp = "whatsapp"
    aplicativo = "aplicativo"
    telefone = "telefone"
    outro = "outro"


class TipoInteracaoEnum(StrEnum):
    mensagem = "mensagem"
    checkin = "checkin"
    resposta_alerta = "resposta_alerta"
    resumo = "resumo"
    outro = "outro"


class TipoAlertaEnum(StrEnum):
    risco_saude = "risco_saude"
    atraso_medicacao = "atraso_medicacao"
    consulta_proxima = "consulta_proxima"
    rotina_nao_cumprida = "rotina_nao_cumprida"
    anomalia_medicao = "anomalia_medicao"
    emergencia = "emergencia"
    outro = "outro"


class PrioridadeAlertaEnum(StrEnum):
    baixa = "baixa"
    media = "media"
    alta = "alta"
    critica = "critica"


class StatusAlertaEnum(StrEnum):
    novo = "novo"
    em_analise = "em_analise"
    resolvido = "resolvido"
    descartado = "descartado"


class TipoLembreteEnum(StrEnum):
    medicamento = "medicamento"
    consulta = "consulta"
    exame = "exame"
    atividade = "atividade"
    hidratacao = "hidratacao"
    checkin = "checkin"
    outro = "outro"


class StatusLembreteEnum(StrEnum):
    agendado = "agendado"
    enviado = "enviado"
    confirmado = "confirmado"
    adiado = "adiado"
    cancelado = "cancelado"
    expirado = "expirado"


class TipoConsultaEnum(StrEnum):
    presencial = "presencial"
    telemedicina = "telemedicina"
    retorno = "retorno"
    exame = "exame"


class StatusConsultaEnum(StrEnum):
    agendada = "agendada"
    confirmada = "confirmada"
    realizada = "realizada"
    cancelada = "cancelada"
    nao_compareceu = "nao_compareceu"
    reagendada = "reagendada"


class ViaAgendamentoEnum(StrEnum):
    manual = "manual"
    agente_ia = "agente_ia"
    integracao_externa = "integracao_externa"


class StatusMedicamentoEnum(StrEnum):
    ativo = "ativo"
    suspenso = "suspenso"
    concluido = "concluido"


class ViaAdministracaoEnum(StrEnum):
    oral = "oral"
    sublingual = "sublingual"
    inalatoria = "inalatoria"
    topica = "topica"
    oftalmica = "oftalmica"
    otologica = "otologica"
    nasal = "nasal"
    subcutanea = "subcutanea"
    intramuscular = "intramuscular"
    intravenosa = "intravenosa"
    retal = "retal"
    vaginal = "vaginal"
    outra = "outra"
