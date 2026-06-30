import React, { useCallback, useContext, useEffect, useMemo, useState } from "react";
import { Image, ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { useIsFocused } from "@react-navigation/native";
import Svg, { Rect } from "react-native-svg";

import { BackendConfigContext, buildBaseUrl } from "../BackendConfigContext";
import { fetchScanStatus } from "../services/scanService";
import { useScanStore } from "../store/useScanStore";

const InventoryDashboardScreen = () => {
    const { report, imageUrl, taskId, applySocketPayload } = useScanStore();
    const { backendIp } = useContext(BackendConfigContext);
    const baseUrl = buildBaseUrl(backendIp);
    const isFocused = useIsFocused();
    const [fetching, setFetching] = useState(false);
    const [fetchError, setFetchError] = useState(null);
    const [sourceSize, setSourceSize] = useState({ width: 1, height: 1 });
    const [canvasSize, setCanvasSize] = useState({ width: 1, height: 1 });

    const refreshFromApi = useCallback(async () => {
        if (!baseUrl || !taskId || fetching) return;
        setFetching(true);
        setFetchError(null);
        try {
            const data = await fetchScanStatus(baseUrl, taskId);
            applySocketPayload({
                state: data.state,
                stage: data.stage,
                progress: data.progress,
                image_url: data.image_url,
                report: data.report,
                triage_queue: data.triage_queue,
            });
        } catch (err) {
            setFetchError("Could not fetch results. Check backend connection.");
        } finally {
            setFetching(false);
        }
    }, [baseUrl, taskId, fetching, applySocketPayload]);

    // Auto-fetch when screen is focused and report is missing but taskId exists
    useEffect(() => {
        if (isFocused && taskId && !report) {
            refreshFromApi();
        }
    }, [isFocused, taskId, report]);

    useEffect(() => {
        if (!imageUrl) {
            return;
        }
        Image.getSize(
            imageUrl,
            (width, height) => setSourceSize({ width, height }),
            () => setSourceSize({ width: 1, height: 1 })
        );
    }, [imageUrl]);

    const counts = useMemo(() => {
        if (!report?.verified_counts) {
            return [];
        }
        return Object.entries(report.verified_counts).map(([name, value]) => ({ name, value }));
    }, [report]);

    const overlayItems = useMemo(() => {
        if (!report) {
            return [];
        }
        return [
            ...report.verified_components.map((item) => ({ color: "#16A34A", item })),
            ...report.anomaly_queue.map((item) => ({ color: "#DC2626", item })),
        ];
    }, [report]);

    // resizeMode="contain" letterboxes the image inside the square container.
    // Compute the actual rendered pixel rect so boxes land on the image, not the empty space.
    const imageAspect = sourceSize.width / sourceSize.height;
    const containerAspect = canvasSize.width / canvasSize.height;

    let renderedWidth, renderedHeight, offsetX, offsetY;
    if (imageAspect > containerAspect) {
        // Landscape image → fits to width, empty space top + bottom
        renderedWidth = canvasSize.width;
        renderedHeight = canvasSize.width / imageAspect;
        offsetX = 0;
        offsetY = (canvasSize.height - renderedHeight) / 2;
    } else {
        // Portrait / square image → fits to height, empty space left + right
        renderedHeight = canvasSize.height;
        renderedWidth = canvasSize.height * imageAspect;
        offsetX = (canvasSize.width - renderedWidth) / 2;
        offsetY = 0;
    }

    const xScale = renderedWidth / sourceSize.width;
    const yScale = renderedHeight / sourceSize.height;

    return (
        <ScrollView style={styles.container} contentContainerStyle={styles.content}>
            <View style={styles.headerRow}>
                <Text style={styles.headerTitle}>Inventory Dashboard</Text>
                <TouchableOpacity
                    style={[styles.refreshBtn, fetching && styles.refreshBtnDisabled]}
                    onPress={refreshFromApi}
                    disabled={fetching || !taskId}
                >
                    <Text style={styles.refreshText}>{fetching ? "Loading..." : "Refresh"}</Text>
                </TouchableOpacity>
            </View>

            {fetchError && (
                <View style={styles.errorBox}>
                    <Text style={styles.errorText}>{fetchError}</Text>
                </View>
            )}

            <View style={styles.card}>
                <Text style={styles.title}>Verified Component Counts</Text>
                {counts.length === 0 ? (
                    <Text style={styles.empty}>
                        {taskId
                            ? fetching
                                ? "Fetching results..."
                                : "No verified components found. Tap Refresh if scan just completed."
                            : "No report loaded yet. Run a scan from Scanner tab."}
                    </Text>
                ) : (
                    counts.map((entry) => (
                        <View key={entry.name} style={styles.row}>
                            <Text style={styles.key}>{entry.name.toUpperCase()}</Text>
                            <Text style={styles.value}>{entry.value}</Text>
                        </View>
                    ))
                )}
            </View>

            <View style={styles.card}>
                <Text style={styles.title}>Board Overlay Preview</Text>
                {!imageUrl ? (
                    <Text style={styles.empty}>Completed scan image will appear here.</Text>
                ) : (
                    <View
                        style={styles.imageWrap}
                        onLayout={(event) => {
                            const { width, height } = event.nativeEvent.layout;
                            setCanvasSize({ width, height });
                        }}
                    >
                        <Image source={{ uri: imageUrl }} style={styles.image} resizeMode="contain" />
                        <Svg style={StyleSheet.absoluteFill}>
                            {overlayItems.map((entry, idx) => {
                                const [x1, y1, x2, y2] = entry.item.bbox;
                                return (
                                    <Rect
                                        key={`${entry.item.status}_${idx}`}
                                        x={x1 * xScale + offsetX}
                                        y={y1 * yScale + offsetY}
                                        width={(x2 - x1) * xScale}
                                        height={(y2 - y1) * yScale}
                                        stroke={entry.color}
                                        strokeWidth={2}
                                        fill="transparent"
                                    />
                                );
                            })}
                        </Svg>
                    </View>
                )}
            </View>
        </ScrollView>
    );
};

const styles = StyleSheet.create({
    container: { flex: 1, backgroundColor: "#0A1118" },
    content: { padding: 12, gap: 12 },
    headerRow: {
        flexDirection: "row",
        justifyContent: "space-between",
        alignItems: "center",
        paddingVertical: 8,
    },
    headerTitle: { color: "#F8FAFC", fontWeight: "800", fontSize: 18 },
    refreshBtn: {
        backgroundColor: "#1F2937",
        borderRadius: 10,
        paddingHorizontal: 14,
        paddingVertical: 8,
        borderWidth: 1,
        borderColor: "#334155",
    },
    refreshBtnDisabled: { opacity: 0.4 },
    refreshText: { color: "#93C5FD", fontWeight: "700", fontSize: 13 },
    errorBox: {
        backgroundColor: "#7F1D1D",
        borderRadius: 8,
        padding: 10,
        borderWidth: 1,
        borderColor: "#B91C1C",
    },
    errorText: { color: "#FECACA", fontSize: 13 },
    card: {
        backgroundColor: "#111827",
        borderRadius: 14,
        borderWidth: 1,
        borderColor: "#1F2937",
        padding: 14,
    },
    title: { color: "#F8FAFC", fontWeight: "800", fontSize: 16, marginBottom: 12 },
    empty: { color: "#94A3B8" },
    row: {
        flexDirection: "row",
        justifyContent: "space-between",
        alignItems: "center",
        paddingVertical: 8,
        borderBottomWidth: 1,
        borderBottomColor: "#1F2937",
    },
    key: { color: "#BFDBFE", fontWeight: "700" },
    value: { color: "#10B981", fontWeight: "800", fontSize: 16 },
    imageWrap: {
        borderRadius: 12,
        overflow: "hidden",
        borderWidth: 1,
        borderColor: "#223243",
        backgroundColor: "#020617",
        width: "100%",
        aspectRatio: 1,
    },
    image: { width: "100%", height: "100%" },
});

export default InventoryDashboardScreen;
