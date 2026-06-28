/* Вспомогательные функции форматирования и общие виджеты. */
import { SITES, STATUS } from "./state.js";

export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

export function fmtDate(d) {
  if (!d) return "—";
  const p = String(d).split("-");
  return p.length === 3 ? `${p[2]}.${p[1]}.${p[0]}` : d;
}

export function dateRange(t) {
  if (!t.date_start && !t.date_end) return "не указаны";
  return `${fmtDate(t.date_start)} – ${fmtDate(t.date_end)}`;
}

export function plural(n, one, few, many) {
  const m10 = n % 10, m100 = n % 100;
  if (m10 === 1 && m100 !== 11) return one;
  if (m10 >= 2 && m10 <= 4 && (m100 < 10 || m100 >= 20)) return few;
  return many;
}

export const siteLabel = (v) => (SITES.find((s) => s.value === v) || {}).label || "VFS";

export function emptyApplicant() {
  return { first_name: "", surname: "", gender: "", birth_date: "", nationality: "",
    passport_number: "", passport_expiry: "", phone_code: "+7", phone: "", email: "" };
}

export function statusBadge(status) {
  const s = STATUS[status] || { label: status, color: "#5b6478", bg: "#eef1f5" };
  return `<span class="vb-badge" style="background:${s.bg};color:${s.color}">${esc(s.label)}</span>`;
}
