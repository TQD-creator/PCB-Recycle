import React, { useContext, useState } from "react";
import { SafeAreaView, StyleSheet, Text, TextInput, TouchableOpacity, View } from "react-native";

import { BackendConfigContext } from "../BackendConfigContext";

const HomeScreen = ({ navigation }) => {
    const { backendIp, setBackendIp } = useContext(BackendConfigContext);
    const [ipDraft, setIpDraft] = useState(backendIp);

    const handleSave = () => {
        setBackendIp(ipDraft);
    };

    return (
        <SafeAreaView style={styles.container}>
            <View style={styles.hero}>
                <Text style={styles.title}>PCB Mobile Console</Text>
                <Text style={styles.subtitle}>Fast mapping, deeper audits, zero downtime.</Text>
            </View>

            <View style={styles.buttonStack}>
                <TouchableOpacity style={styles.primaryButton} onPress={() => navigation.navigate("Scanner")}>
                    <Text style={styles.primaryText}>Scan New PCB</Text>
                </TouchableOpacity>
                <TouchableOpacity style={styles.secondaryButton} onPress={() => navigation.navigate("History")}>
                    <Text style={styles.secondaryText}>Audit History</Text>
                </TouchableOpacity>
            </View>

            <View style={styles.footerCard}>
                <Text style={styles.footerLabel}>Backend IP</Text>
                <TextInput
                    style={styles.input}
                    placeholder="192.168.1.10:8000"
                    placeholderTextColor="#6F6F6F"
                    value={ipDraft}
                    onChangeText={setIpDraft}
                    autoCapitalize="none"
                    keyboardType="url"
                />
                <TouchableOpacity style={styles.saveButton} onPress={handleSave}>
                    <Text style={styles.saveText}>Save IP</Text>
                </TouchableOpacity>
            </View>

            <View style={styles.ambientCircle} />
            <View style={styles.ambientStripe} />
        </SafeAreaView>
    );
};

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: "#121212",
        paddingHorizontal: 24,
        paddingTop: 24,
    },
    hero: {
        marginTop: 10,
        marginBottom: 24,
    },
    title: {
        color: "#FFFFFF",
        fontSize: 28,
        fontFamily: "Georgia",
        fontWeight: "700",
        marginBottom: 8,
    },
    subtitle: {
        color: "#B0B0B0",
        fontSize: 15,
        fontFamily: "Courier New",
    },
    buttonStack: {
        gap: 16,
    },
    primaryButton: {
        backgroundColor: "#00E676",
        borderRadius: 18,
        paddingVertical: 20,
        alignItems: "center",
        elevation: 4,
    },
    secondaryButton: {
        backgroundColor: "#2979FF",
        borderRadius: 18,
        paddingVertical: 20,
        alignItems: "center",
        elevation: 2,
    },
    primaryText: {
        color: "#121212",
        fontSize: 18,
        fontFamily: "Georgia",
        fontWeight: "700",
        letterSpacing: 0.4,
    },
    secondaryText: {
        color: "#FFFFFF",
        fontSize: 18,
        fontFamily: "Georgia",
        fontWeight: "700",
        letterSpacing: 0.4,
    },
    footerCard: {
        marginTop: 30,
        backgroundColor: "#1A1A1A",
        borderRadius: 16,
        padding: 16,
    },
    footerLabel: {
        color: "#8C8C8C",
        fontSize: 12,
        letterSpacing: 1.4,
        textTransform: "uppercase",
        marginBottom: 8,
    },
    input: {
        borderWidth: 1,
        borderColor: "#2C2C2C",
        borderRadius: 12,
        paddingHorizontal: 12,
        paddingVertical: 10,
        color: "#FFFFFF",
        fontSize: 14,
        marginBottom: 12,
    },
    saveButton: {
        backgroundColor: "#232323",
        paddingVertical: 10,
        borderRadius: 10,
        alignItems: "center",
    },
    saveText: {
        color: "#FFFFFF",
        fontSize: 14,
        fontFamily: "Courier New",
    },
    ambientCircle: {
        position: "absolute",
        width: 180,
        height: 180,
        borderRadius: 90,
        backgroundColor: "#00E676",
        opacity: 0.08,
        bottom: -40,
        right: -50,
    },
    ambientStripe: {
        position: "absolute",
        width: 120,
        height: 220,
        borderRadius: 60,
        backgroundColor: "#2979FF",
        opacity: 0.1,
        top: 80,
        left: -40,
    },
});

export default HomeScreen;
