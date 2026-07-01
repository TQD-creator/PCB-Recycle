"""
compare_weights.py
Compare YOLOv8s_HighRes_SAHI_best.pt (FP32) vs high_res_p2_int8.onnx (INT8)
Metrics: mAP@50, latency per image (SAHI), peak RAM, model size, detection count.
"""
import gc, time, os, sys, warnings
warnings.filterwarnings("ignore")

import numpy as np
import cv2
from pathlib import Path

ROOT        = Path(__file__).resolve().parent.parent
WEIGHTS_DIR = ROOT / "Mobile_app_deploy/backend/runtime/assets/weights"
PT_WEIGHT   = WEIGHTS_DIR / "YOLOv8s_HighRes_SAHI_best.pt"
ONNX_WEIGHT = WEIGHTS_DIR / "high_res_p2_int8.onnx"
VAL_IMAGES  = Path(r"D:\Download_save\Foxconn_save\Classification\val\images")
VAL_LABELS  = Path(r"D:\Download_save\Foxconn_save\Classification\val\labels")

N_IMAGES    = 30
CONF        = 0.25
IOU_THRESH  = 0.50
SLICE_SZ    = 512
OVERLAP     = 0.20

sys.path.insert(0, str(ROOT))

# ── helpers ────────────────────────────────────────────────────────────────
def peak_ram_mb():
    try:
        import psutil
        return psutil.Process().memory_info().rss / 1e6
    except Exception:
        return 0.0

def load_gt(label_path, img_w, img_h):
    boxes = []
    if not label_path.exists():
        return boxes
    with open(label_path) as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 5:
                continue
            _, cx, cy, bw, bh = map(float, parts[:5])
            x1 = (cx - bw/2) * img_w
            y1 = (cy - bh/2) * img_h
            x2 = (cx + bw/2) * img_w
            y2 = (cy + bh/2) * img_h
            boxes.append([x1, y1, x2, y2])
    return boxes

def iou(a, b):
    ix1 = max(a[0], b[0]); iy1 = max(a[1], b[1])
    ix2 = min(a[2], b[2]); iy2 = min(a[3], b[3])
    inter = max(0, ix2-ix1) * max(0, iy2-iy1)
    ua = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - inter
    return inter / ua if ua > 0 else 0.0

def voc_ap(pred_boxes_all, confidences_all, gt_boxes_all, iou_thresh=0.50):
    """VOC mAP@50 across all images."""
    entries = []
    total_gt = sum(len(g) for g in gt_boxes_all)
    for img_i, (preds, confs, gts) in enumerate(zip(pred_boxes_all, confidences_all, gt_boxes_all)):
        for box, conf in zip(preds, confs):
            entries.append((conf, img_i, box))
    if not entries or total_gt == 0:
        return 0.0
    entries.sort(key=lambda e: -e[0])
    matched = [set() for _ in gt_boxes_all]
    tp = []; fp = []
    for conf, img_i, box in entries:
        gts = gt_boxes_all[img_i]
        best_iou = 0.0; best_j = -1
        for j, gt in enumerate(gts):
            v = iou(box, gt)
            if v > best_iou:
                best_iou = v; best_j = j
        if best_iou >= iou_thresh and best_j not in matched[img_i]:
            tp.append(1); fp.append(0)
            matched[img_i].add(best_j)
        else:
            tp.append(0); fp.append(1)
    tp_cum = np.cumsum(tp); fp_cum = np.cumsum(fp)
    rec = tp_cum / total_gt
    prec = tp_cum / (tp_cum + fp_cum)
    # add sentinel
    rec  = np.concatenate([[0.0], rec, [rec[-1]]])
    prec = np.concatenate([[1.0], prec, [0.0]])
    for i in range(len(prec)-2, -1, -1):
        prec[i] = max(prec[i], prec[i+1])
    ap = np.sum((rec[1:]-rec[:-1]) * prec[1:])
    return float(ap)


