# === Imports ===
import customtkinter as ctk
from PIL import Image, ImageTk
import serial
import serial.tools.list_ports
from tkinter import messagebox, filedialog
import sys
import os
import time
import csv
from fpdf import FPDF
import datetime


#   ROM Calculation Functions 

class ROMCalculator: #Handles calculation and display of Range of Motion (ROM) values.
    
    def __init__(self, app):
        self.app = app # Reference to main application for accessing entries and canvases

    def safe_float(self, text): # convert text to float. Returns 0.0 on failure.
        try:
            return float(text)
        except (ValueError, TypeError):
            return 0.0

    def calculate_rom_side(self, entries_list):
        '''
        Calculate total ROM per joint group:
        - Wrist: Flexion + Extension
        - Forearm: Supination + Pronation
        - Elbow: Average of Flexion and Extension
        - Wrist Deviation: Radial + Ulnar
        '''
        wrist = self.safe_float(entries_list[0].get()) + self.safe_float(entries_list[1].get())
        forearm = self.safe_float(entries_list[2].get()) + self.safe_float(entries_list[3].get())
        elbow = (self.safe_float(entries_list[4].get()) + self.safe_float(entries_list[5].get())) / 2
        wrist_deviation = self.safe_float(entries_list[6].get()) + self.safe_float(entries_list[7].get())

        return {
            "ROM Wrist": wrist,
            "ROM Forearm": forearm,
            "ROM Elbow": elbow,
            "ROM Wrist Deviation": wrist_deviation,
        }


    def update_rom_display(self): #Refresh all ROM gauges using current entry values for both sides
        try:
            # Calculate ROM for unaffected side
            unaffected_roms = self.calculate_rom_side(self.app.unaffected_angle_entries)
            # Update ROM gauges
            self.app.update_rom_gauge(self.app.unaffected_rom_canvases[0], unaffected_roms["ROM Wrist"])
            self.app.update_rom_gauge(self.app.unaffected_rom_canvases[1], unaffected_roms["ROM Forearm"])
            self.app.update_rom_gauge(self.app.unaffected_rom_canvases[2], unaffected_roms["ROM Elbow"])
            self.app.update_rom_gauge(self.app.unaffected_rom_canvases[3], unaffected_roms["ROM Wrist Deviation"])

            # Calculate ROM for affected side
            affected_roms = self.calculate_rom_side(self.app.affected_angle_entries)
            # Update ROM gauges
            self.app.update_rom_gauge(self.app.affected_rom_canvases[0], affected_roms["ROM Wrist"])
            self.app.update_rom_gauge(self.app.affected_rom_canvases[1], affected_roms["ROM Forearm"])
            self.app.update_rom_gauge(self.app.affected_rom_canvases[2], affected_roms["ROM Elbow"])
            self.app.update_rom_gauge(self.app.affected_rom_canvases[3], affected_roms["ROM Wrist Deviation"])

        except Exception as e:
            messagebox.showerror("Error", f"ROM update error:\n{e}")



