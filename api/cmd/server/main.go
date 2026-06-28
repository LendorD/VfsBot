// Команда server — REST API + отдача фронтенда.
package main

import (
	"log"
	"net/http"

	"visabooking/internal/auth"
	"visabooking/internal/config"
	"visabooking/internal/server"
	"visabooking/internal/store"
)

// seedAdmin создаёт пользователя по умолчанию admin/admin, если его ещё нет.
func seedAdmin(st *store.Store) {
	if _, err := st.UserByLogin("admin"); err == nil {
		return
	}
	hash, err := auth.HashPassword("admin")
	if err != nil {
		return
	}
	if _, err := st.CreateUser("admin@local", "admin", hash); err == nil {
		log.Println("создан пользователь по умолчанию: admin / admin")
	}
}

func main() {
	cfg := config.Load()

	st, err := store.New(cfg.DBPath)
	if err != nil {
		log.Fatalf("открытие БД (%s): %v", cfg.DBPath, err)
	}
	defer st.Close()
	if err := st.Init(); err != nil {
		log.Fatalf("инициализация БД: %v", err)
	}
	seedAdmin(st)

	srv := server.New(cfg, st)
	go srv.RunScheduler() // периодическая перепроверка слотов через воркер

	log.Printf("API слушает %s (фронт из %s, воркер %s)", cfg.Addr, cfg.FrontendDir, cfg.WorkerURL)
	if err := http.ListenAndServe(cfg.Addr, srv.Routes()); err != nil {
		log.Fatal(err)
	}
}