# ── SAHI inference for one model ──────────────────────────────────────────
def run_one_model(name, weight_path, images):
    from sahi import AutoDetectionModel
    from sahi.predict import get_sliced_prediction

    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"  Weight : {weight_path.name}  ({weight_path.stat().st_size/1e6:.2f} MB)")
    print(f"{'='*60}")

    ram_before = peak_ram_mb()
    t_load = time.perf_counter()
    model = AutoDetectionModel.from_pretrained(
        model_type="yolov8",
        model_path=str(weight_path),
        confidence_threshold=CONF,
        device="cpu",
    )
    load_time = time.perf_counter() - t_load
    ram_after_load = peak_ram_mb()
    print(f"  Load time : {load_time:.2f}s  |  RAM delta: +{ram_after_load - ram_before:.0f} MB")

    latencies = []
    all_preds = []
    all_confs = []
    all_gts   = []
    total_dets = 0

    for idx, img_path in enumerate(images):
        img_bgr = cv2.imread(str(img_path))
        if img_bgr is None:
            continue
        h, w = img_bgr.shape[:2]
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

        t0 = time.perf_counter()
        result = get_sliced_prediction(
            img_rgb,
            model,
            slice_height=SLICE_SZ,
            slice_width=SLICE_SZ,
            overlap_height_ratio=OVERLAP,
            overlap_width_ratio=OVERLAP,
            verbose=0,
        )
        lat = (time.perf_counter() - t0) * 1000
        latencies.append(lat)

        preds = [[o.bbox.minx, o.bbox.miny, o.bbox.maxx, o.bbox.maxy]
                 for o in result.object_prediction_list]
        confs = [o.score.value for o in result.object_prediction_list]
        total_dets += len(preds)

        lbl_path = VAL_LABELS / (img_path.stem + ".txt")
        gts = load_gt(lbl_path, w, h)

        all_preds.append(preds)
        all_confs.append(confs)
        all_gts.append(gts)

        print(f"    {idx+1:2d}/{N_IMAGES}  lat={lat:.0f}ms  dets={len(preds)}", flush=True)

    peak_ram = peak_ram_mb()
    ap = voc_ap(all_preds, all_confs, all_gts)

    del model; gc.collect()

    stats = {
        "name":        name,
        "weight":      weight_path.name,
        "size_mb":     round(weight_path.stat().st_size / 1e6, 2),
        "load_s":      round(load_time, 2),
        "map50":       round(ap * 100, 2),
        "lat_mean":    round(float(np.mean(latencies)), 1),
        "lat_p50":     round(float(np.median(latencies)), 1),
        "lat_p95":     round(float(np.percentile(latencies, 95)), 1),
        "lat_max":     round(float(np.max(latencies)), 1),
        "peak_ram_mb": round(peak_ram, 0),
        "total_dets":  total_dets,
        "avg_dets":    round(total_dets / len(images), 1),
    }
    return stats


