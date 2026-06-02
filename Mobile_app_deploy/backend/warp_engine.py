import cv2
import numpy as np
import os

def flatten_dynamic(image_path, relative_corners, target_size=1000):
    """
    Flattens the image based on 4 relative corner taps from the mobile app.
    relative_corners format: [{"x": 0.1, "y": 0.1}, {"x": 0.9, "y": 0.1}, ...]
    """
    print(f"[*] Processing dynamic warp for: {image_path}")
    img = cv2.imread(image_path)
    
    if img is None:
        raise ValueError("Cannot read image for warping.")
        
    img_h, img_w = img.shape[:2]

    # 1. Translate relative mobile screen taps (0.0 to 1.0) into exact image pixels
    src_pts = []
    for corner in relative_corners:
        abs_x = int(corner['x'] * img_w)
        abs_y = int(corner['y'] * img_h)
        src_pts.append([abs_x, abs_y])
        
    source_corners = np.float32(src_pts)

    # 2. Define the perfect output square (1000x1000)
    dest_corners = np.float32([
        [0, 0], 
        [target_size - 1, 0], 
        [target_size - 1, target_size - 1], 
        [0, target_size - 1]
    ])

    # 3. Execute the Math
    matrix = cv2.getPerspectiveTransform(source_corners, dest_corners)
    flattened_img = cv2.warpPerspective(img, matrix, (target_size, target_size))

    # Overwrite the original skewed image with the perfect flat one
    cv2.imwrite(image_path, flattened_img)
    print(f"[+] Successfully flattened and overwritten: {image_path}")
    
    return image_path