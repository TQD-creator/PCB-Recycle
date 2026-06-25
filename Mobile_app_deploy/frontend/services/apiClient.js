import axios from "axios";

const RETRYABLE_STATUS = new Set([408, 429, 500, 502, 503, 504]);

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export const createApiClient = (baseURL) => {
    const client = axios.create({
        baseURL,
        timeout: 15000,
        headers: {
            Accept: "application/json",
        },
    });

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
