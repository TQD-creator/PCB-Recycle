"""
generate_diagrams.py  —  PCB Recognition and Anomaly Classification
Diagrams:
  1. diagram_1_system_pipeline.png
  2. diagram_2_use_case.png
  3. diagram_3_model_pipeline.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import numpy as np
from pathlib import Path

OUT = Path(__file__).resolve().parent / "benchmark_results"
OUT.mkdir(exist_ok=True)

SYSTEM_NAME = "PCB Recognition and Anomaly Classification"

BG     = "#060B12"
PANEL  = "#0F172A"
BORDER = "#1E293B"
BLUE   = "#3B82F6"
GREEN  = "#10B981"
AMBER  = "#F59E0B"
PURPLE = "#8B5CF6"
RED    = "#EF4444"
CYAN   = "#06B6D4"
SLATE  = "#334155"
TXT_HI  = "#F8FAFC"
TXT_MID = "#CBD5E1"
TXT_DIM = "#64748B"


# ── shared primitives ─────────────────────────────────────────────────────────
def rbox(ax, cx, cy, w, h, fc=PANEL, ec=BLUE, lw=1.8, zorder=2):
    ax.add_patch(FancyBboxPatch(
        (cx - w/2, cy - h/2), w, h,
        boxstyle="round,pad=0.006", lw=lw, edgecolor=ec,
        facecolor=fc, zorder=zorder))

def arr(ax, x0, y0, x1, y1, color=BLUE, lw=1.6, ms=9):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                arrowprops=dict(arrowstyle="-|>", color=color,
                                lw=lw, mutation_scale=ms))

def gap_label(ax, x, y, s, color=TXT_DIM, fs=7.0):
    """Label placed in an inter-column gap with solid background."""
    ax.text(x, y, s, ha="center", va="center", fontsize=fs,
            color=color, fontfamily="monospace",
            bbox=dict(fc=BG, ec="none", pad=1.8), zorder=9)

def l_route(ax, x0, y0, xm, y1, color, lw=1.4, dashed=False):
    """L-shaped connector: horizontal x0→xm at y0, then vertical xm at y0→y1.
       Arrow tip is drawn separately by the caller."""
    ls = (0, (4, 2)) if dashed else "solid"
    ax.plot([x0, xm], [y0, y0], color=color, lw=lw, linestyle=ls,
            solid_capstyle="round", zorder=2)
    ax.plot([xm, xm], [y0, y1], color=color, lw=lw, linestyle=ls,
            solid_capstyle="round", zorder=2)


# ═════════════════════════════════════════════════════════════════════════════
# DIAGRAM 1 — End-to-End System Pipeline
# ═════════════════════════════════════════════════════════════════════════════
def draw_system_pipeline():
    fig, ax = plt.subplots(figsize=(24, 14))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.axis("off")

    # ── swim lanes ────────────────────────────────────────────────────────
    lane_w = 0.165
    lanes = [
        (0.080, "#0C1B33", "MOBILE APP\n(Expo / React Native)"),
        (0.270, "#0A1E12", "FASTAPI  /api/v2"),
        (0.500, "#160D2E", "CELERY WORKER\n(solo pool)"),
        (0.735, "#1A0E2E", "AI PIPELINE\ncv_pipeline.py"),
        (0.935, "#0A1A22", "STORAGE"),
    ]
    for lx, lc, lt in lanes:
        ax.add_patch(FancyBboxPatch(
            (lx - lane_w/2, 0.02), lane_w, 0.94,
            boxstyle="round,pad=0", lw=1, edgecolor=BORDER,
            facecolor=lc, alpha=0.30, zorder=0))
        ax.text(lx, 0.965, lt, ha="center", va="center",
                fontsize=8, fontweight="bold", color=TXT_MID,
                fontfamily="monospace",
                bbox=dict(fc=lc, ec=BORDER, pad=3, lw=0.8, alpha=0.9))

    MA, FA, CE, AI, ST = 0.080, 0.270, 0.500, 0.735, 0.935
    W = 0.145; H = 0.052; sw = 0.082
    hw = W / 2   # box half-width = 0.0725

    # gap-channel x coordinates (between lane boxes, never inside a lane)
    # A-B gap: x in [0.1625, 0.1875]  → channel 0.175
    # B-C gap: x in [0.3525, 0.4175]  → channels 0.370 (left) and 0.395 (right)
    # C-D gap: x in [0.5825, 0.6525]  → channel 0.618
    # D-E gap: x in [0.8175, 0.8950]  → channels 0.838 and 0.852
    CH_AB  = 0.175
    CH_BCl = 0.370   # B→C route
    CH_BCr = 0.396   # C→B route
    CH_CD  = 0.618
    CH_DE1 = 0.838   # AI→SQLite
    CH_DE2 = 0.853   # AI→FAISS

    # box edge x-values
    A_R = MA + hw; B_L = FA - hw; B_R = FA + hw
    C_L = CE - hw; C_R = CE + hw
    D_L = AI - hw; D_R = AI + hw
    E_L = ST - sw/2

    def box(cx, cy, t1, t2="", ec=BLUE, fc="#0C1020"):
        rbox(ax, cx, cy, W, H, fc=fc, ec=ec)
        if t2:
            ax.text(cx, cy + 0.012, t1, ha="center", va="center",
                    fontsize=8.0, fontweight="bold", color=TXT_HI,
                    fontfamily="monospace", zorder=5)
            ax.text(cx, cy - 0.013, t2, ha="center", va="center",
                    fontsize=6.6, color=TXT_DIM, fontfamily="monospace", zorder=5)
        else:
            ax.text(cx, cy, t1, ha="center", va="center",
                    fontsize=8.0, fontweight="bold", color=TXT_HI,
                    fontfamily="monospace", zorder=5)

    def store(cy, t1, t2, ec):
        rbox(ax, ST, cy, sw, H, fc="#0A1520", ec=ec)
        ax.text(ST, cy + 0.012, t1, ha="center", va="center",
                fontsize=7.2, fontweight="bold", color=TXT_HI,
                fontfamily="monospace", zorder=5)
        ax.text(ST, cy - 0.013, t2, ha="center", va="center",
                fontsize=5.8, color=TXT_DIM, fontfamily="monospace", zorder=5)

    # ── Column A: Mobile App ──────────────────────────────────────────────
    box(MA, 0.875, "Camera Capture",     "Expo ImagePicker",            BLUE)
    box(MA, 0.790, "Resize -> 1600 px",  "JPEG q=0.8  (~400 KB)",       CYAN)
    box(MA, 0.690, "POST /scan/upload",  "Bearer token + image",        BLUE)
    box(MA, 0.460, "WebSocket listener", "/scan/ws/status/{task_id}",   PURPLE)
    box(MA, 0.355, "Scan Results",       "boxes, verified, anomalies",  GREEN)
    box(MA, 0.245, "BBox Editor",        "filter chips, drag resize",   GREEN)
    box(MA, 0.125, "Anomaly Queue",      "Approve / Reject triage",     AMBER)

    for y0, y1 in [(0.849,0.816),(0.764,0.716),(0.434,0.381),(0.329,0.271),(0.219,0.151)]:
        arr(ax, MA, y0, MA, y1, BLUE)

    # ── Column B: FastAPI ─────────────────────────────────────────────────
    box(FA, 0.875, "Auth Check",           "_require_auth()",               GREEN)
    box(FA, 0.790, "Save to Disk",         "UPLOADS_DIR/scan_<uuid>.jpg",   GREEN)
    box(FA, 0.690, "Enqueue Celery Task",  "pcb.scan.execute",              PURPLE)
    box(FA, 0.580, "Return 202",           "{ task_id, state: queued }",    BLUE)
    box(FA, 0.460, "Redis Pub/Sub",        "scan_status:<task_id>",         PURPLE)
    box(FA, 0.245, "POST /corrections",    "submit_correction()",           AMBER)
    box(FA, 0.125, "POST /anchors/resolve","anchors.resolve -> FAISS",      RED)

    for y0, y1 in [(0.849,0.816),(0.764,0.716),(0.664,0.606),(0.554,0.486)]:
        arr(ax, FA, y0, FA, y1, BLUE)

    # ── Column C: Celery ──────────────────────────────────────────────────
    box(CE, 0.800, "Task Received",     "execute_scan_task(bind=True)", PURPLE)
    box(CE, 0.695, "Publish Progress",  "_publish_sync() -> Redis",     PURPLE)
    box(CE, 0.575, "run_scan_pipeline", "image_path, task_id, cb",      BLUE)
    box(CE, 0.450, "save_scan_to_db()", "task_id, report, user_id",     GREEN)
    box(CE, 0.330, "Broadcast DONE",    "state, image_url, triage",     GREEN)

    for y0, y1 in [(0.774,0.721),(0.669,0.601),(0.549,0.476),(0.424,0.356)]:
        arr(ax, CE, y0, CE, y1, PURPLE)

    # ── Column D: AI Pipeline ─────────────────────────────────────────────
    ai_steps = [
        (0.880, "1. Load Image",       "cv2.imread(image_path)",      CYAN),
        (0.795, "2. Resize 1600 px",   "scale = 1600 / orig_w",       CYAN),
        (0.705, "3. SAHI Slicing",     "512x512  overlap=0.20",       PURPLE),
        (0.615, "4. YOLOv8s-P2",       "INT8 ONNX  4-head  1-class",  BLUE),
        (0.525, "5. Stitch + NMS",     "scale back to orig coords",   BLUE),
        (0.435, "6. Crop Components",  "one 128x128 crop per bbox",   AMBER),
        (0.340, "7. MobileNetV3",      "256-dim L2 embedding",        AMBER),
        (0.248, "8. FAISS L2 Search",  "k=1  204 golden anchors",     AMBER),
        (0.148, "9. Threshold 0.40",   "VERIFIED  /  ANOMALY",        GREEN),
    ]
    for cy, t1, t2, ec in ai_steps:
        box(AI, cy, t1, t2, ec)
    for i in range(len(ai_steps) - 1):
        arr(ax, AI, ai_steps[i][0] - H/2, AI, ai_steps[i+1][0] + H/2,
            ai_steps[i][3])

    # ── Column E: Storage ─────────────────────────────────────────────────
    store(0.840, "SQLite DB",    "scans / components\nusers / sessions", CYAN)
    store(0.680, "FAISS Index",  "golden_anchors.index\n204 references", AMBER)
    store(0.520, "Redis",        "Celery broker\nPub/Sub channel",        PURPLE)
    store(0.360, "Image Files",  "uploads/\ntriage_crops/",               GREEN)

    # ══ Cross-lane connections  (all L-shaped, never crossing a lane box) ══

    # A → B : upload  (horizontal, adjacent)
    arr(ax, A_R, 0.690, B_L, 0.690, CYAN)
    gap_label(ax, CH_AB, 0.703, "HTTPS POST", CYAN)

    # B → A : 202 response (horizontal, adjacent)
    arr(ax, B_L, 0.580, A_R, 0.580, BLUE)
    gap_label(ax, CH_AB, 0.567, "202 Accept", BLUE)

    # B → A : WebSocket push (horizontal, adjacent)
    arr(ax, B_L, 0.460, A_R, 0.460, PURPLE)
    gap_label(ax, CH_AB, 0.447, "WS events", PURPLE)

    # A → B : corrections (horizontal, adjacent)
    arr(ax, A_R, 0.245, B_L, 0.245, AMBER)
    gap_label(ax, CH_AB, 0.232, "corrections", AMBER)

    # A → B : resolve  (horizontal, adjacent)
    arr(ax, A_R, 0.125, B_L, 0.125, RED)
    gap_label(ax, CH_AB, 0.112, "APPROVE/REJECT", RED, fs=6.4)

    # B → C : enqueue  (L-route via CH_BCl: right from FA, up to CE level)
    l_route(ax, B_R, 0.690, CH_BCl, 0.800, PURPLE, lw=1.5)
    arr(ax, CH_BCl, 0.800, C_L, 0.800, PURPLE, lw=1.5)
    gap_label(ax, CH_BCl - 0.012, 0.748, "Celery\nbroker", PURPLE, fs=6.6)

    # C → B : Redis pub  (L-route via CH_BCr: left from CE, down to FA level, dashed)
    l_route(ax, C_L, 0.695, CH_BCr, 0.460, PURPLE, lw=1.2, dashed=True)
    arr(ax, CH_BCr, 0.460, B_R, 0.460, PURPLE, lw=1.2)
    gap_label(ax, CH_BCr + 0.013, 0.578, "Redis\npub", PURPLE, fs=6.6)

    # C → D : run pipeline  (slightly diagonal, label in C-D gap)
    arr(ax, C_R, 0.575, D_L, 0.615, BLUE)
    gap_label(ax, CH_CD, 0.596, "run pipeline", BLUE)

    # AI → SQLite : L-route via CH_DE1 (right from AI, up to SQLite level)
    l_route(ax, D_R, 0.435, CH_DE1, 0.840, CYAN, lw=1.2)
    arr(ax, CH_DE1, 0.840, E_L, 0.840, CYAN, lw=1.2)
    gap_label(ax, CH_DE1 + 0.012, 0.640, "save\nscan", CYAN, fs=6.4)

    # AI → FAISS : L-route via CH_DE2 (right from AI, up to FAISS level)
    l_route(ax, D_R, 0.340, CH_DE2, 0.680, AMBER, lw=1.2)
    arr(ax, CH_DE2, 0.680, E_L, 0.680, AMBER, lw=1.2)
    gap_label(ax, CH_DE2 + 0.012, 0.510, "query", AMBER, fs=6.4)

    # ── legend (bottom strip, data coords) ───────────────────────────────
    items = [
        (BLUE,   "HTTP / REST"),
        (PURPLE, "Celery / Redis"),
        (GREEN,  "DB write"),
        (AMBER,  "AI model I/O"),
        (CYAN,   "Image data"),
        (RED,    "Human action"),
    ]
    for i, (c, lbl) in enumerate(items):
        lx = 0.02 + (i % 3) * 0.155
        ly = 0.055 - (i // 3) * 0.025
        ax.plot([lx, lx + 0.022], [ly, ly], color=c, lw=2.5, zorder=6)
        ax.text(lx + 0.026, ly, lbl, va="center", fontsize=7,
                color=TXT_DIM, fontfamily="monospace", zorder=6)

    fig.suptitle(f"{SYSTEM_NAME} — End-to-End Architecture",
                 color=TXT_HI, fontsize=13, fontweight="bold",
                 fontfamily="monospace", y=0.998)
    plt.tight_layout(rect=[0, 0.06, 1, 0.995])
    p = OUT / "diagram_1_system_pipeline.png"
    plt.savefig(str(p), dpi=150, bbox_inches="tight", facecolor=BG, edgecolor="none")
    plt.close()
    print(f"[OK] {p.name}")


# ═════════════════════════════════════════════════════════════════════════════
# DIAGRAM 2 — Use Case Diagram
# ═════════════════════════════════════════════════════════════════════════════
def draw_use_case():
    fig, ax = plt.subplots(figsize=(20, 14))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.axis("off")

    # system boundary
    ax.add_patch(FancyBboxPatch(
        (0.12, 0.030), 0.76, 0.940,
        boxstyle="round,pad=0", lw=1.5, edgecolor=SLATE,
        facecolor=PANEL, alpha=0.25, zorder=0))
    ax.text(0.50, 0.976, SYSTEM_NAME,
            ha="center", va="center", fontsize=11, fontweight="bold",
            color=TXT_MID, fontfamily="monospace")

    # ── actors ────────────────────────────────────────────────────────────
    def actor(cx, cy, color, name):
        ax.add_patch(plt.Circle((cx, cy + 0.070), 0.024,
                     fc="none", ec=color, lw=2.2, zorder=5))
        ax.plot([cx, cx],              [cy+0.046, cy],       color=color, lw=2.2, zorder=5)
        ax.plot([cx-0.038, cx+0.038], [cy+0.030, cy+0.030], color=color, lw=2.2, zorder=5)
        ax.plot([cx, cx-0.030],        [cy, cy-0.040],       color=color, lw=2.2, zorder=5)
        ax.plot([cx, cx+0.030],        [cy, cy-0.040],       color=color, lw=2.2, zorder=5)
        ax.text(cx, cy - 0.062, name, ha="center", va="center",
                fontsize=9, fontweight="bold", color=color, fontfamily="monospace")

    actor(0.040, 0.580, BLUE,  "Operator\n(User)")
    actor(0.960, 0.580, GREEN, "Admin")

    # ── use-case ellipse ──────────────────────────────────────────────────
    def uc(cx, cy, text, color, w=0.190, h=0.046):
        ax.add_patch(mpatches.Ellipse(
            (cx, cy), w, h, fc=PANEL, ec=color, lw=2.0, zorder=3))
        lines = text.split("\n")
        dy = 0.013
        for i, ln in enumerate(lines):
            ax.text(cx, cy + (len(lines)-1)*dy/2 - i*dy, ln,
                    ha="center", va="center", fontsize=8.0, color=TXT_HI,
                    fontfamily="monospace", fontweight="bold", zorder=4)

    # ── actor → ellipse line (straight from actor body to ellipse edge) ───
    def connect(ax0, ay, ucx, ucy, ew, color, from_right=False):
        ex = (ucx + ew/2) if from_right else (ucx - ew/2)
        ax.plot([ax0, ex], [ay, ucy], color=color, lw=1.0, alpha=0.55, zorder=1)

    # ── User use cases (centre-left column x=0.370) ───────────────────────
    UCX = 0.370
    ax.text(UCX, 0.940, "Operator Actions", ha="center", va="center",
            fontsize=8, fontweight="bold", color=BLUE, fontfamily="monospace",
            bbox=dict(fc=BLUE, ec="none", alpha=0.14, pad=3))

    user_ucs = [
        (UCX, 0.886, "Login / Logout",               BLUE),
        (UCX, 0.816, "Upload PCB Image",              BLUE),
        (UCX, 0.742, "View Scan Results\n& BBoxes",   BLUE),
        (UCX, 0.662, "Filter Labels\nin BBox Editor", BLUE),
        (UCX, 0.582, "Submit Corrections",            AMBER),
        (UCX, 0.502, "View Anomaly Queue",            BLUE),
        (UCX, 0.422, "Approve / Reject\nAnomaly",     AMBER),
        (UCX, 0.336, "Real-time Progress\nWebSocket", PURPLE),
        (UCX, 0.256, "View Scan History",             BLUE),
        (UCX, 0.176, "Session Expiry\n(24 h TTL)",    BLUE),
    ]
    for cx, cy, text, color in user_ucs:
        uc(cx, cy, text, color)
        connect(0.078, 0.580, cx, cy, 0.190, color)

    # ── Admin-only use cases (centre-right column x=0.718) ───────────────
    AUX = 0.718
    ax.text(AUX, 0.940, "Admin-Only Actions", ha="center", va="center",
            fontsize=8, fontweight="bold", color=GREEN, fontfamily="monospace",
            bbox=dict(fc=GREEN, ec="none", alpha=0.14, pad=3))

    admin_ucs = [
        (AUX, 0.872, "Review Pending\nCorrections",   GREEN),
        (AUX, 0.782, "Approve / Reject\nCorrection",  GREEN),
        (AUX, 0.692, "FAISS Anchor\nUpdate (retrain)",RED),
        (AUX, 0.602, "Manage Users\n& Sessions",      GREEN),
        (AUX, 0.512, "Export / Audit\nScan Reports",  GREEN),
    ]
    for cx, cy, text, color in admin_ucs:
        uc(cx, cy, text, color, w=0.200)
        connect(0.922, 0.580, cx, cy, 0.200, color, from_right=True)

    # ── «include» arrows between related use cases ────────────────────────
    # Route each arrow in the clear gap between the two columns (x~0.555)
    # Submit Corrections (UCX, 0.582) --> Review Corrections (AUX, 0.782)
    ax.annotate("", xy=(AUX - 0.100, 0.782), xytext=(UCX + 0.095, 0.582),
                arrowprops=dict(arrowstyle="-|>", color=TXT_DIM,
                                lw=1.0, linestyle=(0,(4,2)),
                                connectionstyle="arc3,rad=-0.15",
                                mutation_scale=7))
    ax.text(0.548, 0.700, "<<include>>", ha="center", va="center",
            fontsize=6.8, color=TXT_DIM, fontfamily="monospace",
            bbox=dict(fc=BG, ec="none", pad=1.5), zorder=8)

    # Approve/Reject Anomaly (UCX, 0.422) --> FAISS update (AUX, 0.692)
    ax.annotate("", xy=(AUX - 0.100, 0.692), xytext=(UCX + 0.095, 0.422),
                arrowprops=dict(arrowstyle="-|>", color=TXT_DIM,
                                lw=1.0, linestyle=(0,(4,2)),
                                connectionstyle="arc3,rad=-0.10",
                                mutation_scale=7))
    ax.text(0.548, 0.572, "<<include>>", ha="center", va="center",
            fontsize=6.8, color=TXT_DIM, fontfamily="monospace",
            bbox=dict(fc=BG, ec="none", pad=1.5), zorder=8)

    # ── Admin-inherits note (inside frame, bottom area) ───────────────────
    ax.text(0.500, 0.112,
            "Admin inherits all Operator use cases",
            ha="center", va="center", fontsize=7.5, color=TXT_DIM,
            fontfamily="monospace",
            bbox=dict(fc=PANEL, ec=SLATE, pad=4, lw=0.8), zorder=5)

    # ── Legend — data coords, all inside boundary ─────────────────────────
    # 5 items in a 3+2 grid, y in [0.050, 0.076] — well inside boundary
    legend_items = [
        (BLUE,   "Operator use case"),
        (GREEN,  "Admin use case"),
        (AMBER,  "Human-in-the-loop"),
        (RED,    "AI model operation"),
        (PURPLE, "System service"),
    ]
    for i, (c, lbl) in enumerate(legend_items):
        col = i % 3;  row = i // 3
        lx = 0.155 + col * 0.230
        ly = 0.076 - row * 0.026     # row 0: 0.076, row 1: 0.050 — both > 0.030 ✓
        ax.add_patch(mpatches.Ellipse(
            (lx, ly), 0.026, 0.016,
            fc=PANEL, ec=c, lw=1.5, zorder=6))
        ax.text(lx + 0.020, ly, lbl, fontsize=7.5, color=TXT_DIM,
                fontfamily="monospace", va="center", zorder=6)

    fig.suptitle(f"{SYSTEM_NAME} — Use Case Diagram",
                 color=TXT_HI, fontsize=13, fontweight="bold",
                 fontfamily="monospace", y=0.998)
    plt.tight_layout(rect=[0, 0, 1, 0.995])
    p = OUT / "diagram_2_use_case.png"
    plt.savefig(str(p), dpi=150, bbox_inches="tight", facecolor=BG, edgecolor="none")
    plt.close()
    print(f"[OK] {p.name}")


# ═════════════════════════════════════════════════════════════════════════════
# DIAGRAM 3 — Model Pipeline
# ═════════════════════════════════════════════════════════════════════════════
def draw_model_pipeline():
    fig, ax = plt.subplots(figsize=(14, 22))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.axis("off")

    # Layout
    # Main step boxes:  x in [0.08, 0.72]  (cx=0.40, W=0.64)
    # Badge strip:      x in [0.745, 0.835] (bx=0.790, bw=0.090)
    # Model legend:     x in [0.848, 0.995] — RIGHT of badge strip, no overlap
    cx = 0.40; W = 0.64; H = 0.056

    steps = [
        # y,     title,                  subtitle,                           border, badge,        bc
        (0.950, "INPUT IMAGE",          "Full PCB board photograph",         SLATE,  None,         None),
        (0.858, "RESIZE -> 1600 px",    "scale = 1600 / original_width",     CYAN,   "Pre-process", CYAN),
        (0.766, "SAHI SLICING",         "512x512 px  |  overlap = 0.20",     PURPLE, "SAHI lib",   PURPLE),
        (0.674, "YOLOv8s-P2 (INT8)",    "4-head P2/P3/P4/P5  |  1-class",   BLUE,   "Model A",    BLUE),
        (0.582, "STITCH + NMS",         "Scale back to original coords",     BLUE,   "SAHI lib",   PURPLE),
        (0.490, "CROP COMPONENTS",      "One 128x128 crop per bbox",         AMBER,  "Pre-process", CYAN),
        (0.394, "MobileNetV3-Small",    "576->512->256 dim  |  L2 norm",     AMBER,  "Model B",    AMBER),
        (0.300, "FAISS Flat L2",        "k=1 nearest of 204 anchors",        AMBER,  "Model C",    AMBER),
        (0.200, "DECISION THRESHOLD",   "dist compared to 0.40 per class",   GREEN,  "Decision",   GREEN),
    ]

    ys = [s[0] for s in steps]

    # badge geometry — placed to the RIGHT of main box, clear of legend
    bx = 0.790; bw = 0.082; bh = 0.032
    box_right = cx + W/2   # 0.72

    for i, (y, title, sub, ec, badge, bc) in enumerate(steps):
        # glow
        ax.add_patch(FancyBboxPatch(
            (cx - W/2 - 0.005, y - H/2 - 0.003), W + 0.010, H + 0.006,
            boxstyle="round,pad=0", lw=0, facecolor=ec, alpha=0.07, zorder=1))
        # main box
        ax.add_patch(FancyBboxPatch(
            (cx - W/2, y - H/2), W, H,
            boxstyle="round,pad=0.005", lw=2.0, edgecolor=ec,
            facecolor=PANEL, zorder=2))
        # step number circle (left inside box)
        circ_x = cx - W/2 + 0.036
        ax.add_patch(plt.Circle((circ_x, y), 0.024,
                     fc=ec, ec="none", alpha=0.85, zorder=3))
        ax.text(circ_x, y, str(i + 1), ha="center", va="center",
                fontsize=9, fontweight="bold", color=BG, zorder=4)
        # title line (upper half of box)
        tx = cx - W/2 + 0.082
        ax.text(tx, y + 0.013, title, ha="left", va="center",
                fontsize=9.2, fontweight="bold", color=TXT_HI,
                fontfamily="monospace", zorder=4)
        # subtitle line (lower half of box)
        ax.text(tx, y - 0.015, sub, ha="left", va="center",
                fontsize=7.5, color=TXT_DIM, fontfamily="monospace", zorder=4)

        # badge — outside main box, left of model legend
        if badge:
            # connector dash from box right edge to badge left edge
            ax.plot([box_right + 0.004, bx - bw/2], [y, y],
                    color=bc, lw=0.8, linestyle="--", alpha=0.45, zorder=2)
            # badge pill
            ax.add_patch(FancyBboxPatch(
                (bx - bw/2, y - bh/2), bw, bh,
                boxstyle="round,pad=0.003", lw=1.4, edgecolor=bc,
                facecolor=bc, alpha=0.18, zorder=3))
            ax.text(bx, y, badge, ha="center", va="center",
                    fontsize=7.2, fontweight="bold", color=bc,
                    fontfamily="monospace", zorder=4)

        # down-arrow to next step
        if i < len(steps) - 1:
            arr(ax, cx, y - H/2 - 0.002, cx, ys[i+1] + H/2 + 0.002,
                ec, lw=2.0, ms=11)

    # ── Decision fork ─────────────────────────────────────────────────────
    dec_y   = steps[-1][0]          # 0.200
    split_y = dec_y - H/2 - 0.003  # 0.169
    fork_y  = 0.096

    ax.plot([cx, cx], [split_y, fork_y + 0.004], color=TXT_DIM, lw=1.8)
    VX, AX = 0.21, 0.59
    ax.plot([VX, AX], [fork_y, fork_y], color=TXT_DIM, lw=1.8)

    # VERIFIED
    vw, vh = 0.25, 0.072
    arr(ax, VX, fork_y, VX, fork_y - 0.002, GREEN)
    ax.add_patch(FancyBboxPatch((VX - vw/2, 0.022), vw, vh,
                 boxstyle="round,pad=0", lw=2.0, edgecolor=GREEN,
                 facecolor=PANEL, zorder=2))
    ax.add_patch(FancyBboxPatch((VX - vw/2, 0.022), vw, vh,
                 boxstyle="round,pad=0", lw=0, facecolor=GREEN, alpha=0.09, zorder=1))
    ax.text(VX, 0.068, "VERIFIED", ha="center", va="center",
            fontsize=12, fontweight="bold", color=GREEN,
            fontfamily="monospace", zorder=4)
    ax.text(VX, 0.043, "Saved to scan report\nShown in mobile app",
            ha="center", va="center", fontsize=7.8, color=TXT_DIM,
            fontfamily="monospace", zorder=4)
    ax.text(VX, fork_y + 0.015, "dist <= 0.40",
            ha="center", va="bottom", fontsize=7.8, color=GREEN,
            fontfamily="monospace", fontweight="bold")

    # ANOMALY
    aw, ah = 0.25, 0.072
    arr(ax, AX, fork_y, AX, fork_y - 0.002, RED)
    ax.add_patch(FancyBboxPatch((AX - aw/2, 0.022), aw, ah,
                 boxstyle="round,pad=0", lw=2.0, edgecolor=RED,
                 facecolor=PANEL, zorder=2))
    ax.add_patch(FancyBboxPatch((AX - aw/2, 0.022), aw, ah,
                 boxstyle="round,pad=0", lw=0, facecolor=RED, alpha=0.09, zorder=1))
    ax.text(AX, 0.068, "ANOMALY", ha="center", va="center",
            fontsize=12, fontweight="bold", color=RED,
            fontfamily="monospace", zorder=4)
    ax.text(AX, 0.043, "Added to triage queue\nHuman review required",
            ha="center", va="center", fontsize=7.8, color=TXT_DIM,
            fontfamily="monospace", zorder=4)
    ax.text(AX, fork_y + 0.015, "dist > 0.40",
            ha="center", va="bottom", fontsize=7.8, color=RED,
            fontfamily="monospace", fontweight="bold")

    # ── Model legend — RIGHT of badge strip (x starts at 0.848) ──────────
    # Badge strip occupies x in [0.749, 0.831]. Legend starts at 0.848. No overlap.
    lx0 = 0.848; lw_box = 0.148; lh_box = 0.178
    ly0 = 0.580   # legend top

    ax.add_patch(FancyBboxPatch(
        (lx0, ly0 - lh_box), lw_box, lh_box,
        boxstyle="round,pad=0.004", lw=1, edgecolor=SLATE,
        facecolor=PANEL, alpha=0.92, zorder=5))
    ax.text(lx0 + lw_box/2, ly0 - 0.018, "Models",
            ha="center", va="center", fontsize=8, fontweight="bold",
            color=TXT_MID, fontfamily="monospace", zorder=6)

    models_legend = [
        (BLUE,  "Model A", "high_res_p2_int8.onnx\nYOLOv8s-P2  10.8 MB"),
        (AMBER, "Model B", "mobilenet_best.pt\nMobileNetV3  15.7 MB"),
        (AMBER, "Model C", "golden_anchors.index\nFAISS L2  204 anchors"),
    ]
    for j, (c, badge_lbl, desc) in enumerate(models_legend):
        ry = ly0 - 0.050 - j * 0.044
        pb_w = 0.058; pb_h = 0.020
        ax.add_patch(FancyBboxPatch(
            (lx0 + 0.008, ry - pb_h/2), pb_w, pb_h,
            boxstyle="round,pad=0.002", lw=1.1, edgecolor=c,
            facecolor=c, alpha=0.20, zorder=6))
        ax.text(lx0 + 0.008 + pb_w/2, ry, badge_lbl,
                ha="center", va="center", fontsize=6.5, fontweight="bold",
                color=c, fontfamily="monospace", zorder=7)
        ax.text(lx0 + 0.075, ry, desc,
                ha="left", va="center", fontsize=6.2, color=TXT_DIM,
                fontfamily="monospace", zorder=7)

    fig.suptitle(f"{SYSTEM_NAME}\nModel Inference Pipeline",
                 color=TXT_HI, fontsize=13, fontweight="bold",
                 fontfamily="monospace", y=0.998)
    plt.tight_layout(rect=[0, 0, 1, 0.995])
    p = OUT / "diagram_3_model_pipeline.png"
    plt.savefig(str(p), dpi=150, bbox_inches="tight", facecolor=BG, edgecolor="none")
    plt.close()
    print(f"[OK] {p.name}")


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Generating diagrams ...")
    draw_system_pipeline()
    draw_use_case()
    draw_model_pipeline()
    print(f"\n[DONE] Saved to: {OUT}")
