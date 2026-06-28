// Package server — HTTP API для фронтенда и связка с воркером.
package server

import (
	"encoding/json"
	"log"
	"net/http"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"visabooking/internal/auth"
	"visabooking/internal/config"
	"visabooking/internal/store"
	"visabooking/internal/worker"
)

type Server struct {
	cfg      config.Config
	store    *store.Store
	sessions *auth.Sessions
	worker   *worker.Client
}

func New(cfg config.Config, st *store.Store) *Server {
	return &Server{
		cfg:      cfg,
		store:    st,
		sessions: auth.NewSessions(cfg.SessionSecret),
		worker:   worker.New(cfg.WorkerURL),
	}
}

// Routes собирает маршрутизатор (Go 1.22 ServeMux с шаблонами).
func (s *Server) Routes() http.Handler {
	mux := http.NewServeMux()

	mux.HandleFunc("GET /api/me", s.me)
	mux.HandleFunc("POST /api/register", s.register)
	mux.HandleFunc("POST /api/login", s.login)
	mux.HandleFunc("POST /api/logout", s.logout)
	mux.HandleFunc("GET /api/options", s.options)
	mux.HandleFunc("GET /api/tasks", s.listTasks)
	mux.HandleFunc("POST /api/tasks", s.createTask)
	mux.HandleFunc("GET /api/tasks/{id}", s.getTask)
	mux.HandleFunc("DELETE /api/tasks/{id}", s.deleteTask)
	mux.HandleFunc("POST /api/tasks/{id}/search", s.runSearch)

	mux.Handle("GET /static/", http.StripPrefix("/static/",
		http.FileServer(http.Dir(s.cfg.FrontendDir))))
	mux.HandleFunc("/", s.serveIndex)
	return mux
}

// ----- утилиты -----

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func errJSON(w http.ResponseWriter, status int, msg string) {
	writeJSON(w, status, map[string]string{"error": msg})
}

// requireUser возвращает пользователя по сессии или пишет 401.
func (s *Server) requireUser(w http.ResponseWriter, r *http.Request) (store.User, bool) {
	id, ok := s.sessions.UserID(r)
	if !ok {
		errJSON(w, http.StatusUnauthorized, "unauthorized")
		return store.User{}, false
	}
	u, err := s.store.UserByID(id)
	if err != nil {
		errJSON(w, http.StatusUnauthorized, "unauthorized")
		return store.User{}, false
	}
	return u, true
}

// ----- статика / SPA -----

func (s *Server) serveIndex(w http.ResponseWriter, r *http.Request) {
	if strings.HasPrefix(r.URL.Path, "/api/") {
		errJSON(w, http.StatusNotFound, "not found")
		return
	}
	http.ServeFile(w, r, filepath.Join(s.cfg.FrontendDir, "index.html"))
}

// ----- аутентификация -----

type credsReq struct {
	Email    string `json:"email"`
	Password string `json:"password"`
}

func (s *Server) me(w http.ResponseWriter, r *http.Request) {
	u, ok := s.requireUser(w, r)
	if !ok {
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"email": displayName(u)})
}

func (s *Server) register(w http.ResponseWriter, r *http.Request) {
	var req credsReq
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		errJSON(w, http.StatusBadRequest, "bad request")
		return
	}
	req.Email = strings.ToLower(strings.TrimSpace(req.Email))
	if req.Email == "" || !strings.Contains(req.Email, "@") {
		errJSON(w, http.StatusBadRequest, "Введите корректный email.")
		return
	}
	if len(req.Password) < 6 {
		errJSON(w, http.StatusBadRequest, "Пароль должен быть не короче 6 символов.")
		return
	}
	if _, err := s.store.UserByEmail(req.Email); err == nil {
		errJSON(w, http.StatusBadRequest, "Пользователь с таким email уже есть.")
		return
	}
	hash, err := auth.HashPassword(req.Password)
	if err != nil {
		errJSON(w, http.StatusInternalServerError, "server error")
		return
	}
	u, err := s.store.CreateUser(req.Email, "", hash)
	if err != nil {
		errJSON(w, http.StatusInternalServerError, "не удалось создать пользователя")
		return
	}
	s.sessions.Set(w, u.ID)
	writeJSON(w, http.StatusOK, map[string]string{"email": displayName(u)})
}

// displayName — что показывать пользователю: логин, если есть, иначе email.
func displayName(u store.User) string {
	if u.Username != "" {
		return u.Username
	}
	return u.Email
}

func (s *Server) login(w http.ResponseWriter, r *http.Request) {
	var req credsReq
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		errJSON(w, http.StatusBadRequest, "bad request")
		return
	}
	req.Email = strings.ToLower(strings.TrimSpace(req.Email))
	u, err := s.store.UserByLogin(req.Email)
	if err != nil || !auth.CheckPassword(u.PasswordHash, req.Password) {
		errJSON(w, http.StatusUnauthorized, "Неверный логин/email или пароль.")
		return
	}
	s.sessions.Set(w, u.ID)
	writeJSON(w, http.StatusOK, map[string]string{"email": displayName(u)})
}

func (s *Server) logout(w http.ResponseWriter, r *http.Request) {
	s.sessions.Clear(w)
	writeJSON(w, http.StatusOK, map[string]bool{"ok": true})
}

// ----- справочник -----

func (s *Server) options(w http.ResponseWriter, r *http.Request) {
	// Пустой справочник — фронт использует вшитый FALLBACK_OPTIONS.
	writeJSON(w, http.StatusOK, map[string]any{
		"centers": []string{}, "categories": []string{}, "subcategories": map[string]any{},
	})
}

// ----- заявки -----

