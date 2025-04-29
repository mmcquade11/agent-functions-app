// src/api/prompt.js

import api from "./axios";

// Existing optimizePrompt function
export const optimizePrompt = async (prompt) => {
  const response = await api.post("/prompt/optimize-prompt", { prompt });
  return response.data;
};

// 🔥 New routePrompt function
export const routePrompt = async (prompt) => {
  const response = await api.post("/prompt/route-prompt", { prompt });
  return response.data;
};
