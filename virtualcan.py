import can
import cantools
import random
import time

# Load the DBC file
DBC_FILE = "your_dbc_file.dbc"  # Replace with your actual DBC file
db = cantools.database.load_file(DBC_FILE)

# List available messages
print("\nAvailable Messages:")
for msg in db.messages:
    print(f"- {msg.name} (ID: {hex(msg.frame_id)})")

# User selects a message
msg_name = input("\nEnter message name to send: ")
try:
    message = db.get_message_by_name(msg_name)
except KeyError:
    print("Error: Message not found in DBC.")
    exit(1)

# List available signals
print("\nAvailable Signals in this Message:")
for sig in message.signals:
    print(f"- {sig.name} (Min: {sig.minimum}, Max: {sig.maximum})")

# User selects a signal
sig_name = input("\nEnter signal name to send: ")
if sig_name not in [s.name for s in message.signals]:
    print("Error: Signal not found in selected message.")
    exit(1)

# Initialize all signals with default values
default_values = {sig.name: 0 for sig in message.signals}

# Setup CAN bus
bus = can.interface.Bus(channel="vcan0", interface="socketcan")

print("\n🔁 Sending random values for signal:", sig_name)
print("Press CTRL+C to stop.\n")

try:
    while True:
        # Generate a random value for the selected signal
        signal_obj = next(s for s in message.signals if s.name == sig_name)
        min_val = signal_obj.minimum if signal_obj.minimum is not None else 0
        max_val = signal_obj.maximum if signal_obj.maximum is not None else 100
        random_value = random.randint(int(min_val), int(max_val))

        # Update only the selected signal, keep others as default
        default_values[sig_name] = random_value

        # Encode the CAN message
        data = message.encode(default_values)

        # Send the CAN message
        can_msg = can.Message(arbitration_id=message.frame_id, data=data, is_extended_id=False)
        bus.send(can_msg)

        print(f"📡 Sent: {sig_name} = {random_value}")

        time.sleep(1)  # Send every second

except KeyboardInterrupt:
    print("\n🚪 Stopping message transmission.")

