-- raw event-level analytics for applications
CREATE TABLE IF NOT EXISTS analytics_app_events
(
    event_time DateTime64(3, 'UTC') DEFAULT now64(3),
    event_type LowCardinality(String),
    app_id UInt64,
    distribution_id Nullable(UInt64),
    category_id Nullable(UInt64),
    user_id Nullable(UInt64),
    ip String DEFAULT '',
    country LowCardinality(String) DEFAULT '',
    os_name LowCardinality(String) DEFAULT '',
    os_version String DEFAULT '',
    browser LowCardinality(String) DEFAULT '',
    referer String DEFAULT '',
    session_id String DEFAULT '',
    meta String DEFAULT '{}'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (app_id, event_type, event_time)
TTL event_time + INTERVAL 24 MONTH
SETTINGS index_granularity = 8192;
