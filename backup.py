import tkinter as tk
from datetime import datetime
import cantools
import can
import threading
import time
import csv
from tkinter import messagebox
from influxdb_client import InfluxDBClient, Point, WritePrecision
import queue


##TODO REMOVE INFLUXDB 


class DynoLogger:
    def __init__(self, root):
        self.root = root
        self.root.title("Dyno Logger")
        self.root.geometry("600x500")
        self.root.config(bg="#f4f4f9")
        self.is_running = False
        self.message_count = 0
        self.log_queue = queue.Queue()
        self.data_dict = {}

        try:
            self.sensor_dbc = cantools.database.load_file("can1_HPF24.dbc")
            self.critical_dbc = cantools.database.load_file("./dbcbackupedited/can2-HPF24.dbc")
            print("Both DBC files loaded successfully.")
            self.print_dbc_signals()
        except cantools.database.UnsupportedDatabaseFormatError as e:
            print(f"Error loading DBC file: {e}")
            self.sensor_dbc = None
            self.critical_dbc = None
            messagebox.showerror("Error", f"Error loading DBC file: {e}")
            self.root.quit()

        try:
            ##ADD BUS2 WHEN WE WANT TO LOG CRITICAL DATA (CAN2 DBC)
            self.bus1 = can.interface.Bus(channel=0, interface='kvaser', bitrate=1000000)  # Sensor CAN bus
        except can.CanError as e:
            print(f"Error initializing Kvaser CAN bus: {e}")
            messagebox.showerror("Error", f"Error initializing CAN bus: {e}")
            self.root.quit()

        # DELETE SOON, INFLUXDB MIGHT NOT BE A GOOD FIT
        try:
            self.influxdb_client = InfluxDBClient(
                url="http://localhost:8086",
                token="your-token-here",
                org="your-org-here"
            )
            self.bucket = "withoutui"
            print("Connected to InfluxDB successfully.")
        except Exception as e:
            print(f"Error connecting to InfluxDB: {e}")
            messagebox.showerror("Error", f"Error connecting to InfluxDB: {e}")
            self.root.quit()

        # Dynamically get all message IDs from both DBC files
        self.valid_message_ids = set()
        if self.sensor_dbc:
            self.valid_message_ids.update(msg.frame_id for msg in self.sensor_dbc.messages)
        if self.critical_dbc:
            self.valid_message_ids.update(msg.frame_id for msg in self.critical_dbc.messages)

        self.setup_ui()

    def print_dbc_signals(self):
        if self.sensor_dbc:
            print(f"Sensor DBC contains {len(self.sensor_dbc.messages)} messages:")
            for message in self.sensor_dbc.messages:
                print(f"Message ID: {message.frame_id}, Name: {message.name}")
                for signal in message.signals:
                    print(f"  Signal Name: {signal.name}, Start Bit: {signal.start}, Length: {signal.length}")

        if self.critical_dbc:
            print(f"Critical DBC contains {len(self.critical_dbc.messages)} messages:")
            for message in self.critical_dbc.messages:
                print(f"Message ID: {message.frame_id}, Name: {message.name}")
                for signal in message.signals:
                    print(f"  Signal Name: {signal.name}, Start Bit: {signal.start}, Length: {signal.length}")

    def setup_ui(self):
        frame = tk.Frame(self.root, bg="#f4f4f9")
        frame.pack(padx=20, pady=20, fill=tk.BOTH, expand=True)

        title_label = tk.Label(frame, text="HPF025 Logger", font=("Arial", 18, "bold"), bg="#f4f4f9", fg="#333")
        title_label.pack(pady=10)

        log_frame = tk.Frame(frame, bg="#f4f4f9")
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(log_frame, height=15, width=60, wrap=tk.WORD, font=("Arial", 10), bg="#f0f0f0",
                                fg="#333")
        self.log_text.pack(side=tk.LEFT, padx=(0, 10), pady=10, fill=tk.BOTH, expand=True)
        self.log_text.config(state=tk.DISABLED)

        scrollbar = tk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)

        button_frame = tk.Frame(frame, bg="#f4f4f9")
        button_frame.pack(pady=10, fill=tk.X)

        self.start_button = tk.Button(button_frame, text="Start", command=self.start_logging, font=("Arial", 12),
                                      bg="#4CAF50", fg="white", relief="raised", width=12)
        self.start_button.pack(side=tk.LEFT, padx=10, expand=True)

        self.stop_button = tk.Button(button_frame, text="Stop", command=self.stop_logging, font=("Arial", 12),
                                     bg="#F44336", fg="white", relief="raised", width=12, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=10, expand=True)

        self.status_label = tk.Label(frame, text="Status: Idle", font=("Arial", 12), bg="#f4f4f9", fg="red")
        self.status_label.pack(pady=10)

    def start_logging(self):
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.status_label.config(text="Status: Logging", fg="green")

        self.is_running = True
        self.message_count = 0
        threading.Thread(target=self.read_can_data, daemon=True).start()

    def stop_logging(self):
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_label.config(text="Status: Idle", fg="red")
        self.is_running = False
        self.save_data_to_csv()

    def read_can_data(self):
        while self.is_running:
            message1 = self.bus1.recv()  # Read from Sensor CAN bus

            if message1:
                decoded_data1 = self.decode_can_message(message1.arbitration_id, message1.data)
                if decoded_data1:
                    # Store data in dictionary
                    self.store_data_in_dict(message1.arbitration_id, decoded_data1)

            time.sleep(0.1)

    def decode_can_message(self, message_id, data):
        decoded_signals = {}
        for dbc in [self.sensor_dbc, self.critical_dbc]:
            if dbc:
                try:
                    message = dbc.get_message_by_frame_id(message_id)
                  
                    raw_data = bytes(data)
                    print("Message and id: ", message, ":", message_id,  "Raw data: ", raw_data)
                    decoded_data = message.decode(raw_data)
                    decoded_signals.update(decoded_data)
                    break
                except KeyError:
                    continue
        return decoded_signals






    ##STORE TO CSV FILE
    def store_data_in_dict(self, message_id, decoded_data):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for signal_name, signal_value in decoded_data.items():
            key = f"{message_id}:{signal_name}"
            if key not in self.data_dict:
                self.data_dict[key] = []  
            self.data_dict[key].append({"value": signal_value, "timestamp": timestamp})  
            
            
            
    
    def save_data_to_csv(self):
        try:
            with open('signals.csv', mode='w', newline='') as file:
                writer = csv.writer(file)

        
                header = list(self.data_dict.keys())
                print(f"Header: {header}")  # Debug print to see the columns

             
                writer.writerow(header)
                print(f"Header written to CSV.")  # Confirm header is written

            
                rows = []
                max_rows = max(len(values) for values in self.data_dict.values())  # Get the maximum row length

        
                print(f"Max rows: {max_rows}")

              
                for i in range(max_rows):
                    row = []  
                    for key in header:
                        try:
                        
                            value_time = self.data_dict[key][i]
                            value_timestamp = f"{value_time['value']}:{value_time['timestamp']}"
                            
                            ##LOOKS BETTER WITHOUT TIMESTAMP. CHANGE TIME FORMAT.
                            ##value_timestamp = f"{value_time['value']}"
                            
                            
                            row.append(value_timestamp)
                        except IndexError:
                        
                            row.append("")
                    rows.append(row)

           
                writer.writerows(rows)
                print(f"Rows written to CSV: {rows}")  

            print("Data saved to CSV successfully.")  
        except Exception as e:
            print(f"Error saving data to CSV: {e}")  


if __name__ == "__main__":
    root = tk.Tk()
    app = DynoLogger(root)
    root.mainloop()
