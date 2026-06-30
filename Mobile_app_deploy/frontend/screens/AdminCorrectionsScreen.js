import React, { useCallback, useContext, useEffect, useState } from "react";
import {
    ActivityIndicator, Alert, FlatList, Image, Modal, RefreshControl,
    ScrollView, StyleSheet, Text, TouchableOpacity, View,
} from "react-native";
import Svg, { Rect, Text as SvgText } from "react-native-svg";
import { useFocusEffect } from "@react-navigation/native";

import { BackendConfigContext, buildBaseUrl } from "../BackendConfigContext";
import { fetchCorrections, reviewCorrection } from "../services/scanService";

// Per-action colour palette (stroke + fill)
const ACTION_COLOR = {
    ADD:              { s: "#06B6D4", f: "rgba(6,182,212,0.18)"   },
    RELABEL:          { s: "#FACC15", f: "rgba(250,204,21,0.18)"  },
    RELABEL_VERIFIED: { s: "#A78BFA", f: "rgba(167,139,250,0.18)" },
    DELETE_VERIFIED:  { s: "#EF4444", f: "rgba(239,68,68,0.18)"   },
    DELETE_ANOMALY:   { s: "#EF4444", f: "rgba(239,68,68,0.18)"   },
};
const ACTION_LABEL = {
    ADD:              "New component added",
    RELABEL:          "Anomaly relabeled",
    RELABEL_VERIFIED: "Verified component relabeled",
    DELETE_VERIFIED:  "Verified component removed",
    DELETE_ANOMALY:   "Anomaly removed",
};

const STATUS = {
    PENDING:  { border: "#F59E0B", text: "#F59E0B" },
    APPROVED: { border: "#10B981", text: "#10B981" },
    REJECTED: { border: "#EF4444", text: "#EF4444" },
};

