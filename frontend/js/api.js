/* Слой обращения к JSON-API бэкенда. */
import { state } from "./state.js";

export async function api(path, method = "GET", body) {
  const opts = { method, credentials: "same-origin", headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  let data = null;
  try { data = await res.json(); } catch (e) { /* тело пустое */ }
  return { ok: res.ok, status: res.status, data };
}

/* Загрузить справочник и заявки текущего пользователя в state. */
export async function loadAppData() {
  const [opt, tasks] = await Promise.all([api("/api/options"), api("/api/tasks")]);
  // Бэкенд перекрывает вшитый справочник, только если реально что-то вернул.
  if (opt.ok && opt.data && opt.data.centers && opt.data.centers.length) state.options = opt.data;
  if (tasks.ok) state.tasks = tasks.data;
}
