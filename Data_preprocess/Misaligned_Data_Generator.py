import cv2
import numpy as np
import random
import os
import math

# ==========================================
# PHẦN 1: CÁC HÀM CỐT LÕI (TUYỆT ĐỐI KHÔNG CHỈNH SỬA)
# ==========================================

def rotate_image_alpha(image, angle):
    """Xoay ảnh PNG có kênh Alpha mà không bị cắt viền do hiệu ứng nở khung"""
    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    
    cos_a, sin_a = np.abs(M[0, 0]), np.abs(M[0, 1])
    new_w = int((h * sin_a) + (w * cos_a))
    new_h = int((h * cos_a) + (w * sin_a))
    
    M[0, 2] += (new_w / 2) - center[0]
    M[1, 2] += (new_h / 2) - center[1]
    
    return cv2.warpAffine(image, M, (new_w, new_h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))

def overlay_transparent(background, overlay, x, y):
    """Dán đè ảnh PNG trong suốt lên ảnh nền với thuật toán Alpha Blending"""
    # Lớp bảo vệ số 2 (Đề phòng trường hợp lỗi kênh)
    if len(overlay.shape) == 3 and overlay.shape[2] == 3:
        overlay = cv2.cvtColor(overlay, cv2.COLOR_BGR2BGRA)
        
    bg_img = background.copy()
    h, w = overlay.shape[:2]
    
    # Bỏ qua nếu tọa độ văng hẳn ra ngoài tấm bo mạch
    if y + h > bg_img.shape[0] or x + w > bg_img.shape[1] or y < 0 or x < 0:
        return bg_img
        
    overlay_img = overlay[..., :3]
    mask = overlay[..., 3:] / 255.0
    
    roi = bg_img[y:y+h, x:x+w]
    blended = (mask * overlay_img + (1 - mask) * roi).astype(np.uint8)
    bg_img[y:y+h, x:x+w] = blended
    return bg_img

def get_obb_corners(cx, cy, w, h, angle_degrees):
    """Tính toán toán học 4 góc của Bounding Box OBB sau khi xoay để nạp cho YOLO"""
    theta = math.radians(-angle_degrees)
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    
    corners = [(-w/2, -h/2), (w/2, -h/2), (w/2, h/2), (-w/2, h/2)]
    
    rotated_corners = []
    for x, y in corners:
        x_rot = x * cos_t - y * sin_t
        y_rot = x * sin_t + y * cos_t
        rotated_corners.append((cx + x_rot, cy + y_rot))
        
    return rotated_corners

# ==========================================
# PHẦN 2: CẤU HÌNH THÔNG SỐ & CHỐT CHẶN AN TOÀN
# ==========================================

# 1. Đọc file đầu vào (Đã sử dụng đường dẫn tuyệt đối chuẩn xác của bạn)
background = cv2.imread(r'C:\Users\Lenovo\Documents\Foxconn\Test_Board\Haboob_socket.jpg') 
raw_chip = cv2.imread(r'C:\Users\Lenovo\Documents\Foxconn\Test_Board\Modify\comp\photopea\Haboob\chip_transparent2.png', cv2.IMREAD_UNCHANGED)

# --- CHỐT CHẶN AN TOÀN TOÀN CỤC ---
# Nếu file PNG xuất lỗi mất nền trong suốt (chỉ có 3 kênh), ép nó thành 4 kênh ngay tại đây!
# Điều này bảo vệ hàm cv2.resize không bị lỗi và xóa sổ "bóng ma trắng"
if len(raw_chip.shape) == 3 and raw_chip.shape[2] == 3:
    raw_chip = cv2.cvtColor(raw_chip, cv2.COLOR_BGR2BGRA)
# -----------------------------------

# 2. Tọa độ vàng (Neo chính xác vị trí cái socket 2 sọc đen trên bo mạch rỗng)
socket_roi = {
    "x": 323,
    "y": 1413,
    "w": 72,
    "h": 92
}
# Habbob chip_transparent3.png
    # "x": 1365,
    # "y": 845,
    # "w": 100,
    # "h": 76
#Habbob chip_transparent1.png
    # "x": 1353,
    # "y": 593,
    # "w": 96,
    # "h": 126
#Habbob chip_transparent.png
    # "x": 1318,
    # "y": 406,
    # "w": 127,
    # "h": 130
#dk chip_transparent.png
    # "x": 1062,
    # "y": 620,
    # "w": 106,
    # "h": 132
#dk chip_transparent1.png
    # "x": 849,
    # "y": 465,
    # "w": 175,
    # "h": 175
#  chip_transparent1.png
    # "x": 606,
    # "y": 1543,
    # "w": 509,
    # "h": 503
