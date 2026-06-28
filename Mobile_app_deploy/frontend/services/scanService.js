import AsyncStorage from "@react-native-async-storage/async-storage";
import NetInfo from "@react-native-community/netinfo";

import { createApiClient } from "./apiClient";

const PENDING_UPLOADS_KEY = "pending_uploads_v2";

const loadPendingUploads = async () => {
    const raw = await AsyncStorage.getItem(PENDING_UPLOADS_KEY);
    return raw ? JSON.parse(raw) : [];
};

const savePendingUploads = async (queue) => {
    await AsyncStorage.setItem(PENDING_UPLOADS_KEY, JSON.stringify(queue));
};

export const enqueuePendingUpload = async (payload) => {
    const queue = await loadPendingUploads();
    queue.push(payload);
    await savePendingUploads(queue);
};

export const flushPendingUploads = async (baseUrl) => {
    const netState = await NetInfo.fetch();
    if (!netState.isConnected || !baseUrl) {
        return [];
    }

    const queue = await loadPendingUploads();
    if (queue.length === 0) {
        return [];
    }

    const client = createApiClient(baseUrl);
    const survivors = [];
    const uploadedTaskIds = [];

    for (const item of queue) {
        try {
            const formData = new FormData();
            formData.append("file", {
                uri: item.imageUri,
                name: item.fileName,
                type: "image/jpeg",
            });

            const response = await client.post("/api/v2/scan/upload", formData, {
                headers: { "Content-Type": "multipart/form-data" },
            });

            uploadedTaskIds.push(response.data.task_id);
        } catch (error) {
            survivors.push(item);
        }
    }

    await savePendingUploads(survivors);
    return uploadedTaskIds;
};

export const uploadScan = async (baseUrl, imageUri) => {
    const client = createApiClient(baseUrl);
    const fileName = `scan_${Date.now()}.jpg`;

    const formData = new FormData();
    formData.append("file", {
        uri: imageUri,
        name: fileName,
        type: "image/jpeg",
    });

    const response = await client.post("/api/v2/scan/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
    });

    return response.data;
};

export const resolveAnomaly = async (baseUrl, payload) => {
    const client = createApiClient(baseUrl);
    const response = await client.post("/api/v2/anchors/resolve", payload);
    return response.data;
};
export const resolveAnomalyApi = async (baseUrl, payload) => {
    // payload should look like: { task_id, anomaly_index, decision, approved_class }
    const response = await fetch(`${baseUrl}/api/v2/anchors/resolve`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
    });

    if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || "Failed to resolve anomaly via API.");
    }

    return await response.json();
}