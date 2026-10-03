import axios from "axios";

const client = axios.create({
  baseURL: "/api",
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
});

/** Redirect expired sessions. @param error API failure. @returns Rejected request. @throws Original error. */
client.interceptors.response.use(undefined, (error) => {
  if (error.response?.status === 401 && window.location.pathname !== "/signin") {
    window.location.assign(`/signin?next=${encodeURIComponent(window.location.pathname + window.location.search)}`);
  }
  return Promise.reject(error);
});

export default client;