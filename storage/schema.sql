CREATE TABLE IF NOT EXISTS dietary_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    preference TEXT NOT NULL,
    sentiment TEXT NOT NULL DEFAULT 'like',
    weight INTEGER NOT NULL DEFAULT 1,
    source_note TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dietary_preferences_category ON dietary_preferences(category);
CREATE INDEX IF NOT EXISTS idx_dietary_preferences_sentiment ON dietary_preferences(sentiment);
CREATE INDEX IF NOT EXISTS idx_dietary_preferences_weight ON dietary_preferences(weight);