const fmtDate = (iso) => {
    if (!iso) return "—";
    const d = new Date(iso);
    return `${d.toLocaleDateString()}  ${d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
};


// ─────────────────────────────────────────────────────────────────────────────
// Full-screen review modal — shows board image + overlaid correction boxes
// ─────────────────────────────────────────────────────────────────────────────
const ReviewModal = ({ item, onClose, onReview }) => {
    const [imgSize,     setImgSize]     = useState(null);  // { width, height } in pixels
    const [canvasWidth, setCanvasWidth] = useState(0);     // measured display width
    const [busy,        setBusy]        = useState(false);

    useEffect(() => {
        if (!item?.image_url) return;
        setImgSize(null);
        Image.getSize(
            item.image_url,
            (w, h) => setImgSize({ width: w, height: h }),
            ()      => setImgSize({ width: 1, height: 1 }), // fallback
        );
    }, [item?.image_url]);

    if (!item) return null;

    const hasImage   = !!item.image_url;
    const scaleReady = imgSize && canvasWidth > 0;
    // uniform scale: canvas pixel → display pixel
    const scale      = scaleReady ? canvasWidth / imgSize.width : 0;
    const aspectRatio = imgSize ? imgSize.width / imgSize.height : 16 / 9;
    const sc = STATUS[item.status] || STATUS.PENDING;

    const doReview = async (action) => {
        setBusy(true);
        try { await onReview(item.id, action); onClose(); }
        catch (err) { Alert.alert("Error", err?.response?.data?.detail || "Review failed."); }
        finally { setBusy(false); }
    };

    return (
        <Modal visible animationType="slide" onRequestClose={onClose}>
            <View style={rm.root}>

                {/* ── Header ── */}
                <View style={rm.header}>
                    <View style={{ flex: 1 }}>
                        <Text style={rm.htitle}>Correction Review</Text>
                        <Text style={rm.hsub} numberOfLines={1}>{item.task_id}</Text>
                    </View>
                    <View style={[rm.badge, { borderColor: sc.border }]}>
                        <Text style={[rm.badgeTxt, { color: sc.text }]}>{item.status}</Text>
                    </View>
                    <TouchableOpacity style={rm.closeBtn} onPress={onClose}>
                        <Text style={rm.closeTxt}>✕</Text>
                    </TouchableOpacity>
                </View>

                <ScrollView style={{ flex: 1 }} showsVerticalScrollIndicator={false}>

                    {/* ── Board image with overlaid correction boxes ── */}
                    <View
                        style={[rm.imgContainer, { aspectRatio }]}
                        onLayout={(e) => setCanvasWidth(e.nativeEvent.layout.width)}
                    >
                        {hasImage ? (
                            <Image
                                source={{ uri: item.image_url }}
                                style={StyleSheet.absoluteFill}
                                resizeMode="stretch"
                            />
                        ) : (
                            <View style={[StyleSheet.absoluteFill, rm.noImage]}>
                                <Text style={rm.noImageTxt}>No image stored</Text>
                            </View>
                        )}

                        {/* Loading spinner while image dimensions resolve */}
                        {hasImage && !imgSize && (
                            <View style={[StyleSheet.absoluteFill, rm.imgLoading]}>
                                <ActivityIndicator color="#10B981" size="large" />
                                <Text style={rm.imgLoadingTxt}>Loading image…</Text>
                            </View>
                        )}

                        {/* SVG correction overlays */}
                        {scale > 0 && (
                            <Svg style={StyleSheet.absoluteFill}>
                                {item.corrections.map((c, i) => {
                                    const ac    = ACTION_COLOR[c.action] ?? { s: "#94A3B8", f: "rgba(148,163,184,0.15)" };
                                    const x     = c.bbox[0] * scale;
                                    const y     = c.bbox[1] * scale;
                                    const bw    = (c.bbox[2] - c.bbox[0]) * scale;
                                    const bh    = (c.bbox[3] - c.bbox[1]) * scale;
                                    const isDel = c.action?.startsWith("DELETE");
                                    // Label shown inside/above the box
                                    const lbl   = c.label ? `${c.label}` : "(remove)";
                                    // Index tag so admin can cross-reference the list below
                                    const tag   = `#${i + 1}`;
                                    return (
                                        <React.Fragment key={i}>
                                            <Rect
                                                x={x} y={y} width={bw} height={bh}
                                                stroke={ac.s} strokeWidth={2.5}
                                                fill={ac.f}
                                                strokeDasharray={isDel ? "8,4" : undefined}
                                            />
                                            {/* Index tag (top-left corner) */}
                                            <Rect
                                                x={x} y={y}
                                                width={Math.max(bw * 0.22, 22)} height={15}
                                                fill={ac.s} rx={3}
                                            />
                                            <SvgText
                                                x={x + 4} y={y + 11}
                                                fontSize={9} fill="#000" fontWeight="bold"
                                            >
                                                {tag}
                                            </SvgText>
                                            {/* Label below the top edge */}
                                            <SvgText
                                                x={x + 3} y={y + 26}
                                                fontSize={10} fill={ac.s} fontWeight="bold"
                                            >
                                                {lbl}
                                            </SvgText>
                                        </React.Fragment>
                                    );
                                })}
                            </Svg>
                        )}
                    </View>

                    {/* ── Legend ── */}
                    <View style={rm.legend}>
                        {Object.entries(ACTION_COLOR)
                            .filter(([k]) => k !== "DELETE_ANOMALY") // deduplicate red
                            .map(([action, { s }]) => (
                                <View key={action} style={rm.li}>
                                    <View style={[rm.dot, { backgroundColor: s }]} />
                                    <Text style={rm.lt}>{ACTION_LABEL[action] ?? action}</Text>
                                </View>
                            ))}
                        <View style={rm.li}>
                            <Text style={[rm.lt, { color: "#475569" }]}>Dashed border = deletion</Text>
                        </View>
                    </View>

                    {/* ── Numbered correction list ── */}
                    <View style={rm.section}>
                        <Text style={rm.sectionTitle}>
                            {item.corrections.length} Correction{item.corrections.length !== 1 ? "s" : ""}
                        </Text>
                        {item.corrections.map((c, i) => {
                            const ac = ACTION_COLOR[c.action] ?? { s: "#94A3B8" };
                            return (
                                <View key={i} style={rm.corrRow}>
                                    {/* Index badge */}
                                    <View style={[rm.indexBadge, { backgroundColor: ac.s }]}>
                                        <Text style={rm.indexTxt}>#{i + 1}</Text>
                                    </View>

                                    <View style={{ flex: 1, gap: 2 }}>
                                        {/* Action label */}
                                        <View style={[rm.actionPill, { borderColor: ac.s }]}>
                                            <Text style={[rm.actionTxt, { color: ac.s }]}>{c.action}</Text>
                                        </View>
                                        {/* Component label */}
                                        <Text style={rm.corrLabel}>
                                            {c.label ? c.label : <Text style={{ color: "#EF4444" }}>(mark for removal)</Text>}
                                        </Text>
                                        {/* Coordinates */}
                                        <Text style={rm.corrBbox}>
                                            coords  [{c.bbox?.[0]}, {c.bbox?.[1]}] → [{c.bbox?.[2]}, {c.bbox?.[3]}]
                                        </Text>
                                    </View>
                                </View>
                            );
                        })}
                    </View>

                    {/* Submitted info */}
                    <View style={rm.section}>
                        <Text style={rm.metaTxt}>Submitted: {fmtDate(item.submitted_at)}</Text>
                        {item.reviewed_at && (
                            <Text style={rm.metaTxt}>Reviewed: {fmtDate(item.reviewed_at)}</Text>
                        )}
                        {item.reviewer_note && (
                            <Text style={rm.metaTxt}>Note: {item.reviewer_note}</Text>
                        )}
                    </View>

                    <View style={{ height: 140 }} />
                </ScrollView>

                {/* ── Approve / Reject ── */}
                {item.status === "PENDING" && (
                    <View style={rm.actions}>
                        {busy ? (
                            <ActivityIndicator color="#10B981" style={{ flex: 1 }} />
                        ) : (
                            <>
                                <TouchableOpacity style={rm.approveBtn} onPress={() => doReview("APPROVE")}>
                                    <Text style={rm.approveTxt}>✓  Approve</Text>
                                </TouchableOpacity>
                                <TouchableOpacity style={rm.rejectBtn} onPress={() => doReview("REJECT")}>
                                    <Text style={rm.rejectTxt}>✕  Reject</Text>
                                </TouchableOpacity>
                            </>
                        )}
                    </View>
                )}
            </View>
        </Modal>
    );
};


