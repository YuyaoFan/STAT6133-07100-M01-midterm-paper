# -*- coding: utf-8 -*-
"""
可选：把 6 页幻灯片与中文配音合成为「不超过 3 分钟」的演讲视频。

依赖：macOS 自带 say（zh_CN 语音 Tingting）、imageio-ffmpeg 提供的 ffmpeg、PyMuPDF。
运行：python3 code/make_video.py
输出：presentation/演讲.mp4
若总时长超过 175 秒会直接报错，需回到 make_slides.py 精简 NARRATION。
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import pymupdf

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from make_slides import NARRATION, OUT, SLIDES  # noqa: E402

try:
    import imageio_ffmpeg
    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError:
    raise SystemExit("请先安装 imageio-ffmpeg：python3 -m pip install imageio-ffmpeg")

MAX_SECONDS = 175.0
VOICE = "Tingting"


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    slides_pdf = OUT / "slides.pdf"
    if not slides_pdf.exists():
        raise SystemExit("请先运行 python3 code/make_slides.py")
    tmp = Path(tempfile.mkdtemp(prefix="wage_talk_"))
    doc = pymupdf.open(str(slides_pdf))
    assert len(doc) == len(NARRATION) == len(SLIDES), "幻灯片页数与讲稿段数不一致"

    print("1/4　渲染幻灯片…")
    for i, page in enumerate(doc):
        page.get_pixmap(dpi=110).save(str(tmp / f"slide{i}.png"))
    doc.close()

    print("2/4　合成中文配音并测量时长…")
    durations = []
    for i, text in enumerate(NARRATION):
        aiff, wav = tmp / f"a{i}.aiff", tmp / f"a{i}.wav"
        run(["say", "-v", VOICE, "-o", str(aiff), text])
        run([FFMPEG, "-y", "-loglevel", "error", "-i", str(aiff),
             "-ar", "44100", "-ac", "1", str(wav)])
        with wave.open(str(wav)) as w:
            durations.append(w.getnframes() / w.getframerate())
        print(f"    第 {i + 1} 页：{durations[-1]:.1f} 秒（{len(text)} 字）")
    total = sum(durations)
    print(f"    配音总时长：{total:.1f} 秒 / 上限 {MAX_SECONDS:.0f} 秒")
    if total > MAX_SECONDS:
        raise SystemExit("讲稿过长：请精简 make_slides.py 中的 NARRATION 后重试")

    print("3/4　生成分段视频…")
    for i in range(len(NARRATION)):
        run([FFMPEG, "-y", "-loglevel", "error",
             "-loop", "1", "-framerate", "10", "-i", str(tmp / f"slide{i}.png"),
             "-i", str(tmp / f"a{i}.wav"),
             "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "96k", "-t", f"{durations[i]:.3f}",
             "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,"
                    "pad=1280:720:(ow-iw)/2:(oh-ih)/2",
             str(tmp / f"seg{i}.mp4")])

    print("4/4　拼接为最终 mp4…")
    concat = tmp / "concat.txt"
    concat.write_text("".join(f"file '{tmp / f'seg{i}.mp4'}'\n" for i in range(len(NARRATION))),
                      encoding="utf-8")
    out = OUT / "演讲.mp4"
    run([FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(concat), "-c", "copy", str(out)])
    info = subprocess.run([FFMPEG, "-i", str(out)], capture_output=True, text=True).stderr
    import re
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", info)
    final = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else float("inf")
    print(f"完成：{out}（配音 {total:.1f} 秒；成片 {final:.1f} 秒，约 {final / 60:.2f} 分钟）")
    if final > 180:
        raise SystemExit("成片超过 3 分钟，请精简讲稿后重试")


if __name__ == "__main__":
    main()
