import React, { useContext, useEffect, useRef, useState } from "react";
import { CameraView, useCameraPermissions } from "expo-camera";
import { ActivityIndicator, Alert, StyleSheet, Text, TouchableOpacity, View, Image } from "react-native";
import * as ImageManipulator from "expo-image-manipulator";
import axios from "axios";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { useIsFocused } from "@react-navigation/native";
import * as ImagePicker from "expo-image-picker";

import { BackendConfigContext, buildBaseUrl } from "../BackendConfigContext";

const ScannerScreen = () => {
    const cameraRef = useRef(null);
    const isFocused = useIsFocused();
    const { backendIp } = useContext(BackendConfigContext);
    
    const [permission, requestPermission] = useCameraPermissions();
    
    const [isProcessing, setIsProcessing] = useState(false);
    const [isTorchOn, setIsTorchOn] = useState(false);
    const [scanMode, setScanMode] = useState("YOLO");
    const [photoData, setPhotoData] = useState(null);
    const [corners, setCorners] = useState([]);
    const [imageLayout, setImageLayout] = useState({ width: 0, height: 0 });

    const appendScanHistory = async (scanId) => {
        try {
            const raw = await AsyncStorage.getItem("scan_history");
            const history = raw ? JSON.parse(raw) : [];
            const entry = { scan_id: scanId, timestamp: new Date().toISOString() };
            const updated = [entry, ...history].slice(0, 50);
            await AsyncStorage.setItem("scan_history", JSON.stringify(updated));
        } catch (e) {
            console.error("Failed to save history", e);
        }
    };

    const takePhoto = async () => {
        if (!cameraRef.current || isProcessing) return;

        try {
            setIsProcessing(true);
            const rawPhoto = await cameraRef.current.takePictureAsync({ quality: 0.8, skipProcessing: true });

            const manipulated = await ImageManipulator.manipulateAsync(
                rawPhoto.uri,
                [{ resize: { width: 1024 } }],
                { compress: 0.8, format: ImageManipulator.SaveFormat.JPEG }
            );

            setPhotoData(manipulated);
            setCorners([]);
        } catch (error) {
            Alert.alert("Capture Failed", "Please try again.");
        } finally {
            setIsProcessing(false);
        }
    };

    const pickImage = async () => {
        if (isProcessing) return;
        
        try {
            let result = await ImagePicker.launchImageLibraryAsync({
                mediaTypes: ImagePicker.MediaTypeOptions.Images,
                allowsEditing: false,
                quality: 1,
            });

            if (!result.canceled) {
                setIsProcessing(true);
                const manipulated = await ImageManipulator.manipulateAsync(
                    result.assets[0].uri,
                    [{ resize: { width: 1024 } }],
                    { compress: 0.8, format: ImageManipulator.SaveFormat.JPEG }
                );
                
                setPhotoData(manipulated);
                setCorners([]);
            }
        } catch (error) {
            Alert.alert("Import Failed", "Could not load image.");
        } finally {
            setIsProcessing(false);
        }
    };

    const handleTap = (e) => {
        if (corners.length >= 4) return;
        if (!imageLayout.width || !imageLayout.height) return;

        const { locationX, locationY } = e.nativeEvent;
        const relativeX = locationX / imageLayout.width;
        const relativeY = locationY / imageLayout.height;

        setCorners((prev) => [...prev, { x: relativeX, y: relativeY }]);
    };

    const sendToAPI = async () => {
        if (corners.length !== 4) {
            Alert.alert("Missing Corners", "Please tap all 4 corners of the PCB.");
            return;
        }

        // Use the IP typed in the Home Screen context. If empty, fallback to the hardcoded local test IP.
        const activeIp = backendIp ? buildBaseUrl(backendIp) : "http://172.20.10.13:8000";

        try {
            setIsProcessing(true);
            const formData = new FormData();
            
            formData.append("file", {
                uri: photoData.uri,
                name: `scan_${Date.now()}.jpg`,
                type: "image/jpeg",
            });
            formData.append("mode", scanMode);
            formData.append("corners", JSON.stringify(corners));

            // Clean URL to prevent 404 double-slash errors
            const cleanUrl = `${activeIp}/api/v2/analyze`.replace(/([^:]\/)\/+/g, "$1");
            console.log("[*] Firing payload to:", cleanUrl);

            // AXIOS REQUEST
            const response = await axios.post(cleanUrl, formData, {
                headers: { 
                    "Content-Type": "multipart/form-data",
                    "Accept": "application/json"
                },
                timeout: 15000 // Kills the request after 15 seconds so it doesn't hang forever
            });

            // AXIOS SUCCESS PATH (Status 200-299)
            console.log("[+] Server Response:", response.data);
            const scanId = response.data?.scan_id;
            if (scanId) {
                await appendScanHistory(scanId);
            }
            
            Alert.alert("Success", "Report is ready in History.");
            setPhotoData(null);
            setCorners([]);

        } catch (error) {
            // AXIOS ERROR PATH (Network fail, 404, 500, etc.)
            console.error("[-] API Error:", error);
            
            if (error.response) {
                // The server received the request but rejected it (e.g., 404, 422, 500)
                Alert.alert(`Server Error (${error.response.status})`, JSON.stringify(error.response.data));
            } else if (error.request) {
                // The request never reached the server (Timeout, bad IP, Firewall)
                Alert.alert("Network Timeout", `Could not reach ${activeIp}. Check your laptop IP and Windows Firewall.`);
            } else {
                // Something else broke in React Native
                Alert.alert("Error", error.message);
            }
        } finally {
            setIsProcessing(false);
        }
    };

    if (!permission) {
        return (
            <View style={styles.loadingWrap}>
                <ActivityIndicator size="large" color="#00E676" />
            </View>
        );
    }

    if (!permission.granted) {
        return (
            <View style={styles.loadingWrap}>
                <Text style={styles.errorText}>Camera access is required.</Text>
                <TouchableOpacity style={[styles.captureButton, {marginTop: 20, paddingHorizontal: 20}]} onPress={requestPermission}>
                    <Text style={styles.captureText}>Grant Permission</Text>
                </TouchableOpacity>
            </View>
        );
    }

    return (
        <View style={styles.container}>
            {!photoData ? (
                <>
                    {isFocused && (
                        <CameraView
                            ref={cameraRef}
                            style={styles.camera}
                            facing="back"
                            autofocus="on"
                            enableTorch={isTorchOn}
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
                        </CameraView>
                    )}

                    <View style={styles.controls}>
                        <View style={styles.modeRow}>
                            <TouchableOpacity
                                style={[styles.modeButton, scanMode === "YOLO" && styles.modeButtonActive]}
                                onPress={() => setScanMode("YOLO")}
                                disabled={isProcessing}
                            >
                                <Text style={styles.modeText}>Inventory Only (YOLO)</Text>
                            </TouchableOpacity>
                            <TouchableOpacity
                                style={[styles.modeButton, scanMode === "MOBILENET" && styles.modeButtonActive]}
                                onPress={() => setScanMode("MOBILENET")}
                                disabled={isProcessing}
                            >
                                <Text style={styles.modeText}>Defect Scan Only (CNN)</Text>
                            </TouchableOpacity>
                            <TouchableOpacity
                                style={[styles.modeButton, scanMode === "UNIFIED" && styles.modeButtonActive]}
                                onPress={() => setScanMode("UNIFIED")}
                                disabled={isProcessing}
                            >
                                <Text style={styles.modeText}>Full Unified Scan</Text>
                            </TouchableOpacity>
                        </View>
                        <TouchableOpacity
                            style={styles.flashButton}
                            onPress={() => setIsTorchOn(!isTorchOn)}
                        >
                            <Text style={styles.flashText}>
                                {isTorchOn ? "Flash On" : "Flash Off"}
                            </Text>
                        </TouchableOpacity>
                        {isProcessing ? (
                            <ActivityIndicator size="large" color="#00E676" />
                        ) : (
                            <View style={{ flexDirection: "row", gap: 10 }}>
                                <TouchableOpacity
                                    style={[styles.captureButton, { flex: 1, backgroundColor: "#2979FF" }]}
                                    onPress={pickImage}
                                    disabled={isProcessing}
                                >
                                    <Text style={[styles.captureText, { color: "#FFFFFF", fontSize: 16 }]}>Import Photo</Text>
                                </TouchableOpacity>
                                
                                <TouchableOpacity
                                    style={[styles.captureButton, { flex: 1 }, isProcessing && styles.captureButtonDisabled]}
                                    onPress={takePhoto}
                                    disabled={isProcessing}
                                >
                                    <Text style={[styles.captureText, { fontSize: 16 }]}>Capture PCB</Text>
                                </TouchableOpacity>
                            </View>
                        )}
                        <Text style={styles.hint}>Ensure all 4 corners are visible.</Text>
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
                </>
            ) : (
                <>
                    <View style={styles.reviewWrap}>
                        <TouchableOpacity
                            style={styles.reviewImageWrap}
                            activeOpacity={1}
                            onPress={handleTap}
                            onLayout={(e) => setImageLayout(e.nativeEvent.layout)}
                        >
                            <Image source={{ uri: photoData.uri }} style={styles.reviewImage} resizeMode="contain" />
                            {corners.map((corner, index) => (
                                <View
                                    key={`${index}-${corner.x}-${corner.y}`}
                                    style={[
                                        styles.cornerMarker,
                                        {
                                            left: corner.x * imageLayout.width - 12,
                                            top: corner.y * imageLayout.height - 12,
                                        },
                                    ]}
                                >
                                    <Text style={styles.cornerLabel}>{index + 1}</Text>
                                </View>
                            ))}
                        </TouchableOpacity>
                    </View>

                    <View style={styles.reviewControls}>
                        <Text style={styles.reviewHint}>Tap the 4 PCB corners to unlock Analyze.</Text>
                        <View style={styles.reviewButtonRow}>
                            <TouchableOpacity
                                style={styles.retakeButton}
                                onPress={() => {
                                    setPhotoData(null);
                                    setCorners([]);
                                }}
                                disabled={isProcessing}
                            >
                                <Text style={styles.retakeText}>Retake</Text>
                            </TouchableOpacity>
                            <TouchableOpacity
                                style={[
                                    styles.analyzeButton,
                                    (corners.length !== 4 || isProcessing) && styles.analyzeButtonDisabled,
                                ]}
                                onPress={sendToAPI}
                                disabled={isProcessing || corners.length !== 4}
                            >
                                {isProcessing ? (
                                    <ActivityIndicator color="#121212" />
                                ) : (
                                    <Text style={styles.analyzeText}>Analyze</Text>
                                )}
                            </TouchableOpacity>
                        </View>
                    </View>
                </>
            )}
        </View>
    );
};

