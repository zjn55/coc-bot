"""
COC自动捐兵 - 图形控制界面
"""
import subprocess
import threading
import time
import os
import sys
import tkinter as tk
from tkinter import scrolledtext
import cv2
import numpy as np

# ============ 配置 ============
ADB = r"D:\leidian\LDPlayer9\adb.exe"
EMULATOR_EXE = r"D:\leidian\LDPlayer9\dnplayer.exe"
DEVICE = "emulator-5554"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
THRESHOLD = 0.75


# ============ 图像工具（支持中文路径） ============
def cv_imread(path):
    return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)


def screencap():
    for attempt in range(5):
        try:
            r = subprocess.run([ADB, "-s", DEVICE, "shell", "screencap", "-p", "/sdcard/_s.png"],
                              capture_output=True, timeout=20)
            tmp = os.path.join(BASE_DIR, "_tmp.png")
            subprocess.run([ADB, "-s", DEVICE, "pull", "/sdcard/_s.png", tmp],
                           capture_output=True, timeout=20)
            return cv_imread(tmp)
        except Exception:
            time.sleep(2)
    raise Exception("screencap连续5次失败")


def adb_shell(cmd):
    return subprocess.run([ADB, "-s", DEVICE, "shell"] + cmd,
                          capture_output=True, text=True, timeout=15)


def tap(x, y):
    adb_shell(["input", "tap", str(x), str(y)])


