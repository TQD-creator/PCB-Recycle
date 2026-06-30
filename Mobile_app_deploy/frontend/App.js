import React, { useContext, useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Text, TouchableOpacity, View } from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { NavigationContainer } from "@react-navigation/native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { createNativeStackNavigator } from "@react-navigation/native-stack";

import { BackendConfigContext, buildBaseUrl } from "./BackendConfigContext";
import { useScanStore } from "./store/useScanStore";

import LoginScreen            from "./screens/LoginScreen";
import ScannerScreen          from "./screens/ScannerScreen";
import HistoryScreen          from "./screens/HistoryScreen";
import AnomalyQueueScreen     from "./screens/AnomalyQueueScreen";
import AdminCorrectionsScreen from "./screens/AdminCorrectionsScreen";
import EditorScreen           from "./screens/EditorScreen";

const Tab   = createBottomTabNavigator();
const Stack = createNativeStackNavigator();

const tabScreenOptions = {
    headerStyle:      { backgroundColor: "#101419" },
    headerTintColor:  "#FFFFFF",
    headerTitleStyle: { fontWeight: "700" },
    tabBarStyle:           { backgroundColor: "#11161C", borderTopColor: "#1D2834" },
    tabBarActiveTintColor:   "#10B981",
    tabBarInactiveTintColor: "#8FA3B8",
};

const LogoutButton = () => {
    const { backendIp } = useContext(BackendConfigContext);
    const { username, logout } = useScanStore();
    return (
        <TouchableOpacity
            onPress={() => logout(buildBaseUrl(backendIp))}
            style={{ marginRight: 14, paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8, borderWidth: 1, borderColor: "#EF4444" }}
        >
            <Text style={{ color: "#EF4444", fontSize: 12, fontWeight: "700" }}>
                {username ? `${username}  ·  Logout` : "Logout"}
            </Text>
        </TouchableOpacity>
    );
};

const tabsWithLogout = {
    ...tabScreenOptions,
    headerRight: () => <LogoutButton />,
};

const UserTabs = () => (
    <Tab.Navigator screenOptions={tabsWithLogout}>
        <Tab.Screen name="Scanner"   component={ScannerScreen}      options={{ title: "Scanner" }} />
        <Tab.Screen name="Inventory" component={HistoryScreen}       options={{ title: "Inventory" }} />
        <Tab.Screen name="Triage"    component={AnomalyQueueScreen}  options={{ title: "Anomaly Triage" }} />
    </Tab.Navigator>
);

const AdminTabs = () => (
    <Tab.Navigator screenOptions={tabsWithLogout}>
        <Tab.Screen name="Scanner"   component={ScannerScreen}           options={{ title: "Scanner" }} />
        <Tab.Screen name="Inventory" component={HistoryScreen}            options={{ title: "Inventory" }} />
        <Tab.Screen name="Triage"    component={AnomalyQueueScreen}       options={{ title: "Anomaly Triage" }} />
        <Tab.Screen name="Reviews"   component={AdminCorrectionsScreen}   options={{ title: "Corrections Review" }} />
    </Tab.Navigator>
);

const HEADER_OPTS = {
    headerShown: true,
    headerStyle: { backgroundColor: "#0A1118" },
    headerTintColor: "#FFFFFF",
    headerTitleStyle: { fontWeight: "700" },
};

const App = () => {
    const [backendIp, setBackendIpState] = useState("");
    const [isReady, setIsReady] = useState(false);

    const { token, role, restoreAuth, logout } = useScanStore();

    useEffect(() => {
        (async () => {
            const stored = await AsyncStorage.getItem("backend_ip");
            if (stored) setBackendIpState(stored);
            await restoreAuth();
            setIsReady(true);
        })();
    }, []);

    const setBackendIp = async (value) => {
        const trimmed = value.trim();
        setBackendIpState(trimmed);
        await AsyncStorage.setItem("backend_ip", trimmed);
    };

    const contextValue = useMemo(
        () => ({ backendIp, setBackendIp }),
        [backendIp],
    );

    if (!isReady) {
        return (
            <View style={{ flex: 1, backgroundColor: "#060B12", alignItems: "center", justifyContent: "center" }}>
                <ActivityIndicator size="large" color="#10B981" />
            </View>
        );
    }

    const MainTabs = role === "admin" ? AdminTabs : UserTabs;

    return (
        <BackendConfigContext.Provider value={contextValue}>
            <NavigationContainer>
                <Stack.Navigator screenOptions={{ headerShown: false }}>
                    {!token ? (
                        <Stack.Screen name="Login" component={LoginScreen} />
                    ) : (
                        <>
                            <Stack.Screen name="Main" component={MainTabs} />
                            <Stack.Screen
                                name="Editor"
                                component={EditorScreen}
                                options={{ ...HEADER_OPTS, title: "Correction Editor" }}
                            />
                        </>
                    )}
                </Stack.Navigator>
            </NavigationContainer>
        </BackendConfigContext.Provider>
    );
};

export default App;
