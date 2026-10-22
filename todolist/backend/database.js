const Database = require('better-sqlite3');
const path = require('path');

const dbPath = process.env.DB_PATH || path.join(__dirname, 'data', 'todo.db');
const db = new Database(dbPath);

// Enable WAL mode for better performance
db.pragma('journal_mode = WAL');

// Create tables
db.exec(`
  CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_name TEXT NOT NULL CHECK(group_name IN ('samuel', 'nadia', 'formicouple')),
    title TEXT NOT NULL,
    date TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'medium' CHECK(priority IN ('low', 'medium', 'high')),
    completed INTEGER NOT NULL DEFAULT 0,
    recurrence TEXT NOT NULL DEFAULT 'none' CHECK(recurrence IN ('none', 'daily', 'weekly', 'monthly')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
  )
`);

module.exports = db;
