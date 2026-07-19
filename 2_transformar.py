import logging
import sys

import banco
from config import TAMANHO_BLOCO
from transformacoes import (
    calcular_duracao_dias,
    calcular_valor_total,
    texto_ou_none,
    texto_para_data,
    texto_para_decimal,
    texto_para_int,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("transformar")


# ---------------------------------------------------------------------------
# Utilitario: le uma tabela Raw em blocos, usando um cursor nomeado
# (server-side cursor) para nao estourar memoria com tabelas grandes.
# ---------------------------------------------------------------------------
def ler_raw_em_blocos(conexao_leitura, nome_tabela: str, colunas: str, nome_cursor: str):
    """
    Le 'nome_tabela' em blocos de TAMANHO_BLOCO linhas usando um cursor
    nomeado (server-side cursor) do PostgreSQL, para nunca carregar a tabela
    inteira na memoria.

    IMPORTANTE: 'conexao_leitura' e uma conexao dedicada so para leitura,
    separada da conexao usada para gravar na Silver. Um cursor nomeado so
    continua valido enquanto a transacao que o criou nao for commitada; como
    a carga na Silver faz commit a cada bloco (dentro de inserir_em_lote),
    usar a mesma conexao para ler e escrever invalidaria o cursor no meio da
    leitura.
    """
    cursor = conexao_leitura.cursor(name=nome_cursor)
    cursor.itersize = TAMANHO_BLOCO
    cursor.execute(f"SELECT {colunas} FROM {nome_tabela}")
    while True:
        bloco = cursor.fetchmany(TAMANHO_BLOCO)
        if not bloco:
            break
        yield bloco
    cursor.close()


# ---------------------------------------------------------------------------
# silver_viagem (carregada primeiro -- as outras 3 tabelas dependem dela)
# ---------------------------------------------------------------------------
COLUNAS_RAW_VIAGEM = (
    "id_viagem, num_proposta, situacao, viagem_urgente, cod_orgao_superior, "
    "nome_orgao_superior, cargo, nome_viajante, data_inicio, data_fim, "
    "destinos, motivo, valor_diarias, valor_passagens, valor_devolucao, "
    "valor_outros_gastos"
)

SQL_INSERT_SILVER_VIAGEM = """
    INSERT INTO silver_viagem (
        id_viagem, num_proposta, situacao, viagem_urgente, cod_orgao_superior,
        nome_orgao_superior, nome_viajante, cargo, data_inicio, data_fim,
        destinos, motivo, valor_diarias, valor_passagens, valor_devolucao,
        valor_outros_gastos, valor_total, duracao_dias
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def transformar_viagem(conexao_leitura, conexao_escrita) -> set:
    """
    Transforma raw_viagem -> silver_viagem. Retorna o conjunto de id_viagem
    que foram efetivamente carregados (usado para validar a FK das outras
    3 tabelas).
    """
    banco.executar(
        conexao_escrita,
        "TRUNCATE TABLE silver_trecho, silver_passagem, silver_pagamento, "
        "silver_viagem RESTART IDENTITY CASCADE",
    )

    ids_carregados = set()
    total_lidas = 0
    total_carregadas = 0
    total_rejeitadas = 0

    for bloco in ler_raw_em_blocos(conexao_leitura, "raw_viagem", COLUNAS_RAW_VIAGEM, "cur_viagem"):
        linhas_silver = []
        for linha in bloco:
            total_lidas += 1
            (
                id_viagem, num_proposta, situacao, viagem_urgente, cod_orgao_superior,
                nome_orgao_superior, cargo, nome_viajante, data_inicio, data_fim,
                destinos, motivo, valor_diarias, valor_passagens, valor_devolucao,
                valor_outros_gastos,
            ) = linha

            id_viagem = texto_ou_none(id_viagem)
            nome_orgao_superior_limpo = texto_ou_none(nome_orgao_superior)

            # id_viagem e nome_orgao_superior sao obrigatorios na Silver
            # (PK / NOT NULL) -- linhas sem esses dados sao rejeitadas.
            if id_viagem is None or nome_orgao_superior_limpo is None:
                total_rejeitadas += 1
                continue
            # id_viagem duplicado (PK): mantem so a primeira ocorrencia.
            if id_viagem in ids_carregados:
                total_rejeitadas += 1
                continue

            data_inicio_convertida = texto_para_data(data_inicio)
            data_fim_convertida = texto_para_data(data_fim)
            valor_diarias_num = texto_para_decimal(valor_diarias)
            valor_passagens_num = texto_para_decimal(valor_passagens)
            valor_devolucao_num = texto_para_decimal(valor_devolucao)
            valor_outros_gastos_num = texto_para_decimal(valor_outros_gastos)

            valor_total = calcular_valor_total(
                valor_diarias_num, valor_passagens_num, valor_devolucao_num, valor_outros_gastos_num
            )
            duracao_dias = calcular_duracao_dias(data_inicio_convertida, data_fim_convertida)

            linhas_silver.append((
                id_viagem[:20],
                texto_ou_none(num_proposta),
                texto_ou_none(situacao),
                texto_ou_none(viagem_urgente),
                texto_ou_none(cod_orgao_superior),
                nome_orgao_superior_limpo,
                texto_ou_none(nome_viajante),
                texto_ou_none(cargo),
                data_inicio_convertida,
                data_fim_convertida,
                texto_ou_none(destinos),
                texto_ou_none(motivo),
                valor_diarias_num,
                valor_passagens_num,
                valor_devolucao_num,
                valor_outros_gastos_num,
                valor_total,
                duracao_dias,
            ))
            ids_carregados.add(id_viagem)

        banco.inserir_em_lote(conexao_escrita, SQL_INSERT_SILVER_VIAGEM, linhas_silver)
        total_carregadas += len(linhas_silver)
        log.info("  silver_viagem: %d linhas carregadas...", total_carregadas)

    log.info(
        "silver_viagem: %d lidas, %d carregadas, %d rejeitadas.",
        total_lidas, total_carregadas, total_rejeitadas,
    )
    return ids_carregados


# ---------------------------------------------------------------------------
# silver_pagamento
# ---------------------------------------------------------------------------
COLUNAS_RAW_PAGAMENTO = (
    "id_viagem, num_proposta, nome_orgao_pagador, nome_ug_pagadora, "
    "tipo_pagamento, valor"
)

SQL_INSERT_SILVER_PAGAMENTO = """
    INSERT INTO silver_pagamento (
        id_viagem, num_proposta, nome_orgao_pagador, nome_ug_pagadora,
        tipo_pagamento, valor
    ) VALUES (%s, %s, %s, %s, %s, %s)
"""


def transformar_pagamento(conexao_leitura, conexao_escrita, ids_viagem_validos: set) -> None:
    total_lidas = 0
    total_carregadas = 0
    total_rejeitadas = 0

    for bloco in ler_raw_em_blocos(conexao_leitura, "raw_pagamento", COLUNAS_RAW_PAGAMENTO, "cur_pagamento"):
        linhas_silver = []
        for linha in bloco:
            total_lidas += 1
            id_viagem, num_proposta, nome_orgao_pagador, nome_ug_pagadora, tipo_pagamento, valor = linha

            id_viagem = texto_ou_none(id_viagem)
            tipo_pagamento_limpo = texto_ou_none(tipo_pagamento)
            valor_num = texto_para_decimal(valor)

            # FK (id_viagem deve existir em silver_viagem), NOT NULL em
            # tipo_pagamento e CHECK (valor >= 0): linhas que nao atendem
            # sao rejeitadas para nao violar as constraints da Silver.
            if id_viagem is None or id_viagem not in ids_viagem_validos:
                total_rejeitadas += 1
                continue
            if tipo_pagamento_limpo is None:
                total_rejeitadas += 1
                continue
            if valor_num is not None and valor_num < 0:
                total_rejeitadas += 1
                continue

            linhas_silver.append((
                id_viagem[:20],
                texto_ou_none(num_proposta),
                texto_ou_none(nome_orgao_pagador),
                texto_ou_none(nome_ug_pagadora),
                tipo_pagamento_limpo,
                valor_num,
            ))

        banco.inserir_em_lote(conexao_escrita, SQL_INSERT_SILVER_PAGAMENTO, linhas_silver)
        total_carregadas += len(linhas_silver)
        log.info("  silver_pagamento: %d linhas carregadas...", total_carregadas)

    log.info(
        "silver_pagamento: %d lidas, %d carregadas, %d rejeitadas.",
        total_lidas, total_carregadas, total_rejeitadas,
    )


# ---------------------------------------------------------------------------
# silver_passagem
# ---------------------------------------------------------------------------
COLUNAS_RAW_PASSAGEM = (
    "id_viagem, meio_transporte, pais_origem_ida, uf_origem_ida, "
    "cidade_origem_ida, pais_destino_ida, uf_destino_ida, cidade_destino_ida, "
    "valor_passagem, taxa_servico, data_emissao"
)

SQL_INSERT_SILVER_PASSAGEM = """
    INSERT INTO silver_passagem (
        id_viagem, meio_transporte, pais_origem_ida, uf_origem_ida,
        cidade_origem_ida, pais_destino_ida, uf_destino_ida, cidade_destino_ida,
        valor_passagem, taxa_servico, data_emissao
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def transformar_passagem(conexao_leitura, conexao_escrita, ids_viagem_validos: set) -> None:
    total_lidas = 0
    total_carregadas = 0
    total_rejeitadas = 0

    for bloco in ler_raw_em_blocos(conexao_leitura, "raw_passagem", COLUNAS_RAW_PASSAGEM, "cur_passagem"):
        linhas_silver = []
        for linha in bloco:
            total_lidas += 1
            (
                id_viagem, meio_transporte, pais_origem_ida, uf_origem_ida,
                cidade_origem_ida, pais_destino_ida, uf_destino_ida, cidade_destino_ida,
                valor_passagem, taxa_servico, data_emissao,
            ) = linha

            id_viagem = texto_ou_none(id_viagem)
            valor_passagem_num = texto_para_decimal(valor_passagem)
            taxa_servico_num = texto_para_decimal(taxa_servico)

            if id_viagem is None or id_viagem not in ids_viagem_validos:
                total_rejeitadas += 1
                continue
            if (valor_passagem_num is not None and valor_passagem_num < 0) or (
                taxa_servico_num is not None and taxa_servico_num < 0
            ):
                total_rejeitadas += 1
                continue

            linhas_silver.append((
                id_viagem[:20],
                texto_ou_none(meio_transporte),
                texto_ou_none(pais_origem_ida),
                texto_ou_none(uf_origem_ida),
                texto_ou_none(cidade_origem_ida),
                texto_ou_none(pais_destino_ida),
                texto_ou_none(uf_destino_ida),
                texto_ou_none(cidade_destino_ida),
                valor_passagem_num,
                taxa_servico_num,
                texto_para_data(data_emissao),
            ))

        banco.inserir_em_lote(conexao_escrita, SQL_INSERT_SILVER_PASSAGEM, linhas_silver)
        total_carregadas += len(linhas_silver)
        log.info("  silver_passagem: %d linhas carregadas...", total_carregadas)

    log.info(
        "silver_passagem: %d lidas, %d carregadas, %d rejeitadas.",
        total_lidas, total_carregadas, total_rejeitadas,
    )


# ---------------------------------------------------------------------------
# silver_trecho
# ---------------------------------------------------------------------------
COLUNAS_RAW_TRECHO = (
    "id_viagem, sequencia_trecho, origem_data, origem_uf, origem_cidade, "
    "destino_data, destino_uf, destino_cidade, meio_transporte, numero_diarias"
)

SQL_INSERT_SILVER_TRECHO = """
    INSERT INTO silver_trecho (
        id_viagem, sequencia_trecho, origem_data, origem_uf, origem_cidade,
        destino_data, destino_uf, destino_cidade, meio_transporte, numero_diarias
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def transformar_trecho(conexao_leitura, conexao_escrita, ids_viagem_validos: set) -> None:
    total_lidas = 0
    total_carregadas = 0
    total_rejeitadas = 0
    chaves_vistas = set()  # para respeitar o UNIQUE (id_viagem, sequencia_trecho)

    for bloco in ler_raw_em_blocos(conexao_leitura, "raw_trecho", COLUNAS_RAW_TRECHO, "cur_trecho"):
        linhas_silver = []
        for linha in bloco:
            total_lidas += 1
            (
                id_viagem, sequencia_trecho, origem_data, origem_uf, origem_cidade,
                destino_data, destino_uf, destino_cidade, meio_transporte, numero_diarias,
            ) = linha

            id_viagem = texto_ou_none(id_viagem)
            sequencia_num = texto_para_int(sequencia_trecho)
            numero_diarias_num = texto_para_decimal(numero_diarias)

            if id_viagem is None or id_viagem not in ids_viagem_validos:
                total_rejeitadas += 1
                continue
            if numero_diarias_num is not None and numero_diarias_num < 0:
                total_rejeitadas += 1
                continue
            chave = (id_viagem, sequencia_num)
            if chave in chaves_vistas:
                total_rejeitadas += 1
                continue
            chaves_vistas.add(chave)

            linhas_silver.append((
                id_viagem[:20],
                sequencia_num,
                texto_para_data(origem_data),
                texto_ou_none(origem_uf),
                texto_ou_none(origem_cidade),
                texto_para_data(destino_data),
                texto_ou_none(destino_uf),
                texto_ou_none(destino_cidade),
                texto_ou_none(meio_transporte),
                numero_diarias_num,
            ))

        banco.inserir_em_lote(conexao_escrita, SQL_INSERT_SILVER_TRECHO, linhas_silver)
        total_carregadas += len(linhas_silver)
        log.info("  silver_trecho: %d linhas carregadas...", total_carregadas)

    log.info(
        "silver_trecho: %d lidas, %d carregadas, %d rejeitadas.",
        total_lidas, total_carregadas, total_rejeitadas,
    )


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------
def main() -> int:
    try:
        conexao_leitura = banco.conectar()
        conexao_escrita = banco.conectar()
        try:
            ids_viagem_validos = transformar_viagem(conexao_leitura, conexao_escrita)
            transformar_pagamento(conexao_leitura, conexao_escrita, ids_viagem_validos)
            transformar_passagem(conexao_leitura, conexao_escrita, ids_viagem_validos)
            transformar_trecho(conexao_leitura, conexao_escrita, ids_viagem_validos)
        finally:
            conexao_leitura.close()
            conexao_escrita.close()
        log.info("Fase 2 (Transformacao -> Silver) concluida com sucesso.")
        return 0
    except Exception as erro:  # noqa: BLE001
        log.error("Falha na Fase 2 (Transformacao -> Silver): %s", erro)
        return 1


if __name__ == "__main__":
    sys.exit(main())
