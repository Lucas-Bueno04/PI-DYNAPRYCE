-- Reversão: restaurar o backup (F1.39). Não há downgrade.
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE SCHEMA core;
CREATE SCHEMA raw;
CREATE SCHEMA job;
CREATE SCHEMA audit;
CREATE SCHEMA auth;

CREATE FUNCTION core.tenant_atual() RETURNS uuid LANGUAGE sql STABLE AS
$$ SELECT NULLIF(current_setting('app.tenant_id', true), '')::uuid $$;

-- core ---------------------------------------------------------------------------------------
CREATE TABLE core.tenant (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  nome text NOT NULL,
  estado text NOT NULL DEFAULT 'ativo' CHECK (estado IN ('ativo', 'suspenso')),
  criado_em timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE core.empresa (
  tenant_id uuid NOT NULL REFERENCES core.tenant,
  id text NOT NULL,
  documento_cifrado bytea,
  regime text NOT NULL CHECK (regime IN ('MEI', 'SN', 'LP', 'LR')),
  departamentos text[] NOT NULL DEFAULT ARRAY['fiscal', 'contabil', 'folha'],
  perfil jsonb NOT NULL DEFAULT '{}',
  PRIMARY KEY (tenant_id, id)
);

CREATE TABLE core.contrato (
  tenant_id uuid NOT NULL REFERENCES core.tenant,
  id text NOT NULL,
  preco_vigente numeric(14, 2) NOT NULL CHECK (preco_vigente >= 0),
  mes_reajuste int CHECK (mes_reajuste BETWEEN 1 AND 12),
  kappa numeric(6, 4) NOT NULL DEFAULT 1,
  kappa_justificativa text NOT NULL DEFAULT '',
  desconto numeric(6, 4) NOT NULL DEFAULT 0,
  desconto_justificativa text NOT NULL DEFAULT '',
  estado text NOT NULL DEFAULT 'provisorio'
    CHECK (estado IN ('provisorio', 'definitivo', 'encerrado')),
  versao int NOT NULL DEFAULT 1,
  PRIMARY KEY (tenant_id, id)
);

CREATE TABLE core.vinculo (
  tenant_id uuid NOT NULL,
  contrato_id text NOT NULL,
  empresa_id text NOT NULL,
  principal boolean NOT NULL DEFAULT false,
  desde date NOT NULL,
  ate date,
  PRIMARY KEY (tenant_id, empresa_id, desde),
  FOREIGN KEY (tenant_id, contrato_id) REFERENCES core.contrato,
  FOREIGN KEY (tenant_id, empresa_id) REFERENCES core.empresa,
  EXCLUDE USING gist (
    tenant_id WITH =, empresa_id WITH =, daterange(desde, ate, '[]') WITH &&
  )
);

CREATE TABLE core.empresa_mes (
  tenant_id uuid NOT NULL,
  empresa_id text NOT NULL,
  competencia date NOT NULL,
  versao_extracao int NOT NULL,
  regime text,
  direcionadores jsonb NOT NULL,
  horas_registradas jsonb NOT NULL DEFAULT '{}',
  PRIMARY KEY (tenant_id, empresa_id, competencia, versao_extracao),
  FOREIGN KEY (tenant_id, empresa_id) REFERENCES core.empresa
);

CREATE TABLE core.honorario_mes (
  tenant_id uuid NOT NULL,
  contrato_id text NOT NULL,
  competencia date NOT NULL,
  valor_cobrado numeric(14, 2) NOT NULL,
  PRIMARY KEY (tenant_id, contrato_id, competencia),
  FOREIGN KEY (tenant_id, contrato_id) REFERENCES core.contrato
);

CREATE TABLE core.indice_inflacao (
  competencia date NOT NULL,
  indice text NOT NULL,
  variacao numeric(10, 6) NOT NULL,
  registrado_por text NOT NULL,
  PRIMARY KEY (competencia, indice)
);

CREATE TABLE core.politica_versao (
  tenant_id uuid NOT NULL REFERENCES core.tenant,
  versao int NOT NULL,
  estado text NOT NULL DEFAULT 'rascunho'
    CHECK (estado IN ('rascunho', 'publicada', 'substituida', 'descartada')),
  documento jsonb NOT NULL,
  portao_aceite boolean,
  relatorio jsonb,
  aprovado_por uuid,
  publicada_em timestamptz,
  PRIMARY KEY (tenant_id, versao)
);
CREATE UNIQUE INDEX politica_uma_publicada ON core.politica_versao (tenant_id)
  WHERE estado = 'publicada';

CREATE FUNCTION core.proteger_politica() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.estado = 'rascunho' THEN
    RETURN NEW;
  END IF;
  IF OLD.estado = 'publicada' AND NEW.estado = 'substituida'
     AND to_jsonb(OLD) - 'estado' = to_jsonb(NEW) - 'estado' THEN
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'política % é imutável', OLD.versao USING ERRCODE = 'integrity_constraint_violation';
END $$;
CREATE TRIGGER politica_imutavel BEFORE UPDATE ON core.politica_versao
  FOR EACH ROW EXECUTE FUNCTION core.proteger_politica();

CREATE TABLE core.preco_alvo (
  tenant_id uuid NOT NULL,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  contrato_id text NOT NULL,
  competencia date NOT NULL,
  politica_versao int NOT NULL,
  nivel_informacao int NOT NULL CHECK (nivel_informacao IN (0, 1, 2)),
  h_pad numeric(12, 4),
  entradas jsonb NOT NULL,
  preco_alvo numeric(14, 2) NOT NULL,
  PRIMARY KEY (tenant_id, id),
  UNIQUE (tenant_id, contrato_id, competencia, politica_versao),
  FOREIGN KEY (tenant_id, contrato_id) REFERENCES core.contrato,
  FOREIGN KEY (tenant_id, politica_versao) REFERENCES core.politica_versao
);

CREATE TABLE core.lote_exportacao (
  tenant_id uuid NOT NULL REFERENCES core.tenant,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  hash_recomendacoes text NOT NULL,
  arquivo bytea,
  arquivo_sha256 text,
  gerado_em timestamptz,
  PRIMARY KEY (tenant_id, id),
  UNIQUE (tenant_id, hash_recomendacoes)
);

CREATE TABLE core.recomendacao (
  tenant_id uuid NOT NULL,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  contrato_id text NOT NULL,
  preco_alvo_id uuid NOT NULL,
  politica_versao int NOT NULL,
  competencia date NOT NULL,
  versao int NOT NULL DEFAULT 1,
  lote_id uuid,
  estado text NOT NULL DEFAULT 'pendente' CHECK (estado IN
    ('pendente', 'aprovada', 'rejeitada', 'expirada', 'exportada', 'falha_exportacao')),
  preco_vigente numeric(14, 2) NOT NULL,
  preco_proposto numeric(14, 2) NOT NULL,
  data_efeito date NOT NULL,
  trajetoria jsonb NOT NULL,
  kappa numeric(6, 4) NOT NULL DEFAULT 1,
  motivo text NOT NULL DEFAULT '',
  decidido_por uuid,
  decidido_em timestamptz,
  PRIMARY KEY (tenant_id, id),
  FOREIGN KEY (tenant_id, contrato_id) REFERENCES core.contrato,
  FOREIGN KEY (tenant_id, preco_alvo_id) REFERENCES core.preco_alvo,
  FOREIGN KEY (tenant_id, lote_id) REFERENCES core.lote_exportacao
);
CREATE UNIQUE INDEX recomendacao_uma_pendente ON core.recomendacao (tenant_id, contrato_id)
  WHERE estado = 'pendente';

CREATE TABLE core.divergencia_cobranca (
  tenant_id uuid NOT NULL,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  contrato_id text NOT NULL,
  recomendacao_id uuid,
  competencia date NOT NULL,
  aprovado numeric(14, 2) NOT NULL,
  cobrado numeric(14, 2) NOT NULL,
  situacao text NOT NULL DEFAULT 'aberta'
    CHECK (situacao IN ('aberta', 'justificada', 'resolvida')),
  justificativa text NOT NULL DEFAULT '',
  PRIMARY KEY (tenant_id, id),
  UNIQUE (tenant_id, contrato_id, competencia),
  FOREIGN KEY (tenant_id, contrato_id) REFERENCES core.contrato,
  FOREIGN KEY (tenant_id, recomendacao_id) REFERENCES core.recomendacao
);

CREATE TABLE core.cotacao (
  tenant_id uuid NOT NULL REFERENCES core.tenant,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  regime text NOT NULL,
  politica_versao int NOT NULL,
  entradas jsonb NOT NULL,
  preco numeric(14, 2) NOT NULL,
  decomposicao jsonb NOT NULL,
  criada_por uuid,
  criada_em timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, id),
  FOREIGN KEY (tenant_id, politica_versao) REFERENCES core.politica_versao
);

