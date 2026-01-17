import axios from "axios";
import config from "@/config";
import { getAuthHeader } from "./authToken";

export const http = axios.create({
  baseURL: config.backendUrl,
  timeout: 15000,
  headers: {
    "Content-Type": "application/json",
  },
});

http.interceptors.request.use((requestConfig) => {
  const authHeader = getAuthHeader();
  if (authHeader) {
    requestConfig.headers.Authorization = authHeader;
  }
  return requestConfig;
},
(error) => {
  return Promise.reject(error);
});
