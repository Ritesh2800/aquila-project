// Set VITE_API_URL (e.g. https://my-server:8000) if the API is on a different address.
const BASE = import.meta.env.VITE_API_URL || "";
let key = localStorage.getItem("aquila_key") || "";

export const getKey = () => key;
export function setKey(k) {
  key = k;
  k ? localStorage.setItem("aquila_key", k) : localStorage.removeItem("aquila_key");
}

// <video> and <img> cannot send headers, so media URLs carry the key in the query string.
export const mediaUrl = (u) => (u ? BASE + u + (key ? `?key=${encodeURIComponent(key)}` : "") : "");

async function req(path, opts = {}) {
  const res = await fetch(BASE + path, {
    ...opts,
    headers: { ...(key ? { "X-API-Key": key } : {}), ...(opts.headers || {}) },
  });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const body = await res.json();
      msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {}
    const err = new Error(msg);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export const api = {
  health: () => req("/api/health"),
  check: () => req("/api/auth/check"),
  analyze: (form) => req("/api/analyze", { method: "POST", body: form }),
  job: (id) => req(`/api/jobs/${id}`),
  alerts: () => req("/api/alerts"),
  confirm: (id) => req(`/api/alerts/${id}/confirm`, { method: "POST" }),
  dismiss: (id) => req(`/api/alerts/${id}/dismiss`, { method: "POST" }),
  cleanup: () => req("/api/cleanup", { method: "POST" }),
  testCall: () => req("/api/test-call", { method: "POST" }),
  callStatus: (sid) => req(`/api/call-status/${sid}`),
};
