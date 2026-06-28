// Команда bot — Telegram-бот: создание заявок на запись прямо в чате.
//
// Бот пишет заявки в ту же БД, что и сайт, и сразу ставит их на поиск
// (статус "searching") — дальше планировщик Go-сервера мониторит слоты.
package main

import (
	"fmt"
	"log"
	"net/http"
	"net/url"
	"strings"
	"sync"
	"time"

	tele "gopkg.in/telebot.v3"

	"visabooking/internal/config"
	"visabooking/internal/store"
)

// ---- Справочники (как на сайте; правятся здесь) ----

var centers = []string{
	"Французский Сервисный Визовый Центр в Санкт Петербурге",
	"Французский Сервисный Визовый Центр в Москве",
	"Французский Сервисный Визовый Центр в Екатеринбурге",
	"Французский Сервисный Визовый Центр в Казани",
	"Французский Сервисный Визовый Центр в Самаре",
	// ... дополните остальными центрами при необходимости.
}

var categories = []string{"Краткосрочная виза", "Национальная виза"}

var subcategories = map[string][]string{
	"Краткосрочная виза": {
		"Другие краткосрочные визы",
		"PRIME TIME (66 euros) Short Stay All kind of other short stay visas",
		"Краткосрочная виза с деловой или профессиональной целью",
		"Краткосрочная виза для моряков",
	},
	"Национальная виза": {
		"Учебная виза (D)",
		"Рабочая виза (D)",
		"Воссоединение семьи (D)",
	},
}

// ---- Шаги диалога ----

const (
	stCenter    = "center"
	stCategory  = "category"
	stSub       = "subcategory"
	stDateStart = "date_start"
	stDateEnd   = "date_end"
	stFirst     = "first_name"
	stSurname   = "surname"
	stGender    = "gender"
	stBirth     = "birth_date"
	stNat       = "nationality"
	stPassport  = "passport_number"
	stExpiry    = "passport_expiry"
	stPhone     = "phone"
	stEmail     = "email"
)

type conv struct {
	step  string
	draft store.Task
	app   store.Applicant
}

var (
	db     *store.Store
	convs  = map[int64]*conv{}
	convMu sync.Mutex
)

func getConv(id int64) *conv  { convMu.Lock(); defer convMu.Unlock(); return convs[id] }
func setConv(id int64, c *conv) { convMu.Lock(); defer convMu.Unlock(); convs[id] = c }
func clearConv(id int64)      { convMu.Lock(); defer convMu.Unlock(); delete(convs, id) }

// ---- Клавиатуры ----

func keyboard(opts []string) *tele.ReplyMarkup {
	m := &tele.ReplyMarkup{ResizeKeyboard: true, OneTimeKeyboard: true}
	rows := make([]tele.Row, 0, len(opts))
	for _, o := range opts {
		rows = append(rows, m.Row(m.Text(o)))
	}
	m.Reply(rows...)
	return m
}

func removeKb() *tele.ReplyMarkup { return &tele.ReplyMarkup{RemoveKeyboard: true} }

// ---- Утилиты ----

func contains(list []string, v string) bool {
	for _, x := range list {
		if x == v {
			return true
		}
	}
	return false
}

func validDate(s string) bool {
	_, err := time.Parse("2006-01-02", s)
	return err == nil
}

func ensureUser(sender *tele.User) (store.User, error) {
	if u, err := db.UserByTelegram(sender.ID); err == nil {
		return u, nil
	}
	return db.CreateTelegramUser(sender.ID, fmt.Sprintf("tg%d", sender.ID))
}

func statusRu(s string) string {
	switch s {
	case "created":
		return "создана"
	case "searching":
		return "идёт поиск"
	case "booked":
		return "слот найден"
	case "error":
		return "ошибка"
	}
	return s
}

// ---- Обработчики команд ----

func onStart(c tele.Context) error {
	return c.Send("Привет! Я бот VisaBooking.\n\n" +
		"/new — создать заявку на отслеживание слотов\n" +
		"/list — мои заявки\n" +
		"/cancel — отменить создание\n" +
		"/help — помощь")
}

func onHelp(c tele.Context) error {
	return c.Send("Создание заявки: /new — дальше отвечайте на вопросы и жмите кнопки.\n" +
		"Я буду следить за появлением свободных слотов и пришлю статус в /list.")
}

func onCancel(c tele.Context) error {
	clearConv(c.Sender().ID)
	return c.Send("Создание заявки отменено.", removeKb())
}

func onNew(c tele.Context) error {
	setConv(c.Sender().ID, &conv{step: stCenter})
	return c.Send("Создаём заявку. Выберите визовый центр:", keyboard(centers))
}

func onList(c tele.Context) error {
	u, err := db.UserByTelegram(c.Sender().ID)
	if err != nil {
		return c.Send("У вас пока нет заявок. /new — создать.")
	}
	tasks, err := db.TasksByUser(u.ID)
	if err != nil || len(tasks) == 0 {
		return c.Send("Заявок нет. /new — создать.")
	}
	var b strings.Builder
	for _, t := range tasks {
		b.WriteString(fmt.Sprintf("#%d · %s · %s\n    %s | %s — %s\n",
			t.ID, statusRu(t.Status), t.Subcategory, t.Center, t.DateStart, t.DateEnd))
	}
	return c.Send(b.String())
}

// ---- Пошаговый диалог ----