# chip_transparent1.png
    # "x": 348,
    # "y": 2097,
    # "w": 111,
    # "h": 76
# chip_transparent8.png
    # "x": 342,
    # "y": 1964,
    # "w": 114,
    # "h": 80
# chip_transparent7.png
    # "x": 388,
    # "y": 1543,
    # "w": 75,
    # "h": 76
    # chip_transparent6.png
    # "x": 370,
    # "y": 1361,
    # "w": 102,
    # "h": 138
    # chip_transparent5.png
    # "x": 347,       # Tọa độ X góc trên bên trái
    # "y": 1198,       # Tọa độ Y góc trên bên trái
    # "w": 119,       # Chiều rộng đích
    # "h": 83        # Chiều cao đích
# socket_roi = { chip_transparent4.png
#    "x": 572,       # Tọa độ X góc trên bên trái
#    "y": 1201,       # Tọa độ Y góc trên bên trái
#    "w": 80,       # Chiều rộng đích
#    "h": 80        # Chiều cao đích
# }

# Auto-resize con chip nguyên bản về đúng form vật lý của socket
resized_chip = cv2.resize(raw_chip, (socket_roi["w"], socket_roi["h"]), interpolation=cv2.INTER_AREA)

# Lấy kích thước ảnh nền gốc để tính tỷ lệ tọa độ (Normalize) cho YOLO
img_h, img_w = background.shape[:2]

# Tạo sẵn kiến trúc thư mục chuẩn của YOLOv8/v11
os.makedirs("dataset_output/images/train", exist_ok=True)
os.makedirs("dataset_output/labels/train", exist_ok=True)

# ==========================================
# PHẦN 3: VÒNG LẶP SINH DỮ LIỆU & LABEL OBB
# ==========================================

TOTAL_IMAGES = 50 # Chỉnh số lượng ảnh bạn muốn sinh ra

for i in range(TOTAL_IMAGES):
    
    # Tạo góc lệch và độ xô lệch ngẫu nhiên (Lệch nhẹ, thực tế)
    angle = random.uniform(-5.0, 5.0) 
    shift_x = random.randint(-8, 8) 
    shift_y = random.randint(-8, 8) 
    
    # Thực thi xoay và tính tọa độ bù trừ do nở khung
    rotated = rotate_image_alpha(resized_chip, angle)
    offset_x = (rotated.shape[1] - socket_roi["w"]) // 2
    offset_y = (rotated.shape[0] - socket_roi["h"]) // 2
    
    paste_x = socket_roi["x"] + shift_x - offset_x
    paste_y = socket_roi["y"] + shift_y - offset_y
    
    # Xác định tâm điểm thực sự của con chip sau khi dán lệch (Để tính tọa độ YOLO)
    true_cx = socket_roi["x"] + shift_x + (socket_roi["w"] / 2)
    true_cy = socket_roi["y"] + shift_y + (socket_roi["h"] / 2)
    
    # Dán đè lên bo mạch
    synthetic_img = overlay_transparent(background, rotated, paste_x, paste_y)
    
    # Làm mờ viền để trộn pixel, tăng tính chân thực
    synthetic_img = cv2.GaussianBlur(synthetic_img, (3, 3), 0.8) 
    
    # Lưu file Ảnh (.jpg)
    img_name = f"defect_nvidia_{i:04d}.jpg"
    cv2.imwrite(f"dataset_output/images/train/{img_name}", synthetic_img)
    
    # --- TÍNH TOÁN VÀ XUẤT LABEL CHO YOLO OBB ---
    corners = get_obb_corners(true_cx, true_cy, socket_roi["w"], socket_roi["h"], angle)
    
    class_id = 1  # 1 = Misaligned (Lệch vị trí)
    label_line = f"{class_id} "
    
    for pt_x, pt_y in corners:
        norm_x = max(0.0, min(1.0, pt_x / img_w)) # Chuẩn hóa tọa độ X (0 -> 1)
        norm_y = max(0.0, min(1.0, pt_y / img_h)) # Chuẩn hóa tọa độ Y (0 -> 1)
        label_line += f"{norm_x:.6f} {norm_y:.6f} "
        
    # Lưu file Label (.txt)
    txt_name = f"defect_nvidia_{i:04d}.txt"
    with open(f"dataset_output/labels/train/{txt_name}", "w") as f:
        f.write(label_line.strip())
        
    print(f"Đã tạo thành công bộ dữ liệu: {img_name} và {txt_name}")

print("\nHOÀN THÀNH TOÀN BỘ PIPELINE TẠO DỮ LIỆU!")