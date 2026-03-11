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
        settings_layout.addWidget(QLabel("提醒音效選擇 ALERT SOUND"), alignment=Qt.AlignmentFlag.AlignLeft)
        self.sound_combo = QComboBox()
        self.sound_items = [
            "清脆雙音 (Classic Duo)", 
            "警急訊號 (Emergency)", 
            "柔和水滴 (Water Drop)", 
            "數位合成 (Digital)", 
            "鋼琴單音 (Piano)",
            "系統預設 (Beep)"
        ]
        self.sound_combo.addItems(self.sound_items)
        settings_layout.addWidget(self.sound_combo)
        
        # 提前秒數
        adv_layout = QHBoxLayout()
        adv_layout.addWidget(QLabel("提前提醒 (秒):"))
        self.advance_secs = QSpinBox()
        self.advance_secs.setRange(0, 59)
        self.advance_secs.setValue(10)
        adv_layout.addWidget(self.advance_secs)
        settings_layout.addLayout(adv_layout)

        main_layout.addWidget(settings_frame)

        # 4. 底部：啟動按鈕
        bottom_layout = QHBoxLayout()
        self.monitor_btn = QPushButton("啟動監控系統")
        self.monitor_btn.setObjectName("ActionBtn")
        self.monitor_btn.setCheckable(True)
        self.monitor_btn.setChecked(True)
        self.monitor_btn.clicked.connect(self.toggle_monitoring)
        
        self.mute_btn = QPushButton("🔊")
        self.mute_btn.setFixedSize(60, 50)
        self.mute_btn.setStyleSheet(f"border-radius: 8px; border: 1px solid #333333; font-size: 20px;")
        self.mute_btn.setCheckable(True)
        self.mute_btn.clicked.connect(self.toggle_5k_mute)
        
        bottom_layout.addWidget(self.monitor_btn, 4)
        bottom_layout.addWidget(self.mute_btn, 1)
        main_layout.addLayout(bottom_layout)

        # 5. 系統日誌
        log_header = QHBoxLayout()
        log_header.addWidget(QLabel("系統日誌 SYSTEM LOGS"))
        self.clear_log_btn = QPushButton("清除")
        self.clear_log_btn.setStyleSheet("color: #666666; font-size: 12px; border: none;")
        self.clear_log_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        log_header.addWidget(self.clear_log_btn, alignment=Qt.AlignmentFlag.AlignRight)
        main_layout.addLayout(log_header)

        self.console_label = QLabel("系統就緒，點擊啟動開始監控...")
        self.console_label.setStyleSheet(f"color: {self.sub_text_color}; font-size: 12px;")
        self.console_label.setWordWrap(True)
        main_layout.addWidget(self.console_label)

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
        # 根據時段選擇主頻率顯示
        main_freq = 5 if session in ['day', 'us_open'] else 60
        self.current_freq_val.setText(f"{main_freq} MIN" if session != 'none' else "休市中")
        
        self.next_5k = self.engine.get_next_k_close(now, 5)
        self.next_60k = self.engine.get_next_k_close(now, 60)
        
        # 判斷下一次最接近的提醒
        if session in ['day', 'us_open']:
            next_t = self.next_5k
        else:
            next_t = self.next_60k
        
        self.next_alarm_val.setText(next_t.strftime("%H:%M:%S"))

        # 4. 提醒邏輯
        if self.is_monitoring:
            advance = self.advance_secs.value()
            diff_5k = int((self.next_5k - now).total_seconds())
            diff_60k = int((self.next_60k - now).total_seconds())
            
            # 5K 提醒
            if session in ['day', 'us_open'] and not self.is_5k_muted:
                if diff_5k == advance:
                    self.trigger_alert("5分K 收線提醒")
            
            # 60K 提醒
            if session in ['night', 'us_open']:
                if diff_60k == advance:
                    self.trigger_alert("60分K 收線提醒")

    def trigger_alert(self, msg):
        self.log_event(msg)
        self.play_alarm()
        self.tray_icon.showMessage("交易鬧鐘", msg, QSystemTrayIcon.MessageIcon.Information, 5000)

    def log_event(self, msg):
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        self.console_label.setText(f"[{now_str}] {msg}")
        # 同時寫入檔案
        log_path = os.path.join("logs", "trading_log.txt")
        if not os.path.exists("logs"): os.makedirs("logs")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now()}] {msg}\n")

    def play_alarm(self):
        idx = self.sound_combo.currentIndex()
        if PYGAME_AVAILABLE:
            # 這裡可以根據 idx 映射到不同音頻檔
            # assets/s0.wav, assets/s1.wav...
            sound_path = f"assets/s{idx}.wav"
            if os.path.exists(sound_path):
                pygame.mixer.Sound(sound_path).play()
                return
        
        # 備援音效 (不同頻率識別)
        import winsound
        freqs = [800, 1200, 1500, 2000, 2500, 1000]
        winsound.Beep(freqs[idx], 600)

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
