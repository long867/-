BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001_initial

CREATE EXTENSION IF NOT EXISTS vector;

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE events (
    title_zh TEXT NOT NULL, 
    summary_zh TEXT, 
    first_seen_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    last_updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    article_count INTEGER DEFAULT '0' NOT NULL, 
    minerals TEXT[] DEFAULT '{}'::text[] NOT NULL, 
    regions TEXT[] DEFAULT '{}'::text[] NOT NULL, 
    importance_score FLOAT DEFAULT '0' NOT NULL, 
    embedding VECTOR(1024), 
    id UUID NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_events_count CHECK (article_count >= 0), 
    CONSTRAINT ck_events_importance CHECK (importance_score BETWEEN 0 AND 100)
);

CREATE INDEX ix_events_embedding ON events USING hnsw (embedding vector_cosine_ops);

CREATE INDEX ix_events_minerals ON events USING gin (minerals);

CREATE INDEX ix_events_regions ON events USING gin (regions);

CREATE INDEX ix_events_updated ON events (last_updated_at);

CREATE TABLE policies (
    title TEXT NOT NULL, 
    title_zh TEXT, 
    country VARCHAR(100) NOT NULL, 
    region VARCHAR(100), 
    minerals TEXT[] DEFAULT '{}'::text[] NOT NULL, 
    effective_date DATE, 
    url TEXT NOT NULL, 
    summary_zh TEXT, 
    impact_score FLOAT DEFAULT '0' NOT NULL, 
    id UUID NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_policies_impact CHECK (impact_score BETWEEN 0 AND 100), 
    UNIQUE (url)
);

CREATE INDEX ix_policies_country ON policies (country);

CREATE TABLE price_records (
    mineral VARCHAR(100) NOT NULL, 
    price NUMERIC(20, 6) NOT NULL, 
    unit VARCHAR(50) NOT NULL, 
    currency VARCHAR(10) NOT NULL, 
    date DATE NOT NULL, 
    source TEXT NOT NULL, 
    change_pct NUMERIC(12, 6), 
    id UUID NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_prices_positive CHECK (price >= 0), 
    CONSTRAINT uq_price_observation UNIQUE (mineral, unit, currency, date, source)
);

CREATE INDEX ix_prices_mineral_date ON price_records (mineral, date);

CREATE TABLE reports (
    kind VARCHAR(20) NOT NULL, 
    period_start DATE NOT NULL, 
    period_end DATE NOT NULL, 
    title TEXT NOT NULL, 
    content TEXT NOT NULL, 
    sources_json JSONB NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_report_period UNIQUE (kind, period_start, period_end)
);

CREATE TABLE sources (
    name VARCHAR(200) NOT NULL, 
    url TEXT NOT NULL, 
    type VARCHAR(20) NOT NULL, 
    category VARCHAR(20) NOT NULL, 
    region VARCHAR(100), 
    language VARCHAR(20) DEFAULT 'en' NOT NULL, 
    authority_score INTEGER DEFAULT '5' NOT NULL, 
    fetch_interval INTEGER DEFAULT '900' NOT NULL, 
    active BOOLEAN DEFAULT 'true' NOT NULL, 
    last_fetched_at TIMESTAMP WITH TIME ZONE, 
    etag TEXT, 
    last_modified TEXT, 
    config_json JSONB DEFAULT '{}'::jsonb NOT NULL, 
    id UUID NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_sources_category CHECK (category IN ('news','price','policy','report','company')), 
    CONSTRAINT ck_sources_type CHECK (type IN ('rss','web','api')), 
    CONSTRAINT ck_sources_authority CHECK (authority_score BETWEEN 1 AND 10), 
    CONSTRAINT ck_sources_interval CHECK (fetch_interval >= 60), 
    UNIQUE (url)
);

CREATE TABLE users (
    email VARCHAR(320) NOT NULL, 
    password_hash TEXT NOT NULL, 
    is_admin BOOLEAN DEFAULT 'false' NOT NULL, 
    active BOOLEAN DEFAULT 'true' NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (email)
);

