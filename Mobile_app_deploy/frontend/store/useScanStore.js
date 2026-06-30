import AsyncStorage from "@react-native-async-storage/async-storage";
import { create } from "zustand";

import { clearApiToken, setApiToken } from "../services/apiClient";
import {
    enqueuePendingUpload,
    flushPendingUploads,
    getAuthMe,
    loginUser,
    logoutUser,
    resolveAnomaly,
    uploadScan,
} from "../services/scanService";

export const useScanStore = create((set, get) => ({
    // ── Auth ──────────────────────────────────────────────────────────────────
    token: null,
    role: null,
    username: null,

    restoreAuth: async () => {
        const token    = await AsyncStorage.getItem("auth_token");
        const role     = await AsyncStorage.getItem("auth_role");
        const username = await AsyncStorage.getItem("auth_username");
        if (token && role && username) {
            setApiToken(token);
            set({ token, role, username });
            return true;
        }
        return false;
    },

    login: async (baseUrl, username, password) => {
        const result = await loginUser(baseUrl, { username, password });
        setApiToken(result.token);
        await AsyncStorage.setItem("auth_token",    result.token);
        await AsyncStorage.setItem("auth_role",     result.role);
        await AsyncStorage.setItem("auth_username", result.username);
        set({ token: result.token, role: result.role, username: result.username });
        return result;
    },

    logout: async (baseUrl) => {
        try { await logoutUser(baseUrl); } catch (_) {}
        clearApiToken();
        await AsyncStorage.multiRemove(["auth_token", "auth_role", "auth_username"]);
        set({ token: null, role: null, username: null });
    },

    // ── Scan ──────────────────────────────────────────────────────────────────
    taskId: null,
    scanState: "IDLE",
    stage: "Idle",
    progress: 0,
    error: null,
    imageUrl: null,
    report: null,
    triageQueue: [],
    socketState: "DISCONNECTED",
    socketError: null,

    setReport: (report) => set({ report }),

    applySocketPayload: (payload) => {
        set((state) => ({
            taskId:      payload.task_id    || state.taskId,
            scanState:   payload.state      || state.scanState,
            stage:       payload.stage      || state.stage,
            progress:    typeof payload.progress === "number" ? payload.progress : state.progress,
            error:       payload.error      || null,
            imageUrl:    payload.image_url  || state.imageUrl,
            report:      payload.report     || state.report,
            triageQueue: payload.triage_queue || state.triageQueue,
        }));
    },

    setSocketState: (socketState, socketError = null) => set({ socketState, socketError }),

    resetScan: () => set({
        taskId: null, scanState: "IDLE", stage: "Idle", progress: 0,
        error: null, imageUrl: null, report: null, triageQueue: [],
        socketState: "DISCONNECTED", socketError: null,
    }),

    uploadAndQueueScan: async ({ baseUrl, imageUri }) => {
        set({ scanState: "UPLOADING", stage: "Uploading", progress: 5, error: null });
        try {
            const accepted = await uploadScan(baseUrl, imageUri);
            set({ taskId: accepted.task_id, scanState: "QUEUED", stage: accepted.message || "Queued", progress: 10 });
            return accepted.task_id;
        } catch (error) {
            await enqueuePendingUpload({ imageUri, fileName: `queued_${Date.now()}.jpg` });
            set({ scanState: "QUEUED_OFFLINE", stage: "Upload deferred (offline queue)", progress: 0, error: "Network unstable. Scan cached for retry." });
            return null;
        }
    },

    syncPendingScans: async (baseUrl) => {
        const taskIds = await flushPendingUploads(baseUrl);
        if (taskIds.length > 0) {
            set({ taskId: taskIds[0], scanState: "QUEUED", stage: "Re-uploaded from local cache", progress: 10, error: null });
        }
        return taskIds;
    },

    decideAnomaly: async ({ baseUrl, taskId, anomalyIndex, decision, approvedClass }) => {
        const response = await resolveAnomaly(baseUrl, {
            task_id: taskId, anomaly_index: anomalyIndex,
            decision, approved_class: approvedClass,
        });
        set((state) => ({ triageQueue: state.triageQueue.filter((item) => item.anomaly_index !== anomalyIndex) }));
        return response;
    },
}));
