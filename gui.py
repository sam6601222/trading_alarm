import sys
import os
import datetime
import pytz
import ctypes
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QComboBox, QSpinBox, 
                             QPushButton, QCheckBox, QSystemTrayIcon, QMenu, QFrame, QMessageBox)
from PyQt6.QtCore import QTimer, Qt, QSize
from PyQt6.QtGui import QIcon, QAction, QFont, QColor, QPalette

# Windows 單一實例檢查 (防止幽靈進程)
def check_single_instance():
    if os.name == 'nt':
        import ctypes
        kernel32 = ctypes.windll.kernel32
        mutex_name = "TradingAlarm_SingleInstance_Mutex_v2"
        mutex = kernel32.CreateMutexW(None, False, mutex_name)
        last_error = kernel32.GetLastError()
        if last_error == 183: # ERROR_ALREADY_EXISTS
            return False, mutex
        return True, mutex
    return True, None

# 嘗試導入 pygame 播放音效
try:
    import pygame
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.mixer.init()
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False

from engine import TradingEngine

class TradingAlarmApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.engine = TradingEngine()
        self.engine.set_keep_awake(True)
        
        self.next_5k = None
        self.next_60k = None
        self.is_5k_muted = False
        self.is_monitoring = True
        
        # 關閉偏好
        self.remember_close_choice = False
        self.last_close_choice = None # 'tray' or 'quit'
        
        self.init_ui()
        self.init_timer()
        self.init_tray()
        
    def init_ui(self):
        self.setWindowTitle("交易收K鬧鐘 v2.6")
        self.setFixedSize(450, 680)
        
        # 設定配色
        self.bg_color = "#121212"
        self.accent_color = "#FF8C00" # 鮮橘色
        self.card_bg = "#1E1E1E"
        self.text_color = "#FFFFFF"
        self.sub_text_color = "#AAAAAA"

        self.setStyleSheet(f"""
            QMainWindow {{ background-color: {self.bg_color}; }}
            QWidget {{ background-color: {self.bg_color}; color: {self.text_color}; font-family: 'Segoe UI', 'Microsoft JhengHei'; }}
            QLabel {{ background: transparent; }}
            QFrame#Card {{ background-color: {self.card_bg}; border: 1px solid #333333; border-radius: 10px; }}
            QPushButton#ActionBtn {{ background-color: {self.text_color}; color: {self.bg_color}; border-radius: 8px; font-weight: bold; font-size: 18px; padding: 10px; }}
            QPushButton#ActionBtn:checked {{ background-color: #444444; color: white; }}
            QComboBox, QSpinBox {{ background-color: {self.card_bg}; border: 1px solid {self.accent_color}; border-radius: 5px; padding: 5px; color: white; }}
            QSlider::handle:horizontal {{ background: {self.accent_color}; border-radius: 3px; width: 14px; margin: -5px 0; }}
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # 1. 頂部：現在時間
        time_container = QVBoxLayout()
        self.current_time_label = QLabel("--:--:--")
        self.current_time_label.setStyleSheet(f"font-size: 72px; font-weight: bold; color: {self.text_color};")
        self.current_time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.current_date_label = QLabel("載入中...")
        self.current_date_label.setStyleSheet(f"font-size: 18px; color: {self.accent_color}; letter-spacing: 2px;")
        self.current_date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        time_container.addWidget(self.current_time_label)
        time_container.addWidget(self.current_date_label)
        main_layout.addLayout(time_container)

        # 2. 中間：卡片區域
        cards_layout = QHBoxLayout()
        next_alarm_card = QFrame(); next_alarm_card.setObjectName("Card")
        next_alarm_layout = QVBoxLayout(next_alarm_card)
        next_alarm_layout.addWidget(QLabel("下次提醒"), alignment=Qt.AlignmentFlag.AlignCenter)
        self.next_alarm_val = QLabel("--:--:--"); self.next_alarm_val.setStyleSheet(f"font-size: 28px; font-weight: bold;")
        next_alarm_layout.addWidget(self.next_alarm_val, alignment=Qt.AlignmentFlag.AlignCenter)
        
        freq_card = QFrame(); freq_card.setObjectName("Card")
        freq_layout = QVBoxLayout(freq_card)
        freq_layout.addWidget(QLabel("目前頻率"), alignment=Qt.AlignmentFlag.AlignCenter)
        self.current_freq_val = QLabel("待機"); self.current_freq_val.setStyleSheet(f"font-size: 28px; font-weight: bold; color: {self.accent_color};")
        freq_layout.addWidget(self.current_freq_val, alignment=Qt.AlignmentFlag.AlignCenter)
        cards_layout.addWidget(next_alarm_card); cards_layout.addWidget(freq_card)
        main_layout.addLayout(cards_layout)

        # 3. 設定區
        settings_frame = QFrame(); settings_frame.setObjectName("Card")
        settings_layout = QVBoxLayout(settings_frame)
        
        # 音效選擇
        settings_layout.addWidget(QLabel("5分K 音效 (5M SOUND)"))
        self.sound_combo_5m = QComboBox(); settings_layout.addWidget(self.sound_combo_5m)
        settings_layout.addWidget(QLabel("60分K 音效 (60M SOUND)"))
        self.sound_combo_60m = QComboBox(); settings_layout.addWidget(self.sound_combo_60m)
        
        self.refresh_assets_btn = QPushButton("🔄 重新掃描 assets 資料夾")
        self.refresh_assets_btn.setStyleSheet("font-size: 11px; padding: 2px; color: #888888; border: 1px dashed #444444;")
        self.refresh_assets_btn.clicked.connect(self.load_sound_files)
        settings_layout.addWidget(self.refresh_assets_btn)
        
        # 音量
        vol_layout = QHBoxLayout()
        vol_layout.addWidget(QLabel("音量 VOLUME:"))
        from PyQt6.QtWidgets import QSlider
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100); self.vol_slider.setValue(80)
        vol_layout.addWidget(self.vol_slider); self.vol_label = QLabel("80%")
        self.vol_slider.valueChanged.connect(lambda v: self.vol_label.setText(f"{v}%"))
        vol_layout.addWidget(self.vol_label)
        settings_layout.addLayout(vol_layout)
        
        # 提前秒數
        adv_layout = QHBoxLayout()
        adv_layout.addWidget(QLabel("提前提醒 (秒):"))
        self.advance_secs = QSpinBox(); self.advance_secs.setRange(0, 59); self.advance_secs.setValue(10)
        adv_layout.addWidget(self.advance_secs)
        settings_layout.addLayout(adv_layout)
        main_layout.addWidget(settings_frame)

        # 4. 底部按鈕
        bottom_layout = QHBoxLayout()
        self.monitor_btn = QPushButton("監控中..."); self.monitor_btn.setObjectName("ActionBtn")
        self.monitor_btn.setCheckable(True); self.monitor_btn.setChecked(True)
        self.monitor_btn.clicked.connect(self.toggle_monitoring)
        bottom_layout.addWidget(self.monitor_btn, 3)
        
        self.test_sound_btn = QPushButton("測試音效")
        self.test_sound_btn.setFixedSize(90, 50); self.test_sound_btn.clicked.connect(lambda: self.play_alarm("test"))
        bottom_layout.addWidget(self.test_sound_btn)
        
        self.mute_btn = QPushButton("🔊"); self.mute_btn.setFixedSize(60, 50); self.mute_btn.setCheckable(True)
        self.mute_btn.clicked.connect(self.toggle_5k_mute)
        bottom_layout.addWidget(self.mute_btn)
        main_layout.addLayout(bottom_layout)

        # 5. 日誌
        self.console_label = QLabel("就緒中..."); self.console_label.setStyleSheet(f"color: {self.sub_text_color}; font-size: 12px;")
        main_layout.addWidget(self.console_label)

        self.load_sound_files()
        self.load_config()
        self.sound_combo_5m.currentIndexChanged.connect(self.save_config)
        self.sound_combo_60m.currentIndexChanged.connect(self.save_config)
        self.vol_slider.valueChanged.connect(self.save_config)
        self.advance_secs.valueChanged.connect(self.save_config)

    def load_config(self):
        import json
        config_path = "config.json"
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f: config = json.load(f)
                self.sound_combo_5m.blockSignals(True); self.sound_combo_60m.blockSignals(True)
                self.vol_slider.blockSignals(True); self.advance_secs.blockSignals(True)
                
                idx_5m = self.sound_combo_5m.findText(config.get("sound_5m", ""))
                if idx_5m >= 0: self.sound_combo_5m.setCurrentIndex(idx_5m)
                idx_60m = self.sound_combo_60m.findText(config.get("sound_60m", ""))
                if idx_60m >= 0: self.sound_combo_60m.setCurrentIndex(idx_60m)
                
                self.vol_slider.setValue(config.get("volume", 80)); self.vol_label.setText(f"{self.vol_slider.value()}%")
                self.advance_secs.setValue(config.get("advance_secs", 10))
                self.remember_close_choice = config.get("remember_close", False)
                self.last_close_choice = config.get("last_close_choice", None)

                self.sound_combo_5m.blockSignals(False); self.sound_combo_60m.blockSignals(False)
                self.vol_slider.blockSignals(False); self.advance_secs.blockSignals(False)
            except Exception as e: print(f"載入設定失敗: {e}")

    def save_config(self):
        import json
        config = {
            "sound_5m": self.sound_combo_5m.currentText(), "sound_60m": self.sound_combo_60m.currentText(),
            "volume": self.vol_slider.value(), "advance_secs": self.advance_secs.value(),
            "remember_close": self.remember_close_choice, "last_close_choice": self.last_close_choice
        }
        try:
            with open("config.json", "w", encoding="utf-8") as f: json.dump(config, f, ensure_ascii=False, indent=4)
        except Exception as e: print(f"儲存設定失敗: {e}")

    def load_sound_files(self):
        old_val_5m = self.sound_combo_5m.currentText(); old_val_60m = self.sound_combo_60m.currentText()
        self.sound_combo_5m.clear(); self.sound_combo_60m.clear()
        assets_dir = "assets"
        if not os.path.exists(assets_dir): os.makedirs(assets_dir)
        supported_exts = ('.wav', '.mp3', '.m4a', '.ogg', '.flac')
        files = [f for f in os.listdir(assets_dir) if f.lower().endswith(supported_exts)]
        if not files:
            self.sound_combo_5m.addItem("無檔案 (系統 Beep)"); self.sound_combo_60m.addItem("無檔案 (系統 Beep)")
            return
        for f in files: self.sound_combo_5m.addItem(f); self.sound_combo_60m.addItem(f)
        idx_5m = self.sound_combo_5m.findText(old_val_5m); idx_60m = self.sound_combo_60m.findText(old_val_60m)
        if idx_5m >= 0: self.sound_combo_5m.setCurrentIndex(idx_5m)
        if idx_60m >= 0: self.sound_combo_60m.setCurrentIndex(idx_60m)
        if hasattr(self, 'console_label'): self.console_label.setText(f"已掃描 assets。找到 {len(files)} 個相容音效檔。")

    def init_timer(self):
        self.refresh_timer = QTimer(self); self.refresh_timer.timeout.connect(self.update_all); self.refresh_timer.start(1000)

    def init_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        show_action = QAction("顯示視窗", self); show_action.triggered.connect(self.show)
        quit_action = QAction("【完全退出】", self); quit_action.triggered.connect(QApplication.instance().quit)
        tray_menu = QMenu(); tray_menu.addAction(show_action); tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu); self.tray_icon.show()

    def toggle_monitoring(self):
        self.is_monitoring = self.monitor_btn.isChecked()
        self.monitor_btn.setText("監控執行中..." if self.is_monitoring else "監控已暫停")
        self.console_label.setText("系統已恢復監控。" if self.is_monitoring else "系統監控已停用。")

    def toggle_5k_mute(self):
        self.is_5k_muted = self.mute_btn.isChecked()
        self.mute_btn.setText("🔇" if self.is_5k_muted else "🔊")
        self.console_label.setText("5分K 提醒已靜音。" if self.is_5k_muted else "5分K 提醒已恢復。")

    def update_all(self):
        now = datetime.datetime.now(self.engine.tz_tw)
        self.current_time_label.setText(now.strftime("%H:%M:%S"))
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        self.current_date_label.setText(now.strftime("%Y年%m月%d日") + f" {weekdays[now.weekday()]}")
        session = self.engine.get_current_session(now)
        main_freq = 5 if session in ['day', 'us_open'] else 60
        self.current_freq_val.setText(f"{main_freq} MIN" if session != 'none' else "休市中")
        self.next_5k = self.engine.get_next_k_close(now, 5); self.next_60k = self.engine.get_next_k_close(now, 60)
        next_t = self.next_5k if session in ['day', 'us_open'] else self.next_60k
        self.next_alarm_val.setText(next_t.strftime("%H:%M:%S"))
        if self.is_monitoring:
            advance = self.advance_secs.value()
            if int((self.next_5k - now).total_seconds()) == advance and session in ['day', 'us_open'] and not self.is_5k_muted:
                self.trigger_alert("5分K 收線提醒", "5m")
            if int((self.next_60k - now).total_seconds()) == advance and session in ['night', 'us_open']:
                self.trigger_alert("60分K 收線提醒", "60m")
            us_open_t = self.engine.get_us_open_time(now)
            opening_alert_t = (datetime.datetime.combine(now.date(), us_open_t) + datetime.timedelta(minutes=5)).time()
            if now.time().hour == opening_alert_t.hour and now.time().minute == opening_alert_t.minute and now.time().second == 0:
                self.trigger_alert("美股開盤 5 分鐘觀察點！", "5m")

    def trigger_alert(self, msg, alarm_type="5m"):
        self.log_event(msg); self.play_alarm(alarm_type)
        self.tray_icon.showMessage("交易鬧鐘", msg, QSystemTrayIcon.MessageIcon.Information, 5000)

    def log_event(self, msg):
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        self.console_label.setText(f"[{now_str}] {msg}")
        log_path = os.path.join("logs", "trading_log.txt")
        if not os.path.exists("logs"): os.makedirs("logs")
        with open(log_path, "a", encoding="utf-8") as f: f.write(f"[{datetime.datetime.now()}] {msg}\n")

    def play_alarm(self, alarm_type="5m"):
        volume = self.vol_slider.value() / 100.0
        filename = (self.sound_combo_5m if alarm_type != "60m" else self.sound_combo_60m).currentText()
        sound_path = os.path.join("assets", filename)
        if PYGAME_AVAILABLE and os.path.exists(sound_path) and "無檔案" not in filename:
            try:
                pygame.mixer.stop() # 停止當前聲音，防止疊加
                s = pygame.mixer.Sound(sound_path); s.set_volume(volume); s.play()
                return
            except Exception as e: print(f"播放失敗: {e}")
        import winsound
        idx = (self.sound_combo_5m if alarm_type != "60m" else self.sound_combo_60m).currentIndex()
        freqs = [800, 1200, 1500, 2000, 2500, 1000]
        winsound.Beep(freqs[idx % len(freqs)], 600)

    def closeEvent(self, event):
        if self.remember_close_choice:
            if self.last_close_choice == 'quit': QApplication.instance().quit()
            else: self.hide(); event.ignore()
            return

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("關閉交易鬧鐘")
        msg_box.setText("您想要如何處理此程式？\n\n【隱藏至托盤】：繼續在背景監控並報時\n【完全退出】：關閉所有監控與提醒")
        tray_btn = msg_box.addButton("隱藏至托盤", QMessageBox.ButtonRole.ActionRole)
        quit_btn = msg_box.addButton("完全退出", QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = msg_box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        
        cb = QCheckBox("下次不再詢問 (可在設定中重設)")
        msg_box.setCheckBox(cb)
        
        msg_box.exec()
        
        if msg_box.clickedButton() == tray_btn:
            if cb.isChecked(): self.remember_close_choice = True; self.last_close_choice = 'tray'; self.save_config()
            self.hide(); event.ignore()
        elif msg_box.clickedButton() == quit_btn:
            if cb.isChecked(): self.remember_close_choice = True; self.last_close_choice = 'quit'; self.save_config()
            QApplication.instance().quit()
        else:
            event.ignore()

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    success, mutex = check_single_instance()
    if not success:
        # 彈窗提醒已在執行
        app = QApplication(sys.argv)
        QMessageBox.warning(None, "重複啟動", "交易鬧鐘已經在執行中了！\n請檢查右下角系統小圖示 (托盤)。")
        sys.exit(0)
    
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    window = TradingAlarmApp()
    window.show()
    sys.exit(app.exec())
