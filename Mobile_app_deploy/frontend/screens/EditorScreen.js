import React, { useContext, useEffect, useState } from "react";
import { ActivityIndicator, Alert, Image, StyleSheet, Text, View } from "react-native";

import { BackendConfigContext, buildBaseUrl } from "../BackendConfigContext";
import { submitCorrection } from "../services/scanService";
import { useScanStore } from "../store/useScanStore";
import BoundingBoxEditor from "./BoundingBoxEditor";

const EditorScreen = ({ navigation }) => {
    const { backendIp } = useContext(BackendConfigContext);
    const { imageUrl, report, taskId } = useScanStore();
    const baseUrl = buildBaseUrl(backendIp);

    const [sourceSize, setSourceSize] = useState(null); // null = loading
    const [submitting, setSubmitting] = useState(false);

    // Resolve image pixel dimensions so BoundingBoxEditor can scale correctly
    useEffect(() => {
        if (!imageUrl) return;
        Image.getSize(
            imageUrl,
            (w, h) => setSourceSize({ width: w, height: h }),
            () => {
                Alert.alert("Image Error", "Could not load board image. Check backend connection.");
                navigation.goBack();
            }
        );
    }, [imageUrl]);

    const verifiedBoxes = (report?.verified_components ?? []).map((c) => ({
        bbox: c.bbox,
        label: c.matched_anchor_class,
    }));

    const anomalyBoxes = (report?.anomaly_queue ?? []).map((c, i) => ({
        bbox: c.bbox,
        label: c.matched_anchor_class,
        anomaly_index: i,
    }));

    const handleSave = async (corrections) => {
        if (!corrections || corrections.length === 0) {
            Alert.alert("Nothing to submit", "Modify or draw a box first.");
            return;
        }
        if (!taskId) {
            Alert.alert("Error", "No active scan task ID. Return to Scanner.");
            return;
        }

        setSubmitting(true);
        try {
            const result = await submitCorrection(baseUrl, {
                task_id: taskId,
                image_url: imageUrl,
                corrections,
            });
            Alert.alert(
                "Submitted",
                `${result.count} correction${result.count !== 1 ? "s" : ""} saved with status PENDING.\n\nAn administrator can approve or reject them from the corrections queue.`,
                [{ text: "OK", onPress: () => navigation.goBack() }]
            );
        } catch (err) {
            Alert.alert("Submission Failed", "Could not reach backend. Try again.");
        } finally {
            setSubmitting(false);
        }
    };

    // ── Guard states ─────────────────────────────────────────────────────────
    if (!imageUrl || !report) {
        return (
            <View style={styles.center}>
                <Text style={styles.warn}>No scan loaded.</Text>
                <Text style={styles.hint}>Complete a scan first, then return here.</Text>
            </View>
        );
    }

    if (!sourceSize) {
        return (
            <View style={styles.center}>
                <ActivityIndicator size="large" color="#10B981" />
                <Text style={styles.hint}>Loading board image…</Text>
            </View>
        );
    }

    if (submitting) {
        return (
            <View style={styles.center}>
                <ActivityIndicator size="large" color="#10B981" />
                <Text style={styles.hint}>Submitting corrections…</Text>
            </View>
        );
    }

    return (
        <BoundingBoxEditor
            imageUri={imageUrl}
            sourceWidth={sourceSize.width}
            sourceHeight={sourceSize.height}
            verifiedBoxes={verifiedBoxes}
            anomalyBoxes={anomalyBoxes}
            onSave={handleSave}
        />
    );
};

const styles = StyleSheet.create({
    center: { flex: 1, backgroundColor: "#0A1118", alignItems: "center", justifyContent: "center", gap: 12 },
    warn: { color: "#F8FAFC", fontSize: 18, fontWeight: "800" },
    hint: { color: "#94A3B8", fontSize: 14, textAlign: "center", paddingHorizontal: 32 },
});

export default EditorScreen;
