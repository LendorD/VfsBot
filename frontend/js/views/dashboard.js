/* Экран «Мои заявки» (список карточек). */
import { state } from "../state.js";
import { esc, plural, siteLabel, dateRange, statusBadge } from "../utils.js";

export function dashboardHTML() {
  const n = state.tasks.length;
  const countLabel = n === 0 ? "Заявок пока нет"
    : `${n} ${plural(n, "активная заявка", "активные заявки", "активных заявок")}`;
  let body;
  if (n === 0) {
    body = `<div style="background:#fff;border:1px dashed #d4daea;border-radius:18px;padding:60px 24px;text-align:center">
        <div style="width:60px;height:60px;border-radius:16px;background:#eef1fd;display:flex;align-items:center;justify-content:center;margin:0 auto 16px;font-size:26px">🛂</div>
        <h2 style="margin:0 0 6px;font-size:18px;font-weight:700">Пока нет заявок</h2>
        <p style="margin:0 auto 22px;font-size:14px;color:var(--muted);max-width:340px">Создайте первую заявку — бот начнёт искать свободные слоты автоматически.</p>
        <button class="vb-btn vb-btn-primary" data-go="new">Создать заявку</button>
      </div>`;
  } else {
    const cards = state.tasks.map((t) => {
      const cnt = t.applicants_count ?? (t.applicants ? t.applicants.length : 0);
      const autoPay = t.auto_pay
        ? `<div style="display:flex;align-items:center;gap:5px;align-self:flex-end;font-size:11.5px;font-weight:600;color:#c2186a;background:#fdeaf2;padding:3px 8px;border-radius:7px">⚡ Авто-оплата</div>` : "";
      return `<div class="vb-req-card" data-open="${t.id}">
        <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:10px;margin-bottom:14px">
          <div style="display:flex;align-items:center;gap:10px;min-width:0">
            <div style="width:38px;height:38px;border-radius:10px;background:#f1f4fb;display:flex;align-items:center;justify-content:center;font-size:18px;flex:none">✈️</div>
            <div style="min-width:0">
              <div style="font-size:14.5px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(t.center || "Центр не указан")}</div>
              <div style="font-size:12px;color:var(--muted2);margin-top:1px">${esc(siteLabel(t.site))}</div>
            </div>
          </div>
          ${statusBadge(t.status)}
        </div>
        <div style="font-size:13.5px;color:#3a4252;font-weight:500;margin-bottom:3px">${esc(t.category || "—")}</div>
        <div style="font-size:12.5px;color:#8a92a4;margin-bottom:16px">${esc(t.subcategory || "")}</div>
        <div style="display:flex;gap:18px;padding-top:14px;border-top:1px solid #f0f2f7">
          <div><div style="font-size:11px;color:var(--muted2);margin-bottom:2px">Заявители</div><div style="font-size:13.5px;font-weight:600">${cnt}</div></div>
          <div style="flex:1"><div style="font-size:11px;color:var(--muted2);margin-bottom:2px">Даты</div><div style="font-size:13.5px;font-weight:600">${esc(dateRange(t))}</div></div>
          ${autoPay}
        </div>
      </div>`;
    }).join("");
    body = `<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:18px">${cards}</div>`;
  }
  return `
  <main class="vb-main vb-pop" style="max-width:1120px;padding:30px 24px 60px">
    <div style="display:flex;align-items:flex-end;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-bottom:24px">
      <div>
        <h1 style="margin:0;font-size:26px;font-weight:700;letter-spacing:-.02em">Мои заявки</h1>
        <p style="margin:6px 0 0;font-size:14px;color:var(--muted)">${esc(countLabel)}</p>
      </div>
      <button class="vb-btn vb-btn-primary" data-go="new" style="display:flex;align-items:center;gap:8px"><span style="font-size:17px;line-height:0">＋</span>Новая заявка</button>
    </div>
    ${body}
  </main>`;
}
