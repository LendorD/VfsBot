/* Экран «Новая заявка»: критерии, даты, авто-оплата, заявители. */
import { state, SITES } from "../state.js";
import { esc } from "../utils.js";

function criteriaSelect(id, value, list, placeholder, disabled) {
  if (!list || !list.length) {
    return `<input id="${id}" class="vb-input" value="${esc(value)}" placeholder="${esc(placeholder)}" />`;
  }
  const opts = [`<option value="">— выберите —</option>`]
    .concat(list.map((o) => `<option value="${esc(o)}" ${o === value ? "selected" : ""}>${esc(o)}</option>`)).join("");
  return `<select id="${id}" class="vb-select" ${disabled ? "disabled" : ""}>${opts}</select>`;
}

function applicantCardHTML(a, i, canRemove) {
  const f = (field, label, ph, type) =>
    `<div class="vb-field"><label class="vb-label" style="font-size:12px">${label}</label>
      <input data-field="${field}" type="${type || "text"}" class="vb-input vb-input-sm" value="${esc(a[field])}" placeholder="${esc(ph || "")}" /></div>`;
  const genderSel = `<div class="vb-field"><label class="vb-label" style="font-size:12px">Пол</label>
      <select data-field="gender" class="vb-select vb-input-sm">
        <option value="">— выберите —</option>
        <option value="Мужской" ${a.gender === "Мужской" ? "selected" : ""}>Мужской</option>
        <option value="Женский" ${a.gender === "Женский" ? "selected" : ""}>Женский</option>
      </select></div>`;
  const removeBtn = canRemove
    ? `<button class="vb-btn vb-btn-danger" data-remove="${i}" style="padding:5px 11px;font-size:12.5px">Удалить</button>` : "";
  return `<div class="vb-applicant" style="border:1px solid #eceef4;border-radius:13px;padding:18px;background:#fafbfd">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px">
      <div style="display:flex;align-items:center;gap:8px;font-size:13.5px;font-weight:700;color:#3a4252">
        <span style="width:22px;height:22px;border-radius:50%;background:var(--primary);color:#fff;display:flex;align-items:center;justify-content:center;font-size:12px">${i + 1}</span>
        Заявитель ${i + 1}
      </div>${removeBtn}
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:13px">
      ${f("first_name", "Имя (латиницей)", "IVAN")}
      ${f("surname", "Фамилия (латиницей)", "IVANOV")}
      ${genderSel}
      ${f("birth_date", "Дата рождения", "", "date")}
      ${f("nationality", "Гражданство (англ.)", "RUSSIA")}
      ${f("passport_number", "Номер паспорта (6 цифр)", "000000")}
      ${f("passport_expiry", "Срок действия паспорта", "", "date")}
      <div style="display:grid;grid-template-columns:78px 1fr;gap:8px">
        ${f("phone_code", "Код", "+7")}
        ${f("phone", "Телефон", "900 000-00-00")}
      </div>
      ${f("email", "Email", "ivan@example.com", "email")}
    </div>
  </div>`;
}

