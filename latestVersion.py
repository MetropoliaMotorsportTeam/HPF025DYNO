import tkinter as tk
from datetime import datetime
import cantools
import can
import threading
import time
import csv
from tkinter import messagebox
import queue


##INFLUXDB REMOVED

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
            # Load DBC files
            self.sensor_dbc = cantools.database.load_file("can1_HPF24.dbc")
            ##critical dbc uses "fixed" dbc, the og has issues it wont work BTN1 error
            self.critical_dbc = cantools.database.load_file("./dbcbackupedited/can2-HPF24.dbc")
            print("Both DBC files loaded successfully.")
            self.print_dbc_signals()
        except cantools.database.UnsupportedDatabaseFormatError as e:
            print(f"Error loading DBC file: {e}")
            self.sensor_dbc = None
            self.critical_dbc = None
            messagebox.showerror("Error", f"Error loading DBC file: {e}")
            self.root.quit()

        self.bus1 = None
        self.bus2 = None
        self.can1_status_label = None
        self.can2_status_label = None
        self.setup_ui()

        self.initialize_can_buses()

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

        # CAN bus status labels inside the UI box
        self.can_status_frame = tk.Frame(frame, bg="#f4f4f9")
        self.can_status_frame.pack(pady=10, fill=tk.X)

        self.can1_status_label = tk.Label(self.can_status_frame, text="CAN1: Not Connected", font=("Arial", 12), bg="#f4f4f9", fg="red")
        self.can1_status_label.pack(side=tk.LEFT, padx=10)

        self.can2_status_label = tk.Label(self.can_status_frame, text="CAN2: Not Connected", font=("Arial", 12), bg="#f4f4f9", fg="red")
        self.can2_status_label.pack(side=tk.LEFT, padx=10)

    def initialize_can_buses(self):
   
        self.bus1 = self.check_can_connection(0, 'can1', self.can1_status_label)

        self.bus2 = self.check_can_connection(1, 'can2', self.can2_status_label)


        threading.Thread(target=self.monitor_can_connections, daemon=True).start()

    def check_can_connection(self, channel, bus_name, status_label):
        try:
            bus = can.interface.Bus(channel=channel, interface='kvaser', bitrate=1000000)
            self.perform_bus_test(bus, bus_name, status_label)
            return bus  #
        except can.CanError as e:
            print(f"Error initializing {bus_name} bus: {e}")
            status_label.config(text=f"{bus_name.upper()}: Not Connected", fg="red")
            return None  

    def perform_bus_test(self, bus, bus_name, status_label):
        try:
            
            message = bus.recv(1) 
            if message:
                status_label.config(text=f"{bus_name.upper()}: Connected", fg="green")
                print(f"{bus_name} bus initialized successfully.")
            else:
                status_label.config(text=f"{bus_name.upper()}: Not Connected", fg="red")
                print(f"No messages received from {bus_name} bus. Marking as Not Connected.")
        except can.CanError:
            status_label.config(text=f"{bus_name.upper()}: Not Connected", fg="red")
            print(f"Error reading from {bus_name} bus. Marking as Not Connected.")

    def monitor_can_connections(self):
        while self.is_running:
            if self.bus1:
                self.check_can_connection_status(self.bus1, 'can1', self.can1_status_label)
            if self.bus2:
                self.check_can_connection_status(self.bus2, 'can2', self.can2_status_label)
            time.sleep(1)

    def check_can_connection_status(self, bus, bus_name, status_label):
        try:
            message = bus.recv(0)  
            if message:
                status_label.config(text=f"{bus_name.upper()}: Connected", fg="green")
        except can.CanError:
            status_label.config(text=f"{bus_name.upper()}: Not Connected", fg="red")

    def start_logging(self):
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.status_label.config(text="Status: Logging", fg="green")

        self.is_running = True
        self.message_count = 0

     
        if self.bus1:
            threading.Thread(target=self.read_can_data, args=(self.bus1,), daemon=True).start()


        if self.bus2:
            threading.Thread(target=self.read_can_data, args=(self.bus2,), daemon=True).start()

    def stop_logging(self):
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_label.config(text="Status: Idle", fg="red")
        self.is_running = False
        print("Total messages amount: ", self.message_count)
        self.save_data_to_csv()

    def read_can_data(self, bus):
        while self.is_running:
            message = bus.recv(timeout=0.1) 
            if message:
                decoded_data = self.decode_can_message(message.arbitration_id, message.data)
                if decoded_data:
                    self.store_data_in_dict(message.arbitration_id, decoded_data)
                    print(f"Logged message: {message.arbitration_id}, Data: {decoded_data}")
            else:
                print(f"No message received on bus.")

    def decode_can_message(self, message_id, data):
        decoded_signals = {}
        for dbc in [self.sensor_dbc, self.critical_dbc]:
            if dbc:
                try:
                    message = dbc.get_message_by_frame_id(message_id)
                    raw_data = bytes(data)
                    print("Message and id: ", message, ":", message_id, "Raw data: ", raw_data)
                    decoded_data = message.decode(raw_data)
                    decoded_signals.update(decoded_data)
                    break
                except KeyError:
                    continue
        return decoded_signals

    def store_data_in_dict(self, message_id, decoded_data):
        ##timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')  
        ##timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]  # Only keep milliseconds

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
                print(f"Header: {header}")  

                writer.writerow(header)
                print(f"Header written to CSV.")  
                rows = []
                max_rows = max(len(values) for values in self.data_dict.values())

                print(f"Max rows: {max_rows}")

                for i in range(max_rows):
                    row = []  
                    for key in header:
                        try:
                            value_time = self.data_dict[key][i]
                            value_timestamp = f"{value_time['value']}:{value_time['timestamp']}"
                            row.append(value_timestamp)
                        except IndexError:
                            row.append("")
                    rows.append(row)

                writer.writerows(rows)
                print("Data saved to CSV successfully.")
        except Exception as e:
            print(f"Error saving data to CSV: {e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = DynoLogger(root)
    root.mainloop()
