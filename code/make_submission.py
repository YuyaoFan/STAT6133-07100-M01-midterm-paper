# -*- coding: utf-8 -*-
"""
生成 Canvas 提交所需的 zip：根目录含「论文.pdf」，并含完整的 code/（r 或 py）。

zip 内容：
    论文.pdf
    README.txt
    code/analysis.py, make_paper.py, make_slides.py, make_video.py,
         make_submission.py, requirements.txt, README.md
    code/data/Wage.csv, SOURCES.md
    code/results/results.json, table_*.csv, figures/*.png

运行：python3 code/make_submission.py
"""
from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "submission"
OUT.mkdir(parents=True, exist_ok=True)
ZIP = OUT / "期中论文_submission.zip"

# 1. 把数据与关键结果复制到 code/ 下，使 zip 解压后代码可独立运行
(HERE / "data").mkdir(exist_ok=True)
(HERE / "results" / "figures").mkdir(parents=True, exist_ok=True)
shutil.copy2(ROOT / "data" / "Wage.csv", HERE / "data" / "Wage.csv")
shutil.copy2(ROOT / "data" / "SOURCES.md", HERE / "data" / "SOURCES.md")
for f in (ROOT / "results").glob("table_*.csv"):
    shutil.copy2(f, HERE / "results" / f.name)
shutil.copy2(ROOT / "results" / "results.json", HERE / "results" / "results.json")
for f in (ROOT / "results" / "figures").glob("*.png"):
    shutil.copy2(f, HERE / "results" / "figures" / f.name)

README_TXT = """期中论文提交包（Canvas）
========================

题目：工资的年龄曲线：参数、非参数与半参数回归方法的比较研究
课程：《非参和半参回归》期中论文

提交内容
  1. 论文.pdf                 论文 PDF（12 页，含数据来源、方法、结论讨论、参考文献、AI 工具使用说明）
  2. code/                    全部 Python 代码、数据、依赖清单与预生成结果
       analysis.py            主分析脚本（参数 / 非参数 / 半参数方法）
       make_paper.py          论文 PDF 自动排版
       make_slides.py         3 分钟演讲幻灯片与讲稿
       make_video.py          可选：合成演讲视频
       requirements.txt       Python 依赖
       data/Wage.csv          清洗后的公开数据
       data/SOURCES.md        数据来源与清洗说明
       results/               预生成的表格、图形与 results.json

复现方法
  python3 -m pip install -r code/requirements.txt
  python3 code/analysis.py
  python3 code/make_paper.py

数据来源：ISLR::Wage（Mid-Atlantic Wage Data），Rdatasets 公开镜像；
原始整理自 2011 年 3 月 CPS 补充调查。详见 code/data/SOURCES.md 与论文第 2 节。

AI 工具使用说明见论文第 6 节。
"""

files = [
    (ROOT / "paper" / "论文.pdf", "论文.pdf"),
]
for name in ["analysis.py", "make_paper.py", "make_slides.py", "make_video.py",
             "make_submission.py", "requirements.txt", "README.md"]:
    files.append((HERE / name, f"code/{name}"))
for name in ["Wage.csv", "SOURCES.md"]:
    files.append((HERE / "data" / name, f"code/data/{name}"))
for f in sorted((HERE / "results").glob("table_*.csv")):
    files.append((f, f"code/results/{f.name}"))
files.append((HERE / "results" / "results.json", "code/results/results.json"))
for f in sorted((HERE / "results" / "figures").glob("*.png")):
    files.append((f, f"code/results/figures/{f.name}"))

with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("README.txt", README_TXT)
    for src, arc in files:
        if not src.exists():
            raise FileNotFoundError(src)
        z.write(src, arc)

size = ZIP.stat().st_size
with zipfile.ZipFile(ZIP) as z:
    names = z.namelist()
print(f"已生成 {ZIP}（{size / 1024:.0f} KB，{len(names)} 个文件）")
for nm in names:
    print("   ", nm)
