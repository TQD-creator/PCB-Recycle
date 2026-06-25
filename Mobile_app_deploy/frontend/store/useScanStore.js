import { create } from "zustand";

import {
    enqueuePendingUpload,
    flushPendingUploads,
    resolveAnomaly,
    uploadScan,
} from "../services/scanService";

export const useScanStore = create((set, get) => ({
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
            taskId: payload.task_id || state.taskId,
            scanState: payload.state || state.scanState,
            stage: payload.stage || state.stage,
            progress: typeof payload.progress === "number" ? payload.progress : state.progress,
            error: payload.error || null,
            imageUrl: payload.image_url || state.imageUrl,
            report: payload.report || state.report,
            triageQueue: payload.triage_queue || state.triageQueue,
        }));
    },

    setSocketState: (socketState, socketError = null) => set({ socketState, socketError }),

    resetScan: () => {
        set({
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
        });
    },

    uploadAndQueueScan: async ({ baseUrl, imageUri }) => {
        set({ scanState: "UPLOADING", stage: "Uploading", progress: 5, error: null });
        try {
            const accepted = await uploadScan(baseUrl, imageUri);
            set({
                taskId: accepted.task_id,
                scanState: "QUEUED",
                stage: accepted.message || "Queued",
                progress: 10,
            });
            return accepted.task_id;
        } catch (error) {
            await enqueuePendingUpload({
                imageUri,
                fileName: `queued_${Date.now()}.jpg`,
            });
            set({
                scanState: "QUEUED_OFFLINE",
                stage: "Upload deferred (offline queue)",
                progress: 0,
                error: "Network unstable. Scan cached for retry.",
            });
            return null;
        }
    },

    syncPendingScans: async (baseUrl) => {
        const taskIds = await flushPendingUploads(baseUrl);
        if (taskIds.length > 0) {
            set({
                taskId: taskIds[0],
                scanState: "QUEUED",
                stage: "Re-uploaded from local cache",
                progress: 10,
                error: null,
            });
        }
        return taskIds;
    },

    decideAnomaly: async ({ baseUrl, taskId, anomalyIndex, decision, approvedClass }) => {
        const response = await resolveAnomaly(baseUrl, {
            task_id: taskId,
            anomaly_index: anomalyIndex,
            decision,
            approved_class: approvedClass,
        });

        const queue = [...get().triageQueue];
        const nextQueue = queue.filter((item) => item.anomaly_index !== anomalyIndex);
        set({ triageQueue: nextQueue });
        return response;
    },
}));
