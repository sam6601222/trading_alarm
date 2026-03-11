import sys
import os
import datetime
import pytz
import ctypes
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QComboBox, QSpinBox, 
                             QPushButton, QCheckBox, QSystemTrayIcon, QMenu, QFrame)
from PyQt6.QtCore import QTimer, Qt, QSize
from PyQt6.QtGui import QIcon, QAction, QFont, QColor, QPalette

# 嘗試導入 pygame 播放音效
try:
    import pygame
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
        
        self.init_ui()
        self.init_timer()
        self.init_tray()
        
    def init_ui(self):
        self.setWindowTitle("交易收K鬧鐘 v2.0")
        self.setFixedSize(450, 650)
        
        # 設定配色
        self.bg_color = "#121212"
        self.accent_color = "#FF8C00" # 鮮橘色
        self.card_bg = "#1E1E1E"
        self.text_color = "#FFFFFF"
        self.sub_text_color = "#AAAAAA"

        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {self.bg_color};
            }}
            QWidget {{
                background-color: {self.bg_color};
                color: {self.text_color};
                font-family: 'Segoe UI', 'Microsoft JhengHei';
            }}
            QLabel {{
                background: transparent;
            }}
            QFrame#Card {{
                background-color: {self.card_bg};
                border: 1px solid #333333;
                border-radius: 10px;
            }}
            QPushButton#ActionBtn {{
                background-color: {self.text_color};
                color: {self.bg_color};
                border-radius: 8px;
                font-weight: bold;
                font-size: 18px;
                padding: 10px;
            }}
            QPushButton#ActionBtn:checked {{
                background-color: #444444;
                color: white;
            }}
            QComboBox {{
                background-color: {self.card_bg};
                border: 1px solid {self.accent_color};
                border-radius: 5px;
                padding: 5px;
                color: white;
            }}
            QSpinBox {{
                background-color: {self.card_bg};
                border: 1px solid {self.accent_color};
                color: white;
                padding: 5px;
            }}
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # 1. 頂部：現在時間
        time_container = QVBoxLayout()
        self.current_time_label = QLabel("15:36:23")
        self.current_time_label.setStyleSheet(f"font-size: 72px; font-weight: bold; color: {self.text_color};")
        self.current_time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.current_date_label = QLabel("2026年03月11日 星期三")
        self.current_date_label.setStyleSheet(f"font-size: 18px; color: {self.accent_color}; letter-spacing: 2px;")
        self.current_date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        time_container.addWidget(self.current_time_label)
        time_container.addWidget(self.current_date_label)
        main_layout.addLayout(time_container)

        # 2. 中間：卡片區域 (下次提醒 | 目前頻率)
        cards_layout = QHBoxLayout()
        
        # 下次提醒卡片
        next_alarm_card = QFrame()
        next_alarm_card.setObjectName("Card")
        next_alarm_layout = QVBoxLayout(next_alarm_card)
        next_alarm_layout.addWidget(QLabel("下次提醒"), alignment=Qt.AlignmentFlag.AlignCenter)
        self.next_alarm_val = QLabel("16:00:00")
        self.next_alarm_val.setStyleSheet(f"font-size: 28px; font-weight: bold; color: {self.text_color};")
        next_alarm_layout.addWidget(self.next_alarm_val, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # 目前頻率卡片
        freq_card = QFrame()
        freq_card.setObjectName("Card")
        freq_layout = QVBoxLayout(freq_card)
        freq_layout.addWidget(QLabel("目前時段 / 週期"), alignment=Qt.AlignmentFlag.AlignCenter)
        self.current_freq_val = QLabel("60 MIN")
        self.current_freq_val.setStyleSheet(f"font-size: 28px; font-weight: bold; color: {self.accent_color};")
        freq_layout.addWidget(self.current_freq_val, alignment=Qt.AlignmentFlag.AlignCenter)
        
        cards_layout.addWidget(next_alarm_card)
        cards_layout.addWidget(freq_card)
        main_layout.addLayout(cards_layout)

        # 3. 手動頻率與設定區
        settings_frame = QFrame()
        settings_frame.setObjectName("Card")
        settings_layout = QVBoxLayout(settings_frame)
        
        # 盤中/盤後週期顯示
        cycle_layout = QHBoxLayout()
        cycle_layout.addWidget(QLabel("盤中 (08:45-13:45)"))
        cycle_layout.addWidget(QLabel("盤後 (15:00-05:00)"))
        settings_layout.addLayout(cycle_layout)
        
        cycle_val_layout = QHBoxLayout()
        self.day_cycle_label = QLabel("5 M")
        self.day_cycle_label.setStyleSheet(f"font-size: 24px; color: {self.text_color}; border-bottom: 2px solid {self.accent_color};")
        self.night_cycle_label = QLabel("60 M")
        self.night_cycle_label.setStyleSheet(f"font-size: 24px; color: {self.text_color}; border-bottom: 2px solid {self.accent_color};")
        cycle_val_layout.addWidget(self.day_cycle_label)
        cycle_val_layout.addWidget(self.night_cycle_label)
        settings_layout.addLayout(cycle_val_layout)
        
        # 音效選擇
        settings_layout.addSpacing(10)
        
        # 5分K 音效
        settings_layout.addWidget(QLabel("5分K 提醒音效 SELECT 5M SOUND"), alignment=Qt.AlignmentFlag.AlignLeft)
        self.sound_combo_5m = QComboBox()
        settings_layout.addWidget(self.sound_combo_5m)
        
        # 60分K 音效
        settings_layout.addSpacing(5)
        settings_layout.addWidget(QLabel("60分K 提醒音效 SELECT 60M SOUND"), alignment=Qt.AlignmentFlag.AlignLeft)
        self.sound_combo_60m = QComboBox()
        settings_layout.addWidget(self.sound_combo_60m)

        # 刷新按鈕
        self.refresh_assets_btn = QPushButton("🔄 重新掃描 assets 資料夾")
        self.refresh_assets_btn.setStyleSheet("font-size: 11px; padding: 2px; color: #888888; border: 1px dashed #444444;")
        self.refresh_assets_btn.clicked.connect(self.load_sound_files)
        settings_layout.addWidget(self.refresh_assets_btn)
        
        # 音量控制
        settings_layout.addSpacing(10)
        vol_layout = QHBoxLayout()
        vol_layout.addWidget(QLabel("提醒音量 VOLUME:"))
        from PyQt6.QtWidgets import QSlider
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(80)
        vol_layout.addWidget(self.vol_slider)
        self.vol_label = QLabel("80%")
        self.vol_slider.valueChanged.connect(lambda v: self.vol_label.setText(f"{v}%"))
        vol_layout.addWidget(self.vol_label)
        settings_layout.addLayout(vol_layout)
        
        self.load_sound_files()
        
        # 提前秒數
        adv_layout = QHBoxLayout()
        adv_layout.addWidget(QLabel("提前提醒 (秒):"))
        self.advance_secs = QSpinBox()
        self.advance_secs.setRange(0, 59)
        self.advance_secs.setValue(10)
        adv_layout.addWidget(self.advance_secs)
        settings_layout.addLayout(adv_layout)

        main_layout.addWidget(settings_frame)

        # 連結訊號以自動儲存設定
        self.sound_combo_5m.currentIndexChanged.connect(self.save_config)
        self.sound_combo_60m.currentIndexChanged.connect(self.save_config)
        self.vol_slider.valueChanged.connect(self.save_config)
        self.advance_secs.valueChanged.connect(self.save_config)

        # 載入現有設定
        self.load_config()

        # 4. 底部：啟動按鈕
        bottom_layout = QHBoxLayout()
        self.monitor_btn = QPushButton("啟動監控系統")
        self.monitor_btn.setObjectName("ActionBtn")
        self.monitor_btn.setCheckable(True)
        self.monitor_btn.setChecked(True)
        self.monitor_btn.clicked.connect(self.toggle_monitoring)
        
        bottom_layout.addWidget(self.monitor_btn, 3)
        
        self.test_sound_btn = QPushButton("測試音效")
        self.test_sound_btn.setFixedSize(90, 50)
        self.test_sound_btn.setStyleSheet(f"border-radius: 8px; border: 1px solid #333333; font-size: 14px;")
        self.test_sound_btn.clicked.connect(lambda: self.play_alarm("test"))
        bottom_layout.addWidget(self.test_sound_btn)
        
        self.mute_btn = QPushButton("🔊")
        self.mute_btn.setFixedSize(60, 50)
        self.mute_btn.setStyleSheet(f"border-radius: 8px; border: 1px solid #333333; font-size: 20px;")
        self.mute_btn.setCheckable(True)
        self.mute_btn.clicked.connect(self.toggle_5k_mute)
        bottom_layout.addWidget(self.mute_btn)
        
        main_layout.addLayout(bottom_layout)

        # 5. 系統日誌
        log_header = QHBoxLayout()
        log_header.addWidget(QLabel("系統日誌 SYSTEM LOGS"))
        self.clear_log_btn = QPushButton("清除")
        self.clear_log_btn.setStyleSheet("color: #666666; font-size: 12px; border: none;")
        self.clear_log_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_log_btn.clicked.connect(lambda: self.console_label.setText("日誌已清除。"))
        log_header.addWidget(self.clear_log_btn, alignment=Qt.AlignmentFlag.AlignRight)
        main_layout.addLayout(log_header)

        self.console_label = QLabel("系統就緒，點擊啟動開始監控...")
        self.console_label.setStyleSheet(f"color: {self.sub_text_color}; font-size: 12px;")
        self.console_label.setWordWrap(True)
        main_layout.addWidget(self.console_label)

    def load_config(self):
        """從 config.json 載入使用者設定"""
        import json
        config_path = "config.json"
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                
                # 暫時禁止訊號以防載入時觸發重複儲存
                self.sound_combo_5m.blockSignals(True)
                self.sound_combo_60m.blockSignals(True)
                self.vol_slider.blockSignals(True)
                self.advance_secs.blockSignals(True)

                # 套用設定
                idx_5m = self.sound_combo_5m.findText(config.get("sound_5m", ""))
                if idx_5m >= 0: self.sound_combo_5m.setCurrentIndex(idx_5m)
                
                idx_60m = self.sound_combo_60m.findText(config.get("sound_60m", ""))
                if idx_60m >= 0: self.sound_combo_60m.setCurrentIndex(idx_60m)
                
                self.vol_slider.setValue(config.get("volume", 80))
                self.vol_label.setText(f"{self.vol_slider.value()}%")
                self.advance_secs.setValue(config.get("advance_secs", 10))

                self.sound_combo_5m.blockSignals(False)
                self.sound_combo_60m.blockSignals(False)
                self.vol_slider.blockSignals(False)
                self.advance_secs.blockSignals(False)
            except Exception as e:
                print(f"載入設定失敗: {e}")

    def save_config(self):
        """儲存目前設定到 config.json"""
        import json
        config = {
            "sound_5m": self.sound_combo_5m.currentText(),
            "sound_60m": self.sound_combo_60m.currentText(),
            "volume": self.vol_slider.value(),
            "advance_secs": self.advance_secs.value()
        }
        try:
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"儲存設定失敗: {e}")

    def load_sound_files(self):
        """讀取 assets 資料夾下的音樂檔案"""
        old_val_5m = self.sound_combo_5m.currentText()
        old_val_60m = self.sound_combo_60m.currentText()

        self.sound_combo_5m.clear()
        self.sound_combo_60m.clear()
        assets_dir = "assets"
        if not os.path.exists(assets_dir):
            os.makedirs(assets_dir)
            
        # 掃描資料夾 (擴充支援格式)
        supported_exts = ('.wav', '.mp3', '.m4a', '.ogg', '.flac')
        files = [f for f in os.listdir(assets_dir) if f.lower().endswith(supported_exts)]
        
        if not files:
            self.sound_combo_5m.addItem("無檔案 (系統 Beep)")
            self.sound_combo_60m.addItem("無檔案 (系統 Beep)")
            return

        for f in files:
            self.sound_combo_5m.addItem(f)
            self.sound_combo_60m.addItem(f)
            
        # 嘗試還原剛才選過的 (如果刷新後還在的話)
        idx_5m = self.sound_combo_5m.findText(old_val_5m)
        if idx_5m >= 0: self.sound_combo_5m.setCurrentIndex(idx_5m)
        idx_60m = self.sound_combo_60m.findText(old_val_60m)
        if idx_60m >= 0: self.sound_combo_60m.setCurrentIndex(idx_60m)
        
        if hasattr(self, 'console_label'):
            self.console_label.setText(f"已掃描 assets。找到 {len(files)} 個相容音效檔。")

    def init_timer(self):
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.update_all)
        self.refresh_timer.start(1000)

    def init_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        show_action = QAction("顯示主視窗", self)
        show_action.triggered.connect(self.show)
        quit_action = QAction("完全結束", self)
        quit_action.triggered.connect(QApplication.instance().quit)
        tray_menu = QMenu()
        tray_menu.addAction(show_action)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def toggle_monitoring(self):
        self.is_monitoring = self.monitor_btn.isChecked()
        if self.is_monitoring:
            self.monitor_btn.setText("監控執行中...")
            self.console_label.setText("系統已恢復監控。")
        else:
            self.monitor_btn.setText("監控已暫停")
            self.console_label.setText("系統監控已手動關停。")

    def toggle_5k_mute(self):
        self.is_5k_muted = self.mute_btn.isChecked()
        if self.is_5k_muted:
            self.mute_btn.setText("🔇")
            self.console_label.setText("5K 提醒已靜音。")
        else:
            self.mute_btn.setText("🔊")
            self.console_label.setText("5K 提醒已恢復。")

    def update_all(self):
        # 1. 更新現在時間
        now = datetime.datetime.now(self.engine.tz_tw)
        self.current_time_label.setText(now.strftime("%H:%M:%S"))
        
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        date_str = now.strftime("%Y年%m月%d日") + f" {weekdays[now.weekday()]}"
        self.current_date_label.setText(date_str)

        # 2. 獲取交易狀態
        session = self.engine.get_current_session(now)
        
        # 3. 計算下次收 K
        main_freq = 5 if session in ['day', 'us_open'] else 60
        self.current_freq_val.setText(f"{main_freq} MIN" if session != 'none' else "休市中")
        
        self.next_5k = self.engine.get_next_k_close(now, 5)
        self.next_60k = self.engine.get_next_k_close(now, 60)
        
        next_t = self.next_5k if session in ['day', 'us_open'] else self.next_60k
        self.next_alarm_val.setText(next_t.strftime("%H:%M:%S"))

        # 4. 提醒邏輯
        if self.is_monitoring:
            advance = self.advance_secs.value()
            diff_5k = int((self.next_5k - now).total_seconds())
            diff_60k = int((self.next_60k - now).total_seconds())
            
            # 美股開盤 5 分鐘強提醒 (21:35 或 22:35)
            us_open_t = self.engine.get_us_open_time(now)
            opening_alert_t = (datetime.datetime.combine(now.date(), us_open_t) + datetime.timedelta(minutes=5)).time()
            if now.time().hour == opening_alert_t.hour and now.time().minute == opening_alert_t.minute and now.time().second == 0:
                self.trigger_alert("美股開盤 5 分鐘觀察點！", "5m")

            # 5K 提醒
            if session in ['day', 'us_open'] and not self.is_5k_muted:
                if diff_5k == advance:
                    self.trigger_alert("5分K 收線提醒", "5m")
            
            # 60K 提醒
            if session in ['night', 'us_open']:
                if diff_60k == advance:
                    self.trigger_alert("60分K 收線提醒", "60m")

    def trigger_alert(self, msg, alarm_type="5m"):
        self.log_event(msg)
        self.play_alarm(alarm_type)
        self.tray_icon.showMessage("交易鬧鐘", msg, QSystemTrayIcon.MessageIcon.Information, 5000)

    def log_event(self, msg):
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        self.console_label.setText(f"[{now_str}] {msg}")
        # 同時寫入檔案
        log_path = os.path.join("logs", "trading_log.txt")
        if not os.path.exists("logs"): os.makedirs("logs")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now()}] {msg}\n")

    def play_alarm(self, alarm_type="5m"):
        # 獲取音量並轉換為 0.0 - 1.0
        volume = self.vol_slider.value() / 100.0
        
        # 決定音效檔名
        if alarm_type == "5m":
            filename = self.sound_combo_5m.currentText()
        elif alarm_type == "60m":
            filename = self.sound_combo_60m.currentText()
        else: # test
            filename = self.sound_combo_5m.currentText()
            
        sound_path = os.path.join("assets", filename)
        
        if PYGAME_AVAILABLE and os.path.exists(sound_path) and "無檔案" not in filename:
            try:
                s = pygame.mixer.Sound(sound_path)
                s.set_volume(volume)
                s.play()
                return
            except Exception as e:
                print(f"播放失敗: {e}")
        
        # 備援音效
        import winsound
        idx = self.sound_combo_5m.currentIndex() if alarm_type != "60m" else self.sound_combo_60m.currentIndex()
        freqs = [800, 1200, 1500, 2000, 2500, 1000]
        # winsound 不支援音量控制，僅播放頻率
        winsound.Beep(freqs[idx % len(freqs)], 600)

    def closeEvent(self, event):
        if self.tray_icon.isVisible():
            self.hide()
            event.ignore()

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    window = TradingAlarmApp()
    window.show()
    sys.exit(app.exec())