CREATE TABLE core.conector_config (
  tenant_id uuid NOT NULL REFERENCES core.tenant,
  tipo text NOT NULL,
  credencial_cifrada bytea,
  parametros jsonb NOT NULL DEFAULT '{}',
  dias_fechamento int NOT NULL DEFAULT 5,
  PRIMARY KEY (tenant_id, tipo)
);

CREATE TABLE core.alerta (
  tenant_id uuid NOT NULL REFERENCES core.tenant,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  tipo text NOT NULL,
  referencia text NOT NULL,
  detalhe jsonb NOT NULL DEFAULT '{}',
  criado_em timestamptz NOT NULL DEFAULT now(),
  reconhecido_em timestamptz,
  PRIMARY KEY (tenant_id, id)
);

-- raw ----------------------------------------------------------------------------------------
CREATE TABLE raw.extracao (
  tenant_id uuid NOT NULL REFERENCES core.tenant,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  fonte text NOT NULL,
  competencia date NOT NULL,
  versao int NOT NULL,
  origem text NOT NULL CHECK (origem IN ('conector', 'planilha')),
  hash_conteudo text NOT NULL,
  conteudo jsonb NOT NULL,
  substituida boolean NOT NULL DEFAULT false,
  extraido_em timestamptz NOT NULL,
  PRIMARY KEY (tenant_id, id),
  UNIQUE (tenant_id, fonte, competencia, versao),
  UNIQUE (tenant_id, fonte, competencia, hash_conteudo)
);

