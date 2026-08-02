PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS node_activity (
    community_id INTEGER NOT NULL,
    node_number INTEGER NOT NULL,
    first_seen INTEGER NOT NULL,
    last_seen INTEGER NOT NULL,
    packets_received INTEGER NOT NULL DEFAULT 0,
    last_root TEXT,
    last_channel TEXT,
    PRIMARY KEY (community_id, node_number),
    FOREIGN KEY (community_id)
        REFERENCES communities(id)
        ON DELETE CASCADE,
    FOREIGN KEY (node_number)
        REFERENCES nodes(node_number)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS room_activity (
    community_id INTEGER NOT NULL,
    mqtt_root TEXT NOT NULL,
    channel_name TEXT NOT NULL,
    first_seen INTEGER NOT NULL,
    last_seen INTEGER NOT NULL,
    packets_received INTEGER NOT NULL DEFAULT 0,
    packets_routed INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (
        community_id,
        mqtt_root,
        channel_name
    ),
    FOREIGN KEY (community_id)
        REFERENCES communities(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS routing_statistics (
    community_id INTEGER PRIMARY KEY,
    packets_accepted INTEGER NOT NULL DEFAULT 0,
    packets_routed INTEGER NOT NULL DEFAULT 0,
    duplicates_blocked INTEGER NOT NULL DEFAULT 0,
    updated_at INTEGER NOT NULL,
    FOREIGN KEY (community_id)
        REFERENCES communities(id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_node_activity_last_seen
    ON node_activity(community_id, last_seen);

CREATE INDEX IF NOT EXISTS idx_room_activity_last_seen
    ON room_activity(community_id, last_seen);
