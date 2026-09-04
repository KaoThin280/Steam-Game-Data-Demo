-- Agent Harness migration for Supabase (safe to run repeatedly).
-- Run manually in Supabase SQL Editor. It only adds harness tables/indexes.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.agent_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT NOT NULL REFERENCES public.app_users(id) ON DELETE CASCADE,
    title TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'archived')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.agent_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES public.agent_sessions(id) ON DELETE CASCADE,
    input_text TEXT NOT NULL,
    output_text TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
    current_step INTEGER NOT NULL DEFAULT 0 CHECK (current_step >= 0),
    max_steps INTEGER NOT NULL DEFAULT 8 CHECK (max_steps BETWEEN 1 AND 30),
    cancel_requested BOOLEAN NOT NULL DEFAULT false,
    error_code VARCHAR(50),
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.agent_events (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES public.agent_runs(id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL CHECK (sequence > 0),
    event_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_agent_event_sequence UNIQUE (run_id, sequence)
);

CREATE INDEX IF NOT EXISTS idx_agent_sessions_user_updated
    ON public.agent_sessions(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_runs_session_created
    ON public.agent_runs(session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_runs_status
    ON public.agent_runs(status) WHERE status IN ('queued', 'running');
CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_runs_one_active_per_session
    ON public.agent_runs(session_id) WHERE status IN ('queued', 'running');
CREATE INDEX IF NOT EXISTS idx_agent_events_run_sequence
    ON public.agent_events(run_id, sequence);

-- Backend connects as its own database role. Keep these tables out of direct
-- anonymous client access; all ownership checks happen in the authenticated API.
ALTER TABLE public.agent_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_events ENABLE ROW LEVEL SECURITY;

SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('agent_sessions', 'agent_runs', 'agent_events')
ORDER BY table_name;
