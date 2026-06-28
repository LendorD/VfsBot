/* Экран входа / регистрации. */
import { state } from "../state.js";
import { esc } from "../utils.js";

export function authHTML() {
  const isLogin = state.screen === "login";
  const title = isLogin ? "Вход в кабинет" : "Создать аккаунт";
  const subtitle = isLogin ? "Войдите, чтобы управлять заявками" : "Пара секунд — и можно создавать заявки";
  const btn = isLogin ? "Войти" : "Зарегистрироваться";
  const switchText = isLogin ? "Нет аккаунта?" : "Уже есть аккаунт?";
  const switchLink = isLogin ? "Зарегистрироваться" : "Войти";
  const err = state.authError
    ? `<div style="display:flex;align-items:center;gap:8px;background:#fdeceb;border:1px solid #f6cfcc;color:#b6322b;font-size:13px;font-weight:500;padding:10px 12px;border-radius:10px;margin-bottom:16px"><span style="width:6px;height:6px;border-radius:50%;background:#c2342d"></span>${esc(state.authError)}</div>`
    : "";
  return `
  <main style="flex:1;display:flex;align-items:center;justify-content:center;padding:32px 20px;background:radial-gradient(1200px 500px at 50% -10%,#e3e9fb 0%,#eef1f7 55%)">
    <div class="vb-pop" style="width:100%;max-width:418px">
      <div style="display:flex;flex-direction:column;align-items:center;gap:14px;margin-bottom:26px">
        <div style="width:52px;height:52px;border-radius:15px;background:var(--primary);display:flex;align-items:center;justify-content:center;color:#fff;font-weight:800;font-size:20px;box-shadow:0 10px 26px rgba(48,86,211,.34)">VB</div>
        <div style="text-align:center">
          <div style="font-weight:700;font-size:21px">VisaBooking</div>
          <div style="font-size:13.5px;color:var(--muted);margin-top:3px">Автоматическая запись на визу</div>
        </div>
      </div>
      <div style="background:#fff;border:1px solid var(--card-bd);border-radius:18px;padding:30px 28px;box-shadow:0 18px 50px -22px rgba(28,40,80,.28)">
        <h1 style="margin:0 0 4px;font-size:20px;font-weight:700">${esc(title)}</h1>
        <p style="margin:0 0 22px;font-size:13.5px;color:var(--muted)">${esc(subtitle)}</p>
        ${err}
        <div class="vb-field" style="margin-bottom:14px">
          <label class="vb-label">${isLogin ? "Email или логин" : "Email"}</label>
          <input id="auth-email" class="vb-input" type="text" placeholder="${isLogin ? "admin или you@example.com" : "you@example.com"}" />
        </div>
        <div class="vb-field" style="margin-bottom:22px">
          <label class="vb-label">Пароль</label>
          <input id="auth-password" class="vb-input" type="password" placeholder="••••••••" />
        </div>
        <button id="auth-submit" class="vb-btn vb-btn-primary" style="width:100%;padding:12px">${esc(btn)}</button>
        <div style="text-align:center;margin-top:18px;font-size:13.5px;color:var(--muted)">
          ${esc(switchText)} <span id="auth-switch" style="color:var(--primary);font-weight:600;cursor:pointer">${esc(switchLink)}</span>
        </div>
      </div>
    </div>
  </main>`;
}