// ─────────────────────────────────────────────────────────────────────────────
// Summary card in the list
// ─────────────────────────────────────────────────────────────────────────────
const CorrectionCard = ({ item, onPress }) => {
    const sc = STATUS[item.status] || STATUS.PENDING;
    // Tally action types for quick summary
    const counts = item.corrections.reduce((acc, c) => {
        acc[c.action] = (acc[c.action] || 0) + 1;
        return acc;
    }, {});

    return (
        <TouchableOpacity
            style={[styles.card, { borderLeftColor: sc.border }]}
            onPress={onPress}
            activeOpacity={0.8}
        >
            <View style={styles.cardTop}>
                <Text style={styles.taskId} numberOfLines={1}>{item.task_id.slice(0, 18)}…</Text>
                <View style={[styles.badge, { borderColor: sc.border }]}>
                    <Text style={[styles.badgeTxt, { color: sc.text }]}>{item.status}</Text>
                </View>
            </View>

            {/* Action summary chips */}
            <View style={styles.chips}>
                {Object.entries(counts).map(([action, n]) => {
                    const color = ACTION_COLOR[action]?.s ?? "#94A3B8";
                    return (
                        <View key={action} style={[styles.chip, { borderColor: color }]}>
                            <Text style={[styles.chipTxt, { color }]}>
                                {n}× {action.replace("_", " ")}
                            </Text>
                        </View>
                    );
                })}
            </View>

            <Text style={styles.meta}>{fmtDate(item.submitted_at)}</Text>
            <Text style={styles.tapHint}>Tap to review image →</Text>
        </TouchableOpacity>
    );
};


