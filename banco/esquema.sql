-- Banco de dados da Coleta de Campo — experimento de meliponicultura, Cametá do Ramos (FIS/IPÊ)
-- SQLite. Uma tabela por ficha do Anexo 05a, com as mesmas colunas, mais:
--   id             identificador do registro (vem do aplicativo; nas planilhas digitadas é calculado)
--   registrado_em  quando o registro foi criado no celular
--   editado_em     última correção no celular
--   dispositivo    código do celular que gerou o registro
--   excluido       1 = registro excluído no celular (fica guardado, sai das visões)
--   origem         arquivo de onde o registro entrou no banco
-- Datas em texto ISO (AAAA-MM-DD); horas em HH:MM.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS importacoes (
  n            INTEGER PRIMARY KEY AUTOINCREMENT,
  arquivo      TEXT NOT NULL,
  sha256       TEXT NOT NULL,
  tipo         TEXT NOT NULL,              -- planilha_app, planilha_05a, copia_json, kits_csv, fotos_zip
  importado_em TEXT NOT NULL,
  novos        INTEGER, atualizados INTEGER, ignorados INTEGER,
  observacao   TEXT
);

CREATE TABLE IF NOT EXISTS colonias (           -- F01_Cadastro: uma linha por colônia
  colonia TEXT PRIMARY KEY, grupo TEXT, especie TEXT, ambiente TEXT, meliponicultor TEXT, monitor TEXT,
  tratamento TEXT CHECK (tratamento IN ('NOVA','ANTIGA') OR tratamento IS NULL),
  kit TEXT, latitude REAL, longitude REAL, modelo_caixa TEXT, observacoes TEXT,
  id TEXT, registrado_em TEXT, editado_em TEXT, dispositivo TEXT, excluido INTEGER DEFAULT 0, origem TEXT
);

CREATE TABLE IF NOT EXISTS linha_base (         -- F02_LinhaBase
  colonia TEXT, data TEXT, observador TEXT, discos_cria INTEGER, diametro_maior_disco_cm REAL,
  potes_mel INTEGER, potes_polen INTEGER, entradas_5min INTEGER, peso_antes_extracao_kg REAL,
  peso_depois_extracao_kg REAL, tara_melgueira_kg REAL, estado_melgueira TEXT, sanidade TEXT, observacoes TEXT,
  id TEXT PRIMARY KEY, registrado_em TEXT, editado_em TEXT, dispositivo TEXT, excluido INTEGER DEFAULT 0, origem TEXT
);

CREATE TABLE IF NOT EXISTS instalacao_kit (     -- F03_InstalacaoKit
  kit TEXT, colonia TEXT, data TEXT, hora TEXT, observador TEXT, profundidade_tc_cm REAL, face_caixa TEXT,
  orientacao_entrada TEXT, altura_solo_cm REAL, correcao_tc1_c REAL, correcao_tc2_c REAL, correcao_tc3_c REAL,
  fator_balanca REAL, fotos TEXT, observacoes TEXT,
  id TEXT PRIMARY KEY, registrado_em TEXT, editado_em TEXT, dispositivo TEXT, excluido INTEGER DEFAULT 0, origem TEXT
);

CREATE TABLE IF NOT EXISTS verificacao_kit (    -- F04_VerificacaoKit
  kit TEXT, data TEXT, observador TEXT, tela_ok TEXT, dados_baixados TEXT, hora_acertada TEXT, bateria_v REAL,
  silica_trocada TEXT, problema TEXT, acao TEXT, observacoes TEXT,
  id TEXT PRIMARY KEY, registrado_em TEXT, editado_em TEXT, dispositivo TEXT, excluido INTEGER DEFAULT 0, origem TEXT
);

CREATE TABLE IF NOT EXISTS ocupacao (           -- F05_Ocupacao
  colonia TEXT, data TEXT, observador TEXT, nivel INTEGER CHECK (nivel BETWEEN 0 AND 5 OR nivel IS NULL),
  foto TEXT, observacoes TEXT,
  id TEXT PRIMARY KEY, registrado_em TEXT, editado_em TEXT, dispositivo TEXT, excluido INTEGER DEFAULT 0, origem TEXT
);

CREATE TABLE IF NOT EXISTS pesagem_atividade (  -- F06_PesagemAtividade
  colonia TEXT, data TEXT, hora TEXT, observador TEXT, peso_kg REAL, entradas_5min INTEGER, observacoes TEXT,
  id TEXT PRIMARY KEY, registrado_em TEXT, editado_em TEXT, dispositivo TEXT, excluido INTEGER DEFAULT 0, origem TEXT
);

