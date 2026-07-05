CREATE TABLE IF NOT EXISTS meals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    restaurant_name TEXT NOT NULL,
    location TEXT DEFAULT '',
    cuisine TEXT DEFAULT '',
    avg_price REAL,
    rating REAL,
    dishes TEXT DEFAULT '',
    scenario TEXT DEFAULT '',
    companions TEXT DEFAULT '',
    comment TEXT DEFAULT '',
    pros TEXT DEFAULT '',
    cons TEXT DEFAULT '',
    revisit_willingness TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_meals_cuisine ON meals(cuisine);
CREATE INDEX IF NOT EXISTS idx_meals_rating ON meals(rating);