// ─────────────────────────────────────────────────────────────────────────────
// Main screen
// ─────────────────────────────────────────────────────────────────────────────
const AdminCorrectionsScreen = () => {
    const { backendIp } = useContext(BackendConfigContext);
    const baseUrl = buildBaseUrl(backendIp);

    const [corrections, setCorrections] = useState([]);
    const [loading,     setLoading]     = useState(false);
    const [previewItem, setPreviewItem] = useState(null);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const data = await fetchCorrections(baseUrl);
            setCorrections(data);
        } catch (err) {
            Alert.alert("Error", err?.response?.data?.detail || "Failed to load corrections.");
        } finally {
            setLoading(false);
        }
    }, [baseUrl]);

    useFocusEffect(useCallback(() => { load(); }, [load]));

    const handleReview = async (correctionId, action) => {
        await reviewCorrection(baseUrl, correctionId, action);
        setCorrections((prev) =>
            prev.map((c) => c.id === correctionId ? { ...c, status: action } : c)
        );
    };

    const pending  = corrections.filter((c) => c.status === "PENDING").length;
    const approved = corrections.filter((c) => c.status === "APPROVED").length;
    const rejected = corrections.filter((c) => c.status === "REJECTED").length;

    return (
        <View style={styles.root}>
            {/* Summary strip */}
            <View style={styles.summary}>
                <View style={styles.stat}>
                    <Text style={[styles.statNum, { color: "#F59E0B" }]}>{pending}</Text>
                    <Text style={styles.statLbl}>Pending</Text>
                </View>
                <View style={styles.stat}>
                    <Text style={[styles.statNum, { color: "#10B981" }]}>{approved}</Text>
                    <Text style={styles.statLbl}>Approved</Text>
                </View>
                <View style={styles.stat}>
                    <Text style={[styles.statNum, { color: "#EF4444" }]}>{rejected}</Text>
                    <Text style={styles.statLbl}>Rejected</Text>
                </View>
            </View>

            <FlatList
                data={corrections}
                keyExtractor={(item) => `${item.id}`}
                contentContainerStyle={styles.list}
                refreshControl={<RefreshControl refreshing={loading} onRefresh={load} tintColor="#10B981" />}
                ListEmptyComponent={
                    loading ? null : (
                        <View style={styles.empty}>
                            <Text style={styles.emptyTxt}>No corrections submitted yet.</Text>
                            <Text style={[styles.emptyTxt, { fontSize: 12, marginTop: 6 }]}>
                                Pull down to refresh.
                            </Text>
                        </View>
                    )
                }
                renderItem={({ item }) => (
                    <CorrectionCard item={item} onPress={() => setPreviewItem(item)} />
                )}
            />

            {/* Full-screen image review modal */}
            {previewItem && (
                <ReviewModal
                    item={previewItem}
                    onClose={() => { setPreviewItem(null); load(); }}
                    onReview={handleReview}
                />
            )}
        </View>
    );
};


