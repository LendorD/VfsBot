/* Экран деталей заявки: параметры, запуск поиска, заявители. */
import { state } from "../state.js";
import { esc, fmtDate, dateRange, siteLabel, statusBadge } from "../utils.js";
import { dashboardHTML } from "./dashboard.js";

export function detailHTML() {
  const t = state.current;
  if (!t) return dashboardHTML();
  const autoPayColor = t.auto_pay ? "#c2186a" : "var(--ink)";
  const autoPayLabel = t.auto_pay ? "включена" : "выключена";
  const searching = t.status === "searching";
  const searchText = searching
    ? "Бот проверяет свободные слоты в выбранном диапазоне дат…"
    : "Запустите поиск — бот будет проверять свободные слоты и попытается записать.";
  const applicants = (t.applicants || []).map((a) => {
    const initials = ((a.first_name || "?")[0] + (a.surname || "")[0] || "?").toUpperCase();
    const meta = `${a.gender || "—"} · ${fmtDate(a.birth_date)}`;
    return `<div style="display:flex;align-items:center;gap:14px;padding:13px 16px;border:1px solid #eceef4;border-radius:12px;background:#fafbfd;flex-wrap:wrap">
      <span style="width:30px;height:30px;border-radius:50%;background:#eef1fd;color:var(--primary);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px;flex:none">${esc(initials)}</span>
      <div style="flex:1;min-width:140px">
        <div style="font-size:14px;font-weight:600">${esc((a.first_name || "") + " " + (a.surname || ""))}</div>
        <div style="font-size:12px;color:var(--muted2)">${esc(meta)}</div>
      </div>
      <div style="font-size:12.5px;color:#6b7488">📄 ${esc(a.passport_number || "—")}</div>
    </div>`;
  }).join("") || `<p style="font-size:14px;color:var(--muted)">Заявители не указаны.</p>`;

  return `
  <main class="vb-main vb-pop" style="max-width:820px;padding:28px 24px 70px">
    <div class="vb-link-back" data-go="dashboard">‹ Назад к заявкам</div>
    <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-bottom:22px">
      <div style="display:flex;align-items:center;gap:14px">
        <div style="width:48px;height:48px;border-radius:13px;background:#f1f4fb;display:flex;align-items:center;justify-content:center;font-size:22px">✈️</div>
        <div>
          <h1 style="margin:0;font-size:22px;font-weight:700">${esc(t.center || "Центр не указан")}</h1>
          <div style="font-size:13.5px;color:#8a92a4;margin-top:2px">${esc(siteLabel(t.site))}</div>
        </div>
      </div>
      ${statusBadge(t.status)}
    </div>

    <section class="vb-card" style="margin-bottom:18px">
      <h2 class="vb-h2" style="margin-bottom:18px">Параметры записи</h2>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:18px 24px">
        <div><div style="font-size:12px;color:var(--muted2);margin-bottom:3px">Категория</div><div style="font-size:14px;font-weight:600">${esc(t.category || "—")}</div></div>
        <div><div style="font-size:12px;color:var(--muted2);margin-bottom:3px">Подкатегория</div><div style="font-size:14px;font-weight:600">${esc(t.subcategory || "—")}</div></div>
        <div><div style="font-size:12px;color:var(--muted2);margin-bottom:3px">Желаемые даты</div><div style="font-size:14px;font-weight:600">${esc(dateRange(t))}</div></div>
        <div><div style="font-size:12px;color:var(--muted2);margin-bottom:3px">Авто-оплата</div><div style="font-size:14px;font-weight:600;color:${autoPayColor}">${esc(autoPayLabel)}</div></div>
      </div>
    </section>

    <section style="background:linear-gradient(135deg,#3056d3,#3f6bf0);border-radius:16px;padding:22px;margin-bottom:18px;color:#fff;box-shadow:0 14px 32px -16px rgba(48,86,211,.6)">
      <div style="display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap">
        <div style="flex:1;min-width:220px">
          <div style="font-size:16px;font-weight:700;margin-bottom:5px">Поиск свободных слотов</div>
          <div style="font-size:13.5px;color:#dde6ff;line-height:1.5">${esc(searchText)}</div>
        </div>
        <button id="run-search" class="vb-btn" ${searching ? "disabled" : ""} style="background:#fff;color:#2848bd;font-weight:700;white-space:nowrap;opacity:${searching ? ".6" : "1"}">${searching ? "Идёт поиск…" : "Запустить поиск"}</button>
      </div>
      ${searching ? `<div style="margin-top:16px;display:flex;align-items:center;gap:10px;background:rgba(255,255,255,.14);padding:10px 14px;border-radius:10px;font-size:13px;font-weight:500"><span style="width:8px;height:8px;border-radius:50%;background:#fff;animation:vbpulse 1s infinite"></span>Бот проверяет слоты в выбранном диапазоне дат…</div>` : ""}
    </section>

    <section class="vb-card" style="margin-bottom:24px">
      <h2 class="vb-h2" style="margin-bottom:16px">Заявители · ${(t.applicants || []).length}</h2>
      <div style="display:flex;flex-direction:column;gap:10px">${applicants}</div>
    </section>

    <button id="delete-task" class="vb-btn vb-btn-danger" style="padding:11px 20px">Удалить заявку</button>
  </main>`;
}