CREATE TABLE IF NOT EXISTS chuva (              -- F07_Chuva
  grupo TEXT, data TEXT, chuva_mm REAL, leitor TEXT,
  id TEXT PRIMARY KEY, registrado_em TEXT, editado_em TEXT, dispositivo TEXT, excluido INTEGER DEFAULT 0, origem TEXT
);

CREATE TABLE IF NOT EXISTS manejo (             -- F08_Manejo
  colonia TEXT, data TEXT, hora TEXT, tipo TEXT, descricao TEXT, responsavel TEXT,
  id TEXT PRIMARY KEY, registrado_em TEXT, editado_em TEXT, dispositivo TEXT, excluido INTEGER DEFAULT 0, origem TEXT
);

CREATE TABLE IF NOT EXISTS extracao (           -- F09_Extracao
  colonia TEXT, safra INTEGER, data TEXT, mel_ml REAL, mel_g REAL, umidade_pct REAL, sabura_g REAL, cerume_g REAL,
  tempo_manejo_min REAL, praticidade_1a5 INTEGER, colonia_viva TEXT, codigo_amostra TEXT, observacoes TEXT,
  id TEXT PRIMARY KEY, registrado_em TEXT, editado_em TEXT, dispositivo TEXT, excluido INTEGER DEFAULT 0, origem TEXT
);

CREATE TABLE IF NOT EXISTS assistencia (        -- F10_Assistencia
  meliponicultor TEXT, data TEXT, tipo TEXT, recomendacoes TEXT, encaminhamentos TEXT, responsavel TEXT,
  id TEXT PRIMARY KEY, registrado_em TEXT, editado_em TEXT, dispositivo TEXT, excluido INTEGER DEFAULT 0, origem TEXT
);

CREATE TABLE IF NOT EXISTS praticas (           -- F10_Praticas (índice de boas práticas)
  meliponicultor TEXT, momento TEXT, data TEXT,
  p01 INTEGER, p02 INTEGER, p03 INTEGER, p04 INTEGER, p05 INTEGER, p06 INTEGER, p07 INTEGER, p08 INTEGER,
  p09 INTEGER, p10 INTEGER, indice INTEGER,
  id TEXT PRIMARY KEY, registrado_em TEXT, editado_em TEXT, dispositivo TEXT, excluido INTEGER DEFAULT 0, origem TEXT
);

CREATE TABLE IF NOT EXISTS producao_assistidos (-- F10_ProducaoAssistidos
  meliponicultor TEXT, safra INTEGER, colonias_produtivas INTEGER, producao_total_l REAL, l_por_colonia REAL,
  colonias_perdidas INTEGER, colonias_multiplicadas INTEGER, mel_vendido_l REAL, mel_perdido_l REAL,
  assistido_desde TEXT, observacoes TEXT,
  id TEXT PRIMARY KEY, registrado_em TEXT, editado_em TEXT, dispositivo TEXT, excluido INTEGER DEFAULT 0, origem TEXT
);

CREATE TABLE IF NOT EXISTS sorteios (           -- sorteio do controle de cada grupo (aba Sorteios do app)
  grupo TEXT, data TEXT, hora TEXT, aptas TEXT, controle TEXT, testemunhas TEXT, observador TEXT, refeito TEXT,
  id TEXT PRIMARY KEY, registrado_em TEXT, editado_em TEXT, dispositivo TEXT, excluido INTEGER DEFAULT 0, origem TEXT
);

CREATE TABLE IF NOT EXISTS leituras_kit (       -- arquivos CSV descarregados dos kits
  kit TEXT NOT NULL, data_hora TEXT NOT NULL, tc1_c REAL, tc2_c REAL, tc3_c REAL, t_ar_c REAL, ur_ar_pct REAL,
  luz_lx REAL, peso_g REAL, bateria_mv REAL, origem TEXT,
  PRIMARY KEY (kit, data_hora)
);

CREATE TABLE IF NOT EXISTS fotos (              -- fotos dos .zip do app, guardadas na pasta fotos/ ao lado do banco
  nome TEXT PRIMARY KEY, arquivo TEXT, bytes INTEGER, sha256 TEXT, origem TEXT
);