export function newTaskHTML() {
  const d = state.draft;
  const subList = d.category ? (state.options.subcategories[d.category] || []) : [];
  const subDisabled = !d.category;
  const aHint = `Можно добавить любое число заявителей. Сейчас: ${d.applicants.length}.`;
  const applicants = d.applicants.map((a, i) => applicantCardHTML(a, i, d.applicants.length > 1)).join("");
  const err = state.createError
    ? `<div style="display:flex;align-items:center;gap:8px;background:#fdeceb;border:1px solid #f6cfcc;color:#b6322b;font-size:13.5px;font-weight:500;padding:11px 14px;border-radius:11px;margin-bottom:16px"><span style="width:6px;height:6px;border-radius:50%;background:#c2342d"></span>${esc(state.createError)}</div>` : "";
  const switchKnob = d.auto_pay ? "translateX(22px)" : "translateX(0)";
  const switchTrack = d.auto_pay ? "#d11a73" : "#cfd6e6";
  const hasSubcats = state.options.subcategories && Object.keys(state.options.subcategories).length;
  return `
  <main class="vb-main vb-pop" style="max-width:820px;padding:28px 24px 70px">
    <div class="vb-link-back" data-go="dashboard">‹ Назад к заявкам</div>
    <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin:0 0 24px;flex-wrap:wrap">
      <h1 style="margin:0;font-size:25px;font-weight:700;letter-spacing:-.02em">Новая заявка</h1>
      <button id="fill-defaults" class="vb-btn vb-btn-light" style="padding:8px 13px;font-size:13px">Заполнить тестовыми</button>
    </div>

    <section class="vb-card" style="margin-bottom:18px">
      <h2 class="vb-h2">Куда записываемся</h2>
      <p style="margin:0 0 18px;font-size:13px;color:var(--muted2)">Выберите визовый центр и категорию записи</p>
      <div class="vb-grid-auto">
        <div class="vb-field"><label class="vb-label">Сайт записи</label>
          <select id="f-site" class="vb-select">${SITES.map((s) => `<option value="${esc(s.value)}" ${s.value === d.site ? "selected" : ""}>${esc(s.label)}</option>`).join("")}</select></div>
        <div class="vb-field"><label class="vb-label">Центр приложений</label>
          ${criteriaSelect("f-center", d.center, state.options.centers, "Название центра", false)}</div>
        <div class="vb-field"><label class="vb-label">Категория записи</label>
          ${criteriaSelect("f-category", d.category, state.options.categories, "Категория визы", false)}</div>
        <div class="vb-field"><label class="vb-label">Подкатегория</label>
          ${hasSubcats
            ? criteriaSelect("f-subcategory", d.subcategory, subList, "", subDisabled)
            : `<input id="f-subcategory" class="vb-input" value="${esc(d.subcategory)}" placeholder="Подкатегория" />`}</div>
      </div>
    </section>

    <section class="vb-card" style="margin-bottom:18px">
      <h2 class="vb-h2" style="margin-bottom:18px">Желаемые даты</h2>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px">
        <div class="vb-field"><label class="vb-label">С</label><input id="f-date_start" type="date" class="vb-input" value="${esc(d.date_start)}" /></div>
        <div class="vb-field"><label class="vb-label">По</label><input id="f-date_end" type="date" class="vb-input" value="${esc(d.date_end)}" /></div>
      </div>
    </section>

    <section style="border:1px solid #f3c9dd;border-radius:16px;padding:18px 20px;margin-bottom:18px;background:#fdf2f7;display:flex;align-items:center;gap:16px;flex-wrap:wrap">
      <div style="flex:1;min-width:200px">
        <div style="display:flex;align-items:center;gap:8px;font-size:15px;font-weight:700;color:#b3115f">⚡ Авто-оплата</div>
        <p style="margin:6px 0 0;font-size:13px;color:#a05277;line-height:1.45">При включении деньги за визовый сбор спишутся <b>автоматически</b> сразу после успешного бронирования.</p>
      </div>
      <div id="toggle-autopay" style="width:52px;height:30px;border-radius:30px;background:${switchTrack};position:relative;cursor:pointer;transition:background .2s;flex:none">
        <div style="position:absolute;top:3px;left:3px;width:24px;height:24px;border-radius:50%;background:#fff;box-shadow:0 2px 5px rgba(0,0,0,.2);transition:transform .2s;transform:${switchKnob}"></div>
      </div>
    </section>

    <section class="vb-card" style="margin-bottom:24px">
      <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:6px">
        <h2 class="vb-h2" style="margin:0">Заявители</h2>
        <button id="add-applicant" class="vb-btn vb-btn-light" style="padding:8px 13px;font-size:13px">＋ Добавить заявителя</button>
      </div>
      <p style="margin:0 0 18px;font-size:13px;color:var(--muted2)">${esc(aHint)}</p>
      <div style="display:flex;flex-direction:column;gap:16px">${applicants}</div>
    </section>

    ${err}
    <div style="display:flex;gap:12px;justify-content:flex-end;flex-wrap:wrap">
      <button class="vb-btn vb-btn-ghost" data-go="dashboard" style="padding:12px 22px">Отмена</button>
      <button id="create-task" class="vb-btn vb-btn-primary" style="padding:12px 26px">Создать заявку</button>
    </div>
  </main>`;
}
