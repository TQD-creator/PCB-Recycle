import React, { useContext } from 'react';
import { View, StyleSheet, Alert, Dimensions } from 'react-native';
import * as FileSystem from 'expo-file-system/legacy';
import * as ImageManipulator from 'expo-image-manipulator'; // <-- THE HEIC ASSASSIN
import BoundingBoxEditor from './BoundingBoxEditor'; 
import { BackendConfigContext, buildBaseUrl } from '../BackendConfigContext';

const API_BASE_URL = ""; 

const EditorScreen = ({ route, navigation }) => {
    const { imageUri, scanId } = route.params || {};
    const { backendIp } = useContext(BackendConfigContext);

    if (!imageUri) {
        Alert.alert("Error", "No image provided to the editor.");
        navigation.goBack();
        return null;
    }

    const getBaseUrl = () => (backendIp ? buildBaseUrl(backendIp) : API_BASE_URL);

    const handleSaveToFlywheel = async (correctedBoxes) => {
        try {
            const baseUrl = getBaseUrl();
            if (!baseUrl) {
                Alert.alert("Missing API", "Set the backend IP on the Home screen first.");
                return;
            }

            const ingestUrl = `${baseUrl}/api/v2/flywheel/ingest`;
            
            console.log("\n[!] ================= FLYWHEEL UPLOAD INITIATED ================= [!]");
            console.log(`[*] Target URL: ${ingestUrl}`);
            
            // 1. Force the OS to transcode the image to a guaranteed JPEG
            // This strips away Apple HEIC formatting and protects the Python backend.
            console.log("[*] Transcoding image to standard JPEG...");
            const transcodeResult = await ImageManipulator.manipulateAsync(
                imageUri,
                [], // No geometric actions (resizing/cropping) needed
                { compress: 0.9, format: ImageManipulator.SaveFormat.JPEG }
            );
            const safeJpegUri = transcodeResult.uri;
            console.log("[*] Transcoding complete.");

            const screenWidth = Dimensions.get('window').width;
            const screenHeight = Dimensions.get('window').height;

            // 2. Fire the payload using the safely transcoded JPEG
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

    return (
        <View style={styles.container}>
            <BoundingBoxEditor 
                imageUri={imageUri} 
                onSave={handleSaveToFlywheel} 
            />
        </View>
    );
};

const styles = StyleSheet.create({
    container: { flex: 1, backgroundColor: '#121212' }
});

export default EditorScreen;