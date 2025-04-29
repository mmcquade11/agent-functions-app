// src/api/axios.js

import axios from "axios";
import { useAuth0 } from "@auth0/auth0-react";

const api = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1", // your FastAPI backend
});

let getAccessTokenSilentlyFunc = null;

// Hook into Auth0 token
export const setAuthFunctions = (auth0) => {
    getAccessTokenSilentlyFunc = auth0.getAccessTokenSilently;
};

// Axios request interceptor
api.interceptors.request.use(async(config) => {
    if (getAccessTokenSilentlyFunc) {
        try {
            const token = await getAccessTokenSilentlyFunc();
            config.headers.Authorization = `Bearer ${token}`;
        } catch (error) {
            console.error("Failed to attach token", error);
        }
    }
    return config;
});

// Axios response interceptor for 401s
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401)
            {
            window.location.href = "/login";
        }
        return Promise.reject(error);
    }
);

export default api;