const styles = StyleSheet.create({
    container: { flex: 1, backgroundColor: "#121212" },
    camera: { flex: 1 },
    overlay: { flex: 1, justifyContent: "center", alignItems: "center" },
    gridBox: { width: "70%", height: "50%", borderWidth: 2, borderColor: "rgba(0, 230, 118, 0.8)", borderRadius: 14, justifyContent: "center", alignItems: "center" },
    gridLineHorizontal: { position: "absolute", width: "100%", height: 1, backgroundColor: "rgba(255, 255, 255, 0.4)" },
    gridLineVertical: { position: "absolute", width: 1, height: "100%", backgroundColor: "rgba(255, 255, 255, 0.4)" },
    crosshairRow: { position: "absolute", top: "50%", left: 0, right: 0, alignItems: "center" },
    crosshair: { width: 12, height: 12, borderRadius: 6, borderWidth: 2, borderColor: "#2979FF", backgroundColor: "rgba(41, 121, 255, 0.2)" },
    controls: { padding: 20, backgroundColor: "#0B0B0B" },
    reviewWrap: { flex: 1, backgroundColor: "#121212", padding: 12 },
    reviewImageWrap: { flex: 1, borderRadius: 16, overflow: "hidden", backgroundColor: "#0B0B0B", borderWidth: 1, borderColor: "#1F1F1F" },
    reviewImage: { width: "100%", height: "100%" },
    cornerMarker: { position: "absolute", width: 24, height: 24, borderRadius: 12, backgroundColor: "rgba(0, 230, 118, 0.85)", borderWidth: 2, borderColor: "#0B0B0B", alignItems: "center", justifyContent: "center" },
    cornerLabel: { color: "#121212", fontSize: 12, fontFamily: "Courier New", fontWeight: "700" },
    reviewControls: { padding: 20, backgroundColor: "#0B0B0B" },
    reviewButtonRow: { flexDirection: "row", gap: 12 },
    retakeButton: { flex: 1, borderRadius: 16, borderWidth: 1, borderColor: "#2B2B2B", backgroundColor: "#141414", paddingVertical: 14, alignItems: "center" },
    retakeText: { color: "#FFFFFF", fontSize: 14, fontFamily: "Georgia", fontWeight: "700" },
    analyzeButton: { flex: 1, borderRadius: 16, backgroundColor: "#00E676", paddingVertical: 14, alignItems: "center" },
    analyzeButtonDisabled: { opacity: 0.5 },
    analyzeText: { color: "#121212", fontSize: 14, fontFamily: "Georgia", fontWeight: "700" },
    reviewHint: { color: "#AFAFAF", fontSize: 12, textAlign: "center", marginBottom: 12, fontFamily: "Courier New" },
    modeRow: { gap: 10, marginBottom: 12, flexDirection: "row", justifyContent: "space-between" },
    modeButton: { flex: 1, borderRadius: 16, paddingVertical: 12, paddingHorizontal: 4, borderWidth: 1, borderColor: "#2B2B2B", backgroundColor: "#121212", alignItems: "center", justifyContent: "center" },
    modeButtonActive: { borderColor: "#00E676", backgroundColor: "rgba(0, 230, 118, 0.12)" },
    modeText: { color: "#FFFFFF", fontSize: 10, fontFamily: "Courier New", textAlign: "center" },
    flashButton: { alignSelf: "center", marginBottom: 12, paddingVertical: 8, paddingHorizontal: 18, borderRadius: 18, borderWidth: 1, borderColor: "#2B2B2B", backgroundColor: "#151515" },
    flashText: { color: "#FFFFFF", fontSize: 12, fontFamily: "Courier New", letterSpacing: 0.6 },
    captureButton: { backgroundColor: "#00E676", borderRadius: 24, paddingVertical: 16, alignItems: "center" },
    captureButtonDisabled: { opacity: 0.6 },
    captureText: { color: "#121212", fontSize: 18, fontFamily: "Georgia", fontWeight: "700" },
    hint: { color: "#AFAFAF", fontSize: 12, marginTop: 12, textAlign: "center", fontFamily: "Courier New" },
    loadingWrap: { flex: 1, backgroundColor: "#121212", alignItems: "center", justifyContent: "center" },
    processingOverlay: { position: "absolute", top: 0, right: 0, bottom: 0, left: 0, alignItems: "center", justifyContent: "center", backgroundColor: "rgba(0, 0, 0, 0.8)" },
    processingText: { color: "#FFFFFF", fontSize: 12, marginTop: 12, textAlign: "center", paddingHorizontal: 24, fontFamily: "Courier New" },
    errorText: { color: "#FFFFFF", fontSize: 16 },
});

export default ScannerScreen;