func onText(c tele.Context) error {
	st := getConv(c.Sender().ID)
	if st == nil {
		return c.Send("Чтобы создать заявку — /new")
	}
	text := strings.TrimSpace(c.Text())

	switch st.step {
	case stCenter:
		if !contains(centers, text) {
			return c.Send("Пожалуйста, выберите центр кнопкой ниже.")
		}
		st.draft.Center = text
		st.step = stCategory
		return c.Send("Категория записи:", keyboard(categories))

	case stCategory:
		if !contains(categories, text) {
			return c.Send("Выберите категорию кнопкой.")
		}
		st.draft.Category = text
		st.step = stSub
		return c.Send("Подкатегория:", keyboard(subcategories[text]))

	case stSub:
		st.draft.Subcategory = text
		st.step = stDateStart
		return c.Send("Желаемый диапазон дат.\nДата НАЧАЛА (ГГГГ-ММ-ДД), напр. 2026-07-01:", removeKb())

	case stDateStart:
		if !validDate(text) {
			return c.Send("Неверный формат. Введите дату как ГГГГ-ММ-ДД.")
		}
		st.draft.DateStart = text
		st.step = stDateEnd
		return c.Send("Дата КОНЦА диапазона (ГГГГ-ММ-ДД):")

	case stDateEnd:
		if !validDate(text) {
			return c.Send("Неверный формат. Введите дату как ГГГГ-ММ-ДД.")
		}
		st.draft.DateEnd = text
		st.step = stFirst
		return c.Send("Данные заявителя.\nИмя (латиницей):")

	case stFirst:
		st.app.FirstName = text
		st.step = stSurname
		return c.Send("Фамилия (латиницей):")

	case stSurname:
		st.app.Surname = text
		st.step = stGender
		return c.Send("Пол:", keyboard([]string{"Мужской", "Женский"}))

	case stGender:
		if text != "Мужской" && text != "Женский" {
			return c.Send("Выберите пол кнопкой.")
		}
		st.app.Gender = text
		st.step = stBirth
		return c.Send("Дата рождения (ГГГГ-ММ-ДД):", removeKb())

	case stBirth:
		if !validDate(text) {
			return c.Send("Неверный формат. ГГГГ-ММ-ДД.")
		}
		st.app.BirthDate = text
		st.step = stNat
		return c.Send("Гражданство (англ., напр. RUSSIA):")

	case stNat:
		st.app.Nationality = text
		st.step = stPassport
		return c.Send("Номер паспорта (6 цифр):")

	case stPassport:
		st.app.PassportNumber = text
		st.step = stExpiry
		return c.Send("Срок действия паспорта (ГГГГ-ММ-ДД):")

	case stExpiry:
		if !validDate(text) {
			return c.Send("Неверный формат. ГГГГ-ММ-ДД.")
		}
		st.app.PassportExpiry = text
		st.step = stPhone
		return c.Send("Телефон (только цифры, без кода страны):")

	case stPhone:
		st.app.Phone = text
		st.app.PhoneCode = "7"
		st.step = stEmail
		return c.Send("Email:")

	case stEmail:
		st.app.Email = text
		return finalize(c, st)
	}
	return nil
}

func finalize(c tele.Context, st *conv) error {
	id := c.Sender().ID
	user, err := ensureUser(c.Sender())
	if err != nil {
		clearConv(id)
		return c.Send("Ошибка БД: "+err.Error(), removeKb())
	}
	st.draft.UserID = user.ID
	st.draft.Site = "vfs_fr"
	st.draft.Applicants = []store.Applicant{st.app}

	task, err := db.CreateTask(st.draft)
	if err != nil {
		clearConv(id)
		return c.Send("Не удалось создать заявку: "+err.Error(), removeKb())
	}
	// Сразу ставим на поиск — планировщик подхватит.
	_ = db.UpdateTaskStatus(task.ID, "searching", "")
	clearConv(id)

	return c.Send(fmt.Sprintf(
		"✅ Заявка #%d создана и поставлена на поиск.\n\n%s\n%s · %s\nДаты: %s — %s\nЗаявитель: %s %s\n\n/list — мои заявки",
		task.ID, st.draft.Center, st.draft.Category, st.draft.Subcategory,
		st.draft.DateStart, st.draft.DateEnd, st.app.FirstName, st.app.Surname,
	), removeKb())
}

func main() {
	cfg := config.Load()
	if cfg.BotToken == "" {
		log.Fatal("BOT_TOKEN не задан")
	}

	st, err := store.New(cfg.DBPath)
	if err != nil {
		log.Fatalf("открытие БД: %v", err)
	}
	if err := st.Init(); err != nil {
		log.Fatalf("инициализация БД: %v", err)
	}
	db = st

	settings := tele.Settings{
		Token:  cfg.BotToken,
		Poller: &tele.LongPoller{Timeout: 10 * time.Second},
	}
	// Прокси для обхода блокировки Telegram (http:// или socks5://).
	if cfg.BotProxy != "" {
		if pu, perr := url.Parse(cfg.BotProxy); perr == nil {
			settings.Client = &http.Client{
				Timeout:   30 * time.Second,
				Transport: &http.Transport{Proxy: http.ProxyURL(pu)},
			}
			log.Printf("Бот работает через прокси: %s", cfg.BotProxy)
		}
	}

	b, err := tele.NewBot(settings)
	if err != nil {
		log.Fatal(err)
	}

	b.Handle("/start", onStart)
	b.Handle("/help", onHelp)
	b.Handle("/new", onNew)
	b.Handle("/cancel", onCancel)
	b.Handle("/list", onList)
	b.Handle(tele.OnText, onText)

	log.Println("Telegram-бот запущен")
	b.Start()
}
