import React, { useContext, useState } from "react";
import { Alert, FlatList, Image, StyleSheet, Text, TextInput, TouchableOpacity, View } from "react-native";

import { BackendConfigContext, buildBaseUrl } from "../BackendConfigContext";
import { useScanStore } from "../store/useScanStore";

const AnomalyQueueScreen = () => {
    const { backendIp } = useContext(BackendConfigContext);
    const { taskId, triageQueue, decideAnomaly } = useScanStore();
    const [classDrafts, setClassDrafts] = useState({});

    const baseUrl = buildBaseUrl(backendIp);

    const onResolve = async (anomalyIndex, decision) => {
        if (!taskId) {
            Alert.alert("No Active Task", "Run a scan first.");
            return;
        }

        try {
            const approvedClass = classDrafts[anomalyIndex] || undefined;
            const response = await decideAnomaly({
                baseUrl,
                taskId,
                anomalyIndex,
                decision,
                approvedClass,
            });
            Alert.alert("Resolution Saved", response.message);
        } catch (error) {
            Alert.alert("Resolution Failed", "Could not submit anomaly decision.");
        }
    };

    return (
        <View style={styles.container}>
            <FlatList
                data={triageQueue}
                keyExtractor={(item) => `${item.anomaly_index}`}
                contentContainerStyle={styles.list}
                ListEmptyComponent={<Text style={styles.empty}>No anomalies queued for triage.</Text>}
                renderItem={({ item }) => (
                    <View style={styles.card}>
                        <Image source={{ uri: item.crop_url }} style={styles.cropImage} resizeMode="cover" />
                        <Text style={styles.title}>Anomaly #{item.anomaly_index}</Text>
                        <Text style={styles.meta}>YOLO: {item.record.yolo_prelim_guess}</Text>
                        <Text style={styles.meta}>Anchor: {item.record.matched_anchor_class}</Text>
                        <Text style={styles.meta}>Distance: {item.record.faiss_distance.toFixed(4)}</Text>
                        <Text style={styles.reason}>{item.record.reason || "Distance anomaly"}</Text>

                        <TextInput
                            style={styles.input}
                            placeholder="approved class (optional)"
                            placeholderTextColor="#6B7280"
                            value={classDrafts[item.anomaly_index] || ""}
                            onChangeText={(value) =>
                                setClassDrafts((prev) => ({
                                    ...prev,
                                    [item.anomaly_index]: value.trim().toLowerCase(),
                                }))
                            }
                        />

                        <View style={styles.buttonRow}>
                            <TouchableOpacity
                                style={[styles.button, styles.rejectButton]}
                                onPress={() => onResolve(item.anomaly_index, "REJECT")}
                            >
                                <Text style={styles.rejectText}>REJECT</Text>
                            </TouchableOpacity>
                            <TouchableOpacity
                                style={[styles.button, styles.approveButton]}
                                onPress={() => onResolve(item.anomaly_index, "APPROVE")}
                            >
                                <Text style={styles.approveText}>APPROVE</Text>
                            </TouchableOpacity>
                        </View>
                    </View>
                )}
            />
        </View>
    );
};

const styles = StyleSheet.create({
    container: { flex: 1, backgroundColor: "#0A1118" },
    list: { padding: 12, gap: 12 },
    empty: { color: "#94A3B8", textAlign: "center", marginTop: 40 },
    card: {
        backgroundColor: "#111827",
        borderWidth: 1,
        borderColor: "#1F2937",
        borderRadius: 14,
        padding: 12,
    },
    cropImage: {
        width: "100%",
        height: 160,
        borderRadius: 10,
        borderWidth: 1,
        borderColor: "#1E293B",
        marginBottom: 10,
    },
    title: { color: "#F8FAFC", fontWeight: "800", fontSize: 16, marginBottom: 4 },
    meta: { color: "#BFDBFE", marginBottom: 2 },
    reason: { color: "#FCA5A5", marginTop: 6, marginBottom: 8 },
    input: {
        borderWidth: 1,
        borderColor: "#334155",
        borderRadius: 10,
        paddingHorizontal: 10,
        paddingVertical: 8,
        color: "#FFFFFF",
        backgroundColor: "#0F172A",
        marginBottom: 10,
    },
    buttonRow: { flexDirection: "row", gap: 10 },
    button: { flex: 1, borderRadius: 10, paddingVertical: 12, alignItems: "center" },
    rejectButton: { backgroundColor: "#7F1D1D" },
    approveButton: { backgroundColor: "#14532D" },
    rejectText: { color: "#FECACA", fontWeight: "800" },
    approveText: { color: "#BBF7D0", fontWeight: "800" },
});

export default AnomalyQueueScreen;
