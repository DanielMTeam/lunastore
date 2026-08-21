-- starter product-analytics events table (foundation only)
CREATE TABLE IF NOT EXISTS analytics_events
(
    event_time DateTime64(3, 'UTC') DEFAULT now64(3),
    event_name LowCardinality(String),
    user_id Nullable(UInt64),
    properties String DEFAULT '{}'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (event_name, event_time)
TTL event_time + INTERVAL 24 MONTH
SETTINGS index_granularity = 8192;
