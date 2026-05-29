import React, { useContext, useEffect, useRef, useState } from "react";
import { ActivityIndicator, Alert, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { Camera } from "expo-camera";
import * as ImageManipulator from "expo-image-manipulator";
import axios from "axios";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { useIsFocused } from "@react-navigation/native";

import { BackendConfigContext, buildBaseUrl } from "../BackendConfigContext";

// Use API_BASE_URL for ngrok/playit tunnels (e.g. https://random-id.ngrok-free.app).
// Leave empty to rely on the Home screen IP field for local Wi-Fi access.
// If you use a .env file, wire the value into API_BASE_URL before release builds.
const API_BASE_URL = "";

const ScannerScreen = () => {
    const cameraRef = useRef(null);
    const isFocused = useIsFocused();
    const { backendIp } = useContext(BackendConfigContext);
    const [hasPermission, setHasPermission] = useState(null);
    const [isProcessing, setIsProcessing] = useState(false);
    const [flashMode, setFlashMode] = useState(Camera.Constants.FlashMode.off);
    const [scanMode, setScanMode] = useState("YOLO");

    useEffect(() => {
        const requestPermission = async () => {
            const { status } = await Camera.requestCameraPermissionsAsync();
            setHasPermission(status === "granted");
        };

        requestPermission();
    }, []);

    useEffect(() => {
        const interceptor = axios.interceptors.response.use(
            (response) => response,
            (error) => {
                if (error?.response?.status >= 500) {
                    Alert.alert(
                        "Server Overload",
                        "Try running Inventory Only to reduce memory usage."
                    );
                }
                return Promise.reject(error);
            }
        );

        return () => axios.interceptors.response.eject(interceptor);
    }, []);

    const appendScanHistory = async (scanId) => {
        const raw = await AsyncStorage.getItem("scan_history");
        const history = raw ? JSON.parse(raw) : [];
        const entry = { scan_id: scanId, timestamp: new Date().toISOString() };
        const updated = [entry, ...history].slice(0, 50);
        await AsyncStorage.setItem("scan_history", JSON.stringify(updated));
    };

    const handleCapture = async () => {
        if (!cameraRef.current || isProcessing) {
            return;
        }

        const baseUrl = backendIp ? buildBaseUrl(backendIp) : API_BASE_URL;
        if (!baseUrl) {
            Alert.alert("Missing API", "Set the backend IP on Home or API_BASE_URL for tunnels.");
            return;
        }

        try {
            setIsProcessing(true);
            const rawPhoto = await cameraRef.current.takePictureAsync({ quality: 1, skipProcessing: true });

            const manipulated = await ImageManipulator.manipulateAsync(
                rawPhoto.uri,
                [{ resize: { width: 1024 } }],
                { compress: 0.8, format: ImageManipulator.SaveFormat.JPEG }
            );

            const formData = new FormData();
            formData.append("file", {
                uri: manipulated.uri,
                name: `scan_${Date.now()}.jpg`,
                type: "image/jpeg",
            });
            formData.append("mode", scanMode);

            const response = await axios.post(`${baseUrl}/api/v2/analyze`, formData, {
                headers: { "Content-Type": "multipart/form-data" },
            });

            const scanId = response.data?.scan_id;
            await appendScanHistory(scanId);

            Alert.alert("Scan Complete", "Report is ready for download in History.");
        } catch (error) {
            Alert.alert("Connection Failed", "Check Laptop IP.");
        } finally {
            setIsProcessing(false);
        }
    };

    if (hasPermission === null) {
        return (
            <View style={styles.loadingWrap}>
                <ActivityIndicator size="large" color="#00E676" />
            </View>
        );
    }

    if (hasPermission === false) {
        return (
            <View style={styles.loadingWrap}>
                <Text style={styles.errorText}>Camera permission denied.</Text>
            </View>
        );
    }

    return (
        <View style={styles.container}>
            {isFocused && (
                <Camera
                    ref={cameraRef}
                    style={styles.camera}
                    type={Camera.Constants.Type.back}
                    autoFocus={Camera.Constants.AutoFocus.on}
                    flashMode={flashMode}
                >
                    <View style={styles.overlay}>
                        <View style={styles.gridBox}>
                            <View style={styles.gridLineHorizontal} />
                            <View style={styles.gridLineVertical} />
                        </View>
                        <View style={styles.crosshairRow}>
                            <View style={styles.crosshair} />
                        </View>
                    </View>
                </Camera>
            )}

            <View style={styles.controls}>
                <View style={styles.modeRow}>
                    <TouchableOpacity
                        style={[
                            styles.modeButton,
                            scanMode === "YOLO" && styles.modeButtonActive,
                        ]}
                        onPress={() => setScanMode("YOLO")}
                        disabled={isProcessing}
                    >
                        <Text style={styles.modeText}>Inventory Only (YOLO)</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                        style={[
                            styles.modeButton,
                            scanMode === "MOBILENET" && styles.modeButtonActive,
                        ]}
                        onPress={() => setScanMode("MOBILENET")}
                        disabled={isProcessing}
                    >
                        <Text style={styles.modeText}>Defect Scan Only (CNN)</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                        style={[
                            styles.modeButton,
                            scanMode === "UNIFIED" && styles.modeButtonActive,
                        ]}
                        onPress={() => setScanMode("UNIFIED")}
                        disabled={isProcessing}
                    >
                        <Text style={styles.modeText}>Full Unified Scan</Text>
                    </TouchableOpacity>
                </View>
                <TouchableOpacity
                    style={styles.flashButton}
                    onPress={() =>
                        setFlashMode((current) =>
                            current === Camera.Constants.FlashMode.off
                                ? Camera.Constants.FlashMode.torch
                                : Camera.Constants.FlashMode.off
                        )
                    }
                >
                    <Text style={styles.flashText}>
                        {flashMode === Camera.Constants.FlashMode.off ? "Flash Off" : "Flash On"}
                    </Text>
                </TouchableOpacity>
                {isProcessing ? (
                    <ActivityIndicator size="large" color="#00E676" />
                ) : (
                    <TouchableOpacity
                        style={[styles.captureButton, isProcessing && styles.captureButtonDisabled]}
                        onPress={handleCapture}
                        disabled={isProcessing}
                    >
                        <Text style={styles.captureText}>Capture</Text>
                    </TouchableOpacity>
                )}
                <Text style={styles.hint}>Align PCB within the frame for fastest mapping.</Text>
            </View>

            {isProcessing && (
                <View style={styles.processingOverlay}>
                    <ActivityIndicator size="large" color="#00E676" />
                    {scanMode === "UNIFIED" && (
                        <Text style={styles.processingText}>
                            Running Dual-Model SAHI Inference... This may take up to 10 seconds.
                        </Text>
                    )}
                </View>
            )}
        </View>
    );
};

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: "#121212",
    },
    camera: {
        flex: 1,
    },
    overlay: {
        flex: 1,
        justifyContent: "center",
        alignItems: "center",
    },
    gridBox: {
        width: "70%",
        height: "50%",
        borderWidth: 2,
        borderColor: "rgba(0, 230, 118, 0.8)",
        borderRadius: 14,
        justifyContent: "center",
        alignItems: "center",
    },
    gridLineHorizontal: {
        position: "absolute",
        width: "100%",
        height: 1,
        backgroundColor: "rgba(255, 255, 255, 0.4)",
    },
    gridLineVertical: {
        position: "absolute",
        width: 1,
        height: "100%",
        backgroundColor: "rgba(255, 255, 255, 0.4)",
    },
    crosshairRow: {
        position: "absolute",
        top: "50%",
        left: 0,
        right: 0,
        alignItems: "center",
    },
    crosshair: {
        width: 12,
        height: 12,
        borderRadius: 6,
        borderWidth: 2,
        borderColor: "#2979FF",
        backgroundColor: "rgba(41, 121, 255, 0.2)",
    },
    controls: {
        padding: 20,
        backgroundColor: "#0B0B0B",
    },
    modeRow: {
        gap: 10,
        marginBottom: 12,
    },
    modeButton: {
        borderRadius: 16,
        paddingVertical: 12,
        paddingHorizontal: 14,
        borderWidth: 1,
        borderColor: "#2B2B2B",
        backgroundColor: "#121212",
    },
    modeButtonActive: {
        borderColor: "#00E676",
        backgroundColor: "rgba(0, 230, 118, 0.12)",
    },
    modeText: {
        color: "#FFFFFF",
        fontSize: 12,
        fontFamily: "Courier New",
    },
    flashButton: {
        alignSelf: "center",
        marginBottom: 12,
        paddingVertical: 8,
        paddingHorizontal: 18,
        borderRadius: 18,
        borderWidth: 1,
        borderColor: "#2B2B2B",
        backgroundColor: "#151515",
    },
    flashText: {
        color: "#FFFFFF",
        fontSize: 12,
        fontFamily: "Courier New",
        letterSpacing: 0.6,
    },
    captureButton: {
        backgroundColor: "#00E676",
        borderRadius: 24,
        paddingVertical: 16,
        alignItems: "center",
    },
    captureButtonDisabled: {
        opacity: 0.6,
    },
    captureText: {
        color: "#121212",
        fontSize: 18,
        fontFamily: "Georgia",
        fontWeight: "700",
    },
    hint: {
        color: "#AFAFAF",
        fontSize: 12,
        marginTop: 12,
        textAlign: "center",
        fontFamily: "Courier New",
    },
    loadingWrap: {
        flex: 1,
        backgroundColor: "#121212",
        alignItems: "center",
        justifyContent: "center",
    },
    processingOverlay: {
        position: "absolute",
        top: 0,
        right: 0,
        bottom: 0,
        left: 0,
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: "rgba(0, 0, 0, 0.35)",
    },
    processingText: {
        color: "#FFFFFF",
        fontSize: 12,
        marginTop: 12,
        textAlign: "center",
        paddingHorizontal: 24,
        fontFamily: "Courier New",
    },
    errorText: {
        color: "#FFFFFF",
        fontSize: 16,
    },
});

export default ScannerScreen;
