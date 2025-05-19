# hmt-proto-v1
# 


## Project Structure

## 🚀 Features

- Tracks wrist, elbow, and forearm movements using a wearable sensor
- Calculates range of motion (ROM) and classifies movement severity
- Compares affected vs unaffected limb in real-time
- Visual interface designed for non-technical clinicians
- Exports results to PDF and CSV for recordkeeping and analysis

## 📂 Folders

- **Arduino/**  
  Contains the complete Arduino sketch that reads data from the MPU6050 and sends it over serial/Bluetooth.

- **PythonApp/**  
  Python GUI app (`gui_app.py`)  It displays real-time data, performs ROM analysis, and handles exports.

- **images/**  
  Contains UI visuals used within the Python app for movement instructions and branding.

## 🧰 Requirements

- Python 3.8+ with the following libraries:
  - `tkinter`
  - `Pillow`
  - `pyserial`
  - `customtkinter`
  - `fpdf`

## 👩‍⚕️ Usage

1. Upload the Arduino sketch from the `Arduino/` folder to your device.
2. Run the Python GUI from the `PythonApp/` folder.
3. Follow on-screen instructions to test movements on affected and unaffected limbs.
4. Export results for clinical documentation or further analysis.




