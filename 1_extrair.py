import csv
import logging
import sys
import zipfile
from pathlib import Path

import banco
from config import (
    ARQUIVOS,
    CSV_ENCODING,
    CSV_SEPARADOR,
    DRIVE_FILE_ID,
    PASTA_DADOS,
    TAMANHO_BLOCO,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("extrair")

NOME_ZIP = "dados_transparencia.zip"


# ---------------------------------------------------------------------------
# 1.1 - Download do .zip no Google Drive
# ---------------------------------------------------------------------------
def baixar_zip_do_drive(destino: Path) -> None:
    """
    Baixa o arquivo do Google Drive usando a biblioteca 'gdown'.
    So baixa se o .zip ainda nao existir localmente (idempotencia de rede).
    """
    if destino.exists():
        log.info("Zip ja existe em '%s' -- pulando download.", destino)
        return

    if not DRIVE_FILE_ID or DRIVE_FILE_ID == "1sMv7C4YcgJvt9XGMrsNCfsLk2HB14L7P":
        raise RuntimeError(
            "DRIVE_FILE_ID nao foi configurado em config.py. Copie o ID do "
            "arquivo compartilhado no Google Drive e cole na variavel "
            "DRIVE_FILE_ID."
        )

    try:
        import gdown
    except ImportError as erro:
        raise RuntimeError(
            "A biblioteca 'gdown' nao esta instalada. Rode: "
            "pip install -r requirements.txt"
        ) from erro

    log.info("Baixando .zip do Google Drive (id=%s)...", DRIVE_FILE_ID)
    url = f"https://drive.google.com/uc?id={DRIVE_FILE_ID}"
    gdown.download(url, str(destino), quiet=False)

    if not destino.exists():
        raise RuntimeError("Download concluido mas o arquivo .zip nao foi encontrado.")
    log.info("Download concluido: %s", destino)


def extrair_zip(caminho_zip: Path, pasta_destino: Path) -> None:
    """Extrai todos os arquivos do .zip para 'pasta_destino'."""
    log.info("Extraindo '%s' em '%s'...", caminho_zip, pasta_destino)
    with zipfile.ZipFile(caminho_zip, "r") as zip_ref:
        zip_ref.extractall(pasta_destino)
    log.info("Extracao concluida.")


def garantir_csvs_disponiveis() -> None:
    """
    Garante que os 4 CSVs esperados existem em PASTA_DADOS. Se algum estiver
    faltando, baixa e extrai o .zip do Drive.
    """
    PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    faltando = [
        info["csv"] for info in ARQUIVOS.values()
        if not (PASTA_DADOS / info["csv"]).exists()
    ]
    if not faltando:
        log.info("Todos os CSVs ja estao disponiveis em '%s'.", PASTA_DADOS)
        return

    log.info("CSVs faltando: %s", faltando)
    caminho_zip = PASTA_DADOS / NOME_ZIP
    baixar_zip_do_drive(caminho_zip)
    extrair_zip(caminho_zip, PASTA_DADOS)

    ainda_faltando = [
        info["csv"] for info in ARQUIVOS.values()
        if not (PASTA_DADOS / info["csv"]).exists()
    ]
    if ainda_faltando:
        raise RuntimeError(
            f"Apos extrair o .zip, os seguintes CSVs continuam ausentes: "
            f"{ainda_faltando}. Verifique se o .zip do Drive contem os "
            f"arquivos certos para o ano {ARQUIVOS}."
        )


# ---------------------------------------------------------------------------
# 1.2 - Leitura em blocos + carga na tabela Raw
# ---------------------------------------------------------------------------
def montar_insert_sql(tabela: str, quantidade_colunas: int) -> str:
    """Monta o 'INSERT INTO tabela VALUES (%s, %s, ...)' generico para a tabela raw."""
    marcadores = ", ".join(["%s"] * quantidade_colunas)
    return f"INSERT INTO {tabela} VALUES ({marcadores})"


def carregar_csv_para_raw(conexao, caminho_csv: Path, tabela_raw: str) -> int:
    """
    Le 'caminho_csv' em blocos de TAMANHO_BLOCO linhas e insere cada bloco na
    'tabela_raw' via banco.inserir_em_lote. Retorna o total de linhas carregadas.
    """
    total_linhas = 0
    with open(caminho_csv, encoding=CSV_ENCODING, newline="") as arquivo:
        leitor = csv.reader(arquivo, delimiter=CSV_SEPARADOR, quotechar='"')
        cabecalho = next(leitor)
        sql_insert = montar_insert_sql(tabela_raw, len(cabecalho))

        bloco = []
        for linha in leitor:
            # Preserva a linha exatamente como veio (nenhuma limpeza aqui).
            # Se a linha tiver menos/mais colunas que o cabecalho (CSV
            # malformado), completa com None / ignora colunas extras para
            # nao derrubar a carga inteira.
            if len(linha) != len(cabecalho):
                linha = (linha + [None] * len(cabecalho))[: len(cabecalho)]
            bloco.append(tuple(linha))

            if len(bloco) >= TAMANHO_BLOCO:
                banco.inserir_em_lote(conexao, sql_insert, bloco)
                total_linhas += len(bloco)
                log.info("  %s: %d linhas carregadas...", tabela_raw, total_linhas)
                bloco = []

        if bloco:
            banco.inserir_em_lote(conexao, sql_insert, bloco)
            total_linhas += len(bloco)

    return total_linhas


def carregar_camada_raw(conexao) -> None:
    """Esvazia e recarrega as 4 tabelas Raw a partir dos CSVs em PASTA_DADOS."""
    for chave, info in ARQUIVOS.items():
        caminho_csv = PASTA_DADOS / info["csv"]
        tabela_raw = info["tabela_raw"]

        log.info("Carregando '%s' -> %s", info["csv"], tabela_raw)
        banco.executar(conexao, f"TRUNCATE TABLE {tabela_raw}")
        total = carregar_csv_para_raw(conexao, caminho_csv, tabela_raw)
        log.info("OK: %s recebeu %d linhas de %s.", tabela_raw, total, info["csv"])


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------
def main() -> int:
    try:
        garantir_csvs_disponiveis()
        conexao = banco.conectar()
        try:
            carregar_camada_raw(conexao)
        finally:
            conexao.close()
        log.info("Fase 1 (Extracao -> Raw) concluida com sucesso.")
        return 0
    except Exception as erro:  # noqa: BLE001 - queremos capturar qualquer falha
        log.error("Falha na Fase 1 (Extracao -> Raw): %s", erro)
        return 1


if __name__ == "__main__":
    sys.exit(main())