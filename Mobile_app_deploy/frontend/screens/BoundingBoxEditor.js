import React, { useEffect, useMemo, useRef, useState } from "react";
import {
    Animated, Image, Modal, PanResponder, ScrollView, StyleSheet,
    Text, TouchableOpacity, View,
} from "react-native";
import Svg, { Rect, Text as SvgText } from "react-native-svg";

const CLASSES = [
    { label: "capacitor", display: "Capacitor" },
    { label: "resistor",  display: "Resistor" },
    { label: "ic",        display: "IC (Integrated Circuit)" },
    { label: "diode",     display: "Diode" },
    { label: "led",       display: "LED" },
    { label: "inductor",  display: "Inductor" },
    { label: "connector", display: "Connector" },
    { label: "unknown",   display: "Unknown / Other" },
];

// ── Pinch helpers ─────────────────────────────────────────────────────────────
const getDist = (t) => {
    const dx = t[1].locationX - t[0].locationX;
    const dy = t[1].locationY - t[0].locationY;
    return Math.sqrt(dx * dx + dy * dy);
};
const getMid = (t) => ({
    x: (t[0].locationX + t[1].locationX) / 2,
    y: (t[0].locationY + t[1].locationY) / 2,
});

/**
 * Color scheme:
 *   Green  (#16A34A) verified (unmodified)
 *   Orange (#F97316) anomaly  (unmodified)
 *   Yellow (#FACC15) relabeled (any type)
 *   Red    (#EF4444) marked for removal
 *   Cyan   (#06B6D4) new user-drawn box
 *
 * Filter / display modes
 *   filterLabel = null  → show all boxes with labels inside them
 *   filterLabel = str   → show only boxes whose effective label matches;
 *                         hide the text labels from the SVG;
 *                         show the class name in large text below the canvas
 */
