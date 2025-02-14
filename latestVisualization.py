import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import tkinter as tk
from tkinter import filedialog, messagebox

# Function to load CSV
def load_csv():
    file_path = filedialog.askopenfilename(title="Select CSV File", filetypes=[("CSV files", "*.csv")])
    if not file_path:
        return None
    try:
        ##df = pd.read_csv(file_path, delimiter=';', decimal=',')  # Ensure semicolon delimiter for consistency
        df = pd.read_csv(file_path, delimiter=';', decimal='.')

        print(df.head())  # Debug: Print first few rows
        print("Columns detected:", df.columns.tolist())  # Debug: Show column names
        return df
    except Exception as e:
        messagebox.showerror("Error", f"Could not load file:\n{e}")
        return None

# Load CSV
df = load_csv()
if df is None:
    exit()

# Convert column names to strings (prevents indexing issues)
df.columns = df.columns.astype(str)

# GUI Setup
root = tk.Tk()
root.title("Visualizer")

tk.Label(root, text="Select columns to plot:").pack()

# Create Listbox for column selection
listbox = tk.Listbox(root, selectmode=tk.MULTIPLE, height=min(10, len(df.columns)))
listbox.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

# Add all columns to listbox
for col in df.columns:
    listbox.insert(tk.END, col)

# Function to extract value and timestamp
def split_value_timestamp(column):
    """
    Splits the column values into numeric values and timestamps.
    Returns a tuple: (numeric values, timestamps)
    """
    try:
        split_data = df[column].astype(str).str.split(":", n=1, expand=True)
        values = pd.to_numeric(split_data[0], errors="coerce")  # First part is the value
        
        ##timestamps = pd.to_datetime(split_data[1], errors="coerce", format='%Y-%m-%d %H:%M:%S.%f', exact=False)  # Handle missing ms
        timestamps = pd.to_datetime(split_data[1], errors="coerce")

        
        return values, timestamps
    except Exception as e:
        messagebox.showerror("Error", f"Failed to process {column}: {e}")
        return None, None

# Function to plot selected columns with interactive zooming/panning
def plot_selected():
    selected_indices = listbox.curselection()
    selected_columns = [listbox.get(i) for i in selected_indices]

    if not selected_columns:
        messagebox.showwarning("No Selection", "Please select at least one column.")
        return

    fig, ax = plt.subplots(figsize=(10, 5))  # Create a subplot for interaction

    for col in selected_columns:
        values, timestamps = split_value_timestamp(col)

        if values is None or timestamps is None:
            continue  # Skip if processing failed

        # Debug: Print extracted values and timestamps
        print(f"\n--- Data for {col} ---")
        print("Extracted Numeric Values:", values.tolist())  # Print ALL values
        print("Extracted Timestamps:", timestamps.tolist())  # Print ALL timestamps

        ax.plot(timestamps, values, label=col, marker='o')

    # Formatting the X-axis for better readability
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())  # Auto spacing for dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d %H:%M:%S.%f"))  # Format with ms
    plt.xticks(rotation=45)  # Rotate x-axis labels for better visibility

    # Enable Grid, Title, and Legend
    ax.grid(True)
    ax.set_xlabel("Timestamp")
    ax.set_ylabel("Values")
    ax.set_title("Interactive Line Graph")
    ax.legend()

    plt.subplots_adjust(bottom=0.2, left=0.1, right=0.95, top=0.9)

    plt.show()

# Button
plot_button = tk.Button(root, text="Plot", command=plot_selected)
plot_button.pack(pady=5)

root.mainloop()
