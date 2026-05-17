import axios from "axios";

// Resolve API base from page URL so the app works at "/" (standalone docker)
// AND under HA Ingress at "/api/hassio_ingress/<token>/" (dynamic prefix).
const appBase = window.location.pathname.replace(/\/[^/]*$/, "/");
const api = axios.create({ baseURL: appBase + "api" });

export const getDashboardStats = (year, month) =>
  api.get("/dashboard/stats", { params: { year, month } }).then((r) => r.data);

export const getDashboardTrend = (months = 6) =>
  api.get("/dashboard/trend", { params: { months } }).then((r) => r.data);

export const getDashboardByCategory = (year, month) =>
  api.get("/dashboard/by-category", { params: { year, month } }).then((r) => r.data);

export const getBalanceHistory = (days = 90) =>
  api.get("/dashboard/balance-history", { params: { days } }).then((r) => r.data);

export const getTransactions = (params) =>
  api.get("/transactions/", { params }).then((r) => r.data);

export const setTransactionCategory = (id, categoryId) =>
  api.patch(`/transactions/${id}/category`, null, { params: { category_id: categoryId } });

export const getTransactionIds = (params) =>
  api.get("/transactions/ids", { params }).then((r) => r.data);

export const bulkSetCategory = (transactionIds, categoryId) =>
  api.post("/transactions/bulk-category", {
    transaction_ids: transactionIds,
    category_id: categoryId,
  }).then((r) => r.data);

export const getDashboardSettings = () =>
  api.get("/dashboard/settings").then((r) => r.data);

export const saveDashboardSettings = (monthStartDay) =>
  api.post("/dashboard/settings", null, { params: { month_start_day: monthStartDay } }).then((r) => r.data);

export const deleteTransaction = (id) =>
  api.delete(`/transactions/${id}`);

export const uploadBankStatement = (file) => {
  const form = new FormData();
  form.append("file", file);
  return api.post("/transactions/upload", form).then((r) => r.data);
};

export const getCategories = () =>
  api.get("/categories/").then((r) => r.data);

export const createCategory = (data) =>
  api.post("/categories/", data).then((r) => r.data);

export const updateCategory = (id, data) =>
  api.put(`/categories/${id}`, data).then((r) => r.data);

export const deleteCategory = (id) =>
  api.delete(`/categories/${id}`);

export const getBudgetProgress = (year, month) =>
  api.get("/budgets/progress", { params: { year, month } }).then((r) => r.data);

export const getBudgets = (year, month) =>
  api.get("/budgets/", { params: { year, month } }).then((r) => r.data);

export const upsertBudget = (data) =>
  api.post("/budgets/", data).then((r) => r.data);

export const deleteBudget = (id) =>
  api.delete(`/budgets/${id}`);

export const getCAOScales = () =>
  api.get("/cao/scales").then((r) => r.data);

export const upsertCAOScale = (data) =>
  api.post("/cao/scales", data).then((r) => r.data);

export const getCAOProjection = (fwgScale, currentStep, years = 10) =>
  api.get("/cao/projection", { params: { fwg_scale: fwgScale, current_step: currentStep, years } }).then((r) => r.data);

export const getCAOSettings = () =>
  api.get("/cao/settings").then((r) => r.data);

export const saveCAOSettings = (fwgScale, currentStep) =>
  api.post("/cao/settings", null, { params: { fwg_scale: fwgScale, current_step: currentStep } });
