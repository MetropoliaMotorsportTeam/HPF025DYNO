import tkinter as tk
import cantools
from canlib import canlib, Frame
import threading
import time
from tkinter import messagebox
from influxdb_client import InfluxDBClient, Point, WritePrecision
import queue


class DynoDashboardApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Dyno Dashboard")
        self.root.geometry("600x500")
        self.root.config(bg="#f4f4f9")
        self.is_running = False
        self.message_count = 0
        self.log_queue = queue.Queue()

        # Load DBC files
        try:
            self.sensor_dbc = cantools.database.load_file("can1_HPF24.dbc")
            self.critical_dbc = cantools.database.load_file("can2-HPF24.dbc")
            print("Both DBC files loaded successfully.")
            self.print_dbc_signals()
        except cantools.database.UnsupportedDatabaseFormatError as e:
            print(f"Error loading DBC file: {e}")
            self.sensor_dbc = None
            self.critical_dbc = None
            messagebox.showerror("Error", f"Error loading DBC file: {e}")
            self.root.quit()

        # Initialize CAN channel (Kvaser)
        try:
            self.channel = canlib.openChannel(
                channel=0,  # Change this to match your Kvaser device's channel
                flags=canlib.Open.ACCEPT_VIRTUAL
            )
            self.channel.setBusOutputControl(canlib.Driver.NORMAL)
            self.channel.setBusParams(canlib.canBITRATE_500K)
            self.channel.busOn()
            print("Kvaser CAN channel initialized successfully.")
        except canlib.KvException as e:
            print(f"Error initializing Kvaser CAN channel: {e}")
            messagebox.showerror("Error", f"Error initializing Kvaser CAN channel: {e}")
            self.root.quit()

        # Connect to InfluxDB
        try:
            self.influxdb_client = InfluxDBClient(
                url="http://localhost:8086",
                token="YOUR_TOKEN",
                org="YOUR_ORG"
            )
            self.bucket = "dyno_data"
            print("Connected to InfluxDB successfully.")
        except Exception as e:
            print(f"Error connecting to InfluxDB: {e}")
            messagebox.showerror("Error", f"Error connecting to InfluxDB: {e}")
            self.root.quit()

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

        self.status_label = tk.Label(frame, text="Status: Idle", font=("Arial", 12), bg="#f4f4f9",
                                     fg="red")  # Red for idle
        self.status_label.pack(pady=10)

    def start_logging(self):
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.status_label.config(text="Status: Logging", fg="green")  # Green for logging

        self.is_running = True
        self.message_count = 0
        threading.Thread(target=self.read_can_data, daemon=True).start()
        threading.Thread(target=self.update_log, daemon=True).start()

    def stop_logging(self):
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_label.config(text="Status: Idle", fg="red")
        self.is_running = False

    def read_can_data(self):
        while self.is_running:
            try:
                frame = self.channel.read(timeout=100)  # 100 ms timeout
                decoded_data = self.decode_can_message(frame.id, frame.data)
                if decoded_data:
                    self.log_queue.put(f"Decoded data for message ID {frame.id}: {decoded_data}")
            except canlib.KvTimeout:
                continue

    def decode_can_message(self, message_id, data):
        decoded_signals = {}
        try:
            message = self.sensor_dbc.get_message_by_frame_id(message_id)
            if message:
                decoded_signals.update(message.decode(data))
        except KeyError:
            pass
        return decoded_signals

    def update_log(self):
        while self.is_running:
            try:
                message = self.log_queue.get(timeout=1)
                self.log_text.config(state=tk.NORMAL)
                self.log_text.insert(tk.END, message + '\n')
                self.log_text.yview(tk.END)
                self.log_text.config(state=tk.DISABLED)
            except queue.Empty:
                continue


if __name__ == "__main__":
    root = tk.Tk()
    app = DynoDashboardApp(root)
    root.mainloop()