CREATE TABLE raw.quarentena (
  tenant_id uuid NOT NULL,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  extracao_id uuid NOT NULL,
  linha jsonb NOT NULL,
  motivo text NOT NULL,
  PRIMARY KEY (tenant_id, id),
  FOREIGN KEY (tenant_id, extracao_id) REFERENCES raw.extracao
);

-- job ----------------------------------------------------------------------------------------
CREATE TABLE job.job (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES core.tenant,
  tipo text NOT NULL,
  chave_idempotencia text NOT NULL,
  parametros jsonb NOT NULL DEFAULT '{}',
  estado text NOT NULL DEFAULT 'pendente'
    CHECK (estado IN ('pendente', 'em_execucao', 'concluido', 'falhou')),
  tentativas int NOT NULL DEFAULT 0,
  max_tentativas int NOT NULL DEFAULT 5,
  proxima_tentativa_em timestamptz NOT NULL,
  lease_ate timestamptz,
  heartbeat_em timestamptz,
  lease_dono text,
  erro text,
  concluido_em timestamptz,
  UNIQUE (tenant_id, chave_idempotencia)
);
CREATE INDEX job_pendentes ON job.job (proxima_tentativa_em) WHERE estado = 'pendente';
CREATE INDEX job_em_execucao ON job.job (lease_ate) WHERE estado = 'em_execucao';

CREATE FUNCTION job.avisar_job_novo() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  PERFORM pg_notify('job_novo', NEW.id::text);
  RETURN NEW;
END $$;
CREATE TRIGGER job_novo AFTER INSERT ON job.job
  FOR EACH ROW EXECUTE FUNCTION job.avisar_job_novo();

-- audit --------------------------------------------------------------------------------------
CREATE TABLE audit.evento (
  tenant_id uuid NOT NULL REFERENCES core.tenant,
  seq bigint NOT NULL,
  usuario_id uuid,
  request_id text,
  tipo text NOT NULL,
  conteudo jsonb NOT NULL,
  criado_em timestamptz NOT NULL,
  hash_anterior bytea NOT NULL,
  hash bytea NOT NULL,
  PRIMARY KEY (tenant_id, seq)
);