CREATE TABLE IF NOT EXISTS parametros (         -- aba F11_Ganhos (preço do mel, custo da tecnologia etc.)
  chave TEXT PRIMARY KEY, valor REAL, descricao TEXT, origem TEXT
);

CREATE INDEX IF NOT EXISTS ix_ocupacao_col ON ocupacao(colonia, data);
CREATE INDEX IF NOT EXISTS ix_pesagem_col ON pesagem_atividade(colonia, data);
CREATE INDEX IF NOT EXISTS ix_chuva ON chuva(grupo, data);
CREATE INDEX IF NOT EXISTS ix_manejo ON manejo(colonia, data);
CREATE INDEX IF NOT EXISTS ix_extracao ON extracao(colonia, safra);
CREATE INDEX IF NOT EXISTS ix_verif ON verificacao_kit(kit, data);

-- ---------------------------------------------------------------- visões
DROP VIEW IF EXISTS v_producao;
CREATE VIEW v_producao AS            -- produção por colônia e safra, com o tratamento sorteado
SELECT c.grupo, c.colonia, c.especie, c.ambiente, c.tratamento,
       SUM(CASE WHEN e.safra = 2026 THEN CASE WHEN e.colonia_viva = 'N' THEN 0 ELSE e.mel_ml END END) AS mel_ml_2026,
       SUM(CASE WHEN e.safra = 2027 THEN CASE WHEN e.colonia_viva = 'N' THEN 0 ELSE e.mel_ml END END) AS mel_ml_2027,
       AVG(CASE WHEN e.safra = 2027 THEN e.umidade_pct END) AS umidade_2027,
       AVG(CASE WHEN e.safra = 2027 THEN e.tempo_manejo_min END) AS tempo_extracao_2027_min
FROM colonias c LEFT JOIN extracao e ON e.colonia = c.colonia AND e.excluido = 0
WHERE c.excluido = 0
GROUP BY c.colonia;

DROP VIEW IF EXISTS v_ocupacao_atual;
CREATE VIEW v_ocupacao_atual AS      -- última observação de ocupação de cada colônia
SELECT c.grupo, c.colonia, c.tratamento, o.data AS ultima_data, o.nivel AS ultimo_nivel,
       CAST(julianday('now') - julianday(o.data) AS INTEGER) AS dias_desde
FROM colonias c LEFT JOIN ocupacao o ON o.colonia = c.colonia AND o.excluido = 0
  AND o.data = (SELECT MAX(data) FROM ocupacao x WHERE x.colonia = c.colonia AND x.excluido = 0)
WHERE c.excluido = 0;

DROP VIEW IF EXISTS v_chuva_mensal;
CREATE VIEW v_chuva_mensal AS
SELECT grupo, substr(data, 1, 7) AS mes, ROUND(SUM(chuva_mm), 1) AS chuva_mm, COUNT(*) AS dias_lidos,
       SUM(CASE WHEN chuva_mm > 0 THEN 1 ELSE 0 END) AS dias_com_chuva
FROM chuva WHERE excluido = 0 GROUP BY grupo, mes;

DROP VIEW IF EXISTS v_kits_diario;
CREATE VIEW v_kits_diario AS         -- médias diárias dos kits, já ligadas à colônia
SELECT c.grupo, c.colonia, c.tratamento, l.kit, substr(l.data_hora, 1, 10) AS dia, COUNT(*) AS leituras,
       ROUND(AVG(l.tc1_c), 2) AS tc1_media, ROUND(MAX(l.tc1_c) - MIN(l.tc1_c), 2) AS tc1_amplitude,
       ROUND(AVG(l.t_ar_c), 2) AS ar_media, ROUND(MAX(l.t_ar_c) - MIN(l.t_ar_c), 2) AS ar_amplitude,
       ROUND(AVG(l.tc3_c - l.tc1_c), 2) AS gradiente, ROUND(AVG(l.peso_g), 0) AS peso_medio_g
FROM leituras_kit l JOIN colonias c ON c.kit = l.kit AND c.excluido = 0
GROUP BY l.kit, dia;

DROP VIEW IF EXISTS v_praticas;
CREATE VIEW v_praticas AS            -- índice de boas práticas antes e depois
SELECT meliponicultor,
       MAX(CASE WHEN momento = 'ANTES' THEN indice END) AS indice_antes,
       MAX(CASE WHEN momento = 'DEPOIS' THEN indice END) AS indice_depois
FROM praticas WHERE excluido = 0 GROUP BY meliponicultor;
