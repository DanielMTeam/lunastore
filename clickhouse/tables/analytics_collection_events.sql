-- raw event-level analytics for collections
CREATE TABLE IF NOT EXISTS analytics_collection_events
(
    event_time DateTime64(3, 'UTC') DEFAULT now64(3),
    event_type LowCardinality(String),
    collection_id UInt64,
    owner_id Nullable(UInt64),
    user_id Nullable(UInt64),
    app_id Nullable(UInt64),
    is_system UInt8 DEFAULT 0,
    is_public UInt8 DEFAULT 1,
    ip String DEFAULT '',
    country LowCardinality(String) DEFAULT '',
    os_name LowCardinality(String) DEFAULT '',
    browser LowCardinality(String) DEFAULT '',
    referer String DEFAULT '',
    session_id String DEFAULT '',
    meta String DEFAULT '{}'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (collection_id, event_type, event_time)
TTL event_time + INTERVAL 24 MONTH
SETTINGS index_granularity = 8192;