// ─────────────────────────────────────────────────────────────────────────────
// Styles
// ─────────────────────────────────────────────────────────────────────────────
const styles = StyleSheet.create({
    root:      { flex: 1, backgroundColor: "#060B12" },
    summary:   { flexDirection: "row", backgroundColor: "#0F1923", paddingVertical: 14, borderBottomWidth: 1, borderColor: "#1D2834" },
    stat:      { flex: 1, alignItems: "center" },
    statNum:   { fontSize: 24, fontWeight: "900" },
    statLbl:   { color: "#64748B", fontSize: 12 },
    list:      { padding: 12, gap: 10 },
    card:      { backgroundColor: "#0F1923", borderRadius: 14, borderLeftWidth: 4, padding: 14, gap: 6 },
    cardTop:   { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
    taskId:    { color: "#F8FAFC", fontWeight: "700", fontSize: 13, fontFamily: "monospace", flex: 1, marginRight: 8 },
    badge:     { borderWidth: 1, borderRadius: 6, paddingHorizontal: 8, paddingVertical: 2 },
    badgeTxt:  { fontSize: 11, fontWeight: "800" },
    chips:     { flexDirection: "row", flexWrap: "wrap", gap: 6 },
    chip:      { borderWidth: 1, borderRadius: 6, paddingHorizontal: 7, paddingVertical: 2 },
    chipTxt:   { fontSize: 10, fontWeight: "700" },
    meta:      { color: "#64748B", fontSize: 12 },
    tapHint:   { color: "#1E3A5F", fontSize: 11 },
    empty:     { alignItems: "center", paddingTop: 60 },
    emptyTxt:  { color: "#334155", fontSize: 15 },
});

// Review modal styles
const rm = StyleSheet.create({
    root:          { flex: 1, backgroundColor: "#060B12" },
    header:        { flexDirection: "row", alignItems: "center", gap: 10, paddingHorizontal: 16, paddingVertical: 12, backgroundColor: "#0F1923", borderBottomWidth: 1, borderColor: "#1D2834" },
    htitle:        { color: "#F8FAFC", fontWeight: "800", fontSize: 16 },
    hsub:          { color: "#64748B", fontSize: 11, fontFamily: "monospace" },
    badge:         { borderWidth: 1, borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3 },
    badgeTxt:      { fontSize: 11, fontWeight: "800" },
    closeBtn:      { backgroundColor: "#1E293B", borderRadius: 8, paddingHorizontal: 12, paddingVertical: 7 },
    closeTxt:      { color: "#94A3B8", fontWeight: "700", fontSize: 14 },
    imgContainer:  { width: "100%", backgroundColor: "#020617" },
    noImage:       { alignItems: "center", justifyContent: "center", backgroundColor: "#0F1923" },
    noImageTxt:    { color: "#334155", fontSize: 14 },
    imgLoading:    { alignItems: "center", justifyContent: "center", backgroundColor: "rgba(0,0,0,0.6)", gap: 8 },
    imgLoadingTxt: { color: "#94A3B8", fontSize: 13 },
    legend:        { flexDirection: "row", flexWrap: "wrap", gap: 10, paddingHorizontal: 14, paddingVertical: 10, backgroundColor: "#0F1923", borderBottomWidth: 1, borderColor: "#1D2834" },
    li:            { flexDirection: "row", alignItems: "center", gap: 5 },
    dot:           { width: 8, height: 8, borderRadius: 4 },
    lt:            { color: "#94A3B8", fontSize: 10 },
    section:       { paddingHorizontal: 14, paddingVertical: 12, borderBottomWidth: 1, borderColor: "#1D2834" },
    sectionTitle:  { color: "#94A3B8", fontSize: 12, fontWeight: "700", marginBottom: 10, textTransform: "uppercase", letterSpacing: 0.8 },
    corrRow:       { flexDirection: "row", gap: 10, marginBottom: 12, alignItems: "flex-start" },
    indexBadge:    { width: 28, height: 28, borderRadius: 14, alignItems: "center", justifyContent: "center" },
    indexTxt:      { color: "#000", fontSize: 11, fontWeight: "900" },
    actionPill:    { alignSelf: "flex-start", borderWidth: 1, borderRadius: 6, paddingHorizontal: 7, paddingVertical: 2, marginBottom: 2 },
    actionTxt:     { fontSize: 10, fontWeight: "800" },
    corrLabel:     { color: "#E2E8F0", fontSize: 14, fontWeight: "700" },
    corrBbox:      { color: "#475569", fontSize: 10, fontFamily: "monospace" },
    metaTxt:       { color: "#64748B", fontSize: 12, marginBottom: 4 },
    actions:       { flexDirection: "row", borderTopWidth: 1, borderColor: "#1D2834", backgroundColor: "#0F1923" },
    approveBtn:    { flex: 1, paddingVertical: 18, alignItems: "center", backgroundColor: "rgba(16,185,129,0.12)" },
    approveTxt:    { color: "#10B981", fontWeight: "800", fontSize: 16 },
    rejectBtn:     { flex: 1, paddingVertical: 18, alignItems: "center", backgroundColor: "rgba(239,68,68,0.10)", borderLeftWidth: 1, borderColor: "#1D2834" },
    rejectTxt:     { color: "#EF4444", fontWeight: "800", fontSize: 16 },
});

export default AdminCorrectionsScreen;
