"""截图工具：把模拟器当前画面存到桌面，方便裁模板"""
import subprocess
import os

ADB = r"D:\leidian\LDPlayer9\adb.exe"
DESKTOP = os.path.join(os.path.expanduser("~"), "Desktop")
OUT = os.path.join(DESKTOP, "COC截图.png")

subprocess.run([ADB, "shell", "screencap", "-p", "/sdcard/_shot.png"], timeout=10)
subprocess.run([ADB, "pull", "/sdcard/_shot.png", OUT], timeout=10)
print(f"截图已保存到: {OUT}")
os.system(f'explorer /select,"{OUT}"')
