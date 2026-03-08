-- WP5 Pilot Platform — Database Schema
-- Applied automatically by PostgreSQL on first container start.

CREATE TABLE IF NOT EXISTS experiments (
    experiment_id TEXT PRIMARY KEY,
    description   TEXT        DEFAULT '',
    config        JSONB       NOT NULL DEFAULT '{}',
    starts_at     TIMESTAMPTZ,
    ends_at       TIMESTAMPTZ,
    paused        BOOLEAN     DEFAULT FALSE,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tokens (
    token           TEXT PRIMARY KEY,
    treatment_group TEXT        NOT NULL,
    experiment_id   TEXT        NOT NULL REFERENCES experiments(experiment_id),
    used            BOOLEAN     DEFAULT FALSE,
    used_at         TIMESTAMPTZ,
    session_id      UUID,
    loaded_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id          UUID        PRIMARY KEY,
    token               TEXT        REFERENCES tokens(token),
    experiment_id       TEXT        NOT NULL REFERENCES experiments(experiment_id),
    treatment_group     TEXT        NOT NULL,
    user_name           TEXT        NOT NULL,
    -- pending | active | ended | crashed
    status              TEXT        NOT NULL DEFAULT 'pending',
    random_seed         INT,
    started_at          TIMESTAMPTZ,
    ended_at            TIMESTAMPTZ,
    end_reason          TEXT,
    simulation_config   JSONB,
    experimental_config JSONB,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS messages (
    message_id  UUID        PRIMARY KEY,
    session_id  UUID        NOT NULL REFERENCES sessions(session_id),
    experiment_id TEXT      NOT NULL,
    sender      TEXT        NOT NULL,
    content     TEXT        NOT NULL,
    sent_at     TIMESTAMPTZ NOT NULL,
    reply_to    UUID        REFERENCES messages(message_id),
    quoted_text TEXT,
    mentions    TEXT[]      DEFAULT '{}',
    liked_by    TEXT[]      DEFAULT '{}',
    reported    BOOLEAN     DEFAULT FALSE,
    metadata    JSONB       DEFAULT '{}',
    seq         BIGSERIAL
);

CREATE INDEX IF NOT EXISTS idx_messages_session_seq ON messages(session_id, seq);
CREATE INDEX IF NOT EXISTS idx_messages_experiment   ON messages(experiment_id);
CREATE INDEX IF NOT EXISTS idx_messages_sender       ON messages(session_id, sender);
CREATE INDEX IF NOT EXISTS idx_messages_reply_to     ON messages(reply_to) WHERE reply_to IS NOT NULL;

CREATE TABLE IF NOT EXISTS events (
    id            BIGSERIAL   PRIMARY KEY,
    session_id    UUID        NOT NULL REFERENCES sessions(session_id),
    experiment_id TEXT        NOT NULL,
    event_type    TEXT        NOT NULL,
    occurred_at   TIMESTAMPTZ DEFAULT NOW(),
    data          JSONB       NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_events_session     ON events(session_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_events_exp_type    ON events(experiment_id, event_type);

CREATE INDEX IF NOT EXISTS idx_sessions_experiment ON sessions(experiment_id, status);

-- Migrations: add schedule/pause columns if missing (idempotent).
DO $$ BEGIN
    ALTER TABLE experiments ADD COLUMN starts_at TIMESTAMPTZ;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE experiments ADD COLUMN ends_at TIMESTAMPTZ;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE experiments ADD COLUMN paused BOOLEAN DEFAULT FALSE;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS agent_blocks (
    session_id  UUID        NOT NULL REFERENCES sessions(session_id),
    agent_name  TEXT        NOT NULL,
    blocked_at  TIMESTAMPTZ NOT NULL,
    blocked_by  TEXT        NOT NULL,
    PRIMARY KEY (session_id, agent_name)
);
