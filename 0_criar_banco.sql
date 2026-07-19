DROP TABLE IF EXISTS raw_viagem CASCADE;
CREATE TABLE raw_viagem (
    id_viagem                 VARCHAR(4000),
    num_proposta              VARCHAR(4000),
    situacao                  VARCHAR(4000),
    viagem_urgente            VARCHAR(4000),
    justificativa_urgencia    VARCHAR(4000),
    cod_orgao_superior         VARCHAR(4000),
    nome_orgao_superior        VARCHAR(4000),
    cod_orgao_solicitante       VARCHAR(4000),
    nome_orgao_solicitante      VARCHAR(4000),
    cpf_viajante               VARCHAR(4000),
    nome_viajante              VARCHAR(4000),
    cargo                     VARCHAR(4000),
    funcao                    VARCHAR(4000),
    descricao_funcao          VARCHAR(4000),
    data_inicio               VARCHAR(4000),
    data_fim                  VARCHAR(4000),
    destinos                  VARCHAR(4000),
    motivo                    VARCHAR(4000),
    valor_diarias             VARCHAR(4000),
    valor_passagens           VARCHAR(4000),
    valor_devolucao           VARCHAR(4000),
    valor_outros_gastos       VARCHAR(4000)
);

DROP TABLE IF EXISTS raw_pagamento CASCADE;
CREATE TABLE raw_pagamento (
    id_viagem              VARCHAR(4000),
    num_proposta           VARCHAR(4000),
    cod_orgao_superior      VARCHAR(4000),
    nome_orgao_superior     VARCHAR(4000),
    cod_orgao_pagador       VARCHAR(4000),
    nome_orgao_pagador      VARCHAR(4000),
    cod_ug_pagadora        VARCHAR(4000),
    nome_ug_pagadora       VARCHAR(4000),
    tipo_pagamento         VARCHAR(4000),
    valor                  VARCHAR(4000)
);

DROP TABLE IF EXISTS raw_passagem CASCADE;
CREATE TABLE raw_passagem (
    id_viagem            VARCHAR(4000),
    num_proposta         VARCHAR(4000),
    meio_transporte      VARCHAR(4000),
    pais_origem_ida      VARCHAR(4000),
    uf_origem_ida        VARCHAR(4000),
    cidade_origem_ida    VARCHAR(4000),
    pais_destino_ida     VARCHAR(4000),
    uf_destino_ida       VARCHAR(4000),
    cidade_destino_ida   VARCHAR(4000),
    pais_origem_volta    VARCHAR(4000),
    uf_origem_volta      VARCHAR(4000),
    cidade_origem_volta  VARCHAR(4000),
    pais_destino_volta   VARCHAR(4000),
    uf_destino_volta     VARCHAR(4000),
    cidade_destino_volta VARCHAR(4000),
    valor_passagem       VARCHAR(4000),
    taxa_servico         VARCHAR(4000),
    data_emissao         VARCHAR(4000),
    hora_emissao         VARCHAR(4000)
);

DROP TABLE IF EXISTS raw_trecho CASCADE;
CREATE TABLE raw_trecho (
    id_viagem         VARCHAR(4000),
    num_proposta      VARCHAR(4000),
    sequencia_trecho  VARCHAR(4000),
    origem_data       VARCHAR(4000),
    origem_pais       VARCHAR(4000),
    origem_uf         VARCHAR(4000),
    origem_cidade     VARCHAR(4000),
    destino_data      VARCHAR(4000),
    destino_pais      VARCHAR(4000),
    destino_uf        VARCHAR(4000),
    destino_cidade    VARCHAR(4000),
    meio_transporte   VARCHAR(4000),
    numero_diarias    VARCHAR(4000),
    missao            VARCHAR(4000)
);


-- -----------------------------------------------------------------------------
-- Camada SILVER
-- Dados limpos e tipados (DECIMAL, DATE), com integridade referencial entre
-- as tabelas. Cada tabela tem PRIMARY KEY + (para as 3 tabelas "filhas")
-- FOREIGN KEY para silver_viagem, alem de 2 constraints extras cada
-- (NOT NULL, CHECK ou UNIQUE), conforme o dicionario de dados do desafio.
-- -----------------------------------------------------------------------------

DROP TABLE IF EXISTS silver_trecho CASCADE;
DROP TABLE IF EXISTS silver_passagem CASCADE;
DROP TABLE IF EXISTS silver_pagamento CASCADE;
DROP TABLE IF EXISTS silver_viagem CASCADE;