# === Main Application Class ===
class App(ctk.CTk):
    def __init__(self):  #Initialize the MedMove Diagnostics application.
       
        super().__init__()

        # --- Core State ---
        self.ser = None                          # Serial connection instance
        self.movement_letter = None              # Movement command to send 
        self.selected_movement = None            # Index of selected movement
        self.selected_side = None                # 'affected' or 'unaffected'
        self.serial_read_start_time = None       # When serial read starts
        self.serial_full_response = ""           # Accumulated serial output
        self.serial_read_duration = 7000         # Read window in milliseconds
        self.serial_read_mode = "measurement"    # 'measurement' or 'calibration'
        self.rom_calculator = ROMCalculator(self)

        # --- UI Entry & Canvas State ---
        self.unaffected_angle_entries = []       # Entry widgets for unaffected movements
        self.affected_angle_entries = []         # Entry widgets for affected movements
        self.unaffected_rom_canvases = []        # ROM gauge canvases (unaffected)
        self.affected_rom_canvases = []          # ROM gauge canvases (affected)

        # --- Appearance ---
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        # --- Window Setup ---
        self.title("MedMove Diagnostics")
        self.geometry("1200x800")
        self.configure(bg='white')

        self.setup_ui()      # Build all GUI components
        self.mainloop()      # Start the application event loop


    # === Resource Path Helper ===
    def resource_path(self, relative_path):
        """
        Return the absolute path to a resource file.
        Update: Support both normal execution and PyInstaller packaging.
        """
        try:
            base_path = sys._MEIPASS  # PyInstaller temp folder
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    # === Serial Communication Utilities ===

    def list_ports(self):
        """Return a list of available COM port device names."""
        return [port.device for port in serial.tools.list_ports.comports()]

    def connect_bluetooth(self):
        """Attempt to connect to the selected Bluetooth COM port."""
        selected_port = self.port_combobox.get()
        if not selected_port:
            messagebox.showerror("Error", "No COM port selected!")
            return
        try:
            self.ser = serial.Serial(selected_port, 115200, timeout=10)
            self.connect_button.configure(text="Connected", fg_color="green")
            messagebox.showinfo("Success", f"Connected to {selected_port}")
        except Exception as e:
            self.connect_button.configure(text="Disconnected", fg_color="red")
            messagebox.showerror("Connection Failed", str(e))



    # === UI Setup Functions ===
    def setup_ui(self):
        """Build and assemble the full UI layout."""
        self.setup_top_bar()
        self.setup_main_area()
        self.setup_sidebar()
        self.setup_center_panel()
        self.setup_center_bottom_buttons()
        self.setup_right_panel()


    # === Serial Reading Functions ===
    def read_serial_live(self):
        """Read serial output live and update UI with incoming angles."""
        if self.ser is None or not self.ser.is_open:
            return

        try:
            while self.ser.in_waiting:
                line = self.ser.readline().decode(errors='ignore').strip()
                self.serial_full_response += line + "\n"

                self.serial_output_box.configure(state="normal")
                self.serial_output_box.insert("end", line + "\n")
                self.serial_output_box.see("end")
                self.serial_output_box.configure(state="disabled")

                try:
                    angle = float(line)
                    self.update_live_angle(angle)
                except ValueError:
                    continue
        except Exception as e:
            messagebox.showerror("Error", f"Serial reading error:\n{e}")

        # Timer check: 
        if (time.time() - self.serial_read_start_time) * 1000 >= self.serial_read_duration:
            if self.serial_read_mode == "measurement":
                self.process_final_serial_data()
        else:
            self.after(50, self.read_serial_live)


    def update_live_angle(self, angle):
        """Render the current angle as an arc and numeric label on canvas."""
        self.live_canvas.delete("all")
        self.live_canvas.create_arc(10, 10, 190, 190, start=0, extent=180, style='arc', outline="#CCCCCC", width=20)
        extent_angle = (angle / 180) * 180
        self.live_canvas.create_arc(10, 10, 190, 190, start=0, extent=extent_angle, style='arc', outline="#00BFFF", width=20)
        self.live_canvas.create_text(100, 115, text=f"{angle:.1f}°", font=("Arial", 24, "bold"), fill="black")


    def process_final_serial_data(self):
        """Parse final angle from serial data and update relevant entries and visuals."""
        try:
            lines = self.serial_full_response.strip().split("\n")
            last_valid_angle = None

            for line in reversed(lines):
                if "ANGLE:" in line:
                    try:
                        angle_str = line.split("ANGLE:")[1].strip()
                        last_valid_angle = float(angle_str)
                        break
                    except (IndexError, ValueError):
                        continue

            if last_valid_angle is None:
                messagebox.showerror("Error", "No valid ANGLE data found!")
                return

            if self.selected_side == "unaffected":
                entry = self.unaffected_angle_entries[self.selected_movement]
            elif self.selected_side == "affected":
                entry = self.affected_angle_entries[self.selected_movement]
            else:
                return

            entry.configure(state="normal")
            entry.delete(0, "end")
            entry.insert(0, f"{last_valid_angle:.1f}")
            entry.configure(state="readonly")
            self.rom_calculator.update_rom_display()

            self.update_live_angle(last_valid_angle)

        except Exception as e:
            messagebox.showerror("Error", f"Processing error:\n{e}")



        
    def clear_all_measurements(self):
        """Reset all entries, ROM gauges, and serial output."""
        try:
            for entry, canvas in zip(self.unaffected_angle_entries, self.unaffected_rom_canvases):
                entry.configure(state="normal")
                entry.delete(0, "end")
                entry.configure(state="readonly")
                self.update_rom_gauge(canvas, 0)

            for entry, canvas in zip(self.affected_angle_entries, self.affected_rom_canvases):
                entry.configure(state="normal")
                entry.delete(0, "end")
                entry.configure(state="readonly")
                self.update_rom_gauge(canvas, 0)

            self.update_live_angle(0)

            self.serial_output_box.configure(state="normal")
            self.serial_output_box.delete("1.0", "end")
            self.serial_output_box.configure(state="disabled")

        except Exception as e:
            messagebox.showerror("Error", f"Clear all error:\n{e}")



    def redo_last_measurement(self):
        """Retry the last movement measurement."""
        try:
            if self.movement_letter is None:
                messagebox.showerror("Error", "No previous movement to redo!")
                return
            self.start_measurement()
        except Exception as e:
            messagebox.showerror("Error", f"Redo measurement error:\n{e}")



    def calibrate(self):
        """Enter calibration mode and begin live serial reading."""
        try:
            if self.ser is None or not self.ser.is_open:
                messagebox.showerror("Error", "Bluetooth not connected!")
                return

            self.ser.reset_input_buffer()
            self.ser.write(b'r')
            self.ser.flush()

            self.serial_output_box.configure(state="normal")
            self.serial_output_box.delete("1.0", "end")
            self.serial_output_box.configure(state="disabled")

            self.serial_read_start_time = time.time()
            self.serial_full_response = ""
            self.serial_read_mode = "calibration"

            self.read_serial_live()
        except Exception as e:
            messagebox.showerror("Error", f"Calibration error:\n{e}")



    def export_to_csv(self):
        """Export movement and ROM data to a CSV file."""
        try:
            patient_id = self.patient_id_entry.get().strip()
            if not patient_id:
                messagebox.showerror("Error", "Please enter a patient ID!")
                return

            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv")],
                initialfile=f"{patient_id}_DiagnosticTest.csv"
            )
            if not file_path:
                return

            movements = [
                "Wrist Flexion", "Wrist Extension",
                "Forearm Supination", "Forearm Pronation",
                "Elbow Flexion", "Elbow Extension",
                "Radial Deviation", "Ulnar Deviation"
            ]

            with open(file_path, mode="w", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(["Patient ID", patient_id])
                writer.writerow([])
                writer.writerow(["Movement Measurements"])
                writer.writerow(["Movement", "Unaffected", "Affected"])

                for i, movement in enumerate(movements):
                    writer.writerow([
                        movement,
                        self.unaffected_angle_entries[i].get(),
                        self.affected_angle_entries[i].get()
                    ])

                writer.writerow([])
                writer.writerow(["Calculated ROM Values"])
                writer.writerow(["ROM Type", "Unaffected", "Affected"])

                for rom_label in ["ROM Wrist", "ROM Forearm", "ROM Elbow", "ROM Wrist Deviation"]:
                    writer.writerow([
                        rom_label,
                        f"{self.rom_calculator.calculate_rom_side(self.unaffected_angle_entries).get(rom_label, 0):.1f}",
                        f"{self.rom_calculator.calculate_rom_side(self.affected_angle_entries).get(rom_label, 0):.1f}"
                    ])

            messagebox.showinfo("Success", "Data exported successfully!")

        except Exception as e:
            messagebox.showerror("Error", f"Export error:\n{e}")

    # === Export Measurements and ROM Data to PDF ===


    def export_to_pdf(self):
        """Export measurements and ROM calculations to a formatted PDF."""
        try:
            patient_id = self.patient_id_entry.get().strip()
            if not patient_id:
                messagebox.showerror("Error", "Please enter a patient ID!")
                return

            file_path = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf")],
                initialfile=f"{patient_id}_DiagnosticTest.pdf"
            )
            if not file_path:
                return

            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            pdf.cell(200, 10, txt="MedMove Diagnostics Report", ln=True, align="C")
            pdf.ln(5)

            current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            pdf.set_font("Arial", size=10)
            pdf.cell(200, 10, txt=f"Date: {current_date}", ln=True, align="C")
            pdf.ln(10)

            pdf.set_fill_color(220, 220, 220)
            pdf.set_font("Arial", size=12)
            pdf.cell(200, 10, txt=f"Patient ID: {patient_id}", ln=True, align="L", fill=True)
            pdf.ln(10)

            # Movements table
            pdf.set_font("Arial", style="B", size=12)
            pdf.cell(200, 10, txt="Movement Measurements", ln=True, align="L")
            pdf.set_font("Arial", style="B", size=11)
            pdf.cell(70, 8, "Movement", border=1, align="C")
            pdf.cell(60, 8, "Unaffected", border=1, align="C")
            pdf.cell(60, 8, "Affected", border=1, align="C")
            pdf.ln(8)

            pdf.set_font("Arial", size=11)
            movements = [
                "Wrist Flexion", "Wrist Extension",
                "Forearm Supination", "Forearm Pronation",
                "Elbow Flexion", "Elbow Extension",
                "Radial Deviation", "Ulnar Deviation"
            ]

            for i, movement in enumerate(movements):
                pdf.cell(70, 8, movement, border=1)
                pdf.cell(60, 8, self.unaffected_angle_entries[i].get(), border=1, align="C")
                pdf.cell(60, 8, self.affected_angle_entries[i].get(), border=1, align="C")
                pdf.ln(8)

            pdf.ln(10)

            # ROM summary
            pdf.set_font("Arial", style="B", size=12)
            pdf.cell(200, 10, txt="Calculated ROM Values", ln=True, align="L")

            pdf.set_font("Arial", style="B", size=11)
            pdf.cell(70, 8, "ROM Type", border=1, align="C")
            pdf.cell(60, 8, "Unaffected", border=1, align="C")
            pdf.cell(60, 8, "Affected", border=1, align="C")
            pdf.ln(8)

            pdf.set_font("Arial", size=11)
            unaffected_roms = self.rom_calculator.calculate_rom_side(self.unaffected_angle_entries)
            affected_roms = self.rom_calculator.calculate_rom_side(self.affected_angle_entries)

            for rom_label in ["ROM Wrist", "ROM Forearm", "ROM Elbow", "ROM Wrist Deviation"]:
                pdf.cell(70, 8, rom_label, border=1)
                pdf.cell(60, 8, f"{unaffected_roms.get(rom_label, 0):.1f}", border=1, align="C")
                pdf.cell(60, 8, f"{affected_roms.get(rom_label, 0):.1f}", border=1, align="C")
                pdf.ln(8)

            pdf.output(file_path)
            messagebox.showinfo("Success", "PDF exported successfully!")

        except Exception as e:
            messagebox.showerror("Error", f"PDF export error:\n{e}")

