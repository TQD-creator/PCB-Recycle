import React, { useState, useRef } from 'react';
import { View, Image, StyleSheet, PanResponder, Modal, Text, TouchableOpacity, ScrollView } from 'react-native';
import Svg, { Rect } from 'react-native-svg';

// The Single Source of Truth for your taxonomy
const YOLO_CLASSES = [
    { label: "capacitor", display: "Capacitor" },
    { label: "resistor", display: "Resistor" },
    { label: "ic", display: "Integrated Circuit (IC)" },
    { label: "diode", display: "Diode" },
    { label: "led", display: "LED" },
    { label: "inductor", display: "Inductor" },
    { label: "connector", display: "Connector" },
    { label: "unknown", display: "Unknown / Other" },
];

const BoundingBoxEditor = ({ imageUri, onSave }) => {
    const [boxes, setBoxes] = useState([]);
    const [currentBox, setCurrentBox] = useState(null);
    const [modalVisible, setModalVisible] = useState(false);
    const [tempBoxIndex, setTempBoxIndex] = useState(null);

    // The PanResponder tracks the user's finger on the screen
    const panResponder = useRef(
        PanResponder.create({
            onStartShouldSetPanResponder: () => true,
            onMoveShouldSetPanResponder: () => true,
            
            // FINGER TOUCHES DOWN
            onPanResponderGrant: (evt) => {
                const { locationX, locationY } = evt.nativeEvent;
                setCurrentBox({
                    startX: locationX,
                    startY: locationY,
                    currentX: locationX,
                    currentY: locationY,
                });
            },
            
            // FINGER DRAGS
            onPanResponderMove: (evt) => {
                const { locationX, locationY } = evt.nativeEvent;
                setCurrentBox((prev) => ({
                    ...prev,
                    currentX: locationX,
                    currentY: locationY,
                }));
            },
            
            // FINGER LIFTS UP
            onPanResponderRelease: () => {
                setCurrentBox((prev) => {
                    if (!prev) return null;
                    
                    // Calculate exact width and height, accounting for dragging backwards
                    const width = Math.abs(prev.currentX - prev.startX);
                    const height = Math.abs(prev.currentY - prev.startY);
                    const x = Math.min(prev.startX, prev.currentX);
                    const y = Math.min(prev.startY, prev.currentY);

                    // Ignore accidental micro-taps (boxes smaller than 10x10 pixels)
                    if (width > 10 && height > 10) {
                        setBoxes((currentBoxes) => {
                            const newBoxes = [...currentBoxes, { x, y, width, height, label: null, displayLabel: null }];
                            setTempBoxIndex(newBoxes.length - 1);
                            setModalVisible(true); // Trigger the labeling modal
                            return newBoxes;
                        });
                    }
                    return null;
                });
            },
        })
    ).current;

    const assignLabel = (item) => {
        setBoxes((prev) => {
            const updated = [...prev];
            updated[tempBoxIndex].label = item.label; // The raw backend string (e.g., 'capacitor')
            updated[tempBoxIndex].displayLabel = item.display; // The UI string (e.g., 'Capacitor')
            return updated;
        });
        setModalVisible(false);
    };

    return (
        <View style={styles.container}>
            {/* The Image and SVG Canvas share the exact same space */}
            <View style={styles.canvasContainer} {...panResponder.panHandlers}>
                <Image source={{ uri: imageUri }} style={styles.image} resizeMode="stretch" />
                
                <Svg style={StyleSheet.absoluteFill}>
                    {/* Render saved boxes */}
                    {boxes.map((box, index) => (
                        <Rect
                            key={index}
                            x={box.x}
                            y={box.y}
                            width={box.width}
                            height={box.height}
                            stroke={box.label ? "#00E676" : "#FF1744"}
                            strokeWidth="3"
                            fill="rgba(0, 230, 118, 0.2)"
                        />
                    ))}
                    
                    {/* Render the box currently being drawn by the finger */}
                    {currentBox && (
                        <Rect
                            x={Math.min(currentBox.startX, currentBox.currentX)}
                            y={Math.min(currentBox.startY, currentBox.currentY)}
                            width={Math.abs(currentBox.currentX - currentBox.startX)}
                            height={Math.abs(currentBox.currentY - currentBox.startY)}
                            stroke="#FFEA00"
                            strokeWidth="2"
                            strokeDasharray="5, 5"
                            fill="rgba(255, 234, 0, 0.2)"
                        />
                    )}
                </Svg>
            </View>

            {/* The Modal for Tagging */}
            <Modal visible={modalVisible} transparent={true} animationType="slide">
                <View style={styles.modalOverlay}>
                    <View style={styles.modalContent}>
                        <Text style={styles.modalTitle}>Select Component Type</Text>
                        
                        {/* ScrollView prevents the 8 buttons from breaking smaller screens */}
                        <ScrollView style={styles.scrollArea} showsVerticalScrollIndicator={true}>
                            {YOLO_CLASSES.map((item, idx) => (
                                <TouchableOpacity 
                                    key={idx} 
                                    style={styles.tagButton} 
                                    onPress={() => assignLabel(item)}
                                >
                                    <Text style={styles.tagText}>{item.display}</Text>
                                </TouchableOpacity>
                            ))}
                        </ScrollView>

                        <TouchableOpacity style={styles.cancelButton} onPress={() => {
                            // If they cancel, delete the box they just drew
                            setBoxes((prev) => prev.filter((_, i) => i !== tempBoxIndex));
                            setModalVisible(false);
                        }}>
                            <Text style={styles.cancelText}>Delete Box (Cancel)</Text>
                        </TouchableOpacity>
                    </View>
                </View>
            </Modal>

            {/* Submit Button to trigger Phase 2 API */}
            <TouchableOpacity 
                style={[styles.submitButton, boxes.length === 0 && styles.submitButtonDisabled]} 
                onPress={() => onSave(boxes)}
                disabled={boxes.length === 0}
            >
                <Text style={styles.submitText}>
                    {boxes.length === 0 ? "Draw a box to begin" : `Submit ${boxes.length} Correction(s)`}
                </Text>
            </TouchableOpacity>
        </View>
    );
};

const styles = StyleSheet.create({
    container: { flex: 1, backgroundColor: '#121212' },
    canvasContainer: { flex: 1, position: 'relative' },
    image: { width: '100%', height: '100%' },
    modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.85)', justifyContent: 'flex-end' },
    modalContent: { backgroundColor: '#1E1E1E', borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 24, maxHeight: '80%' },
    modalTitle: { color: '#FFF', fontSize: 18, fontFamily: 'Georgia', fontWeight: 'bold', marginBottom: 20, textAlign: 'center' },
    scrollArea: { marginBottom: 10 },
    tagButton: { backgroundColor: '#2979FF', padding: 16, borderRadius: 12, marginBottom: 10 },
    tagText: { color: '#FFF', textAlign: 'center', fontWeight: '600', fontSize: 16 },
    cancelButton: { backgroundColor: '#2B2B2B', padding: 16, borderRadius: 12, marginTop: 10 },
    cancelText: { color: '#FF4444', textAlign: 'center', fontWeight: 'bold', fontSize: 16 },
    submitButton: { backgroundColor: '#00E676', padding: 20, alignItems: 'center', paddingBottom: 35 },
    submitButtonDisabled: { backgroundColor: '#1A3324' },
    submitText: { color: '#121212', fontWeight: 'bold', fontSize: 16 }
});

export default BoundingBoxEditor;