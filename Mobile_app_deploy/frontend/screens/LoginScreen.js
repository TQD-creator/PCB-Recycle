import React, { useContext, useState } from "react";
import {
    ActivityIndicator, Alert, KeyboardAvoidingView, Platform,
    StyleSheet, Text, TextInput, TouchableOpacity, View,
} from "react-native";

import { BackendConfigContext, buildBaseUrl } from "../BackendConfigContext";
import { useScanStore } from "../store/useScanStore";

const LoginScreen = () => {
    const { backendIp, setBackendIp } = useContext(BackendConfigContext);
    const login = useScanStore((s) => s.login);

    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [loading, setLoading] = useState(false);

    const handleLogin = async () => {
        if (!backendIp.trim()) { Alert.alert("Missing IP", "Enter the backend IP address first."); return; }
        if (!username.trim())  { Alert.alert("Missing field", "Enter your username."); return; }
        if (!password)         { Alert.alert("Missing field", "Enter your password."); return; }

        setLoading(true);
        try {
            await login(buildBaseUrl(backendIp), username.trim(), password);
            // Navigation updates automatically — App.js watches token state
        } catch (err) {
            const msg = err?.response?.data?.detail || "Check your credentials and backend IP.";
            Alert.alert("Login failed", msg);
        } finally {
            setLoading(false);
        }
    };

    return (
        <KeyboardAvoidingView style={styles.root} behavior={Platform.OS === "ios" ? "padding" : undefined}>
            <View style={styles.card}>
                <Text style={styles.title}>PCB Inspector</Text>
                <Text style={styles.subtitle}>Sign in to continue</Text>

                <Text style={styles.label}>Backend IP</Text>
                <TextInput
                    style={styles.input}
                    placeholder="192.168.x.x"
                    placeholderTextColor="#4B5563"
                    value={backendIp}
                    onChangeText={setBackendIp}
                    autoCapitalize="none"
                    keyboardType="default"
                />

                <Text style={styles.label}>Username</Text>
                <TextInput
                    style={styles.input}
                    placeholder="admin  or  user"
                    placeholderTextColor="#4B5563"
                    value={username}
                    onChangeText={setUsername}
                    autoCapitalize="none"
                    autoCorrect={false}
                />

                <Text style={styles.label}>Password</Text>
                <TextInput
                    style={styles.input}
                    placeholder="••••••••"
                    placeholderTextColor="#4B5563"
                    value={password}
                    onChangeText={setPassword}
                    secureTextEntry
                />

                <TouchableOpacity style={styles.btn} onPress={handleLogin} disabled={loading}>
                    {loading
                        ? <ActivityIndicator color="#022C22" />
                        : <Text style={styles.btnTxt}>Sign In</Text>}
                </TouchableOpacity>

                <Text style={styles.hint}>Default: admin/admin123 · user/user123</Text>
            </View>
        </KeyboardAvoidingView>
    );
};

const styles = StyleSheet.create({
    root:     { flex: 1, backgroundColor: "#060B12", alignItems: "center", justifyContent: "center", padding: 24 },
    card:     { width: "100%", maxWidth: 400, backgroundColor: "#0F1923", borderRadius: 20, padding: 28, borderWidth: 1, borderColor: "#1D2834" },
    title:    { color: "#F8FAFC", fontSize: 26, fontWeight: "900", textAlign: "center", marginBottom: 4 },
    subtitle: { color: "#64748B", fontSize: 14, textAlign: "center", marginBottom: 28 },
    label:    { color: "#94A3B8", fontSize: 13, fontWeight: "600", marginBottom: 6, marginTop: 12 },
    input:    { backgroundColor: "#1E293B", borderRadius: 10, paddingHorizontal: 14, paddingVertical: 12, color: "#F8FAFC", fontSize: 15, borderWidth: 1, borderColor: "#334155" },
    btn:      { marginTop: 24, backgroundColor: "#10B981", borderRadius: 12, paddingVertical: 15, alignItems: "center" },
    btnTxt:   { color: "#022C22", fontWeight: "800", fontSize: 16 },
    hint:     { color: "#334155", fontSize: 11, textAlign: "center", marginTop: 16 },
});

export default LoginScreen;
