import axios, { AxiosError, AxiosInstance } from "axios";

const client: AxiosInstance = axios.create({
  baseURL: "/api/v1",
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
});

// ── Interceptor de resposta — normaliza erros ─────────────────────────────────
client.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail: string; code: string }>) => {
    const detail =
      error.response?.data?.detail ??
      error.message ??
      "Erro desconhecido.";

    const code =
      error.response?.data?.code ?? "INTERNAL_ERROR";

    // Enriquece o error com campos normalizados para os hooks consumirem
    const normalized = Object.assign(error, {
      normalizedMessage: detail,
      normalizedCode: code,
    });

    return Promise.reject(normalized);
  }
);

export default client;