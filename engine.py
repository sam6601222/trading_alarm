import datetime
import pytz
import ctypes

class TradingEngine:
    """
    處理交易時段與 K 線收線時間判斷的核心引擎
    """
    def __init__(self):
        self.tz_tw = pytz.timezone('Asia/Taipei')
        self.tz_ny = pytz.timezone('America/New_York')
        
    def is_dst(self, dt):
        """判斷給定時間在紐約是否為夏令時間"""
        ny_dt = dt.astimezone(self.tz_ny)
        return ny_dt.dst() != datetime.timedelta(0)

    def get_us_open_time(self, dt):
        """根據夏令/冬令判斷美股開盤時間 (台灣時間)"""
        if self.is_dst(dt):
            return datetime.time(21, 30)
        else:
            return datetime.time(22, 30)

    def get_next_k_close(self, current_dt, timeframe_mins):
        """計算下一個 K 線收線時間"""
        # 取得總分鐘數
        total_minutes = current_dt.hour * 60 + current_dt.minute
        # 計算距離下一個收線點還差幾分鐘
        rem = total_minutes % timeframe_mins
        diff = timeframe_mins - rem
        
        next_dt = current_dt + datetime.timedelta(minutes=diff)
        return next_dt.replace(second=0, microsecond=0)

    def get_current_session(self, dt):
        """
        判斷當前處於什麼交易時段
        回傳: 'day', 'night', 'us_open', 'none'
        """
        time_now = dt.time()
        
        # 1. 台股日盤: 08:45 - 13:45
        if datetime.time(8, 45) <= time_now < datetime.time(13, 45):
            return 'day'
        
        # 2. 判斷美股開盤時間
        us_open_time = self.get_us_open_time(dt)
        
        # 3. 台股夜盤: 15:00 - 05:00 (跨日)
        # 夜盤開始到跨日前
        if datetime.time(15, 0) <= time_now:
            if time_now >= us_open_time:
                return 'us_open'
            return 'night'
            
        # 夜盤跨日後到 05:00
        if time_now < datetime.time(5, 0):
            return 'us_open' # 通常跨日後美股也是開著的，或是夜盤持續中
            
        return 'none'

    def set_keep_awake(self, keep_awake=True):
        """
        使用 Windows API 防止系統休眠
        ES_CONTINUOUS (0x80000000)
        ES_SYSTEM_REQUIRED (0x00000001)
        ES_AWAYMODE_REQUIRED (0x00000040)
        """
        if keep_awake:
            # 防止休眠但允許關閉螢幕: ES_CONTINUOUS | ES_SYSTEM_REQUIRED
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
        else:
            # 恢復正常狀態
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)

if __name__ == "__main__":
    # 簡單測試邏輯
    engine = TradingEngine()
    now = datetime.datetime.now(pytz.timezone('Asia/Taipei'))
    print(f"現在時間: {now}")
    print(f"交易時段: {engine.get_current_session(now)}")
    print(f"是否夏令: {engine.is_dst(now)}")
    print(f"美股開盤(台): {engine.get_us_open_time(now)}")
    print(f"下一個 5K: {engine.get_next_k_close(now, 5)}")
    print(f"下一個 60K: {engine.get_next_k_close(now, 60)}")