-- silver_viagem -----------------------------------------------------------
-- Constraints extras: NOT NULL em nome_orgao_superior; CHECK em valor_diarias
CREATE TABLE silver_viagem (
    id_viagem            VARCHAR(20)   NOT NULL,
    num_proposta         VARCHAR(20),
    situacao             VARCHAR(50),
    viagem_urgente       VARCHAR(5),
    cod_orgao_superior   VARCHAR(20),
    nome_orgao_superior  VARCHAR(255)  NOT NULL,
    nome_viajante        VARCHAR(255),
    cargo                VARCHAR(255),
    data_inicio          DATE,
    data_fim             DATE,
    destinos             VARCHAR(4000),
    motivo               VARCHAR(4000),
    valor_diarias        DECIMAL(10,2) CHECK (valor_diarias >= 0),
    valor_passagens      DECIMAL(10,2),
    valor_devolucao      DECIMAL(10,2),
    valor_outros_gastos  DECIMAL(10,2),
    valor_total          DECIMAL(12,2),
    duracao_dias         INT,
    CONSTRAINT pk_silver_viagem PRIMARY KEY (id_viagem)
);

-- silver_pagamento ----------------------------------------------------------
-- Constraints extras: CHECK em valor; NOT NULL em tipo_pagamento
CREATE TABLE silver_pagamento (
    id_pagamento        SERIAL,
    id_viagem           VARCHAR(20)   NOT NULL,
    num_proposta        VARCHAR(20),
    nome_orgao_pagador  VARCHAR(255),
    nome_ug_pagadora    VARCHAR(255),
    tipo_pagamento      VARCHAR(50)   NOT NULL,
    valor               DECIMAL(10,2) CHECK (valor >= 0),
    CONSTRAINT pk_silver_pagamento PRIMARY KEY (id_pagamento),
    CONSTRAINT fk_pagamento_viagem FOREIGN KEY (id_viagem)
        REFERENCES silver_viagem (id_viagem)
);

-- silver_passagem -------------------------------------------------------------
-- Constraints extras: CHECK em valor_passagem; CHECK em taxa_servico
CREATE TABLE silver_passagem (
    id_passagem          SERIAL,
    id_viagem            VARCHAR(20)   NOT NULL,
    meio_transporte      VARCHAR(50),
    pais_origem_ida      VARCHAR(60),
    uf_origem_ida        VARCHAR(40),
    cidade_origem_ida    VARCHAR(80),
    pais_destino_ida     VARCHAR(60),
    uf_destino_ida       VARCHAR(40),
    cidade_destino_ida   VARCHAR(80),
    valor_passagem       DECIMAL(10,2) CHECK (valor_passagem >= 0),
    taxa_servico         DECIMAL(10,2) CHECK (taxa_servico >= 0),
    data_emissao         DATE,
    CONSTRAINT pk_silver_passagem PRIMARY KEY (id_passagem),
    CONSTRAINT fk_passagem_viagem FOREIGN KEY (id_viagem)
        REFERENCES silver_viagem (id_viagem)
);

-- silver_trecho -----------------------------------------------------------
-- Constraints extras: CHECK em numero_diarias; UNIQUE (id_viagem, sequencia_trecho)
CREATE TABLE silver_trecho (
    id_trecho          SERIAL,
    id_viagem          VARCHAR(20)   NOT NULL,
    sequencia_trecho   INT,
    origem_data        DATE,
    origem_uf          VARCHAR(40),
    origem_cidade      VARCHAR(80),
    destino_data       DATE,
    destino_uf         VARCHAR(40),
    destino_cidade     VARCHAR(80),
    meio_transporte    VARCHAR(50),
    numero_diarias     DECIMAL(10,2) CHECK (numero_diarias >= 0),
    CONSTRAINT pk_silver_trecho PRIMARY KEY (id_trecho),
    CONSTRAINT fk_trecho_viagem FOREIGN KEY (id_viagem)
        REFERENCES silver_viagem (id_viagem),
    CONSTRAINT uq_trecho_sequencia UNIQUE (id_viagem, sequencia_trecho)
);

-- Indices auxiliares nas FKs (melhoram o desempenho dos JOINs da camada Gold)
CREATE INDEX IF NOT EXISTS idx_pagamento_id_viagem ON silver_pagamento (id_viagem);
CREATE INDEX IF NOT EXISTS idx_passagem_id_viagem  ON silver_passagem (id_viagem);
CREATE INDEX IF NOT EXISTS idx_trecho_id_viagem     ON silver_trecho (id_viagem);