-- auth (fora da RLS por inquilino) -----------------------------------------------------------
CREATE TABLE auth.usuario (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email text NOT NULL,
  senha_argon2id text NOT NULL,
  totp_cifrado bytea,
  totp_ultimo_passo bigint,
  mfa_ativo boolean NOT NULL DEFAULT false,
  ativo boolean NOT NULL DEFAULT true,
  falhas_login int NOT NULL DEFAULT 0,
  bloqueado_ate timestamptz
);
CREATE UNIQUE INDEX usuario_email ON auth.usuario (lower(email));

CREATE TABLE auth.usuario_papel (
  usuario_id uuid NOT NULL REFERENCES auth.usuario ON DELETE CASCADE,
  tenant_id uuid NOT NULL REFERENCES core.tenant,
  papel text NOT NULL CHECK (papel IN ('analisar', 'aprovar', 'administrar')),
  PRIMARY KEY (usuario_id, tenant_id, papel)
);

CREATE TABLE auth.sessao_familia (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  usuario_id uuid NOT NULL REFERENCES auth.usuario ON DELETE CASCADE,
  tenant_id uuid NOT NULL REFERENCES core.tenant,
  criada_em timestamptz NOT NULL,
  ultima_atividade timestamptz NOT NULL,
  expira_em timestamptz NOT NULL,
  mfa_verificado boolean NOT NULL DEFAULT false,
  revogada_em timestamptz,
  motivo_revogacao text
);

CREATE TABLE auth.refresh_token (
  hash_sha256 bytea PRIMARY KEY,
  familia_id uuid NOT NULL REFERENCES auth.sessao_familia ON DELETE CASCADE,
  emitido_em timestamptz NOT NULL,
  expira_em timestamptz NOT NULL,
  usado_em timestamptz
);

CREATE TABLE auth.codigo_recuperacao (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  usuario_id uuid NOT NULL REFERENCES auth.usuario ON DELETE CASCADE,
  hash_argon2id text NOT NULL,
  usado_em timestamptz
);

CREATE TABLE auth.redefinicao_senha (
  hash_sha256 bytea PRIMARY KEY,
  usuario_id uuid NOT NULL REFERENCES auth.usuario ON DELETE CASCADE,
  expira_em timestamptz NOT NULL,
  usado_em timestamptz
);

-- Limite por IP: o endereço entra só como HMAC (dado pessoal).
CREATE TABLE auth.limite_ip (
  ip_hash bytea PRIMARY KEY,
  falhas int NOT NULL DEFAULT 0,
  bloqueado_ate timestamptz,
  atualizado_em timestamptz NOT NULL
);

-- RLS forçada --------------------------------------------------------------------------------
DO $$
DECLARE tabela text;
BEGIN
  FOREACH tabela IN ARRAY ARRAY[
    'core.empresa', 'core.contrato', 'core.vinculo', 'core.empresa_mes', 'core.honorario_mes',
    'core.politica_versao', 'core.preco_alvo', 'core.lote_exportacao', 'core.recomendacao',
    'core.divergencia_cobranca', 'core.cotacao', 'core.conector_config', 'core.alerta',
    'raw.extracao', 'raw.quarentena', 'job.job', 'audit.evento'
  ] LOOP
    EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY', tabela);
    EXECUTE format('ALTER TABLE %s FORCE ROW LEVEL SECURITY', tabela);
    EXECUTE format(
      'CREATE POLICY isolamento ON %s USING (tenant_id = core.tenant_atual()) '
      'WITH CHECK (tenant_id = core.tenant_atual())', tabela);
  END LOOP;
END $$;

ALTER TABLE core.tenant ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.tenant FORCE ROW LEVEL SECURITY;
CREATE POLICY isolamento ON core.tenant
  USING (id = core.tenant_atual()) WITH CHECK (id = core.tenant_atual());

-- Papel da fila: enxerga só o necessário para distribuir jobs entre inquilinos.
CREATE POLICY fila ON job.job TO dynaprice_fila USING (true) WITH CHECK (true);
CREATE POLICY fila ON core.tenant FOR SELECT TO dynaprice_fila USING (true);
CREATE POLICY fila ON core.alerta FOR INSERT TO dynaprice_fila WITH CHECK (true);

