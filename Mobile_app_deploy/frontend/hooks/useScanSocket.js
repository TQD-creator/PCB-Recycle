import { useEffect, useRef } from "react";

import { useScanStore } from "../store/useScanStore";

const toWebSocketUrl = (baseUrl, taskId) => {
    const normalized = (baseUrl || "").replace(/\/+$/, "");
    const socketBase = normalized.replace(/^http/i, "ws");
    return `${socketBase}/api/v2/scan/ws/status/${taskId}`;
};

export const useScanSocket = (baseUrl, taskId) => {
    const socketRef = useRef(null);
    const reconnectRef = useRef(0);
    const retryTimerRef = useRef(null);
    const terminalStateRef = useRef(false);
    const { applySocketPayload, setSocketState } = useScanStore();

    useEffect(() => {
        if (!baseUrl || !taskId) {
            return undefined;
        }

        let isUnmounted = false;

        const connect = () => {
            if (isUnmounted) {
                return;
            }

            const socketUrl = toWebSocketUrl(baseUrl, taskId);
            const socket = new WebSocket(socketUrl);
            socketRef.current = socket;
            setSocketState("CONNECTING");

            socket.onopen = () => {
                reconnectRef.current = 0;
                setSocketState("CONNECTED");
            };

            socket.onmessage = (event) => {
                try {
                    const payload = JSON.parse(event.data);
                    applySocketPayload(payload);

                    if (payload.state === "COMPLETED" || payload.state === "FAILED") {
                        terminalStateRef.current = true;
                        socket.close();
                    }
                } catch (error) {
                    setSocketState("ERROR", "Malformed websocket payload received.");
                }
            };

            socket.onerror = () => {
                setSocketState("ERROR", "WebSocket connection error.");
            };

            socket.onclose = () => {
                socketRef.current = null;
                if (terminalStateRef.current) {
                    setSocketState("DISCONNECTED");
                    return;
                }
                if (isUnmounted) {
                    return;
                }

                const retryCount = reconnectRef.current + 1;
                reconnectRef.current = retryCount;

                if (retryCount <= 5) {
                    setSocketState("RECONNECTING");
                    retryTimerRef.current = setTimeout(connect, Math.min(1000 * retryCount, 5000));
                } else {
                    setSocketState("DISCONNECTED", "WebSocket disconnected after retries.");
                }
            };
        };

        connect();

        return () => {
            isUnmounted = true;
            terminalStateRef.current = false;
            if (retryTimerRef.current) {
                clearTimeout(retryTimerRef.current);
                retryTimerRef.current = null;
            }
            if (socketRef.current) {
                socketRef.current.close();
                socketRef.current = null;
            }
        };
    }, [baseUrl, taskId, applySocketPayload, setSocketState]);
};
