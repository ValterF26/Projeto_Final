from datetime import date, datetime

# Valores que o Portal usa para indicar "sem dado" em campos de texto.
VALORES_NULOS = {"", "-1", "sem informação", "sem informacao", "null", "none"}


def texto_para_decimal(texto):
    """
    Converte um valor monetario em texto (com virgula decimal, ex: "1.234,56"
    ou "1234,56") para float. Retorna None se o campo estiver vazio/invalido.
    """
    if texto is None:
        return None
    texto = texto.strip()
    if texto.lower() in VALORES_NULOS:
        return None
    # remove separador de milhar (ponto) e troca a virgula decimal por ponto
    texto_normalizado = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto_normalizado)
    except ValueError:
        return None


def texto_para_data(texto):
    """
    Converte uma data em texto no formato DD/MM/AAAA para um objeto date do
    Python. Retorna None se o campo estiver vazio ou em um formato invalido.
    """
    if texto is None:
        return None
    texto = texto.strip()
    if texto.lower() in VALORES_NULOS:
        return None
    try:
        return datetime.strptime(texto, "%d/%m/%Y").date()
    except ValueError:
        return None


def calcular_duracao_dias(data_inicio, data_fim):
    """
    Numero de dias corridos da viagem (inclusive), contando o dia de ida e o
    dia de volta. Retorna None se alguma das datas for invalida/ausente ou se
    a data de fim for anterior a de inicio (dado inconsistente).
    """
    if not isinstance(data_inicio, date) or not isinstance(data_fim, date):
        return None
    diferenca = (data_fim - data_inicio).days
    if diferenca < 0:
        return None
    return diferenca + 1


def calcular_valor_total(valor_diarias, valor_passagens, valor_devolucao, valor_outros_gastos):
    """
    Soma os 4 componentes de custo de uma viagem. Valores ausentes (None)
    entram como zero na soma, mas se TODOS os componentes forem ausentes o
    resultado e None (para nao criar um "custo zero" artificial).
    """
    componentes = [valor_diarias, valor_passagens, valor_devolucao, valor_outros_gastos]
    if all(v is None for v in componentes):
        return None
    return sum(v if v is not None else 0.0 for v in componentes)


def texto_ou_none(texto):
    """Normaliza campos de texto: string vazia/"Sem informacao" vira None."""
    if texto is None:
        return None
    texto_limpo = texto.strip()
    if texto_limpo.lower() in VALORES_NULOS:
        return None
    return texto_limpo


def texto_para_int(texto):
    """Converte texto para int, retornando None em caso de valor ausente/invalido."""
    valor = texto_para_decimal(texto)
    if valor is None:
        return None
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None
