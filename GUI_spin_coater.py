import sys
import json
import csv
import os
import time
import uuid  # Used for generating unique IDs, allowing recipes with duplicate names
from datetime import datetime

# ==========================================
# --- MAC OS FIX (MacOS Compatibility Fix) ---
# ==========================================
if sys.platform == 'darwin':
    try:
        import PyQt6

        # Try to automatically locate plugin paths
        library_dir = os.path.dirname(PyQt6.__file__)
        plugin_path = os.path.join(library_dir, 'Qt6', 'plugins')
        os.environ['QT_PLUGIN_PATH'] = plugin_path
        os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = os.path.join(plugin_path, 'platforms')
    except Exception as e:
        print(f"Warning: Could not apply Mac path fix: {e}")

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QPushButton, QLineEdit,
                             QListWidget, QSpinBox, QMessageBox, QGroupBox,
                             QFormLayout, QAbstractItemView, QComboBox,
                             QTabWidget, QInputDialog, QTableWidget, QTableWidgetItem,
                             QHeaderView, QListWidgetItem, QCheckBox)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QColor

# Try importing serial library (for connecting Arduino/Maxon)
try:
    import serial

    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False


# --- WORKER THREAD (Hardware Control) ---
class MotorWorker(QThread):
    progress_update = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, recipe_steps, loop_count=1, simulation_mode=True):
        super().__init__()
        self.recipe_steps = recipe_steps
        self.loop_count = loop_count
        self.simulation_mode = simulation_mode
        self.is_running = True

        # --- HARDWARE CONFIGURATION ---
        # Modify based on actual setup: Windows usually 'COM3', Mac usually '/dev/tty.usbmodem...'
        self.port = 'COM3'
        self.baud_rate = 9600
        self.ser = None

    def run(self):
        self.progress_update.emit("Initializing...")

        # 1. Connect Hardware
        if not self.simulation_mode:
            if not SERIAL_AVAILABLE:
                self.progress_update.emit("Error: pyserial not installed!")
                self.finished.emit()
                return
            try:
                self.ser = serial.Serial(self.port, self.baud_rate, timeout=1)
                time.sleep(2)  # Wait for Arduino to reset
                self.progress_update.emit(f"Connected to {self.port}")
            except Exception as e:
                self.progress_update.emit(f"Connection Error: {str(e)}")
                self.finished.emit()
                return

        total_loops = self.loop_count

        # 2. Execution Loop
        for current_loop in range(1, total_loops + 1):
            if not self.is_running: break

            for step in self.recipe_steps:
                if not self.is_running: break

                step_type = step.get('type', 'spin')
                name = step.get('name', 'Step')
                duration = step['duration']
                prefix = f"Loop {current_loop}/{total_loops} | {name}"

                # --- WAIT STEP ---
                if step_type == 'wait':
                    # Stop motor during wait
                    if not self.simulation_mode and self.ser:
                        self.ser.write(b"SPEED:0\n")

                    for t in range(duration, 0, -1):
                        if not self.is_running: break
                        self.progress_update.emit(f"{prefix}: WAITING {t}s...")
                        self.sleep(1)

                # --- SPIN STEP ---
                else:
                    speed = step['speed']
                    # Send command to Arduino
                    if not self.simulation_mode and self.ser:
                        # Protocol format: "SPEED:3000\n"
                        cmd = f"SPEED:{speed}\n"
                        self.ser.write(cmd.encode('utf-8'))

                    self.progress_update.emit(f"{prefix}: Ramping to {speed} RPM...")
                    self.sleep(1)  # Simulate acceleration time

                    for t in range(duration, 0, -1):
                        if not self.is_running: break
                        self.progress_update.emit(f"{prefix}: Spinning {speed} RPM ({t}s left)")
                        self.sleep(1)

        # 3. Finish and Stop
        if not self.simulation_mode and self.ser:
            self.ser.write(b"SPEED:0\n")
            self.ser.close()

        self.progress_update.emit("Process Complete.")
        self.finished.emit()

    def stop(self):
        self.is_running = False


