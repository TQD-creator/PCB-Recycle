import React, { useContext, useState } from "react";
import { ActivityIndicator, Alert, FlatList, Linking, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import axios from "axios";
import { useFocusEffect } from "@react-navigation/native";

import { BackendConfigContext, buildBaseUrl } from "../BackendConfigContext";

// Use API_BASE_URL for ngrok/playit tunnels (e.g. https://random-id.ngrok-free.app).
// Leave empty to rely on the Home screen IP field for local Wi-Fi access.
// If you use a .env file, wire the value into API_BASE_URL before release builds.
const API_BASE_URL = "";

const HistoryScreen = () => {
    const { backendIp } = useContext(BackendConfigContext);
    const [scanList, setScanList] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    const [actionId, setActionId] = useState(null);

    const getBaseUrl = () => (backendIp ? buildBaseUrl(backendIp) : API_BASE_URL);

    const loadScans = async () => {
        const baseUrl = getBaseUrl();
        if (!baseUrl) {
            setScanList([]);
            return;
        }

        setIsLoading(true);
        try {
            const response = await axios.get(`${baseUrl}/api/v2/scans`);
            setScanList(response.data?.scans ?? []);
        } catch (error) {
            Alert.alert("Load Failed", "Could not fetch scan history.");
        } finally {
            setIsLoading(false);
        }
    };

    useFocusEffect(
        React.useCallback(() => {
            loadScans();
        }, [backendIp])
    );

    const handleDownload = async (scanId) => {
        const baseUrl = getBaseUrl();
        if (!baseUrl) {
            Alert.alert("Missing API", "Set the backend IP on Home or API_BASE_URL for tunnels.");
            return;
        }

        await Linking.openURL(`${baseUrl}/api/v2/download/${scanId}`);
    };

    const handleUpgrade = async (scanId) => {
        const baseUrl = getBaseUrl();
        if (!baseUrl) {
            Alert.alert("Missing API", "Set the backend IP on Home or API_BASE_URL for tunnels.");
            return;
        }

        setActionId(scanId);
        try {
            const response = await axios.post(`${baseUrl}/api/v2/upgrade/${scanId}`);
            const downloadUrl = response.data?.download_url;
            if (downloadUrl) {
                await Linking.openURL(`${baseUrl}${downloadUrl}`);
            }
            await loadScans();
        } catch (error) {
            Alert.alert("Upgrade Failed", "Could not upgrade scan to unified.");
        } finally {
            setActionId(null);
        }
    };

    return (
        <View style={styles.container}>
            <FlatList
                data={scanList}
                keyExtractor={(item) => item.scan_id}
                contentContainerStyle={styles.listContent}
                ListEmptyComponent={
                    <Text style={styles.emptyText}>
                        {isLoading ? "Loading scans..." : "No scans yet."}
                    </Text>
                }
                renderItem={({ item }) => {
                    const date = new Date(item.timestamp);
                    const isUnified = item.scan_mode === "UNIFIED";
                    return (
                        <View style={styles.card}>
                            <View style={styles.cardHeader}>
                                <Text style={styles.scanId}>{item.scan_id}</Text>
                                <View style={styles.metaRow}>
                                    <Text style={styles.dateText}>{date.toLocaleString()}</Text>
                                    <View style={styles.modeBadge}>
                                        <Text style={styles.modeText}>{item.scan_mode}</Text>
                                    </View>
                                </View>
                            </View>
                            {isUnified ? (
                                <TouchableOpacity
                                    style={styles.primaryButton}
                                    onPress={() => handleDownload(item.scan_id)}
                                >
                                    <Text style={styles.primaryText}>Download Report</Text>
                                </TouchableOpacity>
                            ) : (
                                <TouchableOpacity
                                    style={styles.secondaryButton}
                                    onPress={() => handleUpgrade(item.scan_id)}
                                    disabled={actionId === item.scan_id}
                                >
                                    {actionId === item.scan_id ? (
                                        <ActivityIndicator color="#121212" />
                                    ) : (
                                        <Text style={styles.secondaryText}>Upgrade to Unified</Text>
                                    )}
                                </TouchableOpacity>
                            )}
                        </View>
                    );
                }}
            />
        </View>
    );
};

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: "#121212",
    },
    listContent: {
        padding: 20,
    },
    card: {
        backgroundColor: "#1B1B1B",
        borderRadius: 16,
        padding: 16,
        marginBottom: 16,
    },
    cardHeader: {
        marginBottom: 12,
    },
    scanId: {
        color: "#FFFFFF",
        fontSize: 14,
        fontFamily: "Courier New",
        marginBottom: 6,
    },
    metaRow: {
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "space-between",
    },
    dateText: {
        color: "#7E7E7E",
        fontSize: 12,
    },
    modeBadge: {
        paddingHorizontal: 10,
        paddingVertical: 4,
        borderRadius: 10,
        borderWidth: 1,
        borderColor: "#2C2C2C",
        backgroundColor: "#141414",
    },
    modeText: {
        color: "#FFFFFF",
        fontSize: 10,
        fontFamily: "Courier New",
        letterSpacing: 0.6,
    },
    primaryButton: {
        backgroundColor: "#00E676",
        paddingVertical: 12,
        borderRadius: 12,
        alignItems: "center",
    },
    primaryText: {
        color: "#121212",
        fontSize: 14,
        fontFamily: "Georgia",
        fontWeight: "700",
    },
    secondaryButton: {
        backgroundColor: "#2979FF",
        paddingVertical: 12,
        borderRadius: 12,
        alignItems: "center",
    },
    secondaryText: {
        color: "#FFFFFF",
        fontSize: 14,
        fontFamily: "Georgia",
        fontWeight: "700",
    },
    emptyText: {
        color: "#6F6F6F",
        textAlign: "center",
        marginTop: 40,
    },
});

export default HistoryScreen;
