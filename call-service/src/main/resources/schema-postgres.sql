-- PostgreSQL schema for synced call sessions
-- Run this against your PostgreSQL database to create the target table

CREATE TABLE IF NOT EXISTS call_sessions (
    id VARCHAR(255) PRIMARY KEY,
    agent_id VARCHAR(255) NOT NULL,
    agent_name VARCHAR(255) NOT NULL,
    call_started TIMESTAMP WITH TIME ZONE,
    call_ended TIMESTAMP WITH TIME ZONE,
    duration_seconds BIGINT,
    hangup_reason VARCHAR(50),
    agent_rating INTEGER,
    status VARCHAR(20) NOT NULL
);

-- Index for querying by agent
CREATE INDEX IF NOT EXISTS idx_call_sessions_agent_id ON call_sessions(agent_id);

-- Index for querying by time range
CREATE INDEX IF NOT EXISTS idx_call_sessions_call_started ON call_sessions(call_started DESC);
