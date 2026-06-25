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

    useScanSocket(baseUrl, taskId);

    useEffect(() => {
        if (baseUrl) {
            syncPendingScans(baseUrl);
        }
    }, [baseUrl, syncPendingScans]);

    const prepareImage = async (uri) => {
        const transformed = await ImageManipulator.manipulateAsync(
            uri,
            [{ resize: { width: 1600 } }],
            { compress: 0.72, format: ImageManipulator.SaveFormat.JPEG }
        );
        return transformed.uri;
    };

    const triggerUpload = async (imageUri) => {
        if (!baseUrl) {
            Alert.alert("Missing Backend", "Set backend host before scanning.");
            return;
        }

        const task = await uploadAndQueueScan({ baseUrl, imageUri });
        if (!task) {
            Alert.alert("Queued Offline", "Image cached locally. Upload will retry automatically.");
        }
    };

    const takePhoto = async () => {
        if (!cameraRef.current) {
            return;
        }

        try {
            const photo = await cameraRef.current.takePictureAsync({ quality: 0.9, skipProcessing: true });
            const prepared = await prepareImage(photo.uri);
            setCapturedUri(prepared);
            await triggerUpload(prepared);
        } catch (e) {
            Alert.alert("Capture Failed", "Could not capture image.");
        }
    };

    const pickPhoto = async () => {
        const picked = await ImagePicker.launchImageLibraryAsync({
            mediaTypes: ImagePicker.MediaTypeOptions.Images,
            allowsEditing: false,
            quality: 1,
        });

        if (picked.canceled) {
            return;
        }

        try {
            const prepared = await prepareImage(picked.assets[0].uri);
            setCapturedUri(prepared);
            await triggerUpload(prepared);
        } catch (e) {
            Alert.alert("Import Failed", "Could not prepare selected image.");
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

    const showProgress = scanState !== "IDLE" && scanState !== "COMPLETED" && scanState !== "FAILED";

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
                    <Text style={styles.saveText}>Save</Text>
                </TouchableOpacity>
            </View>

            {showProgress ? (
                <View style={styles.progressCard}>
                    <Text style={styles.progressTitle}>Pipeline Running</Text>
                    <Text style={styles.progressStage}>{stage}</Text>
                    <Text style={styles.socketState}>Socket: {socketState}</Text>
                    <View style={styles.progressTrack}>
                        <View style={[styles.progressFill, { width: `${Math.max(progress, 5)}%` }]} />
                    </View>
                    <Text style={styles.progressMeta}>Task: {taskId || "N/A"}</Text>
                </View>
            ) : (
                <>
                    {isFocused && (
                        <CameraView ref={cameraRef} style={styles.camera} facing="back" autofocus="on" />
                    )}

                    <View style={styles.actions}>
                        <TouchableOpacity style={styles.secondaryButton} onPress={pickPhoto}>
                            <Text style={styles.secondaryText}>Import Image</Text>
                        </TouchableOpacity>
                        <TouchableOpacity style={styles.primaryButton} onPress={takePhoto}>
                            <Text style={styles.primaryText}>Capture & Upload</Text>
                        </TouchableOpacity>
                    </View>
                </>
            )}

            {scanState === "COMPLETED" && (
                <View style={styles.resultCard}>
                    <Text style={styles.resultText}>Scan completed. Open Inventory and Triage tabs.</Text>
                    <TouchableOpacity style={styles.secondaryButton} onPress={resetScan}>
                        <Text style={styles.secondaryText}>Start New Scan</Text>
                    </TouchableOpacity>
                </View>
            )}

            {capturedUri && (
                <Image source={{ uri: capturedUri }} style={styles.preview} resizeMode="cover" />
            )}

            {(error || socketError) && <Text style={styles.errorText}>{error || socketError}</Text>}
        </View>
    );
};

const styles = StyleSheet.create({
    container: { flex: 1, backgroundColor: "#0A1118", padding: 12 },
    centered: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: "#0A1118", padding: 20 },
    warning: { color: "#CBD5E1", textAlign: "center", marginBottom: 14 },
    backendRow: { flexDirection: "row", gap: 8, marginBottom: 10 },
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
    camera: { flex: 1, borderRadius: 14, overflow: "hidden" },
    actions: { flexDirection: "row", gap: 10, marginTop: 10 },
    primaryButton: {
        flex: 1,
        borderRadius: 12,
        backgroundColor: "#10B981",
        paddingVertical: 14,
        alignItems: "center",
    },
    secondaryButton: {
        flex: 1,
        borderRadius: 12,
        borderColor: "#334155",
        borderWidth: 1,
        backgroundColor: "#111827",
        paddingVertical: 14,
        alignItems: "center",
    },
    primaryText: { color: "#042F2E", fontWeight: "800" },
    secondaryText: { color: "#E2E8F0", fontWeight: "700" },
    progressCard: {
        borderRadius: 14,
        backgroundColor: "#111827",
        borderWidth: 1,
        borderColor: "#223243",
        padding: 16,
        marginTop: 16,
    },
    progressTitle: { color: "#F8FAFC", fontWeight: "700", fontSize: 18 },
    progressStage: { color: "#93C5FD", marginTop: 6, marginBottom: 12 },
    socketState: { color: "#A7F3D0", marginBottom: 10, fontSize: 12 },
    progressTrack: {
        height: 10,
        borderRadius: 20,
        backgroundColor: "#1E293B",
        overflow: "hidden",
    },
    progressFill: { height: "100%", backgroundColor: "#10B981" },
    progressMeta: { color: "#94A3B8", marginTop: 10, fontSize: 12 },
    resultCard: {
        marginTop: 12,
        borderRadius: 12,
        backgroundColor: "#0F172A",
        borderColor: "#1E293B",
        borderWidth: 1,
        padding: 12,
        gap: 10,
    },
    resultText: { color: "#E2E8F0" },
    preview: {
        marginTop: 10,
        width: "100%",
        height: 110,
        borderRadius: 10,
        borderWidth: 1,
        borderColor: "#223243",
    },
    errorText: { color: "#FCA5A5", marginTop: 8 },
});

export default ScannerScreen;