const BoundingBoxEditor = ({
    imageUri,
    sourceWidth  = 1,
    sourceHeight = 1,
    verifiedBoxes = [],
    anomalyBoxes  = [],
    onSave,
}) => {
    // ── Core state ────────────────────────────────────────────────────────────
    const [canvasSize, setCanvasSize] = useState({ width: 1, height: 1 });
    const [drawnBoxes, setDrawnBoxes] = useState([]);
    const [boxMods,    setBoxMods]    = useState({}); // { "v_i"|"a_idx": {action,label?} }
    const [currentBox, setCurrentBox] = useState(null);
    const [filterLabel, setFilterLabel] = useState(null); // null = all

    const [modal, setModal] = useState({
        visible: false, phase: "action",
        key: null, origType: null, origLabel: null,
    });

    // ── Zoom state ────────────────────────────────────────────────────────────
    const scaleAnim = useRef(new Animated.Value(1)).current;
    const txAnim    = useRef(new Animated.Value(0)).current;
    const tyAnim    = useRef(new Animated.Value(0)).current;
    const scaleRef  = useRef(1);
    const txRef     = useRef(0);
    const tyRef     = useRef(0);

    // ── Gesture refs (avoid stale closures in PanResponder) ───────────────────
    const canvasSizeRef   = useRef({ width: 1, height: 1 });
    const drawnBoxesRef   = useRef([]);
    const boxModsRef      = useRef({});
    const hitRectsRef     = useRef([]);
    const filterLabelRef  = useRef(null);
    const modeRef         = useRef("idle");
    const startRef        = useRef({ x: 0, y: 0 });
    const pinchInitRef    = useRef(null);

    useEffect(() => { canvasSizeRef.current  = canvasSize;   }, [canvasSize]);
    useEffect(() => { drawnBoxesRef.current  = drawnBoxes;   }, [drawnBoxes]);
    useEffect(() => { boxModsRef.current     = boxMods;      }, [boxMods]);
    useEffect(() => { filterLabelRef.current = filterLabel;  }, [filterLabel]);

    // ── Hit rects (canvas-local coords) ──────────────────────────────────────
    useEffect(() => {
        if (canvasSize.width <= 1 || sourceWidth <= 1) return;
        const sx = canvasSize.width  / sourceWidth;
        const sy = canvasSize.height / sourceHeight;
        const rects = [];
        verifiedBoxes.forEach((b, i) =>
            rects.push({
                key: `v_${i}`, origType: "verified", origLabel: b.label,
                cx: b.bbox[0] * sx, cy: b.bbox[1] * sy,
                cw: (b.bbox[2] - b.bbox[0]) * sx, ch: (b.bbox[3] - b.bbox[1]) * sy,
            })
        );
        anomalyBoxes.forEach((b) =>
            rects.push({
                key: `a_${b.anomaly_index}`, origType: "anomaly", origLabel: b.label,
                cx: b.bbox[0] * sx, cy: b.bbox[1] * sy,
                cw: (b.bbox[2] - b.bbox[0]) * sx, ch: (b.bbox[3] - b.bbox[1]) * sy,
            })
        );
        hitRectsRef.current = rects;
    }, [canvasSize, verifiedBoxes, anomalyBoxes, sourceWidth, sourceHeight]);

    // ── Label helpers ─────────────────────────────────────────────────────────
    // Effective label of an existing box (after any relabeling)
    const effLabel = (key, origLabel) => {
        const mod = boxModsRef.current[key];
        return mod?.action === "relabeled" ? mod.label : origLabel;
    };

    // Unique labels present across all boxes (for filter chips)
    const { allLabels, labelCounts } = useMemo(() => {
        const counts = {};
        const add = (label) => { counts[label] = (counts[label] || 0) + 1; };
        verifiedBoxes.forEach((b, i) => {
            const mod = boxMods[`v_${i}`];
            add(mod?.action === "relabeled" ? mod.label : b.label);
        });
        anomalyBoxes.forEach((b) => {
            const mod = boxMods[`a_${b.anomaly_index}`];
            add(mod?.action === "relabeled" ? mod.label : b.label);
        });
        drawnBoxes.filter((b) => b.label).forEach((b) => add(b.label));
        return { allLabels: Object.keys(counts).sort(), labelCounts: counts };
    }, [verifiedBoxes, anomalyBoxes, drawnBoxes, boxMods]);

    const totalBoxCount = verifiedBoxes.length + anomalyBoxes.length +
        drawnBoxes.filter((b) => b.label).length;

    // ── Zoom helpers ──────────────────────────────────────────────────────────
    const toCanvas = (vx, vy) => {
        const { width: cw, height: ch } = canvasSizeRef.current;
        const s = scaleRef.current;
        return {
            x: (vx - txRef.current - cw / 2) / s + cw / 2,
            y: (vy - tyRef.current - ch / 2) / s + ch / 2,
        };
    };

    const applyZoom = (ns, nt, ny) => {
        const { width: cw, height: ch } = canvasSizeRef.current;
        const mx = (cw / 2) * (ns - 1), my = (ch / 2) * (ns - 1);
        const cx = Math.max(-mx, Math.min(mx, nt));
        const cy = Math.max(-my, Math.min(my, ny));
        scaleRef.current = ns; txRef.current = cx; tyRef.current = cy;
        scaleAnim.setValue(ns); txAnim.setValue(cx); tyAnim.setValue(cy);
    };

    const startPinch = (touches) => {
        const { width: cw, height: ch } = canvasSizeRef.current;
        const s = scaleRef.current; const tx = txRef.current; const ty = tyRef.current;
        const mid = getMid(touches);
        modeRef.current = "pinch";
        setCurrentBox(null);
        pinchInitRef.current = {
            dist: getDist(touches), scale: s, tx, ty,
            cpx: (mid.x - tx - cw / 2) / s + cw / 2,
            cpy: (mid.y - ty - ch / 2) / s + ch / 2,
        };
    };

    // ── PanResponder ──────────────────────────────────────────────────────────
    const panResponder = useRef(
        PanResponder.create({
            onStartShouldSetPanResponder: () => true,
            onMoveShouldSetPanResponder:  () => true,

            onPanResponderGrant: (evt) => {
                const touches = evt.nativeEvent.touches;
                if (touches.length >= 2) {
                    startPinch(touches);
                } else {
                    modeRef.current = "draw";
                    const c = toCanvas(evt.nativeEvent.locationX, evt.nativeEvent.locationY);
                    startRef.current = c;
                    setCurrentBox({ startX: c.x, startY: c.y, currentX: c.x, currentY: c.y });
                }
            },

            onPanResponderMove: (evt) => {
                const touches = evt.nativeEvent.touches;
                if (touches.length >= 2) {
                    if (modeRef.current !== "pinch") startPinch(touches);
                    const init = pinchInitRef.current;
                    if (!init) return;
                    const dist = getDist(touches); const mid = getMid(touches);
                    const { width: cw, height: ch } = canvasSizeRef.current;
                    const ns = Math.max(1, Math.min(5, init.scale * (dist / init.dist)));
                    applyZoom(
                        ns,
                        mid.x - (init.cpx - cw / 2) * ns - cw / 2,
                        mid.y - (init.cpy - ch / 2) * ns - ch / 2,
                    );
                    return;
                }
                if (modeRef.current === "draw") {
                    const c = toCanvas(evt.nativeEvent.locationX, evt.nativeEvent.locationY);
                    setCurrentBox((p) => p ? { ...p, currentX: c.x, currentY: c.y } : null);
                }
            },

            onPanResponderRelease: (evt) => {
                if (modeRef.current === "pinch") { modeRef.current = "idle"; return; }
                const c = toCanvas(evt.nativeEvent.locationX, evt.nativeEvent.locationY);
                const { x: sx, y: sy } = startRef.current;
                const dx = Math.abs(c.x - sx); const dy = Math.abs(c.y - sy);
                modeRef.current = "idle";
                setCurrentBox(null);

                if (dx < 8 && dy < 8) {
                    // TAP — drawn boxes first (on top), then existing
                    const drawnHit = drawnBoxesRef.current.findIndex(
                        (b) => c.x >= b.x && c.x <= b.x + b.w && c.y >= b.y && c.y <= b.y + b.h
                    );
                    if (drawnHit >= 0) {
                        const b = drawnBoxesRef.current[drawnHit];
                        // Filter: only tappable when "all" or label matches
                        const fl = filterLabelRef.current;
                        if (!fl || b.label === fl) {
                            setModal({ visible: true, phase: "action", key: `d_${drawnHit}`, origType: "drawn", origLabel: b.label });
                        }
                        return;
                    }
                    const hit = hitRectsRef.current.find((r) => {
                        if (c.x < r.cx || c.x > r.cx + r.cw || c.y < r.cy || c.y > r.cy + r.ch) return false;
                        const fl = filterLabelRef.current;
                        if (!fl) return true;
                        return effLabel(r.key, r.origLabel) === fl;
                    });
                    if (hit) {
                        setModal({ visible: true, phase: "action", key: hit.key, origType: hit.origType, origLabel: hit.origLabel });
                    }
                } else if (dx > 8 && dy > 8) {
                    const newBox = { x: Math.min(sx, c.x), y: Math.min(sy, c.y), w: dx, h: dy, label: null };
                    const idx = drawnBoxesRef.current.length;
                    const updated = [...drawnBoxesRef.current, newBox];
                    drawnBoxesRef.current = updated;
                    setDrawnBoxes(updated);
                    // In filter mode, pre-fill the label if drawing while a class is selected
                    setModal({ visible: true, phase: "relabel", key: `d_${idx}`, origType: "drawn", origLabel: null });
                }
            },
        })
    ).current;

    // ── Modal actions ─────────────────────────────────────────────────────────
    const currentMod   = modal.key ? boxMods[modal.key] : undefined;
    const currentState = modal.key?.startsWith("d_") ? "drawn" : (currentMod?.action ?? "original");

    const applyRelabel = (classItem) => {
        const { key } = modal;
        if (key?.startsWith("d_")) {
            const idx = parseInt(key.slice(2));
            setDrawnBoxes((prev) => {
                const u = [...prev]; u[idx] = { ...u[idx], label: classItem.label };
                drawnBoxesRef.current = u; return u;
            });
        } else {
            setBoxMods((p) => ({ ...p, [key]: { action: "relabeled", label: classItem.label } }));
        }
        setModal({ visible: false, phase: "action", key: null, origType: null, origLabel: null });
    };

    const applyDelete = () => {
        const { key } = modal;
        if (key?.startsWith("d_")) {
            const idx = parseInt(key.slice(2));
            setDrawnBoxes((prev) => { const u = prev.filter((_, i) => i !== idx); drawnBoxesRef.current = u; return u; });
        } else {
            setBoxMods((p) => ({ ...p, [key]: { action: "deleted" } }));
        }
        setModal({ visible: false, phase: "action", key: null, origType: null, origLabel: null });
    };

    const applyRestore = () => {
        const { key } = modal;
        setBoxMods((p) => { const u = { ...p }; delete u[key]; return u; });
        setModal({ visible: false, phase: "action", key: null, origType: null, origLabel: null });
    };

    const closeModal = () =>
        setModal({ visible: false, phase: "action", key: null, origType: null, origLabel: null });

    // ── Submit ────────────────────────────────────────────────────────────────
    const handleSubmit = () => {
        const scaleX = sourceWidth  / canvasSizeRef.current.width;
        const scaleY = sourceHeight / canvasSizeRef.current.height;
        const toImg  = (b) => [
            Math.round(b.x * scaleX), Math.round(b.y * scaleY),
            Math.round((b.x + b.w) * scaleX), Math.round((b.y + b.h) * scaleY),
        ];

        const corrections = [];
        drawnBoxes.filter((b) => b.label).forEach((b) =>
            corrections.push({ bbox: toImg(b), label: b.label, action: "ADD" })
        );
        Object.entries(boxMods).forEach(([key, mod]) => {
            if (key.startsWith("v_")) {
                const i = parseInt(key.slice(2));
                const b = verifiedBoxes[i]; if (!b) return;
                corrections.push({
                    bbox: b.bbox, label: mod.label ?? "",
                    action: mod.action === "deleted" ? "DELETE_VERIFIED" : "RELABEL_VERIFIED",
                    component_index: i,
                });
            } else if (key.startsWith("a_")) {
                const ai = parseInt(key.slice(2));
                const b = anomalyBoxes.find((x) => x.anomaly_index === ai); if (!b) return;
                corrections.push({
                    bbox: b.bbox, label: mod.label ?? "",
                    action: mod.action === "deleted" ? "DELETE_ANOMALY" : "RELABEL",
                    anomaly_index: ai,
                });
            }
        });
        onSave(corrections);
    };

    // ── Derived SVG rects ─────────────────────────────────────────────────────
    const sx = canvasSize.width  / sourceWidth;
    const sy = canvasSize.height / sourceHeight;

    const getColor = (key, origType) => {
        const mod = boxMods[key];
        if (mod?.action === "deleted")   return { s: "#EF4444", f: "rgba(239,68,68,0.18)" };
        if (mod?.action === "relabeled") return { s: "#FACC15", f: "rgba(250,204,21,0.15)" };
        if (origType === "verified")     return { s: "#16A34A", f: "rgba(22,163,74,0.10)" };
        return                                  { s: "#F97316", f: "rgba(249,115,22,0.12)" };
    };
    const getDisplayLabel = (key, origLabel) => {
        const mod = boxMods[key];
        if (mod?.action === "relabeled") return `→ ${mod.label}`;
        if (mod?.action === "deleted")   return `✕ ${origLabel}`;
        return origLabel;
    };

    // Boxes filtered by selected label; hide text overlay in focus mode
    const scaledVerified = useMemo(() => {
        return verifiedBoxes.map((b, i) => {
            const key = `v_${i}`;
            const eff = boxMods[key]?.action === "relabeled" ? boxMods[key].label : b.label;
            if (filterLabel && eff !== filterLabel) return null;
            const { s, f } = getColor(key, "verified");
            return { key, x: b.bbox[0]*sx, y: b.bbox[1]*sy, w:(b.bbox[2]-b.bbox[0])*sx, h:(b.bbox[3]-b.bbox[1])*sy, s, f, lbl: getDisplayLabel(key, b.label) };
        }).filter(Boolean);
    }, [verifiedBoxes, sx, sy, boxMods, filterLabel]);

    const scaledAnomalies = useMemo(() => {
        return anomalyBoxes.map((b) => {
            const key = `a_${b.anomaly_index}`;
            const eff = boxMods[key]?.action === "relabeled" ? boxMods[key].label : b.label;
            if (filterLabel && eff !== filterLabel) return null;
            const { s, f } = getColor(key, "anomaly");
            return { key, x: b.bbox[0]*sx, y: b.bbox[1]*sy, w:(b.bbox[2]-b.bbox[0])*sx, h:(b.bbox[3]-b.bbox[1])*sy, s, f, lbl: getDisplayLabel(key, b.label) };
        }).filter(Boolean);
    }, [anomalyBoxes, sx, sy, boxMods, filterLabel]);

    const scaledDrawn = useMemo(() => {
        return drawnBoxes.map((b, i) => {
            if (filterLabel && b.label && b.label !== filterLabel) return null;
            return { i, ...b };
        }).filter(Boolean);
    }, [drawnBoxes, filterLabel]);

    const totalChanges = drawnBoxes.filter((b) => b.label).length + Object.keys(boxMods).length;
    const aspectRatio  = sourceWidth / sourceHeight;

    // Classes pre-sorted by count descending for the filter bar
    const sortedLabels = useMemo(
        () => [...allLabels].sort((a, b) => (labelCounts[b] || 0) - (labelCounts[a] || 0)),
        [allLabels, labelCounts]
    );

    return (
        <View style={styles.root}>
            {/* ── Zoom bar ── */}
            <View style={styles.topBar}>
                <Text style={styles.topHint}>Pinch=zoom · 1 finger=draw · tap=edit</Text>
                <TouchableOpacity style={styles.resetBtn} onPress={() => applyZoom(1, 0, 0)}>
                    <Text style={styles.resetTxt}>Reset Zoom</Text>
                </TouchableOpacity>
            </View>

            {/* ── Filter chips ── */}
            <ScrollView
                horizontal
                showsHorizontalScrollIndicator={false}
                style={styles.filterBar}
                contentContainerStyle={styles.filterContent}
            >
                {/* "All" chip */}
                <TouchableOpacity
                    style={[styles.chip, !filterLabel && styles.chipActive]}
                    onPress={() => setFilterLabel(null)}
                >
                    <Text style={[styles.chipTxt, !filterLabel && styles.chipTxtActive]}>
                        All  {totalBoxCount}
                    </Text>
                </TouchableOpacity>

                {sortedLabels.map((label) => {
                    const active = filterLabel === label;
                    return (
                        <TouchableOpacity
                            key={label}
                            style={[styles.chip, active && styles.chipActive]}
                            onPress={() => setFilterLabel(active ? null : label)}
                        >
                            <Text style={[styles.chipTxt, active && styles.chipTxtActive]}>
                                {label}  {labelCounts[label] || 0}
                            </Text>
                        </TouchableOpacity>
                    );
                })}
            </ScrollView>

            {/* ── Canvas viewport ── */}
            <View style={[styles.viewport, { aspectRatio }]} {...panResponder.panHandlers}>
                <Animated.View
                    style={[styles.canvas, { transform: [{ translateX: txAnim }, { translateY: tyAnim }, { scale: scaleAnim }] }]}
                    onLayout={(e) => {
                        const { width, height } = e.nativeEvent.layout;
                        if (width > 1) { setCanvasSize({ width, height }); canvasSizeRef.current = { width, height }; }
                    }}
                >
                    <Image source={{ uri: imageUri }} style={StyleSheet.absoluteFill} resizeMode="stretch" />
                    <Svg style={StyleSheet.absoluteFill}>
                        {/* Verified boxes */}
                        {scaledVerified.map((b) => (
                            <React.Fragment key={b.key}>
                                <Rect x={b.x} y={b.y} width={b.w} height={b.h} stroke={b.s} strokeWidth={1.5} fill={b.f} />
                                {/* Hide text labels in single-class focus mode */}
                                {!filterLabel && (
                                    <SvgText x={b.x+3} y={b.y+11} fontSize={9} fill={b.s} fontWeight="bold">{b.lbl}</SvgText>
                                )}
                            </React.Fragment>
                        ))}
                        {/* Anomaly boxes */}
                        {scaledAnomalies.map((b) => (
                            <React.Fragment key={b.key}>
                                <Rect x={b.x} y={b.y} width={b.w} height={b.h} stroke={b.s} strokeWidth={2} fill={b.f} />
                                {!filterLabel && (
                                    <SvgText x={b.x+3} y={b.y+11} fontSize={9} fill={b.s} fontWeight="bold">{b.lbl}</SvgText>
                                )}
                            </React.Fragment>
                        ))}
                        {/* User-drawn new boxes */}
                        {scaledDrawn.map((b) => (
                            <React.Fragment key={`d${b.i}`}>
                                <Rect
                                    x={b.x} y={b.y} width={b.w} height={b.h}
                                    stroke={b.label ? "#06B6D4" : "#FACC15"} strokeWidth={2}
                                    strokeDasharray={b.label ? undefined : "6,3"}
                                    fill={b.label ? "rgba(6,182,212,0.15)" : "rgba(250,204,21,0.12)"}
                                />
                                {b.label && !filterLabel && (
                                    <SvgText x={b.x+3} y={b.y+11} fontSize={9} fill="#06B6D4" fontWeight="bold">{b.label}</SvgText>
                                )}
                            </React.Fragment>
                        ))}
                        {/* Live draw preview */}
                        {currentBox && (
                            <Rect
                                x={Math.min(currentBox.startX, currentBox.currentX)}
                                y={Math.min(currentBox.startY, currentBox.currentY)}
                                width={Math.abs(currentBox.currentX - currentBox.startX)}
                                height={Math.abs(currentBox.currentY - currentBox.startY)}
                                stroke="#FACC15" strokeWidth={2} strokeDasharray="6,3" fill="rgba(250,204,21,0.08)"
                            />
                        )}
                    </Svg>
                </Animated.View>
            </View>

            {/* ── Focus mode label display ── */}
            {filterLabel ? (
                <View style={styles.focusBar}>
                    <Text style={styles.focusName}>{filterLabel}</Text>
                    <Text style={styles.focusCount}>
                        {labelCounts[filterLabel] || 0} component{(labelCounts[filterLabel] || 0) !== 1 ? "s" : ""}
                        {"  ·  "}boxes only — labels hidden
                    </Text>
                </View>
            ) : (
                /* ── Normal legend ── */
                <View style={styles.legend}>
                    {[
                        ["#16A34A", "Verified — tap to relabel/remove"],
                        ["#F97316", "Anomaly — tap to relabel/remove"],
                        ["#FACC15", "Relabeled"],
                        ["#EF4444", "Marked for removal"],
                        ["#06B6D4", "New — drag to draw"],
                    ].map(([c, t]) => (
                        <View key={c} style={styles.li}>
                            <View style={[styles.dot, { backgroundColor: c }]} />
                            <Text style={styles.lt}>{t}</Text>
                        </View>
                    ))}
                </View>
            )}

            {/* ── Submit ── */}
            <TouchableOpacity
                style={[styles.submitBtn, totalChanges === 0 && styles.submitDisabled]}
                onPress={handleSubmit}
                disabled={totalChanges === 0}
            >
                <Text style={styles.submitTxt}>
                    {totalChanges === 0
                        ? "Tap a box to modify · drag to add a new one"
                        : `Submit ${totalChanges} correction${totalChanges !== 1 ? "s" : ""}`}
                </Text>
            </TouchableOpacity>

            {/* ── Action / relabel modal ── */}
            <Modal visible={modal.visible} transparent animationType="slide">
                <View style={styles.overlay}>
                    <View style={styles.sheet}>
                        {modal.phase === "relabel" ? (
                            <>
                                <Text style={styles.sheetTitle}>Select Component Class</Text>
                                <ScrollView showsVerticalScrollIndicator={false}>
                                    {CLASSES.map((c) => (
                                        <TouchableOpacity key={c.label} style={styles.optBtn} onPress={() => applyRelabel(c)}>
                                            <Text style={styles.optTxt}>{c.display}</Text>
                                        </TouchableOpacity>
                                    ))}
                                </ScrollView>
                                <TouchableOpacity style={styles.cancelBtn} onPress={closeModal}>
                                    <Text style={styles.cancelTxt}>Cancel</Text>
                                </TouchableOpacity>
                            </>
                        ) : (
                            <>
                                <Text style={styles.sheetTitle}>
                                    {modal.origType === "drawn"
                                        ? `New box · ${modal.origLabel ?? "unlabeled"}`
                                        : `${modal.origType === "verified" ? "Verified" : "Anomaly"} · ${modal.origLabel}`}
                                </Text>

                                {currentState !== "original" && currentState !== "drawn" && (
                                    <View style={[styles.stateRow, currentState === "deleted" ? styles.stateRed : styles.stateYellow]}>
                                        <Text style={styles.stateTxt}>
                                            {currentState === "deleted"
                                                ? "Currently marked for removal"
                                                : `Currently relabeled → ${currentMod?.label}`}
                                        </Text>
                                    </View>
                                )}

                                {currentState !== "deleted" && (
                                    <TouchableOpacity style={styles.optBtn}
                                        onPress={() => setModal((p) => ({ ...p, phase: "relabel" }))}>
                                        <Text style={styles.optTxt}>
                                            {currentState === "relabeled" ? "Change Label" : "Relabel this box"}
                                        </Text>
                                    </TouchableOpacity>
                                )}

                                {currentState !== "deleted" && (
                                    <TouchableOpacity style={[styles.optBtn, styles.optRed]} onPress={applyDelete}>
                                        <Text style={styles.optTxt}>
                                            {modal.origType === "drawn" ? "Delete this box" : "Mark for removal (red)"}
                                        </Text>
                                    </TouchableOpacity>
                                )}

                                {(currentState === "relabeled" || currentState === "deleted") && (
                                    <TouchableOpacity style={[styles.optBtn, styles.optGray]} onPress={applyRestore}>
                                        <Text style={styles.optTxt}>Restore original</Text>
                                    </TouchableOpacity>
                                )}

                                {currentState === "deleted" && (
                                    <TouchableOpacity style={styles.optBtn}
                                        onPress={() => setModal((p) => ({ ...p, phase: "relabel" }))}>
                                        <Text style={styles.optTxt}>Relabel instead</Text>
                                    </TouchableOpacity>
                                )}

                                <TouchableOpacity style={styles.cancelBtn} onPress={closeModal}>
                                    <Text style={styles.cancelTxt}>Cancel</Text>
                                </TouchableOpacity>
                            </>
                        )}
                    </View>
                </View>
            </Modal>
        </View>
    );
};