CREATE TABLE articles (
    source_id UUID NOT NULL, 
    title TEXT NOT NULL, 
    title_zh TEXT, 
    summary TEXT, 
    summary_zh TEXT, 
    content TEXT NOT NULL, 
    content_zh TEXT, 
    url TEXT NOT NULL, 
    published_at TIMESTAMP WITH TIME ZONE, 
    fetched_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    category VARCHAR(20) NOT NULL, 
    language VARCHAR(20) NOT NULL, 
    is_translated BOOLEAN DEFAULT 'false' NOT NULL, 
    quality_score FLOAT DEFAULT '0' NOT NULL, 
    relevance_score FLOAT DEFAULT '0' NOT NULL, 
    event_id UUID, 
    embedding VECTOR(1024), 
    minerals TEXT[] DEFAULT '{}'::text[] NOT NULL, 
    regions TEXT[] DEFAULT '{}'::text[] NOT NULL, 
    companies TEXT[] DEFAULT '{}'::text[] NOT NULL, 
    projects TEXT[] DEFAULT '{}'::text[] NOT NULL, 
    tags TEXT[] DEFAULT '{}'::text[] NOT NULL, 
    status VARCHAR(20) DEFAULT 'pending' NOT NULL, 
    processing_error TEXT, 
    id UUID NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_articles_status CHECK (status IN ('pending','processed','published')), 
    CONSTRAINT ck_articles_quality CHECK (quality_score BETWEEN 0 AND 100), 
    CONSTRAINT ck_articles_relevance CHECK (relevance_score BETWEEN 0 AND 100), 
    FOREIGN KEY(event_id) REFERENCES events (id) ON DELETE SET NULL, 
    FOREIGN KEY(source_id) REFERENCES sources (id) ON DELETE RESTRICT, 
    UNIQUE (url)
);

CREATE INDEX ix_articles_embedding ON articles USING hnsw (embedding vector_cosine_ops);

CREATE INDEX ix_articles_event ON articles (event_id);

CREATE INDEX ix_articles_minerals ON articles USING gin (minerals);

CREATE INDEX ix_articles_regions ON articles USING gin (regions);

CREATE INDEX ix_articles_source ON articles (source_id);

CREATE INDEX ix_articles_status_published ON articles (status, published_at);

CREATE INDEX ix_articles_tags ON articles USING gin (tags);

