// API client.
//
// The base URL is derived from the page's own path so the same bundle works at
// "/" (standalone Docker) and at "/api/hassio_ingress/<token>/" (HA Ingress),
// where the prefix is only known at runtime.

const appBase = window.location.pathname.replace(/\/[^/]*$/, "/");
export const API_BASE = appBase + "api";

async function request(path, { method = "GET", body, params, raw = false } = {}) {
  const url = new URL(API_BASE + path, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, value);
      }
    });
  }

  const options = { method, headers: {} };
  if (body instanceof FormData) {
    options.body = body;
  } else if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }

  const response = await fetch(url, options);
  if (raw) return response;
  if (!response.ok) {
    let detail = `Fout ${response.status}`;
    try {
      const data = await response.json();
      if (typeof data.detail === "string") detail = data.detail;
      else if (Array.isArray(data.detail)) detail = data.detail.map((d) => d.msg).join("; ");
    } catch {
      /* keep the status-code message */
    }
    throw new Error(detail);
  }
  return response.status === 204 ? null : response.json();
}

export const api = {
  health: () => request("/health"),

  formats: () => request("/imports/formats"),
  imports: () => request("/imports/"),
  upload: (file, formatKey) => {
    const form = new FormData();
    form.append("file", file);
    form.append("format_key", formatKey);
    return request("/imports/upload", { method: "POST", body: form });
  },
  repreview: (id, formatKey) =>
    request(`/imports/${id}/preview`, { method: "POST", params: { format_key: formatKey } }),
  commitImport: (id, formatKey) =>
    request(`/imports/${id}/commit`, { method: "POST", params: { format_key: formatKey } }),
  reimport: (id) => request(`/imports/${id}/reimport`, { method: "POST" }),
  importImpact: (id) => request(`/imports/${id}/impact`),
  deleteImport: (id, deleteTransactions) =>
    request(`/imports/${id}`, { method: "DELETE", params: { delete_transactions: deleteTransactions } }),
  downloadUrl: (id) => `${API_BASE}/imports/${id}/download`,

  accounts: () => request("/accounts/"),
  updateAccount: (id, payload) => request(`/accounts/${id}`, { method: "PATCH", body: payload }),
  rematchTransfers: () => request("/accounts/rematch-transfers", { method: "POST" }),

  transactions: (params) => request("/transactions/", { params }),
  setCategory: (id, categoryId) =>
    request(`/transactions/${id}/category`, { method: "PATCH", body: { category_id: categoryId } }),
  bulkCategory: (ids, categoryId) =>
    request("/transactions/bulk-category", {
      method: "POST",
      body: { transaction_ids: ids, category_id: categoryId },
    }),
  rulePreview: (id, field, value) => request(`/transactions/${id}/rule-preview`, { params: { field, value } }),
  createRuleFrom: (id, payload) => request(`/transactions/${id}/rule`, { method: "POST", body: payload }),
  setNote: (id, note) => request(`/transactions/${id}/note`, { method: "PATCH", body: { note } }),
  unlinkTransfer: (group) => request(`/transactions/transfer-group/${group}`, { method: "DELETE" }),
  exportUrl: (params) => {
    const url = new URL(`${API_BASE}/transactions/export`, window.location.origin);
    Object.entries(params || {}).forEach(([k, v]) => v && url.searchParams.set(k, v));
    return url.toString();
  },

  categories: () => request("/categories/"),
  createCategory: (payload) => request("/categories/", { method: "POST", body: payload }),
  updateCategory: (id, payload) => request(`/categories/${id}`, { method: "PUT", body: payload }),
  deleteCategory: (id) => request(`/categories/${id}`, { method: "DELETE" }),

  rules: (params) => request("/rules/", { params }),
  createRule: (payload) => request("/rules/", { method: "POST", body: payload }),
  updateRule: (id, payload) => request(`/rules/${id}`, { method: "PUT", body: payload }),
  deleteRule: (id) => request(`/rules/${id}`, { method: "DELETE" }),
  reapplyRules: (includeLocked) =>
    request("/rules/reapply", { method: "POST", params: { include_locked: includeLocked } }),

  periodSettings: () => request("/settings/period"),
  savePeriodSettings: (payload) => request("/settings/period", { method: "PUT", body: payload }),
};
