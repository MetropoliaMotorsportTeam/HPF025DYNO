import tkinter as tk
import cantools
import can
import threading
import time
from tkinter import messagebox
from influxdb_client import InfluxDBClient, Point, WritePrecision
import queue


##INSTALL ALL LIBRARIES, KVASER SDK AND INFLUXDB. 



##1 INFLUXDB -> wget https://download.influxdata.com/influxdb/releases/influxdb2-2.7.11-windows.zip -UseBasicParsing -OutFile influxdb2-2.7.11-windows.zip
#Expand-Archive .\influxdb2-2.7.11-windows.zip -DestinationPath 'C:\Program Files\InfluxData\influxdb\'

##2 INFLUXDB -> CD TO INSTALL LOCATION AND THEN INFLUXD TO RUN
##3 SETUP CORRECT INFLUXDB CRED AND TEST WITH CANKING





class DynoDashboardApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Dyno Dashboard")
        self.root.geometry("600x500")
        self.root.config(bg="#f4f4f9")
        self.is_running = False
        self.message_count = 0
        self.log_queue = queue.Queue()

        try:
            self.sensor_dbc = cantools.database.load_file("./dbcbackupedited/can1_HPF24.dbc")
            self.critical_dbc = cantools.database.load_file("./dbcbackupedited/can2-HPF24.dbc")
            print("Both DBC files loaded successfully.")
            self.print_dbc_signals()
        except cantools.database.UnsupportedDatabaseFormatError as e:
            print(f"Error loading DBC file: {e}")
            self.sensor_dbc = None
            self.critical_dbc = None
            messagebox.showerror("Error", f"Error loading DBC file: {e}")
            self.root.quit()

        #Initialize CAN bus for Kvaser devices (can1 for sensor, can2 for critical)
        try:
            self.bus1 = can.interface.Bus(channel=0, interface='kvaser')  # Sensor CAN bus using Kvaser device
            self.bus2 = can.interface.Bus(channel=1, interface='kvaser')  # Critical CAN bus using Kvaser device
        except can.CanError as e:
            print(f"Error initializing Kvaser CAN bus: {e}")
            messagebox.showerror("Error", f"Error initializing CAN bus: {e}")
            self.root.quit()

        # Connect to database (ensure correct info is used)
        try:
            self.influxdb_client = InfluxDBClient(
                url="http://localhost:8086",
                token="2o82E0x2SAV-vcb-2tPpNhfsE5XItn_qU8VDNcg--r9DeHHYqSZP8wWCFaaYsnfPOkx-uRuxNqzvg-hEpQwLVw==",
                org="metropolia"
            )
            self.bucket = "dyno_data"
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

        # Set up the UI
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

        title_label = tk.Label(frame, text="HPF025 Dyno", font=("Arial", 18, "bold"), bg="#f4f4f9", fg="#333")
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
        threading.Thread(target=self.read_can_data, daemon=True).start()  # Use real CAN data from Kvaser
        threading.Thread(target=self.update_log, daemon=True).start()  # Separate thread for UI updates

    def stop_logging(self):
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_label.config(text="Status: Idle", fg="red")
        self.is_running = False

    def read_can_data(self):
        batch_data = []  # To accumulate data for batch writing

        while self.is_running:
            # Read a message from the Kvaser CAN bus (can1 and can2)
            message1 = self.bus1.recv()  # Sensor CAN bus message
            message2 = self.bus2.recv()  # Critical CAN bus message

            if message1:
                decoded_data1 = self.decode_can_message(message1.arbitration_id, message1.data)
                if decoded_data1:
                    self.log_queue.put(f"Decoded data for message ID {message1.arbitration_id}: {decoded_data1}")
                    batch_data.append((message1.arbitration_id, decoded_data1))

            if message2:
                decoded_data2 = self.decode_can_message(message2.arbitration_id, message2.data)
                if decoded_data2:
                    self.log_queue.put(f"Decoded data for message ID {message2.arbitration_id}: {decoded_data2}")
                    batch_data.append((message2.arbitration_id, decoded_data2))

            # Write to InfluxDB if we have data
            if batch_data:
                self.write_to_influxdb(batch_data)
                batch_data.clear()

            self.message_count += 1
            self.update_status(self.message_count)

            # Sleep for a while before fetching next message
            time.sleep(0.1)  # Adjust the sleep time as needed for the reading frequency

    def decode_can_message(self, message_id, data):
        decoded_signals = {}

        # Attempt to decode using both DBC files
        for dbc in [self.sensor_dbc, self.critical_dbc]:
            if dbc:
                try:
                    message = dbc.get_message_by_frame_id(message_id)
                    raw_data = bytes(data)
                    decoded_data = message.decode(raw_data)
                    decoded_signals.update(decoded_data)
                    break  # Stop after successful decoding
                except KeyError:
                    continue  # Message ID not in this DBC

        if not decoded_signals:
            self.log_queue.put(f"Unknown message ID {message_id}, skipping.")
        return decoded_signals

    def write_to_influxdb(self, batch_data):
        try:
            with self.influxdb_client.write_api() as write_api:
                for message_id, decoded_data in batch_data:
                    for signal_name, signal_value in decoded_data.items():
                        point = Point("can_signals") \
                            .tag("message_id", message_id) \
                            .field(signal_name, signal_value) \
                            .time(time.time_ns(), WritePrecision.NS)
                        write_api.write(bucket=self.bucket, org="metropolia", record=point)
                self.log_queue.put("Batch write to InfluxDB successful.")
        except Exception as e:
            self.log_queue.put(f"Error writing to InfluxDB: {e}")

    def log(self, message, level="INFO"):
        self.log_queue.put(f"[{level}] {message}\n")

    def update_log(self):
        while self.is_running:
            try:
                message = self.log_queue.get(timeout=1)
                self.update_log_text(message)
            except queue.Empty:
                continue

    def update_log_text(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message)
        if len(self.log_text.get("1.0", tk.END).splitlines()) > 1000:
            self.log_text.delete("1.0", "2.0")
        self.log_text.yview(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def update_status(self, message_count):
        self.status_label.config(text=f"Status: Logging ({message_count} messages)", fg="green")


if __name__ == "__main__":
    root = tk.Tk()
    app = DynoDashboardApp(root)
    root.mainloop()