# --- End of PDF Export Function ---


    def update_rom_gauge(self, canvas, angle):
        """Draw updated ROM gauge with the given angle."""
        canvas.delete("all")
        canvas.create_arc(10, 10, 140, 140, start=0, extent=180, style='arc', outline="#CCCCCC", width=15)
        extent_angle = (angle / 180) * 180
        canvas.create_arc(10, 10, 140, 140, start=0, extent=extent_angle, style='arc', outline="#00BFFF", width=15)
        canvas.create_text(75, 90, text=f"{angle:.1f}°", font=("Arial", 16, "bold"), fill="black")



    def select_movement(self, letter, movement_name, idx, side):
        """Handle the user selecting a movement and side (affected/unaffected)."""
        # Set selected movement parameters
        self.movement_letter = letter
        self.selected_movement = idx
        self.selected_side = side

        # Map movement letters to images
        image_mapping = {
            'f': "images/WristMovements.png",
            'e': "images/WristMovements.png",
            's': "images/ForearmMoves.png",
            'p': "images/ForearmMoves.png",
            'x': "images/elborom.png",
            'y': "images/elborom.png",
            'z': "images/UlnarRadialMove.png",
            'z': "images/UlnarRadialMove.png"
            
        }

        # Default image if no match found
        image_path = image_mapping.get(letter, "images/AppLogo.png")

        # Load and display movement image
        movement_image = Image.open(self.resource_path(image_path))
        movement_photo = ctk.CTkImage(light_image=movement_image, dark_image=movement_image, size=(400,300))

        self.movement_image_placeholder.configure(image=movement_photo, text="")
        self.movement_image_placeholder.image = movement_photo

        # Update instruction label
        self.instruction_label.configure(text=f"Perform {movement_name}")


    def start_measurement(self):
        """Start a measurement by sending the movement letter to the device and preparing to read serial output."""

        # Check if Bluetooth is connected
        if self.ser is None or not self.ser.is_open:
            messagebox.showerror("Error", "Bluetooth not connected!")
            return

        # Check if a movement is selected
        if self.movement_letter is None or self.selected_movement is None or self.selected_side is None:
            messagebox.showerror("Error", "No movement selected!")
            return

        try:
            # Reset and prepare serial communication
            self.ser.reset_input_buffer()
            self.ser.write(self.movement_letter.encode())
            self.ser.flush()

            # Clear previous serial output box content
            self.serial_output_box.configure(state="normal")
            self.serial_output_box.delete("1.0", "end")
            self.serial_output_box.configure(state="disabled")

            # Setup for live reading
            self.serial_read_start_time = time.time()
            self.serial_full_response = ""
            self.serial_read_mode = "measurement"  # Set mode to normal measurement

            # Start reading serial data live
            self.read_serial_live()

        except Exception as e:
            messagebox.showerror("Error", f"Serial error:\n{e}")
    
    #Set up each section

    def setup_top_bar(self):
        """Top bar: App name, Patient ID, COM port selection, Connect button."""
        top_frame = ctk.CTkFrame(master=self, height=80, corner_radius=0, fg_color="white")
        top_frame.pack(side="top", fill="x")

        left_top_frame = ctk.CTkFrame(master=top_frame, fg_color="white")
        left_top_frame.pack(side="left", padx=20, pady=20)

        # App Name
        app_name_label = ctk.CTkLabel(master=left_top_frame, text="MedMove Diagnostics", font=("Arial", 24), text_color="black")
        app_name_label.pack(side="left")

        # Patient ID Entry
        self.patient_id_entry = ctk.CTkEntry(master=left_top_frame, width=200, placeholder_text="Enter Patient ID")
        self.patient_id_entry.pack(side="left", padx=20)

        # Port Combobox
        self.port_combobox = ctk.CTkComboBox(master=left_top_frame, width=150, state="readonly")
        self.port_combobox.pack(side="left", padx=20)
        self.port_combobox.configure(values=self.list_ports())
        self.port_combobox.set("Select COM Port")

        # Connect Button with Bluetooth Icon
        bluetooth_icon = ctk.CTkImage(
            light_image=Image.open(self.resource_path("images/bluetooth.png")),
            dark_image=Image.open(self.resource_path("images/bluetooth.png")),
            size=(24, 24)
        )

        self.connect_button = ctk.CTkButton(
            master=top_frame,
            text="Connect",
            command=self.connect_bluetooth,
            image=bluetooth_icon,
            compound="left",
            width=140,
            height=40,
            fg_color="#DDDDDD",
            text_color="black",
            hover_color="#CCCCCC"
        )
        self.connect_button.pack(side="right", padx=20, pady=20)

   # === Sidebar Setup ===

    def setup_sidebar(self):
        """Setup the sidebar frame on the left with movements and input fields."""

        # Sidebar frame
        self.sidebar_frame = ctk.CTkScrollableFrame(master=self.main_area, width=300, corner_radius=0, fg_color="#F5F5F5")
        self.sidebar_frame.pack(side="left", fill="y", padx=(10, 0), pady=10)

        # Movements list
        self.movements = [
            ("Wrist Flexion", 'f'),
            ("Wrist Extension", 'e'),
            ("Forearm Supination", 's'),
            ("Forearm Pronation", 'p'),
            ("Elbow Flexion", 'x'),
            ("Elbow Extension", 'y'),
            ("Radial Deviation", 'z'),
            ("Ulnar Deviation", 'z')
        ]

        # Loop through each movement and create UI elements
        for idx, (movement, letter) in enumerate(self.movements):
            # Movement label
            movement_label = ctk.CTkLabel(master=self.sidebar_frame, text=movement, font=("Arial", 16), text_color="black")
            movement_label.pack(padx=10, pady=(10, 2))

            # Frame for buttons
            button_frame = ctk.CTkFrame(master=self.sidebar_frame, fg_color="#F5F5F5")
            button_frame.pack(padx=10, pady=(0, 5))

            # Button for unaffected side
            unaffected_button = ctk.CTkButton(
                master=button_frame,
                text="Unaffected",
                width=100,
                height=30,
                fg_color="black",
                text_color="white",
                hover_color="gray",
                command=lambda l=letter, m=movement, i=idx: self.select_movement(l, m, i, 'unaffected')
            )
            unaffected_button.pack(side="left", padx=5)

            # Button for affected side
            affected_button = ctk.CTkButton(
                master=button_frame,
                text="Affected",
                width=100,
                height=30,
                fg_color="black",
                text_color="white",
                hover_color="gray",
                command=lambda l=letter, m=movement, i=idx: self.select_movement(l, m, i, 'affected')
            )
            affected_button.pack(side="left", padx=5)

            # Frame for angle entry boxes
            angle_box_frame = ctk.CTkFrame(master=self.sidebar_frame, fg_color="#F5F5F5")
            angle_box_frame.pack(padx=10, pady=(0, 10))

            # Entry for unaffected angle
            unaffected_entry = ctk.CTkEntry(master=angle_box_frame, width=80, state="readonly", justify="center")
            unaffected_entry.pack(side="left", padx=5)
            self.unaffected_angle_entries.append(unaffected_entry)

            # Entry for affected angle
            affected_entry = ctk.CTkEntry(master=angle_box_frame, width=80, state="readonly", justify="center")
            affected_entry.pack(side="left", padx=5)
            self.affected_angle_entries.append(affected_entry)

    

    #Setup the main area with sidebar, center panel, and right panel.
    def setup_main_area(self):
        
                # Create main frame area
        self.main_area = ctk.CTkFrame(master=self, fg_color="white")
        self.main_area.pack(expand=True, fill="both")

        
    
    def setup_center_panel(self): 
        '''
        Setup the center panel 
        '''

        # Center frame
        self.center_frame = ctk.CTkFrame(master=self.main_area, fg_color="white")

        self.center_frame.pack(side="left", expand=True, fill="both", padx=10, pady=10)

        # Load initial logo image for placeholder
        logo_image = Image.open(self.resource_path("images/AppLogo.png"))
        logo_photo = ctk.CTkImage(light_image=logo_image, dark_image=logo_image, size=(400,300))

        # Movement image placeholder
        self.movement_image_placeholder = ctk.CTkLabel(
            master=self.center_frame,
            image=logo_photo,
            text="",
            width=300,
            height=200,
            corner_radius=10,
            fg_color="#E0E0E0"
        )
        self.movement_image_placeholder.pack(pady=20)

        # Instruction label
        self.instruction_label = ctk.CTkLabel(
            master=self.center_frame,
            text="[Instructions]",
            wraplength=400,
            font=("Arial", 20, "bold"),
            text_color="black"
        )
        self.instruction_label.pack(pady=10)

        # Serial monitor text box for live serial output
        self.serial_output_box = ctk.CTkTextbox(
            master=self.center_frame,
            width=400,
            height=80,
            font=("Arial", 20, "bold")
        )
        self.serial_output_box.pack(pady=(10, 2))
        self.serial_output_box.insert("end", "Awaiting Movement Selection...\n")
        self.serial_output_box.configure(state="disabled")  # Make readonly initially

        # Live angle frame container
        live_angle_frame = ctk.CTkFrame(master=self.center_frame, fg_color="white")
        live_angle_frame.pack(pady=20)

        # Frame pair for centering the canvas
        frame_pair = ctk.CTkFrame(master=live_angle_frame, fg_color="white")
        frame_pair.pack()

        # Live angle canvas for arc visualization
        self.live_canvas = ctk.CTkCanvas(
            master=frame_pair,
            width=200,
            height=150,
            bg="white",
            highlightthickness=0
        )
        self.live_canvas.pack(side="left", padx=10)

        # Draw static background arc
        self.live_canvas.create_arc(10, 10, 190, 190, start=0, extent=180, style='arc', outline="#CCCCCC", width=20)

     
    def setup_center_bottom_buttons(self):
        '''Setup the bottom control buttons'''
        center_bottom_frame = ctk.CTkFrame(master=self.center_frame, fg_color="white")
        center_bottom_frame.pack(pady=(40, 10))

        # Buttons
        button_texts = [
            ("Clear All", self.clear_all_measurements),
            ("Redo", self.redo_last_measurement),
            ("Calibrate", self.calibrate)  
        ]

        for text, command in button_texts:
            ctk.CTkButton(
                master=center_bottom_frame,
                text=text,
                width=100,
                height=50,
                fg_color="black",
                text_color="white",
                hover_color="gray",
                command=command
            ).pack(side="left", padx=10)

        # Start button
        start_button = ctk.CTkButton(
            master=center_bottom_frame,
            text="Start",
            width=100,
            height=50,
            fg_color="black",
            text_color="white",
            hover_color="gray",
            command=self.start_measurement
        )
        start_button.pack(side="left", padx=10)

        self.export_menu = ctk.CTkButton(        
            master=center_bottom_frame,
            text="Export",
            width=100,
            height=50,
            fg_color="black",
            text_color="white",
            hover_color="gray",
            command=self.handle_export
        )
        self.export_menu.pack(side="left", padx=10)
        


    def handle_export(self):
        """Handle export"""
        
        self.export_to_csv()
    
        self.export_to_pdf()
        


    #Setup the right panel .
    def setup_right_panel(self):
        

        # Right frame
        self.right_frame = ctk.CTkFrame(master=self.main_area, width=375, fg_color="#F5F5F5")
        self.right_frame.pack(side="left", fill="y", padx=10, pady=10)

        # Container for two columns
        rom_columns = ctk.CTkFrame(master=self.right_frame, fg_color="#F5F5F5")
        rom_columns.pack(expand=True, fill="both", padx=10, pady=10)

        # Left column for unaffected side
        self.unaffected_frame = ctk.CTkFrame(master=rom_columns, fg_color="#F5F5F5")
        self.unaffected_frame.pack(side="left", expand=True, fill="both", padx=5)

        # Right column for affected side
        self.affected_frame = ctk.CTkFrame(master=rom_columns, fg_color="#F5F5F5")
        self.affected_frame.pack(side="left", expand=True, fill="both", padx=5)

        # Titles for each side
        unaffected_title = ctk.CTkLabel(master=self.unaffected_frame, text="Unaffected ROM", font=("Arial", 18, "bold"), text_color="black")
        unaffected_title.pack(pady=(10, 5))

        affected_title = ctk.CTkLabel(master=self.affected_frame, text="Affected ROM", font=("Arial", 18, "bold"), text_color="black")
        affected_title.pack(pady=(10, 5))

        # Labels for ROM types
        rom_labels = ["Wrist ROM", "Forearm ROM", "Elbow ROM","Wrist Deviation ROM"]

        # Build ROM gauges for unaffected side
        for label_text in rom_labels:
            label_widget = ctk.CTkLabel(master=self.unaffected_frame, text=label_text, font=("Arial", 14), text_color="black")
            label_widget.pack(pady=(5, 0))

            canvas = ctk.CTkCanvas(master=self.unaffected_frame, width=150, height=120, bg="#F5F5F5", highlightthickness=0)
            canvas.pack(pady=(0, 10))
            self.draw_rom_gauge(canvas, 0)  # Start with 0 degree
            self.unaffected_rom_canvases.append(canvas)

        # Build ROM gauges for affected side
        for label_text in rom_labels:
            label_widget = ctk.CTkLabel(master=self.affected_frame, text=label_text, font=("Arial", 14), text_color="black")
            label_widget.pack(pady=(5, 0))

            canvas = ctk.CTkCanvas(master=self.affected_frame, width=150, height=120, bg="#F5F5F5", highlightthickness=0)
            canvas.pack(pady=(0, 10))
            self.draw_rom_gauge(canvas, 0)  # Start with 0 degree
            self.affected_rom_canvases.append(canvas)

    def draw_rom_gauge(self, canvas, angle):
        '''Draw an arc gauge representing the ROM angle on a canvas.'''
        canvas.delete("all")  # Clear previous drawing
        canvas.create_arc(10, 10, 140, 140, start=0, extent=180, style='arc', outline="#CCCCCC", width=15)
        extent_angle = (angle / 180) * 180
        canvas.create_arc(10, 10, 140, 140, start=0, extent=extent_angle, style='arc', outline="#00BFFF", width=15)
        canvas.create_text(75, 90, text=f"{angle:.1f}°", font=("Arial", 16, "bold"), fill="black")

    

if __name__ == "__main__":
    App()
