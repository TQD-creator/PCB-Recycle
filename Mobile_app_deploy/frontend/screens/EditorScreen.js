import React, { useContext, useEffect, useState } from 'react';
import { View, StyleSheet, Alert, Dimensions, ActivityIndicator, Text } from 'react-native';
import * as FileSystem from 'expo-file-system/legacy';
import * as ImageManipulator from 'expo-image-manipulator'; 
import BoundingBoxEditor from './BoundingBoxEditor'; 
import { BackendConfigContext, buildBaseUrl } from '../BackendConfigContext';

const API_BASE_URL = ""; 

const EditorScreen = ({ route, navigation }) => {
    // We only rely on the scanId now. We will fetch the image dynamically.
    const { scanId } = route.params || {};
    const { backendIp } = useContext(BackendConfigContext);
    
    const [localImageUri, setLocalImageUri] = useState(null);
    const [isLoading, setIsLoading] = useState(true);

    const getBaseUrl = () => (backendIp ? buildBaseUrl(backendIp) : API_BASE_URL);

    // --- SECURE DOWNLOAD ENGINE ---
    useEffect(() => {
        const fetchFlattenedImage = async () => {
            const baseUrl = getBaseUrl();
            if (!scanId || !baseUrl) {
                Alert.alert("Error", "Missing Scan ID or Backend API.");
                navigation.goBack();
                return;
            }

            try {
                const remoteUri = `${baseUrl}/api/v2/scans/image/${scanId}`;
                const localPath = `${FileSystem.cacheDirectory}flattened_${scanId}.jpg`;
                
                console.log(`[*] Downloading flattened image: ${remoteUri}`);
                
                // We download the image to the phone's local cache so C++ modules don't crash
                const { uri, status } = await FileSystem.downloadAsync(remoteUri, localPath);
                
                if (status === 200) {
                    setLocalImageUri(uri);
                } else {
                    throw new Error(`Server returned HTTP ${status}`);
                }
            } catch (error) {
                console.error("[-] Download failed:", error);
                Alert.alert("Download Error", "Failed to fetch the flattened image from the server.");
                navigation.goBack();
            } finally {
                setIsLoading(false);
            }
        };

        fetchFlattenedImage();
    }, [scanId, backendIp]);

    const handleSaveToFlywheel = async (correctedBoxes) => {
        try {
            const baseUrl = getBaseUrl();
            const ingestUrl = `${baseUrl}/api/v2/flywheel/ingest`;
            
            console.log("\n[!] ================= FLYWHEEL UPLOAD INITIATED ================= [!]");
            console.log(`[*] Target URL: ${ingestUrl}`);
            
            console.log("[*] Transcoding image to standard JPEG...");
            const transcodeResult = await ImageManipulator.manipulateAsync(
                localImageUri, // Use the perfectly flattened image we just downloaded
                [], 
                { compress: 0.9, format: ImageManipulator.SaveFormat.JPEG }
            );
            const safeJpegUri = transcodeResult.uri;
            console.log("[*] Transcoding complete.");

            const screenWidth = Dimensions.get('window').width;
            const screenHeight = Dimensions.get('window').height;

            const uploadResult = await FileSystem.uploadAsync(ingestUrl, safeJpegUri, {
                httpMethod: 'POST',
                uploadType: 1, 
                fieldName: 'file',
                mimeType: 'image/jpeg',
                parameters: {
                    boxes: JSON.stringify(correctedBoxes),
                    screen_width: screenWidth.toString(),
                    screen_height: screenHeight.toString()
                }
            });

            const responseData = JSON.parse(uploadResult.body);

            if (uploadResult.status === 200 && responseData.status === "success") {
                console.log("[+] SUCCESS: Standard JPEG payload delivered flawlessly.");
                Alert.alert(
                    "Flywheel Updated", 
                    "The AI has received your corrections and added them to the staging queue.",
                    [{ text: "OK", onPress: () => navigation.goBack() }]
                );
            } else {
                console.error("[-] SERVER REJECTED PAYLOAD:", responseData);
                Alert.alert("Server Error", responseData.detail || "The server rejected the data.");
            }
        } catch (error) {
            console.error("[-] CRITICAL NETWORK FAILURE:", error.message);
            Alert.alert("Network Error", `Could not reach backend: ${error.message}`);
        }
    };

    // Render a loading screen while the 1000x1000 image is downloaded
    if (isLoading) {
        return (
            <View style={styles.loadingContainer}>
                <ActivityIndicator size="large" color="#00E676" />
                <Text style={styles.loadingText}>Fetching Flattened PCB...</Text>
            </View>
        );
    }

    return (
        <View style={styles.container}>
            <BoundingBoxEditor 
                imageUri={localImageUri} 
                onSave={handleSaveToFlywheel} 
            />
        </View>
    );
};

const styles = StyleSheet.create({
    container: { 
        flex: 1, 
        backgroundColor: '#121212' 
    },
    loadingContainer: { 
        flex: 1, 
        backgroundColor: '#121212', 
        justifyContent: 'center', 
        alignItems: 'center' 
    },
    loadingText: { 
        color: '#00E676', 
        marginTop: 16, 
        fontFamily: 'Georgia', 
        fontSize: 16,
        fontWeight: 'bold'
    }
});

export default EditorScreen;