def find(tpl_name, img=None, threshold=THRESHOLD):
    if img is None:
        img = screencap()
    tpl = cv_imread(os.path.join(TEMPLATE_DIR, tpl_name))
    h, w = tpl.shape[:2]
    res = cv2.matchTemplate(img, tpl, cv2.TM_CCOEFF_NORMED)
    _, maxv, _, maxl = cv2.minMaxLoc(res)
    if maxv >= threshold:
        return (maxl[0] + w // 2, maxl[1] + h // 2, maxv)
    return None


# ============ GUI ============
class App:
    def __init__(self, root):
        self.root = root
        root.title("COC自动捐兵")
        root.geometry("480x560")
        root.resizable(False, False)

        self.running = False

        # 模拟器安装目录输入
        tk.Label(root, text="雷电模拟器安装目录:", font=("微软雅黑", 10)).pack(anchor="w", padx=20)
        self.ld_dir = tk.StringVar(value=r"D:\leidian\LDPlayer9")
        tk.Entry(root, textvariable=self.ld_dir, font=("Consolas", 9), width=60).pack(padx=20)

        # 按钮
        self.btn_start = tk.Button(root, text="启动捐兵脚本", font=("微软雅黑", 14),
                                    width=20, height=2, command=self.on_start)
        self.btn_start.pack(pady=10)

        self.btn_stop = tk.Button(root, text="停止", font=("微软雅黑", 12),
                                   width=10, state=tk.DISABLED, command=self.on_stop)
        self.btn_stop.pack(pady=5)

        # 日志框
        self.log = scrolledtext.ScrolledText(root, font=("Consolas", 10),
                                              width=60, height=18, state=tk.DISABLED)
        self.log.pack(padx=10, pady=5)

    def log_msg(self, msg):
        self.root.after(0, self._append_log, msg)

    def _append_log(self, msg):
        self.log.config(state=tk.NORMAL)
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)
        self.log.config(state=tk.DISABLED)

    def on_start(self):
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.running = True
        threading.Thread(target=self.worker, daemon=True).start()

    def on_stop(self):
        self.running = False
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.log_msg("[已停止]")

    def _reset_btn(self):
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)

    # ============ 自动化流程 ============
    def still_in_donate_page(self):
        """检查是否还在捐兵页面"""
        try:
            img = screencap()
            return find("donate_page.png", img, threshold=0.7) is not None
        except:
            return False

    def is_card_grey(self, img, x, y):
        """判断卡片是否灰色，用平均饱和度判断"""
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        region = hsv[y-35:y, x-25:x+25]
        avg_s = region[:,:,1].mean()
        return avg_s < 30

    def do_donate(self):
        """循环捐兵，直到页面关闭"""
        row1_y = 300
        row2_y = 480
        row3_y = 730
        col_x = [855, 990, 1125, 1260, 1395, 1530, 1665]

        def find_first_colored(ys):
            """扫描整页，返回第一个彩色卡片坐标，没有返回None"""
            img = screencap()
            # 画取色框存debug图
            debug = img.copy()
            for x in col_x:
                for y in [row1_y, row2_y, row3_y]:
                    cv2.rectangle(debug, (x-25, y-35), (x+25, y), (0, 255, 0), 2)
            cv2.imencode('.png', debug)[1].tofile(os.path.join(BASE_DIR, "_debug_grid.png"))
            for x in col_x:
                for y in ys:
                    if not self.is_card_grey(img, x, y):
                        return (x, y)
            return None

        def click_card(x, y, clicks=5):
            while self.running:
                for _ in range(clicks):
                    tap(x, y)
                    time.sleep(0.3)
                if not self.still_in_donate_page():
                    self.log_msg("捐兵完成，页面已关闭")
                    return False
                time.sleep(0.5)
                img = screencap()
                if self.is_card_grey(img, x, y):
                    break
            return True

        # 兵种两行：看→滑→看→滑→看→滑→看→滑→看（滑4次）
        for i in range(5):
            if not self.running: return
            while self.running:
                pos = find_first_colored([row1_y, row2_y])
                if not pos: break
                self.log_msg(f"点兵种卡片 ({pos[0]},{pos[1]})")
                if not click_card(pos[0], pos[1], 5): return
            if i < 4:
                self.log_msg("兵种区域右滑...")
                adb_shell(["input", "swipe", "1500", "390", "892", "390", "500"])
                time.sleep(0.8)

        # 法术行：看→滑→看→滑→看→滑→看（滑3次）
        for i in range(4):
            if not self.running: return
            while self.running:
                pos = find_first_colored([row3_y])
                if not pos: break
                self.log_msg(f"点法术卡片 ({pos[0]},{pos[1]})")
                if not click_card(pos[0], pos[1], 3): return
            if i < 3:
                self.log_msg("法术区域右滑...")
                adb_shell(["input", "swipe", "1500", "730", "892", "730", "500"])
                time.sleep(0.8)

    def detect_scene(self, img):
        """判断当前场景，返回场景名"""
        if img is None:
            return "unknown"
        if find("reload.png", img, threshold=0.8):
            return "reload"
        if find("chat_open.png", img, threshold=0.8):
            return "chat_open"
        if find("chat_bubble.png", img, threshold=0.8):
            return "game_main"
        if find("coc_icon.png", img, threshold=0.8):
            return "emulator_desktop"
        return "unknown"

    def worker(self):
        global ADB, EMULATOR_EXE
        try:
            # 从输入框读取目录，自动拼文件名
            ld = self.ld_dir.get().strip().rstrip("\\/")
            ADB = os.path.join(ld, "adb.exe")
            EMULATOR_EXE = os.path.join(ld, "dnplayer.exe")

            # 检查路径是否存在
            if not os.path.isfile(ADB):
                self.log_msg(f"[错误] 找不到ADB: {ADB}")
                self.root.after(0, self._reset_btn)
                return
            if not os.path.isfile(EMULATOR_EXE):
                self.log_msg(f"[错误] 找不到模拟器: {EMULATOR_EXE}")
                self.root.after(0, self._reset_btn)
                return
            self.log_msg(f"ADB: {ADB}")
            self.log_msg(f"模拟器: {EMULATOR_EXE}")

            # 先检查adb是否连着
            r = subprocess.run([ADB, "devices"], capture_output=True, text=True)
            if DEVICE not in r.stdout:
                self.log_msg("=== 启动雷电模拟器 ===")
                subprocess.Popen([EMULATOR_EXE])
                for i in range(20):
                    if not self.running: return
                    r = subprocess.run([ADB, "devices"], capture_output=True, text=True)
                    if DEVICE in r.stdout:
                        self.log_msg("ADB已连接")
                        break
                    time.sleep(2)
                else:
                    self.log_msg("ADB连接超时！")
                    return
            else:
                self.log_msg("检测到模拟器已在运行")

            # ===== 状态机：导航到聊天界面 =====
            self.log_msg("判断当前场景...")
            in_chat = False
            while self.running and not in_chat:
                try:
                    img = screencap()
                except Exception as e:
                    self.log_msg(f"截图失败，重试... {e}")
                    time.sleep(3)
                    continue

                scene = self.detect_scene(img)
                self.log_msg(f"当前场景: {scene}")

                if scene == "reload":
                    pos = find("reload.png", img)
                    self.log_msg("  点重新载入游戏")
                    tap(pos[0], pos[1])
                    time.sleep(8)

                elif scene == "emulator_desktop":
                    pos = find("coc_icon.png", img)
                    self.log_msg(f"  点COC图标 ({pos[0]},{pos[1]-10})")
                    tap(pos[0], pos[1] - 10)
                    time.sleep(5)

                elif scene == "game_main":
                    pos = find("chat_bubble.png", img)
                    self.log_msg(f"  点聊天气泡 ({pos[0]},{pos[1]})")
                    tap(pos[0], pos[1])
                    time.sleep(2)

                elif scene == "chat_open":
                    self.log_msg("  聊天框已打开")
                    in_chat = True

                else:
                    self.log_msg("  场景未知！响铃警报...")
                    try:
                        import winsound
                        winsound.Beep(1200, 800)
                    except:
                        pass
                    time.sleep(3)

            if not self.running: return

            # ===== 确保在部落聊天标签 =====
            self.log_msg("检查是否在部落聊天...")
            time.sleep(1)
            img = screencap()
            clan = find("clan_tab.png", img)
            if clan:
                self.log_msg(f"  点部落聊天标签 ({clan[0]},{clan[1]})")
                tap(clan[0], clan[1])
                time.sleep(2)

            # ===== 循环监控增援按钮 =====
            self.log_msg("开始监控捐兵请求...")
            no_request_count = 0
            while self.running:
                try:
                    img = screencap()
                except:
                    time.sleep(3)
                    continue

                # 检查断线弹窗
                if find("reload.png", img, threshold=0.8):
                    self.log_msg("断线弹窗！点重新载入")
                    pos = find("reload.png", img)
                    tap(pos[0], pos[1])
                    time.sleep(10)
                    continue

                pos = find("reinforce_btn.png", img, threshold=0.8)
                if pos:
                    self.log_msg(f">>> 发现增援按钮！({pos[0]},{pos[1]})")
                    tap(pos[0], pos[1])
                    time.sleep(2)

                    # 等待增援资源页面加载（带断线检测）
                    self.log_msg("等待增援页面加载...")
                    page_ok = False
                    for i in range(10):
                        if not self.running: break
                        img2 = screencap()
                        if find("reload.png", img2, threshold=0.8):
                            self.log_msg("断线弹窗！点重新载入")
                            p = find("reload.png", img2)
                            tap(p[0], p[1])
                            time.sleep(10)
                            break
                        if find("donate_page.png", img2, threshold=0.8):
                            self.log_msg("增援页面已加载，开始捐兵")
                            time.sleep(1)
                            self.do_donate()
                            page_ok = True
                            break
                        time.sleep(1)
                    if not page_ok:
                        self.log_msg("增援页面加载超时！响铃警报...")
                        try:
                            import winsound
                            winsound.Beep(1200, 800)
                        except:
                            pass
                    no_request_count = 0
                    self.log_msg("捐兵结束，等2秒再继续...")
                    time.sleep(2)
                else:
                    # 没有增援按钮，检测感叹号
                    alert_top = find("alert_top.png", img, threshold=0.8)
                    alert_bottom = find("alert_bottom.png", img, threshold=0.8)
                    if alert_top:
                        self.log_msg(f">>> 发现上面感叹号！({alert_top[0]},{alert_top[1]})")
                        tap(alert_top[0], alert_top[1])
                        time.sleep(2)
                    elif alert_bottom:
                        self.log_msg(f">>> 发现下面感叹号！({alert_bottom[0]},{alert_bottom[1]})")
                        tap(alert_bottom[0], alert_bottom[1])
                        time.sleep(2)
                    else:
                        self.log_msg("无请求，10秒后再查...")
                        time.sleep(10)

        except Exception as e:
            self.log_msg(f"[错误] {e}")
        finally:
            self.root.after(0, lambda: self.btn_start.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.btn_stop.config(state=tk.DISABLED))


if __name__ == "__main__":
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 59273))
    except socket.error:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, "COC捐兵已经在运行了！", "提示", 0x40)
        sys.exit()
    root = tk.Tk()
    app = App(root)
    root.mainloop()
