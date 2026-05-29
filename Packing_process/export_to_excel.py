import os
import pandas as pd

def convert_yolo_to_excel():
    print("[*] Starting Data Extraction...")
    
    # Path to the folder where your .txt files were saved
    labels_folder = r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\Foxconn_PCB\Inference_Results\labels"
    
    # Ensure the folder exists
    if not os.path.exists(labels_folder):
        print(f"[!] ERROR: Cannot find folder {labels_folder}")
        return

    # TODO: Update this dictionary with the exact names from your data.yaml file
    class_map = {
        0: "Capacitor",
        1: "Resistor",
        2: "IC",
        3: "Diode",
        4: "LED",
        5: "Inductor",
        6: "Connector",
        99: "Random Printed Text Letters Numbers"
    }

    data_rows = []

    # Loop through every .txt file in the folder
    for filename in os.listdir(labels_folder):
        if filename.endswith(".txt"):
            filepath = os.path.join(labels_folder, filename)
            
            # Read the file line by line
            with open(filepath, "r") as file:
                lines = file.readlines()
                
                for line in lines:
                    # Split the line into individual numbers
                    parts = line.strip().split()
                    
                    if len(parts) >= 6:
                        class_id = int(parts[0])
                        component_name = class_map.get(class_id, f"Unknown_{class_id}")
                        
                        # Package the data
                        data_rows.append({
                            "Image_File": filename.replace(".txt", ".jpg"), # Assumes original images were .jpg
                            "Class_ID": class_id,
                            "Component_Name": component_name,
                            "Center_X (Norm)": float(parts[1]),
                            "Center_Y (Norm)": float(parts[2]),
                            "Width (Norm)": float(parts[3]),
                            "Height (Norm)": float(parts[4]),
                            "Confidence": f"{float(parts[5]) * 100:.2f}%"
                        })

    # Convert the extracted data into a Pandas DataFrame
    df = pd.DataFrame(data_rows)
    
    if df.empty:
        print("[!] No data found to export.")
        return

    # Save to Excel
    output_file = "Foxconn_PCB_Coordinates.xlsx"
    df.to_excel(output_file, index=False, engine='openpyxl')
    
    print(f"[*] EXTRACTION COMPLETE!")
    print(f"[*] Found {len(df)} components across all images.")
    print(f"[*] Saved exactly to: {os.path.abspath(output_file)}")

if __name__ == "__main__":
    convert_yolo_to_excel()