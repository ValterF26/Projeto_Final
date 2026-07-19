# Transparência de Viagens a Serviço -- Pipeline de Dados (Medallion)

Pipeline de dados ponta a ponta que baixa os dados de **Viagens a Serviço** do
Portal da Transparência do Governo Federal, preserva o histórico bruto,
limpa e tipa a informação, e responde perguntas de negócio sobre o gasto
público com viagens -- seguindo a **Arquitetura Medallion** (Raw → Silver →
Gold).

## 1. Problema que o projeto resolve

O órgão responsável publica os dados de viagens a serviço no Portal da
Transparência, mas eles chegam brutos, em CSV, sem tipagem e sem garantia de
integridade entre as tabelas. Este projeto automatiza a extração, o
tratamento e a análise desses dados, entregando:

- **Rastreabilidade**: a camada Raw guarda uma cópia fiel do dado original,
  permitindo auditar qualquer transformação feita depois.
- **Confiabilidade**: a camada Silver tipa e valida os dados (datas, valores
  monetários, chaves estrangeiras), eliminando duplicidades e inconsistências.
- **Decisão**: a camada Gold responde, com SQL + gráficos, às perguntas de
  negócio que a equipe de transparência precisa acompanhar.

## 2. Técnicas e tecnologias utilizadas

- **Python 3** -- orquestração do pipeline (`psycopg2`, `pandas`, `gdown`)
- **PostgreSQL** -- banco relacional, com as 3 camadas (Raw/Silver/Gold)
- **SQL** -- DDL com `PRIMARY KEY`, `FOREIGN KEY`, `CHECK`, `UNIQUE`, `VIEW`
- **Jupyter Notebook** -- camada Gold (perguntas de negócio + gráficos)
- **Matplotlib** -- visualização dos resultados

```
CSV (Portal da Transparência)
        │  1_extrair.py  (download + leitura em blocos)
        ▼
   camada RAW        (VARCHAR puro, sem constraints, fiel ao CSV)
        │  2_transformar.py  (tipagem, limpeza, colunas calculadas)
        ▼
   camada SILVER      (tipada, com PK/FK/CHECK/UNIQUE)
        │  3_analise.ipynb  (SQL + JOIN + GROUP BY)
        ▼
   camada GOLD        (tabela agregada + view + gráficos)
```

### Arquivos do projeto

| Arquivo               | Fase                          | Descrição                                                        |
|------------------------|--------------------------------|-------------------------------------------------------------------|
| `config.py`             | --                              | Parâmetros do projeto e leitura do `.env`                          |
| `banco.py`              | --                              | Conexão e utilitários de acesso ao PostgreSQL                      |
| `transformacoes.py`     | --                              | Funções de conversão de tipo (texto→decimal, texto→data)           |
| `0_criar_banco.sql`     | Fase 0 -- Banco e tabelas        | Cria o database e as 8 tabelas (4 Raw + 4 Silver)                  |
| `1_extrair.py`          | Fase 1 -- Extração / Raw         | Baixa o `.zip`, lê os CSVs em blocos e carrega a camada Raw        |
| `2_transformar.py`      | Fase 2 -- Transformação / Silver | Tipa, limpa e carrega a camada Silver                              |
| `3_analise.ipynb`       | Fase 3 -- Análise / Gold         | Perguntas de negócio, gráficos e camada Gold (tabela + view)       |

## 3. Como executar

### 3.1 Pré-requisitos

- Python 3.10+
- PostgreSQL instalado e rodando localmente (ou acessível via rede)

### 3.2 Passo a passo

```bash
# 1. Clone o repositório e entre na pasta
git clone <url-do-seu-repositorio>
cd desafio_transparencia

# 2. Crie um ambiente virtual e instale as dependências
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Configure as credenciais
cp env.example .env
# edite o .env com o usuário/senha do seu PostgreSQL

# 4. Configure o Google Drive (em config.py)
# edite a variável DRIVE_FILE_ID com o ID do arquivo compartilhado no Drive

# 5. Fase 0 -- cria o banco e as 8 tabelas
psql -U postgres -f 0_criar_banco.sql

# 6. Fase 1 -- baixa o .zip e carrega a camada Raw
python 1_extrair.py

# 7. Fase 2 -- limpa, tipa e carrega a camada Silver
python 2_transformar.py

# 8. Fase 3 -- abra o notebook e rode todas as células
jupyter notebook 3_analise.ipynb
```

Cada uma das fases 1 e 2 é **idempotente**: pode ser executada quantas vezes
for necessário (as tabelas são esvaziadas com `TRUNCATE` antes da carga) e
**resiliente** a falhas de download/conexão (erros são capturados e
reportados com uma mensagem clara em vez de um traceback cru).

## 4. Perguntas de negócio respondidas

1. Os 5 órgãos com maior custo total (Silver)
2. Os 3 destinos com maior custo médio por viagem (Silver)
3. A viagem de maior duração e seu custo total (Silver)
4. Qual órgão pagou mais no total (Gold -- `gold_orgao_resumo` / view)
5. Qual o tipo de pagamento com maior valor médio (Silver)
6. Qual o meio de transporte mais usado nos trechos (Silver)
7. Qual UF de destino aparece em mais trechos (Silver)

Todas com consulta SQL, tabela e gráfico no `3_analise.ipynb`.

## 5. Melhorias futuras

- Orquestração das 3 fases com Airflow/Prefect em vez de execução manual;
- Testes automatizados (pytest) para as funções de `transformacoes.py`;
- Camada Gold adicional por viajante/cargo, para identificar padrões de uso;
- Carga incremental (por período) em vez de `TRUNCATE` completo a cada rodada;
- Deploy do banco em um serviço gerenciado (ex.: RDS/Cloud SQL) com backups.

## 6. Conclusões e insights

Abaixo estão os principais insights derivados das sete perguntas de negócio respondidas pelo arquivo 3_analise.ipynb.

1. Top Órgãos com Maior Custo
Identifica quais ministérios e autarquias demandam maior orçamento para deslocamento de pessoal, permitindo auditorias focadas.

2. Destinos de Maior Custo Médio (Tratado)
Utilizando técnicas de split de texto (SPLIT_PART), foram limpos os históricos de escalas para isolar o destino principal.

Isso revelou localidades com maiores custos médios de diárias fora do eixo administrativo comum de Brasília.

3. Análise de Outliers (Maior Duração)
Localizou de forma precisa uma viagem atípica de 378 dias, cujo custo totalizado foi de R$ 120.650,00.

O valor se mostrou proporcional ao período (cerca de R$ 319,00 por dia), demonstrando a capacidade do pipeline de isolar missões contínuas no exterior ou de longo prazo sem distorcer as médias gerais.

4. Meio de Transporte Mais Utilizado
Inicialmente visualizado em gráfico de pizza, foi convertido para um gráfico de barras horizontais para evitar a sobreposição de rótulos pequenos (Ferroviário e Marítimo).

O resultado mostrou de forma clara o predomínio dos modais Aéreo e Rodoviário.

5. Tipo de Pagamento com Maior Valor Médio
Revelou quais modalidades de repasse financeiro concentram os maiores tickets médios por transação via VIEW analítica.

6. UF de Destino Mais Frequente
Mapeamento geográfico de trechos que auxilia na negociação de contratos corporativos de passagens para os estados mais visitados.

7. Órgão Pagador Líder em Recursos
Demonstra a concentração do desembolso de verbas públicas por entidade financeira de origem.