func parseID(r *http.Request) (int64, error) {
	return strconv.ParseInt(r.PathValue("id"), 10, 64)
}

func (s *Server) listTasks(w http.ResponseWriter, r *http.Request) {
	u, ok := s.requireUser(w, r)
	if !ok {
		return
	}
	tasks, err := s.store.TasksByUser(u.ID)
	if err != nil {
		errJSON(w, http.StatusInternalServerError, "db error")
		return
	}
	if tasks == nil {
		tasks = []store.Task{}
	}
	writeJSON(w, http.StatusOK, tasks)
}

func (s *Server) createTask(w http.ResponseWriter, r *http.Request) {
	u, ok := s.requireUser(w, r)
	if !ok {
		return
	}
	var t store.Task
	if err := json.NewDecoder(r.Body).Decode(&t); err != nil {
		errJSON(w, http.StatusBadRequest, "bad request")
		return
	}
	t.UserID = u.ID
	if t.Site == "" {
		t.Site = "vfs_fr"
	}
	created, err := s.store.CreateTask(t)
	if err != nil {
		errJSON(w, http.StatusInternalServerError, "не удалось создать заявку")
		return
	}
	writeJSON(w, http.StatusOK, created)
}

func (s *Server) getTask(w http.ResponseWriter, r *http.Request) {
	u, ok := s.requireUser(w, r)
	if !ok {
		return
	}
	id, err := parseID(r)
	if err != nil {
		errJSON(w, http.StatusBadRequest, "bad id")
		return
	}
	t, err := s.store.TaskByID(id)
	if err != nil || t.UserID != u.ID {
		errJSON(w, http.StatusNotFound, "not found")
		return
	}
	writeJSON(w, http.StatusOK, t)
}

func (s *Server) deleteTask(w http.ResponseWriter, r *http.Request) {
	u, ok := s.requireUser(w, r)
	if !ok {
		return
	}
	id, err := parseID(r)
	if err != nil {
		errJSON(w, http.StatusBadRequest, "bad id")
		return
	}
	if err := s.store.DeleteTask(id, u.ID); err != nil {
		errJSON(w, http.StatusInternalServerError, "db error")
		return
	}
	writeJSON(w, http.StatusOK, map[string]bool{"ok": true})
}

// runSearch ставит задание воркеру и помечает заявку «searching».
func (s *Server) runSearch(w http.ResponseWriter, r *http.Request) {
	u, ok := s.requireUser(w, r)
	if !ok {
		return
	}
	id, err := parseID(r)
	if err != nil {
		errJSON(w, http.StatusBadRequest, "bad id")
		return
	}
	t, err := s.store.TaskByID(id)
	if err != nil || t.UserID != u.ID {
		errJSON(w, http.StatusNotFound, "not found")
		return
	}
	jobID, err := s.worker.CreateJob(s.checkRequestFor(t))
	if err != nil {
		errJSON(w, http.StatusBadGateway, "воркер недоступен: "+err.Error())
		return
	}
	if err := s.store.UpdateTaskStatus(t.ID, "searching", jobID); err != nil {
		errJSON(w, http.StatusInternalServerError, "db error")
		return
	}
	t.Status, t.JobID = "searching", jobID
	writeJSON(w, http.StatusOK, t)
}

// checkRequestFor собирает запрос к воркеру по заявке.
func (s *Server) checkRequestFor(t store.Task) worker.CheckRequest {
	return worker.CheckRequest{
		Login:           s.cfg.VFSLogin,
		Password:        s.cfg.VFSPassword,
		Center:          t.Center,
		Category:        t.Category,
		Subcategory:     t.Subcategory,
		DateStart:       t.DateStart,
		DateEnd:         t.DateEnd,
		ApplicantsCount: max(1, len(t.Applicants)),
	}
}

// RunScheduler периодически перепроверяет слоты по заявкам в статусе «searching»:
// ставит задание воркеру, ждёт результата, и если слотов нет — повторяет через
// CheckIntervalSec секунд. При найденной подходящей дате — статус «booked».
func (s *Server) RunScheduler() {
	interval := time.Duration(s.cfg.CheckIntervalSec) * time.Second
	lastCheck := map[int64]time.Time{}
	ticker := time.NewTicker(3 * time.Second)
	for range ticker.C {
		tasks, err := s.store.TasksByStatus("searching")
		if err != nil {
			continue
		}
		for _, t := range tasks {
			if t.JobID != "" {
				// Есть активное задание — проверяем результат.
				js, err := s.worker.GetJob(t.JobID)
				if err != nil {
					continue
				}
				switch js.Status {
				case "done":
					if js.Result.Matched != "" {
						_ = s.store.UpdateTaskStatus(t.ID, "booked", "")
						log.Printf("задача %d: найден слот %s", t.ID, js.Result.Matched)
					} else {
						// Слотов нет — снимаем задание, повторим через интервал.
						_ = s.store.UpdateTaskStatus(t.ID, "searching", "")
						lastCheck[t.ID] = time.Now()
					}
				case "error":
					log.Printf("задача %d: ошибка воркера: %s", t.ID, js.Message)
					_ = s.store.UpdateTaskStatus(t.ID, "searching", "")
					lastCheck[t.ID] = time.Now()
				}
			} else if time.Since(lastCheck[t.ID]) >= interval {
				// Пора запускать новую проверку.
				jobID, err := s.worker.CreateJob(s.checkRequestFor(t))
				if err != nil {
					log.Printf("задача %d: воркер недоступен: %v", t.ID, err)
					lastCheck[t.ID] = time.Now() // backoff
					continue
				}
				_ = s.store.UpdateTaskStatus(t.ID, "searching", jobID)
				lastCheck[t.ID] = time.Now()
			}
		}
	}
}
