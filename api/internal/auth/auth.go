// Package auth — хеширование паролей (bcrypt) и cookie-сессии (подпись HMAC).
package auth

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"net/http"
	"strconv"
	"strings"
	"time"

	"golang.org/x/crypto/bcrypt"
)

const cookieName = "vb_session"

func HashPassword(p string) (string, error) {
	b, err := bcrypt.GenerateFromPassword([]byte(p), bcrypt.DefaultCost)
	return string(b), err
}

func CheckPassword(hash, p string) bool {
	return bcrypt.CompareHashAndPassword([]byte(hash), []byte(p)) == nil
}

// Sessions подписывает и проверяет cookie-сессии.
type Sessions struct{ secret []byte }

func NewSessions(secret string) *Sessions { return &Sessions{secret: []byte(secret)} }

func (s *Sessions) sign(payload string) string {
	mac := hmac.New(sha256.New, s.secret)
	mac.Write([]byte(payload))
	return base64.RawURLEncoding.EncodeToString(mac.Sum(nil))
}

// Set кладёт подписанную cookie с user_id.
func (s *Sessions) Set(w http.ResponseWriter, userID int64) {
	payload := strconv.FormatInt(userID, 10)
	http.SetCookie(w, &http.Cookie{
		Name:     cookieName,
		Value:    payload + "." + s.sign(payload),
		Path:     "/",
		HttpOnly: true,
		SameSite: http.SameSiteLaxMode,
		Expires:  time.Now().Add(30 * 24 * time.Hour),
	})
}

func (s *Sessions) Clear(w http.ResponseWriter) {
	http.SetCookie(w, &http.Cookie{Name: cookieName, Value: "", Path: "/", MaxAge: -1})
}

// UserID извлекает и проверяет user_id из cookie.
func (s *Sessions) UserID(r *http.Request) (int64, bool) {
	c, err := r.Cookie(cookieName)
	if err != nil {
		return 0, false
	}
	payload, sig, ok := strings.Cut(c.Value, ".")
	if !ok || !hmac.Equal([]byte(sig), []byte(s.sign(payload))) {
		return 0, false
	}
	id, err := strconv.ParseInt(payload, 10, 64)
	if err != nil {
		return 0, false
	}
	return id, true
}
