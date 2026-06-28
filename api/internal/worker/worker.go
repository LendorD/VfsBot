// Package worker — HTTP-клиент к Python-воркеру обхода VFS.
// Контракт описан в backend/WORKER_API.md.
package worker

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"time"
)

type Client struct {
	BaseURL string
	http    *http.Client
}

func New(baseURL string) *Client {
	return &Client{BaseURL: baseURL, http: &http.Client{Timeout: 15 * time.Second}}
}

// CheckRequest — задание проверки доступности (см. POST /jobs воркера).
type CheckRequest struct {
	Login           string `json:"login"`
	Password        string `json:"password"`
	Center          string `json:"center"`
	Category        string `json:"category"`
	Subcategory     string `json:"subcategory"`
	DateStart       string `json:"date_start,omitempty"`
	DateEnd         string `json:"date_end,omitempty"`
	ApplicantsCount int    `json:"applicants_count"`
}

// JobStatus — ответ GET /jobs/{id}.
type JobStatus struct {
	JobID   string `json:"job_id"`
	Status  string `json:"status"` // pending | running | done | error
	Message string `json:"message"`
	Result  struct {
		HasSlots bool              `json:"has_slots"`
		Nearest  map[string]string `json:"nearest"`
		Matched  string            `json:"matched"`
	} `json:"result"`
}

// CreateJob ставит задание и возвращает его id.
func (c *Client) CreateJob(req CheckRequest) (string, error) {
	body, _ := json.Marshal(req)
	resp, err := c.http.Post(c.BaseURL+"/jobs", "application/json", bytes.NewReader(body))
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("worker /jobs: статус %d", resp.StatusCode)
	}
	var out struct {
		JobID string `json:"job_id"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		return "", err
	}
	return out.JobID, nil
}

// GetJob возвращает статус задания.
func (c *Client) GetJob(id string) (JobStatus, error) {
	var js JobStatus
	resp, err := c.http.Get(c.BaseURL + "/jobs/" + id)
	if err != nil {
		return js, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return js, fmt.Errorf("worker /jobs/%s: статус %d", id, resp.StatusCode)
	}
	err = json.NewDecoder(resp.Body).Decode(&js)
	return js, err
}