// ─────────────────────────────────────────────────────────────────────────────
const styles = StyleSheet.create({
    root:           { flex: 1, backgroundColor: "#0A1118" },

    // Top bar
    topBar:         { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 14, paddingVertical: 8, backgroundColor: "#111827", borderBottomWidth: 1, borderColor: "#1F2937" },
    topHint:        { color: "#4B5563", fontSize: 11, flex: 1 },
    resetBtn:       { backgroundColor: "#1E3A5F", paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8 },
    resetTxt:       { color: "#93C5FD", fontSize: 12, fontWeight: "700" },

    // Filter chip bar
    filterBar:      { backgroundColor: "#0D1520", borderBottomWidth: 1, borderColor: "#1F2937", flexGrow: 0 },
    filterContent:  { flexDirection: "row", gap: 8, paddingHorizontal: 12, paddingVertical: 8 },
    chip:           { borderWidth: 1, borderColor: "#1F2937", borderRadius: 20, paddingHorizontal: 14, paddingVertical: 5, backgroundColor: "#111827" },
    chipActive:     { backgroundColor: "#10B981", borderColor: "#10B981" },
    chipTxt:        { color: "#64748B", fontSize: 12, fontWeight: "600" },
    chipTxtActive:  { color: "#022C22", fontWeight: "800" },

    // Canvas
    viewport:       { width: "100%", overflow: "hidden", backgroundColor: "#020617" },
    canvas:         { width: "100%", height: "100%" },

    // Focus mode label display (replaces legend when filter active)
    focusBar:       { alignItems: "center", paddingVertical: 14, paddingHorizontal: 20, backgroundColor: "#0D1520", borderBottomWidth: 1, borderColor: "#1F2937" },
    focusName:      { color: "#10B981", fontSize: 28, fontWeight: "900", letterSpacing: 1.5, textTransform: "uppercase" },
    focusCount:     { color: "#64748B", fontSize: 12, marginTop: 4 },

    // Normal legend
    legend:         { flexDirection: "row", flexWrap: "wrap", gap: 8, paddingHorizontal: 12, paddingVertical: 8, backgroundColor: "#111827" },
    li:             { flexDirection: "row", alignItems: "center", gap: 5 },
    dot:            { width: 8, height: 8, borderRadius: 4 },
    lt:             { color: "#94A3B8", fontSize: 10 },

    // Submit
    submitBtn:      { margin: 12, backgroundColor: "#10B981", borderRadius: 12, paddingVertical: 16, alignItems: "center" },
    submitDisabled: { backgroundColor: "#064E3B" },
    submitTxt:      { color: "#022C22", fontWeight: "800", fontSize: 15 },

    // Modal
    overlay:        { flex: 1, backgroundColor: "rgba(0,0,0,0.88)", justifyContent: "flex-end" },
    sheet:          { backgroundColor: "#1E293B", borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 24, maxHeight: "80%" },
    sheetTitle:     { color: "#F8FAFC", fontSize: 17, fontWeight: "800", marginBottom: 12, textAlign: "center" },
    stateRow:       { borderRadius: 10, paddingVertical: 8, paddingHorizontal: 14, marginBottom: 10 },
    stateYellow:    { backgroundColor: "rgba(250,204,21,0.12)" },
    stateRed:       { backgroundColor: "rgba(239,68,68,0.12)" },
    stateTxt:       { color: "#E2E8F0", fontSize: 13, textAlign: "center", fontStyle: "italic" },
    optBtn:         { backgroundColor: "#1D4ED8", padding: 14, borderRadius: 10, marginBottom: 8 },
    optRed:         { backgroundColor: "#7F1D1D" },
    optGray:        { backgroundColor: "#1E293B", borderWidth: 1, borderColor: "#334155" },
    optTxt:         { color: "#FFF", textAlign: "center", fontWeight: "600", fontSize: 15 },
    cancelBtn:      { backgroundColor: "transparent", padding: 14, borderRadius: 10, marginTop: 4 },
    cancelTxt:      { color: "#64748B", textAlign: "center", fontWeight: "700", fontSize: 14 },
});

export default BoundingBoxEditor;
