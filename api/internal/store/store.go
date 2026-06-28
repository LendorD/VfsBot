// Package store — доступ к данным (SQLite): пользователи и заявки.
package store

import (
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"

	_ "modernc.org/sqlite" // чистый Go-драйвер SQLite (без cgo)
)

var ErrNotFound = errors.New("not found")

type Store struct{ db *sql.DB }

// New открывает файловую БД SQLite (создаёт каталог при необходимости).
func New(path string) (*Store, error) {
	if dir := filepath.Dir(path); dir != "" && dir != "." {
		_ = os.MkdirAll(dir, 0o755)
	}
	// WAL + busy_timeout — чтобы API и бот могли писать в один файл без блокировок.
	dsn := "file:" + path + "?_pragma=busy_timeout(5000)&_pragma=journal_mode(WAL)"
	db, err := sql.Open("sqlite", dsn)
	if err != nil {
		return nil, err
	}
	if err := db.Ping(); err != nil {
		return nil, err
	}
	return &Store{db: db}, nil
}

func (s *Store) Close() error { return s.db.Close() }

// Init создаёт таблицы, если их ещё нет.
func (s *Store) Init() error {
	_, err := s.db.Exec(`
CREATE TABLE IF NOT EXISTS users (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  email         TEXT UNIQUE NOT NULL,
  username      TEXT UNIQUE,
  password_hash TEXT NOT NULL,
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS tasks (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id     INTEGER NOT NULL,
  site        TEXT NOT NULL DEFAULT 'vfs_fr',
  center      TEXT NOT NULL DEFAULT '',
  category    TEXT NOT NULL DEFAULT '',
  subcategory TEXT NOT NULL DEFAULT '',
  date_start  TEXT NOT NULL DEFAULT '',
  date_end    TEXT NOT NULL DEFAULT '',
  applicants  TEXT NOT NULL DEFAULT '[]',
  auto_pay    INTEGER NOT NULL DEFAULT 0,
  status      TEXT NOT NULL DEFAULT 'created',
  job_id      TEXT NOT NULL DEFAULT '',
  created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);`)
	if err != nil {
		return err
	}
	// telegram_id: на уже существующих БД добавляем колонку (ошибку «уже есть»
	// игнорируем — ALTER ... IF NOT EXISTS в SQLite нет).
	_, _ = s.db.Exec(`ALTER TABLE users ADD COLUMN telegram_id INTEGER`)
	_, _ = s.db.Exec(
		`CREATE UNIQUE INDEX IF NOT EXISTS users_tg_key ON users (telegram_id) WHERE telegram_id IS NOT NULL`)
	return nil
}

// ----- Модели -----

type User struct {
	ID           int64  `json:"id"`
	Email        string `json:"email"`
	Username     string `json:"username"`
	PasswordHash string `json:"-"`
	CreatedAt    string `json:"-"`
}

type Applicant struct {
	FirstName      string `json:"first_name"`
	Surname        string `json:"surname"`
	Gender         string `json:"gender"`
	BirthDate      string `json:"birth_date"`
	Nationality    string `json:"nationality"`
	PassportNumber string `json:"passport_number"`
	PassportExpiry string `json:"passport_expiry"`
	PhoneCode      string `json:"phone_code"`
	Phone          string `json:"phone"`
	Email          string `json:"email"`
}

type Task struct {
	ID          int64       `json:"id"`
	UserID      int64       `json:"-"`
	Site        string      `json:"site"`
	Center      string      `json:"center"`
	Category    string      `json:"category"`
	Subcategory string      `json:"subcategory"`
	DateStart   string      `json:"date_start"`
	DateEnd     string      `json:"date_end"`
	Applicants  []Applicant `json:"applicants"`
	AutoPay     bool        `json:"auto_pay"`
	Status      string      `json:"status"`
	JobID       string      `json:"-"`
	CreatedAt   string      `json:"-"`
}

// MarshalJSON добавляет applicants_count для фронта.
func (t Task) MarshalJSON() ([]byte, error) {
	type alias Task
	return json.Marshal(struct {
		alias
		ApplicantsCount int `json:"applicants_count"`
	}{alias(t), len(t.Applicants)})
}

// ----- помощники -----

func nullIfEmpty(s string) any {
	if s == "" {
		return nil
	}
	return s
}

func boolToInt(b bool) int {
	if b {
		return 1
	}
	return 0
}

// ----- Пользователи -----

func (s *Store) CreateUser(email, username, hash string) (User, error) {
	res, err := s.db.Exec(
		`INSERT INTO users (email, username, password_hash) VALUES (?, ?, ?)`,
		email, nullIfEmpty(username), hash,
	)
	if err != nil {
		return User{}, err
	}
	id, _ := res.LastInsertId()
	return User{ID: id, Email: email, Username: username, PasswordHash: hash}, nil
}

