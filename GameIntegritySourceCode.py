import sys
import hashlib
import os
import subprocess
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton, 
                             QLabel, QFileDialog, QProgressBar, QTextEdit, 
                             QHBoxLayout, QMessageBox, QListWidget, QSplitter, QFrame, QLineEdit,QCheckBox)
from PyQt6.QtCore import QThread, pyqtSignal, Qt

# --- WORKER THREAD ---
class HashWorker(QThread):
    progress_update = pyqtSignal(int)
    log_update = pyqtSignal(str, str)
    finished_signal = pyqtSignal(dict)
    
    def __init__(self, folder_path, mode, md5_file_path=None):
        super().__init__()
        self.folder_path = folder_path
        self.mode = mode
        self.md5_file_path = md5_file_path
        self.is_running = True
    
    def stop(self):
        self.is_running = False

    def calculate_md5(self, file_path):
        hasher = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    if not self.is_running: return None
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return None

    def run(self):
        stats = {"ok": 0, "bad": 0, "missing": 0, "extra": 0}
        
        # --- GENERATE MODE ---
        if self.mode == "generate":
            generated_hashes = []
            files_to_hash = []
            for root, _, files in os.walk(self.folder_path):
                for f in files:
                    if f.endswith(".md5"): continue
                    files_to_hash.append(os.path.join(root, f))
            
            total_files = len(files_to_hash)
            for i, full_path in enumerate(files_to_hash):
                if not self.is_running: break
                rel_path = os.path.relpath(full_path, self.folder_path)
                file_hash = self.calculate_md5(full_path)
                if file_hash:
                    generated_hashes.append(f"{file_hash} *{rel_path}")
                    self.log_update.emit(f"HASHED: {rel_path}", "#B0BEC5")
                self.progress_update.emit(int(((i + 1) / total_files) * 100) if total_files > 0 else 100)
            stats["data"] = generated_hashes
            self.finished_signal.emit(stats)

        # --- VERIFY MODE ---
        elif self.mode == "verify":
            master_list = {}
            
            # 1. READ THE MD5 FILE (This was missing!)
            try:
                with open(self.md5_file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith(';'): continue
                        parts = line.split(None, 1)
                        if len(parts) == 2:
                            h, name = parts
                            # Normalize path to handle Windows/Linux slashes
                            clean_name = name.lstrip('*').replace('\\', os.sep).replace('/', os.sep)
                            master_list[clean_name] = h.lower()
            except Exception as e:
                self.log_update.emit(f"ERROR reading hash file: {e}", "red")
                return

            # 2. SCAN CURRENT FOLDER
            current_files = []
            for root, _, files in os.walk(self.folder_path):
                for f in files:
                    if f.endswith(".md5"): continue
                    # Get relative path
                    rel_path = os.path.relpath(os.path.join(root, f), self.folder_path)
                    current_files.append(rel_path)

            # 3. VERIFY FILES
            total_items = len(master_list)
            processed = 0
            
            for rel_path, expected_hash in master_list.items():
                if not self.is_running: break
                full_path = os.path.join(self.folder_path, rel_path)
                
                # Check if it exists
                if not os.path.exists(full_path):
                    self.log_update.emit(f"❌ MISSING: {rel_path}", "#FF5252")
                    stats["missing"] += 1
                else:
                    # Calculate Hash
                    current_hash = self.calculate_md5(full_path)
                    if current_hash == expected_hash:
                        self.log_update.emit(f"✅ OK: {rel_path}", "#66BB6A")
                        stats["ok"] += 1
                    else:
                        self.log_update.emit(f"⚠️ CORRUPT: {rel_path}", "#FFA726")
                        stats["bad"] += 1
                
                # REMOVE FROM EXTRA LIST (Important!)
                if rel_path in current_files:
                    current_files.remove(rel_path)
                
                processed += 1
                self.progress_update.emit(int((processed / total_items) * 100) if total_items > 0 else 100)

            # 4. REPORT EXTRAS
            stats["extra"] = len(current_files)
            for extra_file in current_files:
                self.log_update.emit(f"➕ NEW/UNKNOWN: {extra_file}", "#BA68C8")

            self.finished_signal.emit(stats)

class IntegrityDashboard(QWidget):
    def __init__(self):
        super().__init__()
        self.library_path = ""
        self.current_game_path = ""
        self.worker = None
        self.ensure_checksum_folder()
        self.initUI()
        self.all_messages = [] 


    def ensure_checksum_folder(self):
        # Correctly find path whether running as .py or .exe
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        
        self.checksum_dir = os.path.join(base_path, "Checksums")
        if not os.path.exists(self.checksum_dir):
            os.makedirs(self.checksum_dir)

    def filter_games(self):
        search_text = self.searchBar.text().lower()
        
        # Loop through every item in the QListWidget
        for i in range(self.game_list.count()):
            item = self.game_list.item(i)
            item_hidden = search_text not in item.text().lower()
            self.game_list.setRowHidden(i, item_hidden)

    def export_as(self):
        if not self.current_game_path:
            return
        
        content = self.log.toPlainText().strip()
        if not content:
            self.log.append("<span style='color:orange'>Nothing to export! Generate a log first.</span>")
            return
            
        game_name = os.path.basename(self.current_game_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{game_name}_log_{timestamp}.txt"
        
        try:
            content = self.log.toPlainText()
            with open(filename, 'w', encoding='utf-8') as file:
                file.write(content)
            self.log.append(f"<br><b style='color:cyan'>Log exported to {filename}</b>")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Could not save log: {e}")

    def load_external_hash(self):
        if not self.current_game_path:
            QMessageBox.warning(self, "No Selection", "Please select a game folder on the left first.")
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Master Hash File", "", "Hash Files (*.md5);;All Files (*)"
        )
        
        if file_path:
            self.log.clear()
            self.log.append(f"<b>Verifying against external hash:</b> {file_path}")
            # Trigger the verification using the external file
            self.toggle_controls(True)
            self.worker = HashWorker(self.current_game_path, "verify", file_path)
            self.worker.progress_update.connect(self.progress.setValue)
            self.worker.log_update.connect(lambda m, c: self.log.append(f'<span style="color:{c}">{m}</span>'))
            self.worker.finished_signal.connect(self.on_finished)
            self.worker.start()
    def handle_log_filtering(self, message, color):
        self.all_messages.append((message, color))
        is_summary = "📊" in message or "---" in message or "SUMMARY" in message
        if self.chk_errors_only.isChecked():
            # Added "➕" to the filter
            if "❌" in message or "⚠️" in message or "➕" in message or is_summary:
                self.log.append(f'<span style="color:{color}">{message}</span>')
        else:
            self.log.append(f'<span style="color:{color}">{message}</span>')

    def redraw_log(self):
        # Prevent redrawing while the worker is still running (to avoid lag)
        if self.worker and self.worker.isRunning():
            return
            
        self.log.clear()
        for message, color in self.all_messages:
            is_summary = "📊" in message or "---" in message or "SUMMARY" in message
            if self.chk_errors_only.isChecked():
                # Show only errors + the summary/lines
                if "❌" in message or "⚠️" in message or "➕" in message or is_summary:
                    self.log.append(f'<span style="color:{color}">{message}</span>')
            else:
                # Show everything
                self.log.append(f'<span style="color:{color}">{message}</span>')


    def initUI(self):
        self.setWindowTitle("Game Integrity Tool")
        self.resize(1100, 700)
        self.setStyleSheet("""
            QWidget { background-color: #121212; color: #E0E0E0; font-family: 'Segoe UI'; }
            QListWidget { background-color: #1E1E1E; border: 1px solid #333; outline: none; border-radius: 4px; }
            QListWidget::item { padding: 12px; border-bottom: 1px solid #252525; }
            QListWidget::item:selected { background-color: #2D2D2D; color: #00A2FF; border-left: 4px solid #00A2FF; }
            QPushButton { background-color: #2A2A2A; border: 1px solid #444; padding: 10px; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: #353535; }
            QPushButton#btn_ver[ready="true"] { background-color: #1B5E20; border: 1px solid #2E7D32; color: white; }
            QProgressBar { border: none; background: #222; height: 6px; text-align: center; border-radius: 3px; }
            QProgressBar::chunk { background: #00A2FF; border-radius: 3px; }
            QTextEdit { background: #080808; border: 1px solid #222; font-family: 'Consolas'; font-size: 11px; border-radius: 4px; }
            QLineEdit { background-color: #2A2A2A; border: 1px solid #444; padding: 10px;  border-radius: 4px;font-weight: bold;}
        """)

        layout = QVBoxLayout(self)
        
        # --- TOP BAR ---
        top_bar = QHBoxLayout()
        self.btn_lib = QPushButton("📂 Set Game Library Directory")
        self.btn_lib.clicked.connect(self.select_library)
        self.btn_open_folder = QPushButton("📁 Open Local Checksums")
        self.btn_open_folder.clicked.connect(self.open_checksum_folder)
        self.searchBar = QLineEdit()
        self.searchBar.setPlaceholderText("🔍 Search games...")
        self.searchBar.setFixedWidth(200)
        self.searchBar.setFixedHeight(38)
        self.searchBar.textChanged.connect(self.filter_games)
        top_bar.addWidget(self.btn_lib,0)
        top_bar.addWidget(self.btn_open_folder,0)
        top_bar.addWidget(self.searchBar,1)

        self.lbl_path = QLabel("Select your games folder to begin...")
        self.lbl_path.setStyleSheet("color: #777; margin-left: 10px;")
        top_bar.addWidget(self.lbl_path)
        layout.addLayout(top_bar,0)

        

        # --- SPLITTER ---
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.game_list = QListWidget()
        self.game_list.itemClicked.connect(self.update_game_selection)
        splitter.addWidget(self.game_list)

        # Right Panel
        right_panel = QFrame()
        right_vbox = QVBoxLayout(right_panel)
        
        self.lbl_title = QLabel("Select a Game")
        self.lbl_title.setStyleSheet("font-size: 24px; font-weight: bold; color: #00A2FF;")
        right_vbox.addWidget(self.lbl_title)

        ctrl_box = QHBoxLayout()
        self.btn_gen = QPushButton("🛠️ Create Hash")
        self.btn_gen.clicked.connect(self.action_generate)
        
        self.btn_ver = QPushButton("🔍 Verify Using Local Hash")
        self.btn_ver.setObjectName("btn_ver")
        self.btn_ver.clicked.connect(self.action_verify)
        
        self.btn_sum = QPushButton("🛠️ Select Hash")
        self.btn_sum.clicked.connect(self.load_external_hash)

        self.btn_stop = QPushButton("🛑 Stop")
        self.btn_stop.clicked.connect(self.stop_worker)

        self.btn_gen.setEnabled(False)
        self.btn_ver.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.btn_sum.setEnabled(False)
        
        ctrl_box.addWidget(self.btn_gen)
        ctrl_box.addWidget(self.btn_ver)
        ctrl_box.addWidget(self.btn_sum)
        ctrl_box.addWidget(self.btn_stop)
        right_vbox.addLayout(ctrl_box)

        self.progress = QProgressBar()
        right_vbox.addWidget(self.progress)

        # Log Header
        log_header = QHBoxLayout()

        log_header.addWidget(QLabel("ACTIVITY LOG"))
        btn_export = QPushButton("Export Log")
        btn_export.setFixedWidth(80)
        btn_export.setStyleSheet("font-size: 10px; padding: 2px;")
        btn_export.clicked.connect(self.export_as)
        btn_clear = QPushButton("Clear Log")
        btn_clear.setFixedWidth(80)
        btn_clear.setStyleSheet("font-size: 10px; padding: 2px;")
        btn_clear.clicked.connect(lambda: self.log.clear())
        self.chk_errors_only = QCheckBox("Errors Only")
        self.chk_errors_only.setStyleSheet("font-size: 10px;")
        self.chk_errors_only.stateChanged.connect(self.redraw_log)
        log_header.addWidget(self.chk_errors_only)
        log_header.addWidget(btn_export)
        log_header.addWidget(btn_clear)
        right_vbox.addLayout(log_header)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        right_vbox.addWidget(self.log)

        splitter.addWidget(right_panel)
        splitter.setSizes([280, 820])
        layout.addWidget(splitter,1)
        
        self.toggle_controls(False)


    def open_checksum_folder(self):
        if os.path.exists(self.checksum_dir):
            if sys.platform == 'win32':
                os.startfile(self.checksum_dir)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', self.checksum_dir])
            else:
                subprocess.Popen(['xdg-open', self.checksum_dir])

    def select_library(self):
        path = QFileDialog.getExistingDirectory(self, "Select Library")
        if path:
            self.library_path = path
            self.lbl_path.setText(path)
            self.refresh_list()

    def refresh_list(self):
        self.game_list.clear()
        try:
            dirs = [d for d in os.listdir(self.library_path) if os.path.isdir(os.path.join(self.library_path, d))]
            self.game_list.addItems(sorted(dirs))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not list directory: {e}")

    def update_game_selection(self):
        item = self.game_list.currentItem()
        if not item:
            return
        
        
        game_name = item.text()
        self.current_game_path = os.path.join(self.library_path, game_name)
        self.lbl_title.setText(game_name)
        md5_path = os.path.join(self.checksum_dir, f"{game_name}.md5")
        local_exists = os.path.exists(md5_path)
        
        md5_path = os.path.join(self.checksum_dir, f"{game_name}.md5")
        exists = os.path.exists(md5_path)
        

        self.btn_gen.setEnabled(True)
        self.btn_ver.setEnabled(local_exists)
        self.btn_stop.setEnabled(True)
        self.btn_sum.setEnabled(True)
        self.btn_ver.setProperty("ready", "true" if exists else "false")
        self.btn_ver.setText("🔍 Verify Using Local Hash" if exists else "🔍 (No Local Hash Found)")
        self.btn_ver.style().unpolish(self.btn_ver)
        self.btn_ver.style().polish(self.btn_ver)

    def toggle_controls(self, busy):
        if busy:
            self.btn_gen.setEnabled(False)
            self.btn_ver.setEnabled(False)
            self.btn_sum.setEnabled(False)
            self.btn_lib.setEnabled(False)
            self.game_list.setEnabled(False)
            self.chk_errors_only.setEnabled(False)
            self.btn_stop.setEnabled(True)
            self.progress.setValue(0)
        else:
            has_selection = bool(self.current_game_path)
            self.btn_gen.setEnabled(has_selection)
            self.btn_ver.setEnabled(has_selection)
            self.btn_sum.setEnabled(has_selection)
            self.chk_errors_only.setEnabled(True)
            self.btn_lib.setEnabled(True)
            self.game_list.setEnabled(True)
            self.btn_stop.setEnabled(False)

    def action_generate(self):
        self.toggle_controls(True)
        self.log.clear()
        self.worker = HashWorker(self.current_game_path, "generate")
        self.worker.progress_update.connect(self.progress.setValue)
        self.worker.log_update.connect(lambda m, c: self.log.append(f'<span style="color:{c}">{m}</span>'))
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()

    def run_verification(self, md5_path):
        self.all_messages = []
        
        self.toggle_controls(True)
        self.log.clear()
        
        self.worker = HashWorker(self.current_game_path, "verify", md5_path)
        self.worker.progress_update.connect(self.progress.setValue)

        self.worker.log_update.connect(self.handle_log_filtering)
        self.worker.finished_signal.connect(self.on_finished)

        self.worker.start()

    def action_verify(self):
        game_name = os.path.basename(self.current_game_path)
        md5_path = os.path.join(self.checksum_dir, f"{game_name}.md5")
        self.run_verification(md5_path)

    def load_external_hash(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Master Hash File", "", "Hash Files (*.md5)")
        if file_path:
            self.run_verification(file_path)

    def stop_worker(self):
        if self.worker: 
            self.worker.stop()
            self.log.append("<span style='color:orange'>Stopping worker...</span>")

    def on_finished(self, stats):
        if self.worker.mode == "generate" and "data" in stats:
            if self.worker.is_running:
                game_name = os.path.basename(self.current_game_path)
                save_path = os.path.join(self.checksum_dir, f"{game_name}.md5")
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(stats["data"]))
                self.log.append(f"<br><b style='color:#00E676'>Hash created for {game_name}</b>")
        
        if self.worker.mode == "verify" and self.worker.is_running:
            # 1. Define the summary lines
            summary_lines = [
                ("<br>" + "-"*30, "white"),
                ("<b>📊 VERIFICATION SUMMARY</b>", "white"),
                (f"✅ Healthy: {stats['ok']}", "#66BB6A"),
                (f"⚠️ Corrupt: {stats['bad']}", "#FFA726"),
                (f"❌ Missing: {stats['missing']}", "#FF5252"),
                (f"➕ Extra Files: {stats.get('extra', 0)}", "#BA68C8"),
                ("-"*30 + "<br>", "white")
            ]
            
            # 2. Add them to memory AND print them
            for msg, color in summary_lines:
                self.all_messages.append((msg, color))
                self.log.append(f'<span style="color:{color}">{msg}</span>')
            
            # 3. Show Pop-up
            total_errors = stats['bad'] + stats['missing']
            if total_errors > 0:
                QMessageBox.warning(self, "Verification Complete", 
                                    f"Found {total_errors} issues! Check the log for details.")
            else:
                QMessageBox.information(self, "Success", "All files verified successfully!")

        self.toggle_controls(False)
        self.update_game_selection()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = IntegrityDashboard()
    window.show()
    sys.exit(app.exec())