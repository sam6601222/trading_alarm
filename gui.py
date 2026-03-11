import sys
import os
import datetime
import pytz
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QComboBox, QSpinBox, 
                             QPushButton, QCheckBox, QSystemTrayIcon, QMenu)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QIcon, QAction

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
        
        self.init_ui()
        self.init_timer()
        self.init_tray()
        
    def init_ui(self):
        self.setWindowTitle("交易收K鬧鐘 v1.0")
        self.setFixedSize(350, 450)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 狀態顯示區域
        self.status_label = QLabel("正在初始化...")
        self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        
        # 倒數計時區域
        self.timer_label_5k = QLabel("5K 下次收線: --:--:--")
        self.timer_label_60k = QLabel("60K 下次收線: --:--:--")
        layout.addWidget(self.timer_label_5k)
        layout.addWidget(self.timer_label_60k)
        
        # 設定區
        layout.addSpacing(20)
        layout.addWidget(QLabel("提前提醒秒數:"))
        self.advance_secs = QSpinBox()
        self.advance_secs.setRange(0, 59)
        self.advance_secs.setValue(10)
        layout.addWidget(self.advance_secs)
        
        layout.addWidget(QLabel("音效選擇:"))
        self.sound_combo = QComboBox()
        self.sound_items = ["內建鈴聲 1", "內建鈴聲 2", "警示音 1", "警示音 2", "短促音"]
        self.sound_combo.addItems(self.sound_items)
        layout.addWidget(self.sound_combo)
        
        # 暫停按鈕
        self.mute_5k_btn = QPushButton("暫停 5K 提醒")
        self.mute_5k_btn.setCheckable(True)
        self.mute_5k_btn.clicked.connect(self.toggle_5k_mute)
        layout.addWidget(self.mute_5k_btn)
        
        # 測試按鈕
        self.test_btn = QPushButton("測試音效")
        self.test_btn.clicked.connect(self.play_alarm)
        layout.addWidget(self.test_btn)
        
        layout.addStretch()
        
        # 版權/狀態
        author_label = QLabel("Antigravity Trading Tools")
        author_label.setStyleSheet("color: gray; font-size: 10px;")
        author_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(author_label)

    def init_timer(self):
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.update_status)
        self.refresh_timer.start(1000) # 每秒更新一次

    def init_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        # 這裡需要一個 icon 檔案，暫時先用預設或空白
        # self.tray_icon.setIcon(QIcon("icon.png")) 
        
        show_action = QAction("顯示視窗", self)
        show_action.triggered.connect(self.show)
        
        quit_action = QAction("結束程式", self)
        quit_action.triggered.connect(QApplication.instance().quit)
        
        tray_menu = QMenu()
        tray_menu.addAction(show_action)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        
    def toggle_5k_mute(self):
        self.is_5k_muted = self.mute_5k_btn.isChecked()
        if self.is_5k_muted:
            self.mute_5k_btn.setText("恢復 5K 提醒")
        else:
            self.mute_5k_btn.setText("暫停 5K 提醒")

    def update_status(self):
        now = datetime.datetime.now(self.engine.tz_tw)
        session = self.engine.get_current_session(now)
        
        session_names = {
            'day': '台股日盤',
            'night': '台股夜盤',
            'us_open': '美股開盤時段',
            'none': '非交易時段'
        }
        self.status_label.setText(f"目前時段: {session_names.get(session, '未知')}")
        
        # 更新收 K 時間
        self.next_5k = self.engine.get_next_k_close(now, 5)
        self.next_60k = self.engine.get_next_k_close(now, 60)
        
        diff_5k = (self.next_5k - now).total_seconds()
        diff_60k = (self.next_60k - now).total_seconds()
        
        self.timer_label_5k.setText(f"5K 下次收線: {self.next_5k.strftime('%H:%M:%S')} (倒數 {int(diff_5k)}s)")
        self.timer_label_60k.setText(f"60K 下次收線: {self.next_60k.strftime('%H:%M:%S')} (倒數 {int(diff_60k)}s)")
        
        # 檢查是否需要提醒
        advance = self.advance_secs.value()
        
        # 5K 提醒邏輯
        if session in ['day', 'us_open'] and not self.is_5k_muted:
            if int(diff_5k) == advance:
                self.trigger_alert("5 分 K 即將收線！")
                
        # 60K 提醒邏輯
        if session in ['night', 'us_open']:
             if int(diff_60k) == advance:
                self.trigger_alert("60 分 K 即將收線！")

    def trigger_alert(self, msg):
        self.log_event(msg)
        self.play_alarm()
        self.tray_icon.showMessage("交易鬧鐘", msg, QSystemTrayIcon.MessageIcon.Information, 5000)

    def log_event(self, msg):
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_path = os.path.join("logs", "trading_log.txt")
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[{now_str}] {msg}\n")
        except Exception as e:
            print(f"寫入日誌失敗: {e}")

    def play_alarm(self):
        # 根據選擇的 index 播放不同檔名 (預期放置在 assets/ 下)
        sound_idx = self.sound_combo.currentIndex()
        sound_files = ["chime1.wav", "chime2.wav", "alarm1.wav", "alarm2.wav", "short.wav"]
        sound_path = os.path.join("assets", sound_files[sound_idx])
        
        print(f"嘗試播放: {sound_path}")
        if PYGAME_AVAILABLE and os.path.exists(sound_path):
            try:
                pygame.mixer.Sound(sound_path).play()
            except Exception as e:
                print(f"播放失敗: {e}")
        else:
            # 備份方案：使用 Windows 系統音效
            import winsound
            winsound.Beep(1000, 500)

    def closeEvent(self, event):
        # 點擊關閉視窗時改為隱藏到系統托盤
        event.ignore()
        self.hide()
        self.tray_icon.showMessage("交易鬧鐘", "應用程式已縮小至托盤運行", QSystemTrayIcon.MessageIcon.Information, 2000)

if __name__ == "__main__":
    # 設定當前目錄為腳本所在目錄，確保路徑正確
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    window = TradingAlarmApp()
    window.show()
    sys.exit(app.exec())