func (s *Store) UserByEmail(email string) (User, error) {
	var u User
	err := s.db.QueryRow(
		`SELECT id, email, COALESCE(username, ''), password_hash FROM users WHERE email = ?`, email,
	).Scan(&u.ID, &u.Email, &u.Username, &u.PasswordHash)
	if errors.Is(err, sql.ErrNoRows) {
		return u, ErrNotFound
	}
	return u, err
}

// UserByLogin ищет пользователя по email ИЛИ по логину (username).
func (s *Store) UserByLogin(login string) (User, error) {
	var u User
	err := s.db.QueryRow(
		`SELECT id, email, COALESCE(username, ''), password_hash FROM users WHERE email = ? OR username = ?`,
		login, login,
	).Scan(&u.ID, &u.Email, &u.Username, &u.PasswordHash)
	if errors.Is(err, sql.ErrNoRows) {
		return u, ErrNotFound
	}
	return u, err
}

func (s *Store) UserByID(id int64) (User, error) {
	var u User
	err := s.db.QueryRow(
		`SELECT id, email, COALESCE(username, ''), password_hash FROM users WHERE id = ?`, id,
	).Scan(&u.ID, &u.Email, &u.Username, &u.PasswordHash)
	if errors.Is(err, sql.ErrNoRows) {
		return u, ErrNotFound
	}
	return u, err
}

// UserByTelegram ищет пользователя по Telegram ID.
func (s *Store) UserByTelegram(tgID int64) (User, error) {
	var u User
	err := s.db.QueryRow(
		`SELECT id, email, COALESCE(username, ''), password_hash FROM users WHERE telegram_id = ?`, tgID,
	).Scan(&u.ID, &u.Email, &u.Username, &u.PasswordHash)
	if errors.Is(err, sql.ErrNoRows) {
		return u, ErrNotFound
	}
	return u, err
}

// CreateTelegramUser создаёт пользователя для Telegram (без пароля).
func (s *Store) CreateTelegramUser(tgID int64, username string) (User, error) {
	email := fmt.Sprintf("tg%d@telegram.local", tgID)
	res, err := s.db.Exec(
		`INSERT INTO users (email, username, password_hash, telegram_id) VALUES (?, ?, '', ?)`,
		email, nullIfEmpty(username), tgID,
	)
	if err != nil {
		return User{}, err
	}
	id, _ := res.LastInsertId()
	return User{ID: id, Email: email, Username: username}, nil
}

// ----- Заявки -----

const taskCols = `id, user_id, site, center, category, subcategory, date_start, date_end, applicants, auto_pay, status, job_id, created_at`

func (s *Store) CreateTask(t Task) (Task, error) {
	apps, _ := json.Marshal(t.Applicants)
	res, err := s.db.Exec(
		`INSERT INTO tasks (user_id, site, center, category, subcategory, date_start, date_end, applicants, auto_pay, status)
		 VALUES (?,?,?,?,?,?,?,?,?, 'created')`,
		t.UserID, t.Site, t.Center, t.Category, t.Subcategory, t.DateStart, t.DateEnd, string(apps), boolToInt(t.AutoPay),
	)
	if err != nil {
		return t, err
	}
	id, _ := res.LastInsertId()
	t.ID, t.Status = id, "created"
	return t, nil
}

func scanTask(rows *sql.Rows) (Task, error) {
	var t Task
	var apps string
	var ap int
	err := rows.Scan(&t.ID, &t.UserID, &t.Site, &t.Center, &t.Category, &t.Subcategory,
		&t.DateStart, &t.DateEnd, &apps, &ap, &t.Status, &t.JobID, &t.CreatedAt)
	if err != nil {
		return t, err
	}
	t.AutoPay = ap != 0
	_ = json.Unmarshal([]byte(apps), &t.Applicants)
	return t, nil
}

func (s *Store) TasksByUser(userID int64) ([]Task, error) {
	rows, err := s.db.Query(`SELECT `+taskCols+` FROM tasks WHERE user_id = ? ORDER BY created_at DESC, id DESC`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []Task
	for rows.Next() {
		t, err := scanTask(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, t)
	}
	return out, rows.Err()
}

func (s *Store) TaskByID(id int64) (Task, error) {
	rows, err := s.db.Query(`SELECT `+taskCols+` FROM tasks WHERE id = ?`, id)
	if err != nil {
		return Task{}, err
	}
	defer rows.Close()
	if !rows.Next() {
		return Task{}, ErrNotFound
	}
	return scanTask(rows)
}

func (s *Store) TasksByStatus(status string) ([]Task, error) {
	rows, err := s.db.Query(`SELECT `+taskCols+` FROM tasks WHERE status = ?`, status)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []Task
	for rows.Next() {
		t, err := scanTask(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, t)
	}
	return out, rows.Err()
}

func (s *Store) DeleteTask(id, userID int64) error {
	_, err := s.db.Exec(`DELETE FROM tasks WHERE id = ? AND user_id = ?`, id, userID)
	return err
}

func (s *Store) UpdateTaskStatus(id int64, status, jobID string) error {
	_, err := s.db.Exec(`UPDATE tasks SET status = ?, job_id = ? WHERE id = ?`, status, jobID, id)
	return err
}
