# hooks/rthook_meipass_path.py
import os, sys

# 将 PyInstaller 的临时解压目录 (_MEIPASS) 加入 PATH，便于找到 ffmpeg.exe/ffprobe.exe
base = getattr(sys, "_MEIPASS", None)
if base and os.path.isdir(base):
    os.environ["PATH"] = base + os.pathsep + os.environ.get("PATH", "")