# --- MAIN GUI WINDOW ---
class SpinCoaterGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lab SpinCoater - User & Shared System")
        self.resize(1100, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- TOP BLOCK: User & Configuration ---
        top_group = QGroupBox("Configuration")
        top_layout = QHBoxLayout()

        self.user_combo = QComboBox()
        self.user_combo.setPlaceholderText("Select Operator")
        # Refresh list when user changes
        self.user_combo.currentTextChanged.connect(self.refresh_recipe_list)

        top_layout.addWidget(QLabel("Operator:"))
        top_layout.addWidget(self.user_combo, 1)

        add_user_btn = QPushButton("Add User")
        add_user_btn.clicked.connect(self.add_new_user)
        top_layout.addWidget(add_user_btn)

        del_user_btn = QPushButton("Delete User")
        del_user_btn.setStyleSheet("color: red;")
        del_user_btn.clicked.connect(self.delete_user)
        top_layout.addWidget(del_user_btn)

        top_layout.addSpacing(20)

        # Simulation Mode Button
        self.sim_btn = QPushButton("Simulation Mode: ON")
        self.sim_btn.setCheckable(True)
        self.sim_btn.setChecked(True)
        self.sim_btn.setStyleSheet("background-color: orange; color: black; font-weight: bold;")
        self.sim_btn.clicked.connect(self.toggle_simulation)
        top_layout.addWidget(self.sim_btn)

        top_group.setLayout(top_layout)
        main_layout.addWidget(top_group)

        # --- TABS ---
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.operation_tab = QWidget()
        self.setup_operation_tab()
        self.tabs.addTab(self.operation_tab, "Control Panel")

        self.history_tab = QWidget()
        self.setup_history_tab()
        self.tabs.addTab(self.history_tab, "History Log")

        # Data Initialization
        self.saved_recipes = {}  # Storage structure: UUID -> Data
        self.users = []
        self.load_data()

    def toggle_simulation(self):
        if self.sim_btn.isChecked():
            self.sim_btn.setText("Simulation Mode: ON")
            self.sim_btn.setStyleSheet("background-color: orange; color: black; font-weight: bold;")
        else:
            self.sim_btn.setText("Simulation Mode: OFF (LIVE MOTOR)")
            self.sim_btn.setStyleSheet("background-color: red; color: white; font-weight: bold;")

    def setup_operation_tab(self):
        layout = QHBoxLayout(self.operation_tab)

        # --- LEFT: Recipe Library ---
        left_panel = QGroupBox("Recipe Library")
        left_layout = QVBoxLayout()

        self.recipe_list = QListWidget()
        self.recipe_list.setDragEnabled(True)
        self.recipe_list.itemClicked.connect(self.load_selected_recipe_details)
        left_layout.addWidget(self.recipe_list)

        form = QFormLayout()
        self.author_label = QLineEdit()
        self.author_label.setReadOnly(True)
        self.author_label.setPlaceholderText("(Auto-filled)")
        self.author_label.setStyleSheet("background-color: #f0f0f0; color: #555;")

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Recipe Name")

        self.speed_input = QSpinBox()
        self.speed_input.setRange(0, 100000)
        self.speed_input.setSuffix(" RPM")

        self.duration_input = QSpinBox()
        self.duration_input.setRange(0, 360000)
        self.duration_input.setSuffix(" s")

        self.accel_input = QSpinBox()
        self.accel_input.setRange(0, 100000)
        self.accel_input.setSuffix(" RPM/s")

        form.addRow("Name:", self.name_input)
        form.addRow("Author:", self.author_label)
        form.addRow("Speed:", self.speed_input)
        form.addRow("Time:", self.duration_input)
        form.addRow("Accel:", self.accel_input)
        left_layout.addLayout(form)

        # Share Option
        self.shared_checkbox = QCheckBox("Share this recipe (Visible to everyone)")
        self.shared_checkbox.setStyleSheet("color: blue; font-weight: bold;")
        left_layout.addWidget(self.shared_checkbox)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save Recipe")
        save_btn.clicked.connect(self.save_recipe)
        btn_layout.addWidget(save_btn)

        del_btn = QPushButton("Delete")
        del_btn.setStyleSheet("color: red;")
        del_btn.clicked.connect(self.delete_recipe)
        btn_layout.addWidget(del_btn)

        left_layout.addLayout(btn_layout)
        left_panel.setLayout(left_layout)
        layout.addWidget(left_panel, 1)

        # --- RIGHT: Execution Queue ---
        right_wrapper = QVBoxLayout()
        right_panel = QGroupBox("Execution Queue")
        right_layout = QVBoxLayout()

        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-weight: bold; font-size: 16px; color: blue;")
        right_layout.addWidget(self.status_label)

        self.queue_list = QListWidget()
        self.queue_list.setAcceptDrops(True)
        self.queue_list.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self.queue_list.setDefaultDropAction(Qt.DropAction.CopyAction)
        right_layout.addWidget(QLabel("Drag recipes here:"))
        right_layout.addWidget(self.queue_list)

        # Wait Functionality
        wait_layout = QHBoxLayout()
        self.wait_input = QSpinBox()
        self.wait_input.setRange(1, 360000)
        self.wait_input.setPrefix("Wait: ")
        self.wait_input.setSuffix(" s")
        add_wait_btn = QPushButton("Add Wait")
        add_wait_btn.clicked.connect(self.add_wait_step)
        wait_layout.addWidget(self.wait_input)
        wait_layout.addWidget(add_wait_btn)
        right_layout.addLayout(wait_layout)

        # Queue Control
        q_btns = QHBoxLayout()
        rem_btn = QPushButton("Remove Step")
        rem_btn.clicked.connect(self.remove_queue_step)
        clr_btn = QPushButton("Clear All")
        clr_btn.clicked.connect(self.queue_list.clear)
        q_btns.addWidget(rem_btn)
        q_btns.addWidget(clr_btn)
        right_layout.addLayout(q_btns)

        right_layout.addWidget(QLabel("--- Execution ---"))

        # Loop Control
        loop_layout = QHBoxLayout()
        loop_layout.addWidget(QLabel("Loop Count:"))
        self.loop_spin = QSpinBox()
        self.loop_spin.setRange(1, 1000)
        loop_layout.addWidget(self.loop_spin)
        right_layout.addLayout(loop_layout)

        self.start_btn = QPushButton("RUN PROCESS")
        self.start_btn.setStyleSheet("background-color: green; color: white; font-weight: bold; height: 50px;")
        self.start_btn.clicked.connect(self.start_process)
        right_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("EMERGENCY STOP")
        self.stop_btn.setStyleSheet("background-color: red; color: white; font-weight: bold;")
        self.stop_btn.clicked.connect(self.stop_process)
        self.stop_btn.setEnabled(False)
        right_layout.addWidget(self.stop_btn)

        right_panel.setLayout(right_layout)
        right_wrapper.addWidget(right_panel)
        layout.addLayout(right_wrapper, 1)

    def setup_history_tab(self):
        layout = QVBoxLayout(self.history_tab)
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(3)
        self.history_table.setHorizontalHeaderLabels(["Timestamp", "User", "Action"])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.history_table)

        h_btns = QHBoxLayout()
        ref_btn = QPushButton("Refresh")
        ref_btn.clicked.connect(self.load_history)
        h_btns.addWidget(ref_btn)

        clr_h_btn = QPushButton("Clear History")
        clr_h_btn.setStyleSheet("background-color: #ffcccc; color: red;")
        clr_h_btn.clicked.connect(self.clear_history)
        h_btns.addWidget(clr_h_btn)
        layout.addLayout(h_btns)

    # --- CORE LOGIC: Data Loading & Recipe List ---

    def load_data(self):
        if os.path.exists("users.json"):
            with open("users.json", "r") as f:
                self.users = json.load(f)
                self.user_combo.blockSignals(True)
                self.user_combo.addItems(self.users)
                self.user_combo.blockSignals(False)

        if os.path.exists("recipes.json"):
            with open("recipes.json", "r") as f:
                raw_data = json.load(f)
                # Data migration logic (Old format -> New UUID)
                self.saved_recipes = {}
                for key, val in raw_data.items():
                    if 'name' not in val:  # If old format
                        new_id = str(uuid.uuid4())
                        val['name'] = key
                        self.saved_recipes[new_id] = val
                    else:  # Already new format
                        self.saved_recipes[key] = val

        self.refresh_recipe_list()
        self.load_history()

    def refresh_recipe_list(self):
        """
        Core Function: Split recipes into 'My Private' and 'Shared' based on user permissions.
        """
        current_user = self.user_combo.currentText()
        self.recipe_list.clear()

        if not current_user: return

        my_private_recipes = []
        all_shared_recipes = []

        # Iterate through all data, classify by logic
        for r_id, data in self.saved_recipes.items():
            author = data.get('author', 'Unknown')
            is_shared = data.get('shared', False)

            # 1. If shared, put into shared pool (including my own shared ones)
            if is_shared:
                all_shared_recipes.append((r_id, data))

            # 2. If not shared and authored by me, put into private pool
            elif author == current_user:
                my_private_recipes.append((r_id, data))

            # 3. If not shared and authored by others -> Hide (Invisible)

        # Sort (A-Z)
        my_private_recipes.sort(key=lambda x: x[1]['name'])
        all_shared_recipes.sort(key=lambda x: x[1]['name'])

        # --- Render: My Private Section ---
        if my_private_recipes:
            header = QListWidgetItem(f"--- My Private Recipes ---")
            header.setBackground(QColor("#e3f2fd"))  # Light Blue
            header.setForeground(QColor("#1565c0"))  # Dark Blue Text
            header.setFlags(Qt.ItemFlag.NoItemFlags)  # Not selectable
            self.recipe_list.addItem(header)

            for r_id, data in my_private_recipes:
                item = QListWidgetItem(data['name'])
                item.setData(Qt.ItemDataRole.UserRole, r_id)  # Hidden ID
                self.recipe_list.addItem(item)

        # Spacer
        if my_private_recipes and all_shared_recipes:
            spacer = QListWidgetItem("")
            spacer.setFlags(Qt.ItemFlag.NoItemFlags)
            self.recipe_list.addItem(spacer)

        # --- Render: Shared Section ---
        if all_shared_recipes:
            header = QListWidgetItem("--- Shared Recipes (All Users) ---")
            header.setBackground(QColor("#fff3e0"))  # Light Orange
            header.setForeground(QColor("#ef6c00"))  # Dark Orange Text
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            self.recipe_list.addItem(header)

            for r_id, data in all_shared_recipes:
                display_name = data['name']
                # If authored by others, append author name
                if data['author'] != current_user:
                    display_name += f" ({data['author']})"

                item = QListWidgetItem(display_name)
                item.setData(Qt.ItemDataRole.UserRole, r_id)  # Hidden ID

                # Italic Style
                font = item.font()
                font.setItalic(True)
                item.setFont(font)
                self.recipe_list.addItem(item)

    def save_recipe(self):
        name = self.name_input.text()
        user = self.user_combo.currentText()
        if not user:
            QMessageBox.warning(self, "Error", "Please select a User first!")
            return
        if not name: return

        # Check if updating an existing recipe
        current_item = self.recipe_list.currentItem()
        recipe_id = None

        # Only consider update if selected item is not Header and name matches
        if current_item and not current_item.text().startswith("---"):
            # Note: Shared item might have " (Tom)" suffix, simple prefix check suffices
            # Or rely directly on UserRole ID
            selected_id = current_item.data(Qt.ItemDataRole.UserRole)
            if selected_id:
                # For simplicity here, if ID exists, treat as update intent
                recipe_id = selected_id

        # --- Permission Check ---
        if recipe_id and recipe_id in self.saved_recipes:
            existing_data = self.saved_recipes[recipe_id]
            author = existing_data.get('author')
            is_shared = existing_data.get('shared', False)

            # Rule: Can only modify if (I am author) OR (It is shared)
            if author != user and not is_shared:
                QMessageBox.warning(self, "Permission Denied",
                                    f"You cannot modify '{name}' because it belongs to {author} and is not shared.")
                return
        # -----------------------------

        # If new recipe, generate new UUID
        if not recipe_id:
            recipe_id = str(uuid.uuid4())

        # Save Data
        self.saved_recipes[recipe_id] = {
            "name": name,
            "speed": self.speed_input.value(),
            "duration": self.duration_input.value(),
            "acceleration": self.accel_input.value(),
            # If update, keep original author; if new, author is current user
            "author": user if recipe_id not in self.saved_recipes else self.saved_recipes[recipe_id]['author'],
            "shared": self.shared_checkbox.isChecked()
        }

        with open("recipes.json", "w") as f:
            json.dump(self.saved_recipes, f, indent=4)

        self.log_action(f"Saved: {name}")
        self.refresh_recipe_list()
        self.status_label.setText(f"Saved: {name}")

    def load_selected_recipe_details(self, item):
        recipe_id = item.data(Qt.ItemDataRole.UserRole)
        if not recipe_id: return

        data = self.saved_recipes.get(recipe_id)
        if data:
            self.name_input.setText(data['name'])
            self.speed_input.setValue(data['speed'])
            self.duration_input.setValue(data['duration'])
            self.accel_input.setValue(data['acceleration'])
            self.author_label.setText(data.get('author', 'Unknown'))
            self.shared_checkbox.setChecked(data.get('shared', False))

    def delete_recipe(self):
        item = self.recipe_list.currentItem()
        if not item: return

        recipe_id = item.data(Qt.ItemDataRole.UserRole)
        if not recipe_id: return

        data = self.saved_recipes.get(recipe_id)
        if not data: return

        current_user = self.user_combo.currentText()
        author = data.get('author')
        is_shared = data.get('shared', False)

        # --- Permission Check ---
        # Rule: Can only delete own recipes or shared ones
        if author != current_user and not is_shared:
            QMessageBox.warning(self, "Permission Denied",
                                "You cannot delete this recipe. It belongs to another user.")
            return

        if recipe_id in self.saved_recipes:
            name = self.saved_recipes[recipe_id]['name']
            del self.saved_recipes[recipe_id]
            with open("recipes.json", "w") as f: json.dump(self.saved_recipes, f)
            self.log_action(f"Deleted: {name}")
            self.refresh_recipe_list()
            self.name_input.clear()

    # --- Execution Logic ---

    def start_process(self):
        user = self.user_combo.currentText()
        if not user:
            QMessageBox.warning(self, "Error", "Select a User first!")
            return

        steps = []
        names = []

        # Iterate Queue
        for i in range(self.queue_list.count()):
            item = self.queue_list.item(i)
            # 1. Check if Wait Step
            data = item.data(Qt.ItemDataRole.UserRole)

            if data and 'type' in data and data['type'] == 'wait':
                steps.append(data)
                names.append("Wait")
            else:
                # 2. Is Recipe (Likely dragged in)
                # When dragging, Text is name. Best if we can get UserRole UUID
                # But PyQt default drag might lose UserRole, so we do a name lookup here
                item_text = item.text()
                # Remove possible " (Tom)" suffix
                clean_name = item_text.split(" (")[0]

                # Find matching recipe in library
                found_data = None
                for rid, rdata in self.saved_recipes.items():
                    if rdata['name'] == clean_name:
                        found_data = rdata
                        break

                if found_data:
                    d = found_data.copy()
                    d['type'] = 'spin'
                    steps.append(d)
                    names.append(clean_name)

        if not steps: return

        sim_mode = self.sim_btn.isChecked()
        mode_text = "[SIM]" if sim_mode else "[LIVE]"
        self.log_action(f"Started {mode_text}: {', '.join(names)}")

        self.worker = MotorWorker(steps, self.loop_spin.value(), simulation_mode=sim_mode)
        self.worker.progress_update.connect(self.status_label.setText)
        self.worker.finished.connect(self.on_finished)

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.worker.start()

    def stop_process(self):
        if hasattr(self, 'worker'): self.worker.stop()
        self.log_action("Emergency Stop")

    def on_finished(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.log_action("Process Finished")

    def add_wait_step(self):
        dur = self.wait_input.value()
        item = QListWidgetItem(f"--- WAIT {dur}s ---")
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setBackground(QColor("lightgray"))
        item.setData(Qt.ItemDataRole.UserRole, {'type': 'wait', 'name': 'Wait', 'duration': dur})
        self.queue_list.addItem(item)

    def remove_queue_step(self):
        row = self.queue_list.currentRow()
        if row >= 0: self.queue_list.takeItem(row)

    def add_new_user(self):
        name, ok = QInputDialog.getText(self, "Add User", "Name:")
        if ok and name and name not in self.users:
            self.users.append(name)
            self.user_combo.addItem(name)
            with open("users.json", "w") as f: json.dump(self.users, f)

    def delete_user(self):
        u = self.user_combo.currentText()
        if u and u in self.users:
            if QMessageBox.question(self, "Delete", f"Delete {u}?") == QMessageBox.StandardButton.Yes:
                self.users.remove(u)
                index = self.user_combo.findText(u)
                if index >= 0: self.user_combo.removeItem(index)
                with open("users.json", "w") as f:
                    json.dump(self.users, f)

    def log_action(self, action):
        t = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        u = self.user_combo.currentText() or "Unknown"
        file_exists = os.path.exists("history.csv")
        with open("history.csv", "a", newline="") as f:
            w = csv.writer(f)
            if not file_exists: w.writerow(["Timestamp", "User", "Action"])
            w.writerow([t, u, action])
        self.load_history()

    def load_history(self):
        self.history_table.setRowCount(0)
        if os.path.exists("history.csv"):
            with open("history.csv", "r") as f:
                r = csv.reader(f)
                next(r, None)
                for row in r:
                    if len(row) == 3:
                        i = self.history_table.rowCount()
                        self.history_table.insertRow(i)
                        for c, txt in enumerate(row):
                            self.history_table.setItem(i, c, QTableWidgetItem(txt))
                        self.history_table.scrollToBottom()

    def clear_history(self):
        if QMessageBox.question(self, "Clear", "Clear History?") == QMessageBox.StandardButton.Yes:
            with open("history.csv", "w") as f: f.write("Timestamp,User,Action\n")
            self.load_history()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SpinCoaterGUI()
    window.show()
    sys.exit(app.exec())