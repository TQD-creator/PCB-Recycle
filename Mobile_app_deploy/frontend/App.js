import React, { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, View } from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { NavigationContainer } from "@react-navigation/native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";

import { BackendConfigContext } from "./BackendConfigContext";
import ScannerScreen from "./screens/ScannerScreen";
import HistoryScreen from "./screens/HistoryScreen";
import AnomalyQueueScreen from "./screens/AnomalyQueueScreen";

const Tab = createBottomTabNavigator();

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
                <Tab.Navigator
                    screenOptions={{
                        headerStyle: { backgroundColor: "#101419" },
                        headerTintColor: "#FFFFFF",
                        headerTitleStyle: { fontWeight: "700" },
                        tabBarStyle: { backgroundColor: "#11161C", borderTopColor: "#1D2834" },
                        tabBarActiveTintColor: "#10B981",
                        tabBarInactiveTintColor: "#8FA3B8",
                    }}
                >
                    <Tab.Screen name="Scanner" component={ScannerScreen} options={{ title: "Scanner" }} />
                    <Tab.Screen name="Inventory" component={HistoryScreen} options={{ title: "Inventory Dashboard" }} />
                    <Tab.Screen name="Triage" component={AnomalyQueueScreen} options={{ title: "Anomaly Triage" }} />
                </Tab.Navigator>
            </NavigationContainer>
        </BackendConfigContext.Provider>
    );
};

export default App;
