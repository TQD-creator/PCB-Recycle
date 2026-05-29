import cv2
import numpy as np
import os

# ==========================================
# CONFIGURATION PARAMETERS
# ==========================================
# 1. Path to your skewed/oblique image
image_path = r'C:\Users\Lenovo\Documents\Foxconn\Test_Board\Haboob_socket.jpg'

# 2. SOURCE POINTS: The 4 corners of the chip on the skewed image
# (Strict order: Top-Left -> Top-Right -> Bottom-Right -> Bottom-Left)
src_pts = np.float32([
    [970, 454],   # Top-Left
    [1277, 769],   # Top-Right
    [970, 1075],  # Bottom-Right
    [649, 755]   # Bottom-Left
])

# 3. TARGET SIZE: The desired pixel size for the flattened chip
# The NVIDIA chip is square, so 300x300 pixels ensures HD quality
target_size = (510, 510)  # Width x Height

# ==========================================
# EXECUTION ALGORITHM
# ==========================================
def flatten_chip(img_path, source_points, dst_size):
    """
    Extracts and applies a planar homography transformation to a specific region.
    """
    # Read the image
    image_oblique = cv2.imread(img_path)
    if image_oblique is None:
        raise ValueError(f"Cannot find image at: {img_path}. Please check the file path!")

    # TARGET POINTS: Map the chip to the (0, 0) coordinates of a new square canvas
    dst_pts = np.float32([
        [0, 0],                           # Top-Left
        [dst_size[0] - 1, 0],                # Top-Right
        [dst_size[0] - 1, dst_size[1] - 1],     # Bottom-Right
        [0, dst_size[1] - 1]                 # Bottom-Left
    ])

    # Calculate the Homography perspective transformation matrix
    matrix = cv2.getPerspectiveTransform(source_points, dst_pts)

    # Apply warp perspective to extract and flatten the chip
    rectified_chip = cv2.warpPerspective(image_oblique, matrix, dst_size, flags=cv2.INTER_LINEAR)
    
    return rectified_chip

# ==========================================
# MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    try:
        # Pass the globally defined variables into the function
        result_image = flatten_chip(image_path, src_pts, target_size)
        
        output_name = 'flattened_chip4.jpg'
        cv2.imwrite(output_name, result_image)
        
        print(f"Success! The chip has been extracted and flattened.")
        print(f"Saved at: {os.path.abspath(output_name)}")
        print("-> Next step: Import this file into Photopea to remove the background (transparent).")
        
    except Exception as e:
        print(f"FATAL ERROR: {e}")