import React, { useEffect, useMemo, useState } from "react";
import { Image, ScrollView, StyleSheet, Text, View } from "react-native";
import Svg, { Rect } from "react-native-svg";

import { useScanStore } from "../store/useScanStore";

const InventoryDashboardScreen = () => {
    const { report, imageUrl } = useScanStore();
    const [sourceSize, setSourceSize] = useState({ width: 1, height: 1 });
    const [canvasSize, setCanvasSize] = useState({ width: 1, height: 1 });

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

    const xScale = canvasSize.width / sourceSize.width;
    const yScale = canvasSize.height / sourceSize.height;

    return (
        <ScrollView style={styles.container} contentContainerStyle={styles.content}>
            <View style={styles.card}>
                <Text style={styles.title}>Verified Component Counts</Text>
                {counts.length === 0 ? (
                    <Text style={styles.empty}>No report loaded yet. Run a scan from Scanner tab.</Text>
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
                                        x={x1 * xScale}
                                        y={y1 * yScale}
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
