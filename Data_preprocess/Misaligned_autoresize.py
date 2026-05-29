import cv2
import numpy as np
import random
import os

def rotate_image_alpha(image, angle):
    """Xoay ảnh PNG có kênh Alpha không bị cắt viền"""
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
    """Dán đè ảnh PNG trong suốt lên ảnh nền"""
    bg_img = background.copy()
    h, w = overlay.shape[:2]
    
    # Kiểm tra xem ảnh dán có vượt quá viền background không
    if y + h > bg_img.shape[0] or x + w > bg_img.shape[1] or y < 0 or x < 0:
        return bg_img # Bỏ qua nếu tràn viền
        
    overlay_img = overlay[..., :3]
    mask = overlay[..., 3:] / 255.0
    
    roi = bg_img[y:y+h, x:x+w]
    blended = (mask * overlay_img + (1 - mask) * roi).astype(np.uint8)
    bg_img[y:y+h, x:x+w] = blended
    return bg_img

# ==========================================
# CẤU HÌNH VÀ THỰC THI
# ==========================================

# 1. Đọc ảnh nền bo mạch rỗng và ảnh chip trong suốt
background = cv2.imread(r'C:\Users\Lenovo\Documents\Foxconn\Test_Board\bo_mach_rong.jpg') 
raw_chip = cv2.imread(r'C:\Users\Lenovo\Documents\Foxconn\Test_Board\Modify\comp\photopea\chip_transparent.png', cv2.IMREAD_UNCHANGED)
# --- THÊM 2 DÒNG NÀY ĐỂ FIX LỖI TRIỆT ĐỂ ---
# Nếu Photopea cắt mất kênh Alpha (ảnh chỉ có 3 kênh), ta tự động thêm kênh Alpha vào!
if len(raw_chip.shape) == 3 and raw_chip.shape[2] == 3:
    raw_chip = cv2.cvtColor(raw_chip, cv2.COLOR_BGR2BGRA)

# 2. KHAI BÁO TỌA ĐỘ VÀ KÍCH THƯỚC CHUẨN CỦA SOCKET TRÊN BO MẠCH (ROI)
# (Chúng ta sẽ lấy số này từ bức ảnh chụp bo mạch đã có linh kiện)
socket_roi = {
    "x": 315,       
    "y": 342,       
    "w": 144,       
    "h": 147        
}

# 3. TỰ ĐỘNG THU PHÓNG (AUTO-RESIZE)
# Ép ảnh chip gốc về đúng kích thước vật lý của socket trên hình chụp
resized_chip = cv2.resize(raw_chip, (socket_roi["w"], socket_roi["h"]), interpolation=cv2.INTER_AREA)

# Tạo thư mục
os.makedirs("dataset_output/misaligned", exist_ok=True)

# 4. TẠO HÀNG LOẠT DATASET LỖI
for i in range(100):
    # Tạo góc lệch và độ xô lệch ngẫu nhiên
    angle = random.uniform(-5.0, 5.0) 
    shift_x = random.randint(-7, 7)
    shift_y = random.randint(-7, 7)
    
    # Xoay con chip đã được thu phóng
    rotated = rotate_image_alpha(resized_chip, angle)
    
    # Do ảnh xoay bị nở ra (new_w, new_h), ta cần tính lại tọa độ X, Y để giữ chip ở trung tâm socket
    offset_x = (rotated.shape[1] - socket_roi["w"]) // 2
    offset_y = (rotated.shape[0] - socket_roi["h"]) // 2
    
    paste_x = socket_roi["x"] + shift_x - offset_x
    paste_y = socket_roi["y"] + shift_y - offset_y
    
    # Hợp nhất ảnh
    synthetic_img = overlay_transparent(background, rotated, paste_x, paste_y)
    
    # Đồng bộ nhiễu pixel toàn ảnh (Quan trọng cho AI)
    synthetic_img = cv2.GaussianBlur(synthetic_img, (3, 3), 0.8)
    
    cv2.imwrite(f"dataset_output/misaligned/defect_{i:04d}.jpg", synthetic_img)
    print(f"Hoàn thành: defect_{i:04d}.jpg")