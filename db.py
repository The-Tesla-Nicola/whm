import sqlite3
conn = sqlite3.connect('warehouse.db')
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS anchors (
    id TEXT PRIMARY KEY,
    x REAL NOT NULL,
    y REAL NOT NULL
)''')
cursor.execute('''
CREATE TABLE IF NOT EXISTS tags (
    id TEXT PRIMARY KEY,
    last_x REAL DEFAULT 25.0,
    last_y REAL DEFAULT 25.0,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')
cursor.execute('''
CREATE TABLE IF NOT EXISTS destinations (
    name TEXT PRIMARY KEY,
    x REAL NOT NULL,
    y REAL NOT NULL
)''')
anchors_to_add = [
    ('ANCHOR_1', 0.0, 0.0),
    ('ANCHOR_2', 50.0, 0.0),
    ('ANCHOR_3', 50.0, 50.0),
    ('ANCHOR_4', 0.0, 50.0)
]
cursor.executemany("INSERT OR IGNORE INTO anchors (id, x, y) VALUES (?, ?, ?)", anchors_to_add)
dests_to_add = [
    ('Loading Dock', 5.0, 5.0),
    ('Rack A-01', 15.0, 25.0),
    ('Office', 45.0, 45.0)
]
cursor.executemany("INSERT OR IGNORE INTO destinations (name, x, y) VALUES (?, ?, ?)", dests_to_add)
conn.commit()
conn.close()
print("'warehouse.db' created")