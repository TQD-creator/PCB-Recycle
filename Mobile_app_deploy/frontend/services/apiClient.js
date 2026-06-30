import axios from "axios";

const RETRYABLE_STATUS = new Set([408, 429, 500, 502, 503, 504]);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// Module-level token — set on login, cleared on logout
let _authToken = null;
export const setApiToken    = (token) => { _authToken = token; };
export const clearApiToken  = ()      => { _authToken = null; };

export const createApiClient = (baseURL) => {
    const headers = { Accept: "application/json" };
    if (_authToken) headers.Authorization = `Bearer ${_authToken}`;

    const client = axios.create({ baseURL, timeout: 15000, headers });

    client.interceptors.response.use(
        (response) => response,
        async (error) => {
            const config = error.config;
            if (!config) {
                return Promise.reject(error);
            }

            config.__retryCount = config.__retryCount || 0;
            const status = error.response?.status;
            const shouldRetry = !status || RETRYABLE_STATUS.has(status);

            if (!shouldRetry || config.__retryCount >= 3) {
                return Promise.reject(error);
            }

            config.__retryCount += 1;
            await sleep(300 * Math.pow(2, config.__retryCount));
            return client(config);
        }
    );

    return client;
};
