/* Контроллер SPA: рендер экранов, навигация, обработчики событий. */
import { state, AFIELDS } from "./state.js";
import { emptyApplicant } from "./utils.js";
import { api, loadAppData } from "./api.js";
import { headerHTML } from "./views/header.js";
import { authHTML } from "./views/auth.js";
import { dashboardHTML } from "./views/dashboard.js";
import { newTaskHTML } from "./views/newTask.js";
import { detailHTML } from "./views/detail.js";

const app = () => document.getElementById("app");

// ---------- рендер ----------
function render() {
  let main;
  if (state.screen === "login" || state.screen === "register") main = authHTML();
  else if (state.screen === "dashboard") main = dashboardHTML();
  else if (state.screen === "new") main = newTaskHTML();
  else if (state.screen === "detail") main = detailHTML();
  else main = dashboardHTML();
  app().innerHTML = headerHTML() + main;
  bind();
}

function bind() {
  const $ = (id) => document.getElementById(id);
  const logo = $("nav-logo"); if (logo) logo.onclick = () => go("dashboard");
  const logout = $("nav-logout"); if (logout) logout.onclick = onLogout;
  document.querySelectorAll("[data-go]").forEach((b) => b.onclick = () => {
    const dest = b.getAttribute("data-go");
    if (dest === "new") openNew(); else go(dest);
  });

  if (state.screen === "login" || state.screen === "register") {
    $("auth-submit").onclick = onAuthSubmit;
    $("auth-switch").onclick = () => { state.authError = ""; go(state.screen === "login" ? "register" : "login"); };
    $("auth-password").onkeydown = (e) => { if (e.key === "Enter") onAuthSubmit(); };
  }
  if (state.screen === "dashboard") {
    document.querySelectorAll("[data-open]").forEach((c) => c.onclick = () => openDetail(c.getAttribute("data-open")));
  }
  if (state.screen === "new") {
    const fd = $("fill-defaults"); if (fd) fd.onclick = fillDefaults;
    $("add-applicant").onclick = () => { syncDraft(); state.draft.applicants.push(emptyApplicant()); render(); };
    document.querySelectorAll("[data-remove]").forEach((b) => b.onclick = () => {
      syncDraft(); const i = +b.getAttribute("data-remove");
      if (state.draft.applicants.length > 1) state.draft.applicants.splice(i, 1); render();
    });
    $("toggle-autopay").onclick = () => { syncDraft(); state.draft.auto_pay = !state.draft.auto_pay; render(); };
    const cat = $("f-category"); if (cat) cat.onchange = () => { syncDraft(); state.draft.subcategory = ""; render(); };
    $("create-task").onclick = onCreateTask;
  }
  if (state.screen === "detail") {
    const rs = $("run-search"); if (rs) rs.onclick = onRunSearch;
    $("delete-task").onclick = onDeleteTask;
  }
}

// ---------- навигация ----------
function go(screen) { state.screen = screen; window.scrollTo(0, 0); render(); }

function openNew() {
  state.draft = { site: "vfs_fr", center: "", category: "", subcategory: "",
    date_start: "", date_end: "", auto_pay: false, applicants: [emptyApplicant()] };
  state.createError = ""; go("new");
}

// Быстрое заполнение тестовыми данными (для отладки).
function fillDefaults() {
  state.draft = {
    site: "vfs_fr",
    center: "Французский Сервисный Визовый Центр в Санкт Петербурге",
    category: "Краткосрочная виза",
    subcategory: "Другие краткосрочные визы",
    date_start: "2026-07-01",
    date_end: "2026-07-31",
    auto_pay: false,
    applicants: [{
      first_name: "DMITRO", surname: "LUTSEN", gender: "Мужской",
      birth_date: "2011-06-02", nationality: "MOROCCO",
      passport_number: "111222", passport_expiry: "2026-07-31",
      phone_code: "7", phone: "9622840766", email: "PODNEBESVISACENTER@MAIL.RU",
    }],
  };
  state.createError = "";
  render();
}

async function openDetail(id) {
  const r = await api(`/api/tasks/${id}`);
  if (r.ok) { state.current = r.data; go("detail"); }
}

// ---------- работа с формой новой заявки ----------
function val(id) { const e = document.getElementById(id); return e ? e.value : ""; }

function syncDraft() {
  if (state.screen !== "new" || !state.draft) return;
  const d = state.draft;
  d.site = val("f-site") || "vfs_fr";
  d.center = val("f-center");
  d.category = val("f-category");
  d.subcategory = val("f-subcategory");
  d.date_start = val("f-date_start");
  d.date_end = val("f-date_end");
  d.applicants = Array.from(document.querySelectorAll(".vb-applicant")).map((card) => {
    const a = {};
    AFIELDS.forEach((f) => {
      const inp = card.querySelector(`[data-field="${f}"]`);
      a[f] = inp ? inp.value : "";
    });
    return a;
  });
  if (!d.applicants.length) d.applicants = [emptyApplicant()];
}

// ---------- действия ----------
async function onAuthSubmit() {
  const email = val("auth-email").trim();
  const password = val("auth-password");
  if (!email || !password) { state.authError = "Введите email и пароль."; return render(); }
  const path = state.screen === "login" ? "/api/login" : "/api/register";
  const r = await api(path, "POST", { email, password });
  if (!r.ok) { state.authError = (r.data && r.data.error) || "Не удалось войти."; return render(); }
  state.me = r.data.email; state.authError = "";
  await loadAppData(); go("dashboard");
}

async function onLogout() {
  await api("/api/logout", "POST");
  state.me = null; state.tasks = []; go("login");
}

async function onCreateTask() {
  syncDraft();
  const d = state.draft;
  if (!d.center) { state.createError = "Укажите центр приложений."; return render(); }
  const r = await api("/api/tasks", "POST", d);
  if (!r.ok) { state.createError = (r.data && r.data.error) || "Не удалось создать заявку."; return render(); }
  const tasks = await api("/api/tasks"); if (tasks.ok) state.tasks = tasks.data;
  state.current = r.data; go("detail");
}

async function onRunSearch() {
  const r = await api(`/api/tasks/${state.current.id}/search`, "POST");
  if (r.ok) { state.current = r.data; const t = await api("/api/tasks"); if (t.ok) state.tasks = t.data; render(); }
}

async function onDeleteTask() {
  if (!confirm("Удалить заявку?")) return;
  await api(`/api/tasks/${state.current.id}`, "DELETE");
  const t = await api("/api/tasks"); if (t.ok) state.tasks = t.data;
  go("dashboard");
}

// ---------- старт ----------
async function bootstrap() {
  const me = await api("/api/me");
  if (me.ok) {
    state.me = me.data.email;
    await loadAppData();
    state.screen = "dashboard";
  } else {
    state.screen = "login";
  }
  render();
}

bootstrap();
