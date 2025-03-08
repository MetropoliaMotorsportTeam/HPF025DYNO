import tkinter as tk
from datetime import datetime
import cantools
import can
import threading
import time
import csv
import queue
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from tkinter import filedialog, messagebox
import pandas as pd

class DynoLogger:
    def __init__(self, root):
        self.root = root
        self.root.title("Dyno app")
        self.root.geometry("800x600")
        self.root.config(bg="#f4f4f9")
        self.is_running = False
        self.log_queue = queue.Queue()
        self.data_dict = {}
        self.selected_columns = []
        self.all_columns = []

        try:
            self.sensor_dbc = cantools.database.load_file("can1_HPF24.dbc")
            self.critical_dbc = cantools.database.load_file("./dbcbackupedited/can2-HPF24.dbc")
        except cantools.database.UnsupportedDatabaseFormatError as e:
            messagebox.showerror("Error", f"Error loading DBC file: {e}")
            self.root.quit()

        self.setup_ui()
        self.initialize_can_buses()
        self.root.after(50, self.process_log_queue)

    def setup_ui(self):
        frame = tk.Frame(self.root, bg="#f4f4f9")
        frame.pack(padx=20, pady=20, fill=tk.BOTH, expand=True)

        self.search_entry = tk.Entry(frame)
        self.search_entry.pack(pady=5)
        self.search_entry.bind("<KeyRelease>", self.search_columns)

        self.start_button = tk.Button(frame, text="Start", command=self.start_logging, bg="#4CAF50", fg="white")
        self.start_button.pack(pady=5)

        self.stop_button = tk.Button(frame, text="Stop & Save to CSV", command=self.stop_logging, bg="#F44336", fg="white", state=tk.DISABLED)
        self.stop_button.pack(pady=5)

        self.listbox = tk.Listbox(frame, selectmode=tk.MULTIPLE, height=10)
        self.listbox.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

        self.plot_button = tk.Button(frame, text="Live Plot", command=self.start_live_plot)
        self.plot_button.pack(pady=5)

    def search_columns(self, event):
        search_text = self.search_entry.get().lower()
        self.listbox.delete(0, tk.END)
        if not search_text:
            for key in self.all_columns:
                self.listbox.insert(tk.END, key)
        else:
            for key in self.all_columns:
                if search_text in key.lower():
                    self.listbox.insert(tk.END, key)

    def initialize_can_buses(self):
        self.bus1 = self.check_can_connection(0, 'can1')
        self.bus2 = self.check_can_connection(1, 'can2')

    def check_can_connection(self, channel, bus_name):
        try:
            ####return can.interface.Bus(channel="vcan0", interface='socketcan', bitrate=1000000)
            return can.interface.Bus(channel=channel, interface='kvaser', bitrate=1000000)
        except can.CanError:
            return None

    def start_logging(self):
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.is_running = True
        self.threads = []

        if self.bus1:
            t1 = threading.Thread(target=self.read_can_data, args=(self.bus1,), daemon=True)
            self.threads.append(t1)
            t1.start()
        if self.bus2:
            t2 = threading.Thread(target=self.read_can_data, args=(self.bus2,), daemon=True)
            self.threads.append(t2)
            t2.start()

    def stop_logging(self):
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.is_running = False
        for t in self.threads:
            t.join(timeout=1)

    def read_can_data(self, bus):
        while self.is_running:
            message = bus.recv(timeout=0.1)
            if message:
                decoded_data = self.decode_can_message(message.arbitration_id, message.data)
                if decoded_data:
                    timestamp = time.perf_counter() * 1000
                    self.log_queue.put((message.arbitration_id, decoded_data, timestamp))

    def process_log_queue(self):
        while not self.log_queue.empty():
            message_id, decoded_data, timestamp = self.log_queue.get()
            self.store_data_in_dict(message_id, decoded_data, timestamp)
        self.root.after(50, self.process_log_queue)

    def decode_can_message(self, message_id, data):
        for dbc in [self.sensor_dbc, self.critical_dbc]:
            if dbc:
                try:
                    message = dbc.get_message_by_frame_id(message_id)
                    return message.decode(bytes(data))
                except KeyError:
                    continue
        return {}

    def store_data_in_dict(self, message_id, decoded_data, timestamp):
        for signal_name, signal_value in decoded_data.items():
            key = f"{message_id}:{signal_name}"
            if key not in self.data_dict:
                self.data_dict[key] = []
                self.all_columns.append(key)
                self.listbox.insert(tk.END, key)
            self.data_dict[key].append({"value": signal_value, "timestamp": timestamp})

    def start_live_plot(self):
        selected_indices = self.listbox.curselection()
        self.selected_columns = [self.listbox.get(i) for i in selected_indices]
        if not self.selected_columns:
            messagebox.showwarning("No Selection", "Please select at least one column.")
            return
        self.fig, self.ax = plt.subplots(figsize=(12, 6))
        self.ani = animation.FuncAnimation(self.fig, self.update_plot, interval=200)
        plt.show()

    def update_plot(self, frame):
        self.ax.clear()
        for col in self.selected_columns:
            if col in self.data_dict:
                timestamps = [entry["timestamp"] for entry in self.data_dict[col]][-100:]
                values = [entry["value"] for entry in self.data_dict[col]][-100:]
                self.ax.plot(timestamps, values, label=col, marker='o', linestyle='-', markersize=3, alpha=0.7)
        self.ax.legend()
        self.ax.set_xlabel("Timestamp (ms)")
        self.ax.set_ylabel("Values")
        self.ax.set_title("Live Data Plot")
        self.ax.grid(True)
        self.fig.autofmt_xdate()

if __name__ == "__main__":
    root = tk.Tk()
    app = DynoLogger(root)
    root.mainloop()
