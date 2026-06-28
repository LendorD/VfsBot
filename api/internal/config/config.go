// Package config загружает настройки из переменных окружения.
package config

import (
	"bufio"
	"os"
	"strconv"
	"strings"
)

// loadDotEnv подхватывает переменные из .env (корень проекта или рядом),
// не перезаписывая уже заданные в окружении. Go сам .env не читает.
func loadDotEnv() {
	for _, path := range []string{".env", "../.env"} {
		f, err := os.Open(path)
		if err != nil {
			continue
		}
		sc := bufio.NewScanner(f)
		for sc.Scan() {
			line := strings.TrimSpace(sc.Text())
			if line == "" || strings.HasPrefix(line, "#") {
				continue
			}
			key, val, ok := strings.Cut(line, "=")
			if !ok {
				continue
			}
			key, val = strings.TrimSpace(key), strings.TrimSpace(val)
			if _, exists := os.LookupEnv(key); !exists {
				_ = os.Setenv(key, val)
			}
		}
		f.Close()
	}
}

type Config struct {
	Addr          string // адрес HTTP-сервера, напр. ":8000"
	DBPath        string // путь к файлу БД SQLite
	FrontendDir   string // путь к папке с фронтендом
	WorkerURL     string // базовый URL Python-воркера
	SessionSecret string // секрет для подписи cookie-сессий
	VFSLogin         string // логин личного кабинета VFS (для воркера)
	VFSPassword      string // пароль личного кабинета VFS
	BotToken         string // токен Telegram-бота
	BotProxy         string // прокси для бота (http:// или socks5://), если Telegram заблокирован
	CheckIntervalSec int    // период перепроверки слотов, сек
}

func env(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

func envInt(key string, def int) int {
	if v := os.Getenv(key); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			return n
		}
	}
	return def
}

// Load читает конфигурацию из окружения с разумными значениями по умолчанию.
func Load() Config {
	loadDotEnv()
	return Config{
		Addr:          env("ADDR", ":8000"),
		DBPath:        env("DB_PATH", "data/visabooking.db"),
		FrontendDir:   env("FRONTEND_DIR", "../frontend"),
		WorkerURL:     env("WORKER_URL", "http://127.0.0.1:8800"),
		SessionSecret: env("WEBAPP_SECRET", "dev-secret-change-me-in-production"),
		VFSLogin:         env("VFS_LOGIN", ""),
		VFSPassword:      env("VFS_PASSWORD", ""),
		BotToken:         env("BOT_TOKEN", ""),
		BotProxy:         env("BOT_PROXY", ""),
		CheckIntervalSec: envInt("CHECK_INTERVAL_SECONDS", 45),
	}
}