# ── main ──────────────────────────────────────────────────────────────────
def main():
    import random
    rng = random.Random(42)
    all_imgs = sorted(VAL_IMAGES.glob("*.jpg")) + sorted(VAL_IMAGES.glob("*.png"))
    images   = rng.sample(all_imgs, min(N_IMAGES, len(all_imgs)))
    print(f"Sampled {len(images)} val images from {VAL_IMAGES}")

    # --- FP32 PyTorch first ---
    stats_pt   = run_one_model("FP32 (.pt)", PT_WEIGHT, images)
    gc.collect()

    # --- INT8 ONNX second ---
    stats_onnx = run_one_model("INT8 ONNX (.onnx)", ONNX_WEIGHT, images)
    gc.collect()

    # ── Print comparison table ────────────────────────────────────────────
    print("\n")
    print("=" * 68)
    print(f"  COMPARISON : FP32 .pt  vs  INT8 ONNX")
    print("=" * 68)

    rows = [
        ("Model file",             stats_pt["weight"],        stats_onnx["weight"]),
        ("File size",              f"{stats_pt['size_mb']} MB", f"{stats_onnx['size_mb']} MB"),
        ("Load time",              f"{stats_pt['load_s']} s",   f"{stats_onnx['load_s']} s"),
        ("mAP@50 (SAHI VOC)",      f"{stats_pt['map50']}%",     f"{stats_onnx['map50']}%"),
        ("Latency mean",           f"{stats_pt['lat_mean']} ms", f"{stats_onnx['lat_mean']} ms"),
        ("Latency p50",            f"{stats_pt['lat_p50']} ms",  f"{stats_onnx['lat_p50']} ms"),
        ("Latency p95",            f"{stats_pt['lat_p95']} ms",  f"{stats_onnx['lat_p95']} ms"),
        ("Latency max",            f"{stats_pt['lat_max']} ms",  f"{stats_onnx['lat_max']} ms"),
        ("Peak RAM",               f"{stats_pt['peak_ram_mb']:.0f} MB", f"{stats_onnx['peak_ram_mb']:.0f} MB"),
        ("Avg detections/image",   str(stats_pt['avg_dets']),    str(stats_onnx['avg_dets'])),
    ]

    col0 = 26; col1 = 22; col2 = 22
    hdr = f"  {'Metric':<{col0}}  {'FP32 .pt':>{col1}}  {'INT8 ONNX':>{col2}}"
    print(hdr)
    print("  " + "-"*(col0+col1+col2+4))
    for label, v_pt, v_onnx in rows:
        print(f"  {label:<{col0}}  {v_pt:>{col1}}  {v_onnx:>{col2}}")

    # delta summary
    size_ratio  = stats_pt["size_mb"] / stats_onnx["size_mb"]
    lat_delta   = stats_pt["lat_mean"] - stats_onnx["lat_mean"]
    map_delta   = stats_onnx["map50"]  - stats_pt["map50"]
    print("\n  Summary deltas (INT8 vs FP32):")
    print(f"    File size  : INT8 is {size_ratio:.1f}x smaller")
    print(f"    Latency    : {'faster' if lat_delta>0 else 'slower'} by {abs(lat_delta):.0f} ms mean")
    print(f"    mAP@50     : {'gain' if map_delta>=0 else 'loss'} of {abs(map_delta):.2f}pp")

    # save CSV
    import csv
    out_csv = Path(__file__).resolve().parent / "benchmark_results" / "weight_comparison.csv"
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=stats_pt.keys())
        w.writeheader()
        w.writerow(stats_pt)
        w.writerow(stats_onnx)
    print(f"\n  CSV saved: {out_csv}")

    # ── Bar chart ────────────────────────────────────────────────────────
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    BG = "#060B12"; PANEL = "#0F172A"; BLUE = "#3B82F6"; AMBER = "#F59E0B"
    TXT_HI = "#F8FAFC"; TXT_DIM = "#64748B"; BORDER = "#1E293B"

    metrics = {
        "mAP@50 (%)":        (stats_pt["map50"],     stats_onnx["map50"]),
        "Latency mean (ms)":  (stats_pt["lat_mean"],  stats_onnx["lat_mean"]),
        "Latency p95 (ms)":   (stats_pt["lat_p95"],   stats_onnx["lat_p95"]),
        "File size (MB)":     (stats_pt["size_mb"],   stats_onnx["size_mb"]),
        "Load time (s)":      (stats_pt["load_s"],    stats_onnx["load_s"]),
        "Avg dets/image":     (stats_pt["avg_dets"],  stats_onnx["avg_dets"]),
    }

    n = len(metrics)
    fig, axes = plt.subplots(2, 3, figsize=(16, 9))
    fig.patch.set_facecolor(BG)
    axes = axes.flatten()

    for ax, (metric, (vpt, vonnx)) in zip(axes, metrics.items()):
        ax.set_facecolor(PANEL)
        for sp in ax.spines.values():
            sp.set_edgecolor(BORDER)
        bars = ax.bar(
            ["FP32\n(.pt)", "INT8\n(.onnx)"],
            [vpt, vonnx],
            color=[BLUE, AMBER], width=0.45, zorder=3
        )
        ax.set_title(metric, color=TXT_HI, fontsize=11, fontweight="bold", pad=8)
        ax.tick_params(colors=TXT_DIM, labelsize=9)
        ax.yaxis.set_tick_params(colors=TXT_DIM)
        ax.set_ylabel("", color=TXT_DIM)
        # value labels on bars
        for bar, v in zip(bars, [vpt, vonnx]):
            ax.text(bar.get_x() + bar.get_width()/2,
                    bar.get_height() * 1.02,
                    str(v), ha="center", va="bottom",
                    fontsize=10, fontweight="bold",
                    color=TXT_HI)
        ax.set_ylim(0, max(vpt, vonnx) * 1.20 or 1)
        ax.grid(axis="y", color=BORDER, lw=0.8, zorder=0)

    fig.suptitle(
        "FP32 (.pt)  vs  INT8 ONNX  —  SAHI inference on 30 val images",
        color=TXT_HI, fontsize=13, fontweight="bold", y=1.01)
    plt.tight_layout()
    out_png = Path(__file__).resolve().parent / "benchmark_results" / "weight_comparison.png"
    plt.savefig(str(out_png), dpi=150, bbox_inches="tight",
                facecolor=BG, edgecolor="none")
    plt.close()
    print(f"  Chart saved: {out_png}")


if __name__ == "__main__":
    main()
