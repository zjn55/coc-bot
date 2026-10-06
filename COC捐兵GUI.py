"""
COC自动捐兵 - 图形控制界面
"""
import subprocess
import threading
import time
import os
import sys
import tkinter as tk
from tkinter import scrolledtext, ttk
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

        # 部署栏数量选择
        row = tk.Frame(root)
        row.pack(pady=5)
        tk.Label(row, text="兵种:", font=("微软雅黑", 10)).pack(side=tk.LEFT)
        self.cmb_troops = ttk.Combobox(row, width=3, values=[str(i) for i in range(0,8)], state="readonly")
        self.cmb_troops.set("1")
        self.cmb_troops.pack(side=tk.LEFT, padx=5)
        tk.Label(row, text="工程机", font=("微软雅黑", 10)).pack(side=tk.LEFT, padx=10)
        self.cmb_machine = ttk.Combobox(row, width=3, values=["0","1"], state="readonly")
        self.cmb_machine.set("1")
        self.cmb_machine.pack(side=tk.LEFT, padx=5)
        tk.Label(row, text="英雄:", font=("微软雅黑", 10)).pack(side=tk.LEFT, padx=10)
        self.cmb_heroes = ttk.Combobox(row, width=3, values=[str(i) for i in range(0,8)], state="readonly")
        self.cmb_heroes.set("4")
        self.cmb_heroes.pack(side=tk.LEFT, padx=5)
        tk.Label(row, text="法术:", font=("微软雅黑", 10)).pack(side=tk.LEFT, padx=10)
        self.cmb_spells = ttk.Combobox(row, width=3, values=[str(i) for i in range(0,8)], state="readonly")
        self.cmb_spells.set("1")
        self.cmb_spells.pack(side=tk.LEFT, padx=5)

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

    def do_raid(self):
        """打资源：6→10→4→3→2→6"""
        def recover():
            self.log_msg("等待超时，重新识别场景...")
            self.back_to_game_main()

        # 6→10: 点前往战斗
        self.log_msg("点前往战斗...")
        found = False
        for _ in range(15):
            if not self.running: return
            img = screencap()
            if find("reload.png", img, threshold=0.8):
                p = find("reload.png", img)
                tap(p[0], p[1])
                time.sleep(10)
                continue
            pos = find("find_match.png", img, threshold=0.8)
            if pos:
                time.sleep(0.5)
                tap(pos[0], pos[1])
                found = True
                break
            time.sleep(1)
        if not found:
            recover()
            return

        # 10: 选常规战
        self.log_msg("选常规战...")
        found = False
        for _ in range(15):
            if not self.running: return
            img = screencap()
            if find("reload.png", img, threshold=0.8):
                p = find("reload.png", img)
                tap(p[0], p[1])
                time.sleep(10)
                continue
            pos = find("normal_battle.png", img, threshold=0.8)
            if pos:
                time.sleep(0.5)
                tap(pos[0], pos[1])
                found = True
                break
            time.sleep(1)
        if not found:
            recover()
            return

        # 4: 点搜索对手
        self.log_msg("点搜索对手...")
        found = False
        for _ in range(15):
            if not self.running: return
            img = screencap()
            if find("reload.png", img, threshold=0.8):
                p = find("reload.png", img)
                tap(p[0], p[1])
                time.sleep(10)
                continue
            if find("battle_ready.png", img, threshold=0.8):
                found = True
                break
            pos = find("search_enemy.png", img, threshold=0.8)
            if pos:
                time.sleep(0.5)
                tap(pos[0], pos[1])
                time.sleep(1)
                img = screencap()
                confirm = find("confirm.png", img, threshold=0.8)
                if confirm:
                    time.sleep(0.5)
                    tap(confirm[0], confirm[1])
                found = True
                break
            time.sleep(1)
        if not found:
            recover()
            return

        # 等匹配完成，点进攻
        self.log_msg("等待匹配，点进攻...")
        for _ in range(60):
            if not self.running: return
            img = screencap()
            if find("reload.png", img, threshold=0.8):
                p = find("reload.png", img)
                tap(p[0], p[1])
                time.sleep(10)
                continue
            pos = find("battle_ready.png", img, threshold=0.8)
            if pos:
                time.sleep(1)
                self.log_msg(f"  点进攻 ({pos[0]},{pos[1]})")
                time.sleep(0.5)
                tap(pos[0], pos[1])
                # 等10秒看是否进入战斗
                time.sleep(1)
                entered = False
                for _ in range(10):
                    if not self.running: return
                    img = screencap()
                    if find("battle.png", img, threshold=0.8):
                        entered = True
                        break
                    time.sleep(1)
                if entered:
                    break
                else:
                    self.log_msg("未进入战斗，重新搜索...")
                    continue
            time.sleep(2)

        # 等进入战斗场景（检测到结束战斗按钮）
        self.log_msg("等待进入战斗场景...")
        for _ in range(30):
            if not self.running: return
            img = screencap()
            if find("battle.png", img, threshold=0.8):
                self.log_msg("已进入战斗场景")
                break
            time.sleep(1)
        time.sleep(2)

        # 3: 部署兵种和英雄
        self.log_msg("开始部署...")
        # 根据下拉框配置计算卡片位置
        n_troops = int(self.cmb_troops.get())
        n_machine = int(self.cmb_machine.get())
        n_heroes = int(self.cmb_heroes.get())
        n_spells = int(self.cmb_spells.get())

        start_x = 207
        y = 980
        same_gap = 150
        diff_gap = 160

        cards = []
        x = start_x
        sections = [("troop", n_troops), ("machine", n_machine), ("hero", n_heroes), ("spell", n_spells)]
        first = True
        for ctype, count in sections:
            if count == 0: continue
            if not first:
                x += diff_gap - same_gap  # 不同栏目之间补10像素
            for i in range(count):
                cards.append((x, y, ctype))
                x += same_gap
            first = False

        self.log_msg(f"卡片: 兵种{n_troops} 工程机{n_machine} 英雄{n_heroes} 法术{n_spells} 共{len(cards)}个")

        # 先往上拉动屏幕视角
        adb_shell(["input", "swipe", "960", "600", "960", "200", "500"])
        time.sleep(1)

        # 放兵位置：沿红线均匀取点
        deploy_start = (1140, 700)
        deploy_end = (1772, 236)
        n_points = 10
        deploy_points = []
        for i in range(n_points):
            t = i / (n_points - 1)
            px = int(deploy_start[0] + (deploy_end[0] - deploy_start[0]) * t)
            py = int(deploy_start[1] + (deploy_end[1] - deploy_start[1]) * t)
            deploy_points.append((px, py))

        # 判断卡片是否变灰
        def card_is_gray(cx, cy):
            img = screencap()
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            region = hsv[cy-20:cy+20, cx-20:cx+20]
            avg_s = region[:,:,1].mean()
            return avg_s < 30

        # 兵种：循环点，直到变灰（最多10轮）
        for cx, cy, ctype in cards:
            if ctype != "troop": continue
            for _ in range(10):
                if card_is_gray(cx, cy): break
                tap(cx, cy)
                time.sleep(0.1)
                for p in deploy_points:
                    adb_shell(["input", "swipe", str(p[0]), str(p[1]), str(p[0]), str(p[1]), "300"])
                    time.sleep(0.05)
                if not self.running: return

        # 工程机械：只放一次，第一个点
        for cx, cy, ctype in cards:
            if ctype != "machine": continue
            tap(cx, cy)
            time.sleep(0.1)
            p = deploy_points[0]
            adb_shell(["input", "swipe", str(p[0]), str(p[1]), str(p[0]), str(p[1]), "500"])
            time.sleep(0.1)

        # 英雄：点英雄→放→再点一次英雄取消选中
        for cx, cy, ctype in cards:
            if ctype != "hero": continue
            tap(cx, cy)
            time.sleep(0.1)
            p = deploy_points[0]
            tap(p[0], p[1])
            time.sleep(0.1)
            tap(cx, cy)
            time.sleep(0.1)

        # 法术：隔一个点放，没灰就循环（最多5轮）
        for cx, cy, ctype in cards:
            if ctype != "spell": continue
            for _ in range(5):
                if card_is_gray(cx, cy): break
                tap(cx, cy)
                time.sleep(0.1)
                for i in range(0, n_points, 2):
                    p = deploy_points[i]
                    tap(p[0], p[1])
                    time.sleep(0.1)
                if not self.running: return

        # 等战斗结束：60秒内每7秒检测一次，超时点放弃
        self.log_msg("等待战斗结束（60秒超时）...")
        ended = False
        for i in range(60):
            if not self.running: return
            if i % 7 == 0:
                img = screencap()
                self.log_msg(f"等待战斗结束... 剩余{60-i}秒")
                # 1.奖励弹窗
                reward_pos = find("选择一项奖励.png", img, threshold=0.8)
                if reward_pos:
                    self.log_msg("发现奖励弹窗，点下方")
                    tap(reward_pos[0], reward_pos[1] + 200)
                    time.sleep(1)
                    continue
                # 2.回营
                if find("battle_result.png", img, threshold=0.8):
                    self.log_msg("战斗结束，回营")
                    pos = find("battle_result.png", img)
                    time.sleep(0.5)
                    tap(pos[0], pos[1])
                    ended = True
                    break
                # 3.断线
                if find("reload.png", img, threshold=0.8):
                    p = find("reload.png", img)
                    tap(p[0], p[1])
                    time.sleep(10)
                    continue
            time.sleep(1)

        if not ended and self.running:
            self.log_msg("超时，点放弃...")
            for _ in range(15):
                if not self.running: return
                img = screencap()
                # 1.奖励
                reward_pos = find("选择一项奖励.png", img, threshold=0.8)
                if reward_pos:
                    tap(reward_pos[0], reward_pos[1] + 200)
                    time.sleep(1)
                    continue
                # 2.断线
                if find("reload.png", img, threshold=0.8):
                    p = find("reload.png", img)
                    tap(p[0], p[1])
                    time.sleep(10)
                    continue
                # 3.回营
                if find("battle_result.png", img, threshold=0.8):
                    pos = find("battle_result.png", img)
                    tap(pos[0], pos[1])
                    break
                # 4.结束战斗
                end_pos = find("battle.png", img, threshold=0.8)
                if end_pos:
                    tap(end_pos[0], end_pos[1])
                    time.sleep(1)
                    continue
                # 5.放弃
                cancel_pos = find("放弃.png", img, threshold=0.8)
                if cancel_pos:
                    tap(cancel_pos[0], cancel_pos[1])
                    time.sleep(1)
                    for _ in range(5):
                        if not self.running: return
                        img = screencap()
                        confirm_pos = find("confirm.png", img, threshold=0.8)
                        if confirm_pos:
                            tap(confirm_pos[0], confirm_pos[1])
                            time.sleep(2)
                            break
                        time.sleep(1)
                    break
                time.sleep(1)

    def detect_scene(self, img):
        """判断当前场景，返回场景名"""
        if img is None:
            return "unknown"
        if find("reload.png", img, threshold=0.8):
            return "reload"
        if find("battle_result.png", img, threshold=0.8):
            return "battle_result"
        if find("battle.png", img, threshold=0.8):
            return "battle"
        if find("battle_ready.png", img, threshold=0.8):
            return "battle_ready"
        if find("donate_page.png", img, threshold=0.8):
            return "donate_page"
        if find("normal_battle.png", img, threshold=0.8) or find("ranked_battle.png", img, threshold=0.8):
            return "mode_select"
        if find("chat_open.png", img, threshold=0.8):
            return "chat_open"
        if find("chat_bubble.png", img, threshold=0.8):
            return "game_main"
        if find("coc_icon.png", img, threshold=0.8):
            return "emulator_desktop"
        return "unknown"

    def back_to_game_main(self):
        """从任何场景回到游戏主界面(6号)"""
        unknown_time = 0
        for _ in range(15):
            if not self.running: return
            img = screencap()
            scene = self.detect_scene(img)
            self.log_msg(f"当前场景: {scene}")

            if scene == "unknown":
                unknown_time += 2
                if unknown_time >= 20:
                    self.log_msg("未知场景持续20秒，停止脚本")
                    self.running = False
                    return
            else:
                unknown_time = 0

            if scene == "game_main":
                return
            elif scene == "reload":
                pos = find("reload.png", img)
                self.log_msg("  点重新载入游戏")
                tap(pos[0], pos[1])
                time.sleep(8)
            elif scene == "battle_result":
                pos = find("battle_result.png", img)
                self.log_msg(f"  点回营 ({pos[0]},{pos[1]})")
                tap(pos[0], pos[1])
                time.sleep(3)
            elif scene == "battle":
                pos = find("battle.png", img)
                self.log_msg(f"  点结束战斗 ({pos[0]},{pos[1]})")
                tap(pos[0], pos[1])
                time.sleep(3)
            elif scene == "battle_ready":
                pos = find("battle_ready.png", img, threshold=0.8)
                if pos:
                    self.log_msg(f"  点进攻 ({pos[0]},{pos[1]})")
                    tap(pos[0], pos[1])
                    time.sleep(3)
            elif scene == "mode_select":
                pos = find("normal_battle.png", img, threshold=0.8)
                if pos:
                    self.log_msg(f"  点常规战 ({pos[0]},{pos[1]})")
                    tap(pos[0], pos[1])
                    time.sleep(2)
                else:
                    self.log_msg("  模式选择页，无常规战按钮")
            elif scene == "donate_page":
                # 关闭捐兵页面，点返回箭头
                tap(420, 100)
                time.sleep(2)
            elif scene == "chat_open":
                pos = find("chat_open.png", img)
                self.log_msg(f"  点返回箭头 ({pos[0]},{pos[1]})")
                tap(pos[0], pos[1])
                time.sleep(2)
            elif scene == "emulator_desktop":
                pos = find("coc_icon.png", img)
                self.log_msg(f"  点COC图标 ({pos[0]},{pos[1]-10})")
                tap(pos[0], pos[1] - 10)
                time.sleep(5)
            else:
                self.log_msg("  场景未知！响铃警报...")
                try:
                    import winsound
                    winsound.Beep(1200, 800)
                except:
                    pass
                time.sleep(3)

    def navigate_to_chat(self):
        """导航到部落聊天页面"""
        self.back_to_game_main()
        if not self.running: return

        # 从主界面进聊天
        while self.running:
            img = screencap()
            scene = self.detect_scene(img)
            if scene == "chat_open":
                break
            elif scene == "game_main":
                pos = find("chat_bubble.png", img)
                self.log_msg(f"  点聊天气泡 ({pos[0]},{pos[1]})")
                tap(pos[0], pos[1])
                time.sleep(2)
            else:
                self.back_to_game_main()
                if not self.running: return

        if not self.running: return

        # 确保在部落聊天标签
        self.log_msg("检查是否在部落聊天...")
        time.sleep(1)
        img = screencap()
        clan = find("clan_tab.png", img)
        if clan:
            self.log_msg(f"  点部落聊天标签 ({clan[0]},{clan[1]})")
            tap(clan[0], clan[1])
            time.sleep(2)

    def worker(self):
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

            # ===== 主循环：看捐兵→打资源→循环 =====
            self.log_msg("开始主循环...")
            while self.running:
                # 1. 去聊天看有没有人要兵
                self.navigate_to_chat()
                if not self.running: break

                img = screencap()
                pos = find("reinforce_btn.png", img, threshold=0.8)
                if pos:
                    self.log_msg(f">>> 发现增援按钮！({pos[0]},{pos[1]})")
                    tap(pos[0], pos[1])
                    time.sleep(2)
                    self.log_msg("等待增援页面加载...")
                    page_ok = False
                    for i in range(10):
                        if not self.running: break
                        img2 = screencap()
                        if find("reload.png", img2, threshold=0.8):
                            p = find("reload.png", img2)
                            tap(p[0], p[1])
                            time.sleep(10)
                            break
                        if find("donate_page.png", img2, threshold=0.8):
                            self.log_msg("开始捐兵")
                            time.sleep(1)
                            self.do_donate()
                            page_ok = True
                            break
                        time.sleep(1)
                    self.log_msg("捐兵结束，等2秒...")
                    time.sleep(2)
                else:
                    self.log_msg("无捐兵请求")

                # 2. 回主界面打资源
                self.back_to_game_main()
                if not self.running: break
                self.log_msg("=== 开始打资源 ===")
                self.do_raid()
                if not self.running: break
                self.log_msg("=== 打资源结束 ===")

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