CREATE TABLE chat_sessions (
    user_id UUID NOT NULL, 
    title VARCHAR(200) NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_chat_sessions_user_id ON chat_sessions (user_id);

CREATE TABLE pipeline_runs (
    source_id UUID, 
    task_id VARCHAR(100), 
    status VARCHAR(20) NOT NULL, 
    fetched_count INTEGER NOT NULL, 
    error TEXT, 
    finished_at TIMESTAMP WITH TIME ZONE, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(source_id) REFERENCES sources (id) ON DELETE SET NULL
);

CREATE INDEX ix_pipeline_runs_task_id ON pipeline_runs (task_id);

CREATE TABLE subscriptions (
    user_id UUID NOT NULL, 
    subscribed_minerals TEXT[] DEFAULT '{}'::text[] NOT NULL, 
    subscribed_regions TEXT[] DEFAULT '{}'::text[] NOT NULL, 
    frequency VARCHAR(20) DEFAULT 'daily' NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_subscriptions_frequency CHECK (frequency IN ('daily','weekly')), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    UNIQUE (user_id)
);

CREATE TABLE article_chunks (
    article_id UUID NOT NULL, 
    chunk_index INTEGER NOT NULL, 
    text TEXT NOT NULL, 
    search_text TEXT NOT NULL, 
    start_char INTEGER NOT NULL, 
    end_char INTEGER NOT NULL, 
    embedding VECTOR(1024), 
    id UUID NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_chunks_span CHECK (start_char >= 0 AND end_char > start_char), 
    FOREIGN KEY(article_id) REFERENCES articles (id) ON DELETE CASCADE, 
    CONSTRAINT uq_chunks_article_index UNIQUE (article_id, chunk_index)
);

CREATE INDEX ix_article_chunks_article_id ON article_chunks (article_id);

CREATE INDEX ix_chunks_embedding ON article_chunks USING hnsw (embedding vector_cosine_ops);

CREATE INDEX ix_chunks_search ON article_chunks USING gin (search_text gin_trgm_ops);

CREATE TABLE chat_messages (
    session_id UUID NOT NULL, 
    question TEXT NOT NULL, 
    answer TEXT NOT NULL, 
    sources_json JSONB DEFAULT '[]'::jsonb NOT NULL, 
    mode VARCHAR(30) DEFAULT 'extractive' NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(session_id) REFERENCES chat_sessions (id) ON DELETE CASCADE
);

CREATE INDEX ix_chat_messages_session_id ON chat_messages (session_id);

CREATE INDEX ix_chunks_fts ON article_chunks USING gin (to_tsvector('simple', search_text));

INSERT INTO alembic_version (version_num) VALUES ('0001_initial') RETURNING alembic_version.version_num;

-- Running upgrade 0001_initial -> 0002_collection

ALTER TABLE sources ADD COLUMN fetch_state JSONB DEFAULT '{}'::jsonb NOT NULL;

ALTER TABLE sources ADD COLUMN failure_count INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE sources ADD COLUMN last_attempted_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE sources ADD COLUMN next_retry_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE sources ADD COLUMN last_error TEXT;

ALTER TABLE articles ADD COLUMN raw_json JSONB DEFAULT '{}'::jsonb NOT NULL;

ALTER TABLE articles ADD COLUMN content_fingerprint VARCHAR(16);

ALTER TABLE articles ADD COLUMN title_normalized TEXT;

ALTER TABLE articles ADD COLUMN policy_names TEXT[] DEFAULT '{}'::text[] NOT NULL;

CREATE INDEX ix_articles_fingerprint ON articles (content_fingerprint);

CREATE INDEX ix_articles_title_normalized ON articles USING gin (title_normalized gin_trgm_ops);

ALTER TABLE pipeline_runs ADD COLUMN new_count INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE pipeline_runs ADD COLUMN duplicate_count INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE pipeline_runs ADD COLUMN error_count INTEGER DEFAULT '0' NOT NULL;

UPDATE alembic_version SET version_num='0002_collection' WHERE alembic_version.version_num = '0001_initial';

-- Running upgrade 0002_collection -> 0003_vector_index

ALTER TABLE articles ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL;

ALTER TABLE articles ADD COLUMN indexed_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE articles ADD COLUMN embedding_model VARCHAR(200);

ALTER TABLE articles ADD COLUMN embedding_hash VARCHAR(64);

CREATE TABLE vector_sync_jobs (
    article_id UUID NOT NULL, 
    revision VARCHAR(64) NOT NULL, 
    attempts INTEGER DEFAULT '0' NOT NULL, 
    next_retry_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    last_error TEXT, 
    PRIMARY KEY (article_id), 
    FOREIGN KEY(article_id) REFERENCES articles (id) ON DELETE CASCADE
);

CREATE INDEX ix_vector_sync_jobs_next_retry_at ON vector_sync_jobs (next_retry_at);

UPDATE alembic_version SET version_num='0003_vector_index' WHERE alembic_version.version_num = '0002_collection';

-- Running upgrade 0003_vector_index -> 0004_business_api

CREATE INDEX ix_articles_published_at ON articles (published_at);

CREATE INDEX ix_articles_quality_score ON articles (quality_score);

CREATE INDEX ix_articles_companies ON articles USING gin (companies);

CREATE INDEX ix_events_importance ON events (importance_score);

ALTER TABLE price_records ADD COLUMN product VARCHAR(200);

ALTER TABLE price_records ADD COLUMN price_type VARCHAR(20) DEFAULT 'spot' NOT NULL;

ALTER TABLE price_records ADD COLUMN source_url TEXT;

ALTER TABLE subscriptions ADD COLUMN email_enabled BOOLEAN DEFAULT 'false' NOT NULL;

ALTER TABLE reports ADD COLUMN evidence_hash VARCHAR(64);

ALTER TABLE reports ADD COLUMN mode VARCHAR(20) DEFAULT 'extractive' NOT NULL;

CREATE TABLE api_keys (
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    user_id UUID NOT NULL, 
    name VARCHAR(100) NOT NULL, 
    prefix VARCHAR(20) NOT NULL, 
    token_hash VARCHAR(64) NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    revoked_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    UNIQUE (token_hash)
);

CREATE INDEX ix_api_keys_user_id ON api_keys (user_id);

CREATE TABLE notification_deliveries (
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    subscription_id UUID NOT NULL, 
    report_id UUID NOT NULL, 
    sent_at TIMESTAMP WITH TIME ZONE, 
    attempts INTEGER DEFAULT '0' NOT NULL, 
    last_error VARCHAR(100), 
    PRIMARY KEY (id), 
    CONSTRAINT uq_notification_report UNIQUE (subscription_id, report_id), 
    FOREIGN KEY(subscription_id) REFERENCES subscriptions (id) ON DELETE CASCADE, 
    FOREIGN KEY(report_id) REFERENCES reports (id) ON DELETE CASCADE
);

UPDATE alembic_version SET version_num='0004_business_api' WHERE alembic_version.version_num = '0003_vector_index';

COMMIT;