-- Privilégios --------------------------------------------------------------------------------
GRANT USAGE ON SCHEMA core, raw, job, audit, auth TO dynaprice_app;
GRANT USAGE ON SCHEMA core, job TO dynaprice_fila;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA core TO dynaprice_app;
REVOKE INSERT, UPDATE, DELETE ON core.indice_inflacao FROM dynaprice_app;
REVOKE UPDATE, DELETE ON core.tenant FROM dynaprice_app;
REVOKE DELETE ON core.politica_versao FROM dynaprice_app;
GRANT SELECT, INSERT, DELETE ON ALL TABLES IN SCHEMA raw TO dynaprice_app;
GRANT UPDATE (substituida) ON raw.extracao TO dynaprice_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON job.job TO dynaprice_app;
GRANT SELECT, INSERT ON audit.evento TO dynaprice_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA auth TO dynaprice_app;
GRANT SELECT, UPDATE ON job.job TO dynaprice_fila;
GRANT SELECT ON core.tenant TO dynaprice_fila;
GRANT INSERT ON core.alerta TO dynaprice_fila;

-- Funções da fila: SECURITY DEFINER com dono sem login e search_path fixo.
CREATE FUNCTION job.reservar_proximo(
  p_dono text, p_agora timestamptz, p_lease interval, p_max integer)
RETURNS SETOF job.job LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
  UPDATE job.job j
     SET estado = 'em_execucao', tentativas = j.tentativas + 1, lease_dono = p_dono,
         heartbeat_em = p_agora, lease_ate = p_agora + p_lease, max_tentativas = p_max
   WHERE j.id = (
     SELECT p.id FROM job.job p
      WHERE p.estado = 'pendente' AND p.proxima_tentativa_em <= p_agora
      ORDER BY p.proxima_tentativa_em
      FOR UPDATE SKIP LOCKED LIMIT 1)
  RETURNING j.*
$$;

CREATE FUNCTION job.recuperar_orfaos(p_agora timestamptz)
RETURNS integer LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE orfao job.job; total integer := 0;
BEGIN
  FOR orfao IN
    SELECT * FROM job.job
     WHERE estado = 'em_execucao' AND lease_ate < p_agora
     FOR UPDATE SKIP LOCKED
  LOOP
    total := total + 1;
    IF orfao.tentativas >= orfao.max_tentativas THEN
      UPDATE job.job SET estado = 'falhou', erro = 'lease vencido', lease_dono = NULL,
                         lease_ate = NULL
       WHERE id = orfao.id;
      INSERT INTO core.alerta (tenant_id, tipo, referencia)
      VALUES (orfao.tenant_id, 'job_falhou', orfao.id::text);
    ELSE
      UPDATE job.job SET estado = 'pendente', proxima_tentativa_em = p_agora, lease_dono = NULL,
                         lease_ate = NULL, erro = 'lease vencido'
       WHERE id = orfao.id;
    END IF;
  END LOOP;
  RETURN total;
END $$;

CREATE FUNCTION job.listar_tenants_ativos()
RETURNS SETOF uuid LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
  SELECT id FROM core.tenant WHERE estado = 'ativo'
$$;

GRANT CREATE ON SCHEMA job TO dynaprice_fila;
ALTER FUNCTION job.reservar_proximo(text, timestamptz, interval, integer) OWNER TO dynaprice_fila;
ALTER FUNCTION job.recuperar_orfaos(timestamptz) OWNER TO dynaprice_fila;
ALTER FUNCTION job.listar_tenants_ativos() OWNER TO dynaprice_fila;
REVOKE CREATE ON SCHEMA job FROM dynaprice_fila;
REVOKE ALL ON FUNCTION job.reservar_proximo(text, timestamptz, interval, integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION job.recuperar_orfaos(timestamptz) FROM PUBLIC;
REVOKE ALL ON FUNCTION job.listar_tenants_ativos() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION job.reservar_proximo(text, timestamptz, interval, integer) TO dynaprice_app;
GRANT EXECUTE ON FUNCTION job.recuperar_orfaos(timestamptz) TO dynaprice_app;
GRANT EXECUTE ON FUNCTION job.listar_tenants_ativos() TO dynaprice_app;
