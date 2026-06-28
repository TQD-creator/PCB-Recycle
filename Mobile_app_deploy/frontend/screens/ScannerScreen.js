import React, { useContext, useEffect, useRef, useState } from "react";
import { CameraView, useCameraPermissions } from "expo-camera";
import { ActivityIndicator, Alert, Image, StyleSheet, Text, TextInput, TouchableOpacity, View } from "react-native";
import { useIsFocused } from "@react-navigation/native";
import * as ImageManipulator from "expo-image-manipulator";
import * as ImagePicker from "expo-image-picker";

import { BackendConfigContext, buildBaseUrl } from "../BackendConfigContext";
import { useScanSocket } from "../hooks/useScanSocket";
import { useScanStore } from "../store/useScanStore";

const ScannerScreen = () => {
    const cameraRef = useRef(null);
    const isFocused = useIsFocused();
    const { backendIp, setBackendIp } = useContext(BackendConfigContext);

    const [permission, requestPermission] = useCameraPermissions();
    const [backendDraft, setBackendDraft] = useState(backendIp);
    const [capturedUri, setCapturedUri] = useState(null);

    const {
        taskId,
        scanState,
        stage,
        progress,
        error,
        uploadAndQueueScan,
        syncPendingScans,
        resetScan,
        socketState,
        socketError,
    } = useScanStore();

    useEffect(() => {
        setBackendDraft(backendIp);
    }, [backendIp]);

    const baseUrl = buildBaseUrl(backendIp);

    // This hook will automatically connect to ws://.../api/v2/scan/ws/status/{taskId}
    // exactly as we configured in the FastAPI main.py
    useScanSocket(baseUrl, taskId);

    useEffect(() => {
        if (baseUrl) {
            syncPendingScans(baseUrl);
        }
    }, [baseUrl, syncPendingScans]);

    const prepareImage = async (uri) => {
        // High quality preservation for the AI Engine
        const transformed = await ImageManipulator.manipulateAsync(
            uri,
            [{ resize: { width: 1600 } }], // Keeps pixel density high for SAHI
            { compress: 0.8, format: ImageManipulator.SaveFormat.JPEG }
        );
        return transformed.uri;
    };

    const triggerUpload = async (imageUri) => {
        if (!baseUrl) {
            Alert.alert("Missing Backend", "Set backend host before scanning.");
            return;
        }

        // We reset the UI before triggering a new upload
        resetScan(); 

        const task = await uploadAndQueueScan({ baseUrl, imageUri });
        if (!task) {
            Alert.alert("Queued Offline", "Network unreachable. Image cached locally and will upload automatically when connection is restored.");
        }
    };

    const takePhoto = async () => {
        if (!cameraRef.current) return;
        try {
            const photo = await cameraRef.current.takePictureAsync({ quality: 1, skipProcessing: true });
            const prepared = await prepareImage(photo.uri);
            setCapturedUri(prepared);
            await triggerUpload(prepared);
        } catch (e) {
            Alert.alert("Capture Failed", "Could not capture image from device hardware.");
        }
    };

    const pickPhoto = async () => {
        const picked = await ImagePicker.launchImageLibraryAsync({
            mediaTypes: ImagePicker.MediaTypeOptions.Images,
            allowsEditing: false,
            quality: 1,
        });

        if (picked.canceled) return;

        try {
            const prepared = await prepareImage(picked.assets[0].uri);
            setCapturedUri(prepared);
            await triggerUpload(prepared);
        } catch (e) {
            Alert.alert("Import Failed", "Could not process selected image.");
        }
    };

    if (!permission) {
        return (
            <View style={styles.centered}>
                <ActivityIndicator size="large" color="#10B981" />
            </View>
        );
    }

    if (!permission.granted) {
        return (
            <View style={styles.centered}>
                <Text style={styles.warning}>Camera permission is required for scanner mode.</Text>
                <TouchableOpacity style={styles.primaryButton} onPress={requestPermission}>
                    <Text style={styles.primaryText}>Grant Camera Permission</Text>
                </TouchableOpacity>
            </View>
        );
    }

    // Modernized UI state logic based on our updated ScanState enum
    const showProgress = scanState === "QUEUED" || scanState === "PROCESSING";

    return (
        <View style={styles.container}>
            <View style={styles.backendRow}>
                <TextInput
                    value={backendDraft}
                    onChangeText={setBackendDraft}
                    placeholder="192.168.1.10:8000"
                    placeholderTextColor="#6B7280"
                    style={styles.input}
                    autoCapitalize="none"
                />
                <TouchableOpacity style={styles.saveButton} onPress={() => setBackendIp(backendDraft)}>
                    <Text style={styles.saveText}>Set Gateway</Text>
                </TouchableOpacity>
            </View>

            {showProgress ? (
                <View style={styles.progressCard}>
                    <Text style={styles.progressTitle}>Pipeline Running</Text>
                    <Text style={styles.progressStage}>{stage}</Text>
                    
                    <View style={styles.socketRow}>
                        <View style={[styles.socketIndicator, { backgroundColor: socketState === "Connected" ? "#10B981" : "#F59E0B" }]} />
                        <Text style={styles.socketState}>Telemetry: {socketState}</Text>
                    </View>

                    <View style={styles.progressTrack}>
                        <View style={[styles.progressFill, { width: `${Math.max(progress, 2)}%` }]} />
                    </View>
                    <Text style={styles.progressMeta}>Job ID: {taskId || "Allocating..."}</Text>
                </View>
            ) : (
                <>
                    {isFocused && (
                        <CameraView ref={cameraRef} style={styles.camera} facing="back" autofocus="on" />
                    )}

                    <View style={styles.actions}>
                        <TouchableOpacity style={styles.secondaryButton} onPress={pickPhoto}>
                            <Text style={styles.secondaryText}>Import</Text>
                        </TouchableOpacity>
                        <TouchableOpacity style={styles.primaryButton} onPress={takePhoto}>
                            <Text style={styles.primaryText}>Capture & Analyze</Text>
                        </TouchableOpacity>
                    </View>
                </>
            )}

            {scanState === "COMPLETED" && (
                <View style={styles.resultCard}>
                    <Text style={styles.successText}>✓ Verification Complete</Text>
                    <Text style={styles.resultText}>Check the Inventory tab for verified components and the Triage tab for anomalies.</Text>
                    <TouchableOpacity style={styles.secondaryButton} onPress={() => { resetScan(); setCapturedUri(null); }}>
                        <Text style={styles.secondaryText}>Clear Screen</Text>
                    </TouchableOpacity>
                </View>
            )}

            {capturedUri && (
                <Image source={{ uri: capturedUri }} style={styles.preview} resizeMode="cover" />
            )}

            {(error || socketError) && (
                <View style={styles.errorBox}>
                    <Text style={styles.errorText}>⚠ {error || socketError}</Text>
                </View>
            )}
        </View>
    );
};

