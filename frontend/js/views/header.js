/* Шапка кабинета (показывается на экранах dashboard/new/detail). */
import { state } from "../state.js";
import { esc } from "../utils.js";

export function headerHTML() {
  if (!state.me || !["dashboard", "new", "detail"].includes(state.screen)) return "";
  const initial = (state.me[0] || "?").toUpperCase();
  return `
  <header class="vb-header">
    <div class="vb-header-in">
      <div id="nav-logo" style="display:flex;align-items:center;gap:10px;cursor:pointer">
        <div class="vb-logo-badge">VB</div>
        <span style="font-weight:700;font-size:17px">VisaBooking</span>
      </div>
      <div style="flex:1"></div>
      <div style="display:flex;align-items:center;gap:14px">
        <div style="display:flex;align-items:center;gap:9px">
          <div class="vb-avatar">${esc(initial)}</div>
          <span style="font-size:13.5px;color:var(--label);font-weight:500">${esc(state.me)}</span>
        </div>
        <button id="nav-logout" class="vb-btn vb-btn-ghost" style="padding:8px 14px;font-size:13px">Выйти</button>
      </div>
    </div>
  </header>`;
}
