import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || '/api/v1';

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
  timeout: 120000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    // Only auto-logout on 401 from non-login endpoints
    // Avoid logging out while the user is filling forms
    if (err.response?.status === 401) {
      const url = err.config?.url || '';
      const isLoginRequest = url.includes('/auth/login') || url.includes('/auth/register');
      if (!isLoginRequest) {
        // Token expired or invalid — clear and redirect
        localStorage.removeItem('token');
        window.location.href = '/login';
      }
    }
    return Promise.reject(err);
  },
);

export default api;
