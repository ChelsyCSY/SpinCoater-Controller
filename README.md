# SpinCoater-Controller
Lab spincoater control and documentation
# Lab SpinCoater Controller

Control software for the custom laboratory Spin Coater. This project consists of a Python-based GUI for process management and Arduino firmware for driving the Maxon EPOS4 motor controller.

## 🚀 Features

* **GUI Control:** User-friendly interface built with **PyQt6**.
* **Recipe Management:** Create, save, and load spin protocols (e.g., "PM6", "ZnO"). Supports user-specific vs. shared recipes.
* **Data Logging:** Automatically records run history (Timestamp, User, Action) to `history.csv`.
* **Real-time Visualization:** Live plotting of target speed vs. time.
* **Hardware Bridge:** Interfaces with Maxon motors via Arduino (Analog Velocity Mode).

## 📂 Project Structure

```text
├── spin_coater.py       # Main GUI Application (Python)
├── maxon_bridge.ino     # Firmware for Arduino (Signal Bridge)
├── recipes.json         # Database of spin parameters (Auto-generated)
├── users.json           # User profile list (Auto-generated)
├── history.csv          # Usage logs
└── README.md            # This documentation
