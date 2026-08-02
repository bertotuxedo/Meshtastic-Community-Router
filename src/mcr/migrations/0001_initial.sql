PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS communities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    community_key TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    channel_name TEXT NOT NULL,
    rendezvous_root TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS roots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    community_id INTEGER NOT NULL,
    mqtt_root TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    system_root INTEGER NOT NULL DEFAULT 0,
    registered_by INTEGER,
    created_at INTEGER NOT NULL,
    last_activity INTEGER,
    UNIQUE(community_id, mqtt_root),
    FOREIGN KEY(community_id)
        REFERENCES communities(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS nodes (
    node_number INTEGER PRIMARY KEY,
    first_seen INTEGER NOT NULL,
    last_seen INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS registrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    community_id INTEGER NOT NULL,
    node_number INTEGER NOT NULL,
    root_id INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    UNIQUE(community_id, node_number, root_id),
    FOREIGN KEY(community_id)
        REFERENCES communities(id),
    FOREIGN KEY(node_number)
        REFERENCES nodes(node_number),
    FOREIGN KEY(root_id)
        REFERENCES roots(id)
);

CREATE TABLE IF NOT EXISTS pending_confirmations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    community_id INTEGER NOT NULL,
    node_number INTEGER NOT NULL,
    requested_root TEXT NOT NULL,
    confirmation_code TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    UNIQUE(community_id, node_number),
    FOREIGN KEY(community_id)
        REFERENCES communities(id),
    FOREIGN KEY(node_number)
        REFERENCES nodes(node_number)
);

CREATE TABLE IF NOT EXISTS routed_packets (
    packet_key TEXT PRIMARY KEY,
    source_root TEXT NOT NULL,
    source_topic TEXT NOT NULL,
    first_seen INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_roots_enabled
    ON roots(community_id, enabled);

CREATE INDEX IF NOT EXISTS idx_routed_packets_first_seen
    ON routed_packets(first_seen);

CREATE INDEX IF NOT EXISTS idx_pending_expiration
    ON pending_confirmations(expires_at);
