import React, { useContext, useState } from "react";
import { Alert, FlatList, Image, StyleSheet, Text, TextInput, TouchableOpacity, View } from "react-native";

import { BackendConfigContext, buildBaseUrl } from "../BackendConfigContext";
import { useScanStore } from "../store/useScanStore";

const AnomalyQueueScreen = ({ navigation }) => {
    const { backendIp } = useContext(BackendConfigContext);
    const { taskId, triageQueue, report, decideAnomaly } = useScanStore();
    const [classDrafts, setClassDrafts] = useState({});
    const [busy, setBusy] = useState({});

    const baseUrl = buildBaseUrl(backendIp);

    const onResolve = async (anomalyIndex, decision) => {
        if (!taskId) {
            Alert.alert("No Active Task", "Run a scan first.");
            return;
        }
        setBusy((prev) => ({ ...prev, [anomalyIndex]: true }));
        try {
            const approvedClass = classDrafts[anomalyIndex] || undefined;
            const response = await decideAnomaly({ baseUrl, taskId, anomalyIndex, decision, approvedClass });
            Alert.alert("Saved", response.message || "Decision recorded.");
        } catch {
            Alert.alert("Failed", "Could not submit decision. Check backend connection.");
        } finally {
            setBusy((prev) => ({ ...prev, [anomalyIndex]: false }));
        }
    };

    const onEditOnBoard = () => {
        if (!taskId) {
            Alert.alert("No Active Task", "Run a scan first.");
            return;
        }
        navigation.navigate("Editor");
    };

    // Show the editor button whenever a scan report is loaded in the store
    const canEdit = !!(report || taskId);

    return (
        <View style={styles.container}>
            {/* Always-visible header button — shown whenever a scan has been done */}
            <TouchableOpacity
                style={[styles.boardButton, !canEdit && styles.boardButtonDisabled]}
                onPress={onEditOnBoard}
                disabled={!canEdit}
            >
                <Text style={styles.boardButtonText}>
                    {canEdit ? "✏  Edit Boxes on Full Board" : "Run a scan first"}
                </Text>
            </TouchableOpacity>

            <FlatList
                data={triageQueue}
                keyExtractor={(item) => `${item.anomaly_index}`}
                contentContainerStyle={styles.list}
                ListEmptyComponent={
                    <View style={styles.emptyWrap}>
                        <Text style={styles.empty}>No anomalies queued for triage.</Text>
                        <Text style={styles.emptyHint}>Run a scan — anomalies will appear here for review.</Text>
                    </View>
                }
                renderItem={({ item }) => (
                    <View style={styles.card}>
                        <Image source={{ uri: item.crop_url }} style={styles.cropImage} resizeMode="cover" />

                        <View style={styles.badgeRow}>
                            <Text style={styles.badgeIndex}>ANOMALY #{item.anomaly_index}</Text>
                            <Text style={styles.badgeDist}>L2 {item.record.faiss_distance.toFixed(4)}</Text>
                        </View>

                        <View style={styles.metaGrid}>
                            <View style={styles.metaCell}>
                                <Text style={styles.metaLabel}>YOLO GUESS</Text>
                                <Text style={styles.metaValue}>{item.record.yolo_prelim_guess}</Text>
                            </View>
                            <View style={styles.metaCell}>
                                <Text style={styles.metaLabel}>NEAREST ANCHOR</Text>
                                <Text style={styles.metaValue}>{item.record.matched_anchor_class}</Text>
                            </View>
                        </View>

                        <Text style={styles.reason}>{item.record.reason || "L2 distance exceeded threshold"}</Text>

                        <TextInput
                            style={styles.input}
                            placeholder="Override class label (optional)"
                            placeholderTextColor="#6B7280"
                            value={classDrafts[item.anomaly_index] || ""}
                            onChangeText={(v) =>
                                setClassDrafts((prev) => ({ ...prev, [item.anomaly_index]: v.trim().toLowerCase() }))
                            }
                        />

                        <View style={styles.buttonRow}>
                            <TouchableOpacity
                                style={[styles.button, styles.rejectButton, busy[item.anomaly_index] && styles.disabled]}
                                onPress={() => onResolve(item.anomaly_index, "REJECT")}
                                disabled={!!busy[item.anomaly_index]}
                            >
                                <Text style={styles.rejectText}>REJECT</Text>
                            </TouchableOpacity>
                            <TouchableOpacity
                                style={[styles.button, styles.approveButton, busy[item.anomaly_index] && styles.disabled]}
                                onPress={() => onResolve(item.anomaly_index, "APPROVE")}
                                disabled={!!busy[item.anomaly_index]}
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
    emptyWrap: { alignItems: "center", marginTop: 60, gap: 8 },
    empty: { color: "#94A3B8", fontSize: 16, fontWeight: "700" },
    emptyHint: { color: "#475569", fontSize: 13, textAlign: "center", paddingHorizontal: 32 },
    boardButton: {
        backgroundColor: "#1E3A5F",
        borderRadius: 0,
        paddingVertical: 16,
        alignItems: "center",
        borderBottomWidth: 1,
        borderColor: "#2979FF",
    },
    boardButtonDisabled: { backgroundColor: "#111827", borderColor: "#1F2937" },
    boardButtonText: { color: "#93C5FD", fontWeight: "800", fontSize: 15, letterSpacing: 0.4 },
    card: {
        backgroundColor: "#111827",
        borderWidth: 1,
        borderColor: "#1F2937",
        borderRadius: 14,
        padding: 12,
        gap: 8,
    },
    cropImage: {
        width: "100%",
        height: 160,
        borderRadius: 10,
        borderWidth: 1,
        borderColor: "#1E293B",
    },
    badgeRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
    badgeIndex: { color: "#F8FAFC", fontWeight: "800", fontSize: 15 },
    badgeDist: { color: "#FCD34D", fontWeight: "700", fontSize: 13, fontFamily: "monospace" },
    metaGrid: { flexDirection: "row", gap: 10 },
    metaCell: { flex: 1, backgroundColor: "#0F172A", borderRadius: 8, padding: 8 },
    metaLabel: { color: "#64748B", fontSize: 10, fontWeight: "700", letterSpacing: 1, textTransform: "uppercase" },
    metaValue: { color: "#BFDBFE", fontWeight: "700", marginTop: 2 },
    reason: { color: "#FCA5A5", fontSize: 12 },
    input: {
        borderWidth: 1,
        borderColor: "#334155",
        borderRadius: 10,
        paddingHorizontal: 10,
        paddingVertical: 8,
        color: "#FFFFFF",
        backgroundColor: "#0F172A",
    },
    buttonRow: { flexDirection: "row", gap: 10 },
    button: { flex: 1, borderRadius: 10, paddingVertical: 12, alignItems: "center" },
    rejectButton: { backgroundColor: "#7F1D1D" },
    approveButton: { backgroundColor: "#14532D" },
    rejectText: { color: "#FECACA", fontWeight: "800" },
    approveText: { color: "#BBF7D0", fontWeight: "800" },
    disabled: { opacity: 0.4 },
});

export default AnomalyQueueScreen;
