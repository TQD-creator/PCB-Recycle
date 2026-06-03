import React, { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, View } from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";

import { BackendConfigContext } from "./BackendConfigContext";
import HomeScreen from "./screens/HomeScreen";
import ScannerScreen from "./screens/ScannerScreen";
import HistoryScreen from "./screens/HistoryScreen";
import EditorScreen from "./screens/EditorScreen";

const Stack = createNativeStackNavigator();

const App = () => {
    const [backendIp, setBackendIp] = useState("");
    const [isReady, setIsReady] = useState(false);

    useEffect(() => {
        const loadConfig = async () => {
            const stored = await AsyncStorage.getItem("backend_ip");
            if (stored) {
                setBackendIp(stored);
            }
            setIsReady(true);
        };

        loadConfig();
    }, []);

    const setBackendIpAndStore = async (value) => {
        const trimmed = value.trim();
        setBackendIp(trimmed);
        await AsyncStorage.setItem("backend_ip", trimmed);
    };

    const contextValue = useMemo(
        () => ({ backendIp, setBackendIp: setBackendIpAndStore }),
        [backendIp]
    );

    if (!isReady) {
        return (
            <View style={{ flex: 1, backgroundColor: "#121212", alignItems: "center", justifyContent: "center" }}>
                <ActivityIndicator size="large" color="#00E676" />
            </View>
        );
    }

    return (
        <BackendConfigContext.Provider value={contextValue}>
            <NavigationContainer>
                <Stack.Navigator
                    screenOptions={{
                        headerStyle: { backgroundColor: "#0B0B0B" },
                        headerTintColor: "#FFFFFF",
                        headerTitleStyle: { fontFamily: "Georgia", fontWeight: "700" },
                    }}
                >
                    <Stack.Screen name="Home" component={HomeScreen} options={{ title: "PCB Ops" }} />
                    <Stack.Screen name="Scanner" component={ScannerScreen} options={{ title: "Scanner" }} />
                    <Stack.Screen name="History" component={HistoryScreen} options={{ title: "Audit History" }} />
                    <Stack.Screen name="Editor" component={EditorScreen} options={{ title: "Flywheel Correction" }} />
                </Stack.Navigator>
            </NavigationContainer>
        </BackendConfigContext.Provider>
    );
};

export default App;
