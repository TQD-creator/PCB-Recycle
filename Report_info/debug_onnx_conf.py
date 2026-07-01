"""
debug_onnx_conf.py
Run one image through high_res_p2_int8.onnx directly via onnxruntime
and print the raw confidence scores to understand why CONF=0.25 yields 0 dets.
"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np
import cv2
from pathlib import Path

ONNX = Path(r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\Mobile_app_deploy\backend\runtime\assets\weights\high_res_p2_int8.onnx")
VAL  = Path(r"D:\Download_save\Foxconn_save\Classification\val\images")

import onnxruntime as ort

sess = ort.InferenceSession(str(ONNX), providers=["CPUExecutionProvider"])
inp  = sess.get_inputs()[0]
out  = sess.get_outputs()

print(f"Input  : {inp.name}  shape={inp.shape}  dtype={inp.type}")
for o in out:
    print(f"Output : {o.name}  shape={o.shape}  dtype={o.type}")

# pick first image, resize to model input (assume 640x640)
img_paths = sorted(VAL.glob("*.jpg"))[:1]
img = cv2.imread(str(img_paths[0]))
H, W = img.shape[:2]
img_resized = cv2.resize(img, (640, 640))
img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
tensor  = img_rgb.transpose(2, 0, 1)[np.newaxis]  # 1,3,H,W

raw = sess.run(None, {inp.name: tensor})
print(f"\nOutput shapes: {[r.shape for r in raw]}")

# YOLOv8 output is typically [1, 5+nc, num_anchors]
# or [1, num_anchors, 5+nc] — check both
arr = raw[0]
print(f"Output[0] dtype={arr.dtype}  shape={arr.shape}  min={arr.min():.4f}  max={arr.max():.4f}")

# Check conf distribution — for 1-class YOLOv8, output is [1, 5, N] (cx,cy,w,h,conf)
# or transposed [1, N, 5]
if arr.ndim == 3:
    if arr.shape[1] < arr.shape[2]:  # [1, 5, N]
        confs = arr[0, 4, :]
    else:                             # [1, N, 5]
        confs = arr[0, :, 4]
    print(f"\nConf scores — total boxes: {len(confs)}")
    print(f"  min={confs.min():.5f}  max={confs.max():.5f}  mean={confs.mean():.5f}")
    thresholds = [0.001, 0.01, 0.05, 0.10, 0.20, 0.25, 0.30]
    for t in thresholds:
        n = int((confs > t).sum())
        print(f"  > {t:.3f} : {n} boxes")