const styles = StyleSheet.create({
    container: { flex: 1, backgroundColor: "#0A1118", padding: 12 },
    centered: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: "#0A1118", padding: 20 },
    warning: { color: "#CBD5E1", textAlign: "center", marginBottom: 14 },
    backendRow: { flexDirection: "row", gap: 8, marginBottom: 10, marginTop: 40 },
    input: {
        flex: 1,
        borderRadius: 12,
        borderWidth: 1,
        borderColor: "#243447",
        backgroundColor: "#111B25",
        color: "#FFFFFF",
        paddingHorizontal: 12,
        paddingVertical: 10,
    },
    saveButton: {
        backgroundColor: "#1F2937",
        borderRadius: 12,
        paddingHorizontal: 16,
        justifyContent: "center",
    },
    saveText: { color: "#F9FAFB", fontWeight: "700" },
    camera: { flex: 1, borderRadius: 14, overflow: "hidden", borderWidth: 1, borderColor: '#223243' },
    actions: { flexDirection: "row", gap: 10, marginTop: 10 },
    primaryButton: {
        flex: 2,
        borderRadius: 12,
        backgroundColor: "#10B981",
        paddingVertical: 16,
        alignItems: "center",
    },
    secondaryButton: {
        flex: 1,
        borderRadius: 12,
        borderColor: "#334155",
        borderWidth: 1,
        backgroundColor: "#111827",
        paddingVertical: 16,
        alignItems: "center",
        justifyContent: "center"
    },
    primaryText: { color: "#042F2E", fontWeight: "800", fontSize: 16 },
    secondaryText: { color: "#E2E8F0", fontWeight: "700", fontSize: 16 },
    progressCard: {
        borderRadius: 14,
        backgroundColor: "#111827",
        borderWidth: 1,
        borderColor: "#223243",
        padding: 20,
        marginTop: 16,
    },
    progressTitle: { color: "#F8FAFC", fontWeight: "700", fontSize: 20 },
    progressStage: { color: "#93C5FD", marginTop: 8, marginBottom: 16, fontSize: 16 },
    socketRow: { flexDirection: "row", alignItems: "center", marginBottom: 12 },
    socketIndicator: { width: 8, height: 8, borderRadius: 4, marginRight: 8 },
    socketState: { color: "#A7F3D0", fontSize: 12 },
    progressTrack: {
        height: 12,
        borderRadius: 20,
        backgroundColor: "#1E293B",
        overflow: "hidden",
    },
    progressFill: { height: "100%", backgroundColor: "#10B981" },
    progressMeta: { color: "#94A3B8", marginTop: 12, fontSize: 12, fontFamily: 'monospace' },
    resultCard: {
        marginTop: 12,
        borderRadius: 12,
        backgroundColor: "#064E3B",
        borderColor: "#059669",
        borderWidth: 1,
        padding: 16,
        gap: 12,
    },
    successText: { color: "#A7F3D0", fontWeight: "bold", fontSize: 18 },
    resultText: { color: "#ECFDF5", lineHeight: 20 },
    preview: {
        marginTop: 12,
        width: "100%",
        height: 140,
        borderRadius: 12,
        borderWidth: 1,
        borderColor: "#223243",
    },
    errorBox: {
        marginTop: 12,
        padding: 12,
        backgroundColor: "#7F1D1D",
        borderRadius: 8,
        borderWidth: 1,
        borderColor: "#B91C1C"
    },
    errorText: { color: "#FECACA", fontWeight: "600" },
});

export default ScannerScreen;