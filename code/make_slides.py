# -*- coding: utf-8 -*-
"""
生成 3 分钟论文演讲的幻灯片（16:9，6 页）与讲稿文本。
NARRATION 同时被 make_video.py 用于合成配音，保证音画一致。

运行：python3 make_slides.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent if (HERE.parent / "results").exists() else HERE
RES = ROOT / "results" / "figures"
OUT = ROOT / "presentation"
OUT.mkdir(parents=True, exist_ok=True)

SONG = Path("/System/Library/Fonts/Supplemental/Songti.ttc")
HEI = Path("/System/Library/Fonts/STHeiti Medium.ttc")
pdfmetrics.registerFont(TTFont("Body", str(SONG), subfontIndex=6))
pdfmetrics.registerFont(TTFont("Head", str(HEI), subfontIndex=1))

W, H = 960.0, 540.0
ACCENT = colors.HexColor("#1f4e79")
GREY = colors.HexColor("#555555")

# 每页讲稿：约 95–105 字，整体约 600 字；按中文 TTS 约 4 字/秒，总时长约 2.5–2.9 分钟
NARRATION = [
    "各位老师同学好，我报告的题目是工资的年龄曲线，比较参数、非参数与半参数三类回归方法。"
    "数据是一份三千人的公开工资样本。我想回答两个问题：控制其他因素后，年龄对工资的效应是不是线性的；"
    "如果不是，线性设定会不会把教育回报也带偏。",

    "方法上我把三类工具放在同一份样本上比较。参数方法用含年龄一次、二次、三次项的线性模型；"
    "非参数方法用核密度估计、局部线性光滑、秩检验和经验似然；"
    "半参数方法用部分线性模型、广义似然比检验、样条筛法和变系数模型。响应变量是对数工资。",

    "第一个发现，年龄效应显著非线性。蓝色曲线在四十五岁左右见顶，年轻时上升快，中年走平，六十岁后略降。"
    "导数估计显示，三十岁每增龄十岁对数工资约上升零点一七，六十岁已经转负。"
    "而红色直线给出恒定的零点零二五，在两端都系统性偏离。",

    "第二个发现有点意外：教育回报很稳健。大学毕业生相对高中毕业生的溢价，参数模型是零点二零零六，"
    "半参数是零点一九四八。配对自助法估计差值约零点零零六，区间不含零，统计上能检出，"
    "但幅度不到百分之三，经济意义很小。半参数估计的标准误也几乎没有变大。",

    "检验上，年龄高次项的联合检验，显著性概率约十的负十六次方；可是通用的设定检验却没拒绝线性模型，"
    "说明检验功效很关键。广义似然比统计量四十点四，自助法概率不超过千分之一。"
    "预测误差从零点零七八一降到零点零七六二，改善约百分之二点四。经验似然区间和常规区间几乎重合。",

    "小结：年龄曲线非单调，半参数模型既保留可解释参数又修正设定错误，教育溢价本身很稳健。"
    "局限是横截面数据不能作因果解释，年龄、队列和时期效应混在一起；工资只有五百零八个不同取值，"
    "让交叉验证选带宽失效，高年龄段置信带也很宽，论文里都如实记录了。"
    "人工智能工具的使用在论文第六节完整说明，代码可以一键复现。谢谢。",
]

SLIDES = [
    dict(title="工资的年龄曲线",
         subtitle="参数、非参数与半参数回归方法的比较研究",
         lines=[
             "数据：ISLR Wage，3000 名美国中大西洋地区男性工人（2003–2009）",
             "Q1　控制其他因素后，年龄对工资的效应是线性的吗？",
             "Q2　若非线性，线性设定会不会扭曲教育回报？",
             "",
             "《非参和半参回归》期中论文　|　全部代码与结果见本 GitHub 仓库",
         ], image=None),
    dict(title="数据与方法：三类工具，同一份样本",
         lines=[
             "Y = logwage；U = age（18–80）；Z = 15 个协变量；无缺失值",
             "参数：线性 / 二次 / 三次年龄回归，OLS + HC3，RESET、JB 检验",
             "非参数：核密度、NW 与局部线性、KS/MW/KW、经验似然、bootstrap",
             "半参数：部分线性模型、GLR 检验、样条筛法、变系数模型",
         ], image="fig1_data"),
    dict(title="发现一　年龄效应显著非线性",
         lines=[
             "曲线约 45 岁见顶；30 岁每增龄 10 岁约 +0.169，60 岁约 −0.015",
             "参数直线给出恒定 +0.025，两端系统性偏离",
         ], image="fig3_nonparametric"),
    dict(title="发现二　教育溢价其实很稳健",
         lines=[
             "大学：0.2006（M0） → 0.1948（PLM）；研究生：0.3512 → 0.3432",
             "配对 bootstrap 差值 0.0058 / 0.0080：统计显著，经济幅度不足 3%",
             "β 的标准误与参数模型相当（√n 有效）",
         ], image="fig4_plm"),
    dict(title="模型检验与预测",
         lines=[
             "年龄二/三次项 F = 37.15，p ≈ 1.15e−16；RESET 反而 p = 0.447",
             "GLR = 40.40，bootstrap p ≤ 0.001（拒绝线性）",
             "五折 CV MSE：0.078084 → 0.076194（约 −2.4%）",
             "经验似然 95% 区间 [0.2199, 0.2815] ≈ Welch 区间",
         ], image="fig5_tests"),
    dict(title="结论、局限与说明",
         lines=[
             "结论：年龄曲线非单调；半参数模型兼顾可解释性与稳健性；教育溢价稳健",
             "局限：横截面不能识别因果；年龄/队列/时期混杂；高年龄段置信带宽",
             "诚实记录：工资仅 508 个不同取值 → LSCV 带宽失效，改用规则带宽",
             "AI 使用：论文第 6 节完整说明（检索、编程、起草、图表、校对）",
             "复现：python3 code/analysis.py  &&  python3 code/make_paper.py",
         ], image=None),
]


def fit_image(c, name, x, y, box_w, box_h):
    path = RES / f"{name}.png"
    if not path.exists():
        return
    with PILImage.open(path) as im:
        iw, ih = im.size
    scale = min(box_w / iw, box_h / ih)
    w, h = iw * scale, ih * scale
    c.drawImage(str(path), x + (box_w - w) / 2, y + (box_h - h) / 2,
                width=w, height=h, preserveAspectRatio=True, anchor="c")


def build():
    pdf = OUT / "slides.pdf"
    c = canvas.Canvas(str(pdf), pagesize=(W, H))
    c.setTitle("工资的年龄曲线 · 3 分钟论文演讲")
    for k, s in enumerate(SLIDES):
        c.setFillColor(colors.white); c.rect(0, 0, W, H, fill=1, stroke=0)
        c.setFillColor(ACCENT); c.rect(0, H - 8, W, 8, fill=1, stroke=0)
        c.setFont("Head", 27); c.setFillColor(ACCENT)
        c.drawString(45, H - 62, s["title"])
        if s.get("subtitle"):
            c.setFont("Body", 15); c.setFillColor(GREY)
            c.drawString(47, H - 90, s["subtitle"])
        c.setStrokeColor(colors.HexColor("#c9d4e0")); c.setLineWidth(1.2)
        c.line(45, H - (104 if s.get("subtitle") else 78), W - 45, H - (104 if s.get("subtitle") else 78))

        lines = s["lines"]
        if s["image"]:
            top = H - (132 if s.get("subtitle") else 112)
            c.setFont("Body", 15); c.setFillColor(colors.HexColor("#222222"))
            yy = top
            for line in lines:
                if line:
                    c.drawString(48, yy, line)
                yy -= 24
            fit_image(c, s["image"], 45, 28, W - 90, yy - 44)
        else:
            yy = H - (145 if s.get("subtitle") else 120)
            c.setFont("Body", 17)
            for line in lines:
                if line:
                    c.setFillColor(colors.HexColor("#222222"))
                    c.drawString(52, yy, line)
                yy -= 36
            c.setFillColor(GREY); c.setFont("Body", 13)
            c.drawString(52, 60, "《非参和半参回归》期中论文 · 数据与代码见 GitHub 仓库")
        c.setFillColor(GREY); c.setFont("Body", 11)
        c.drawRightString(W - 45, 32, f"{k + 1} / {len(SLIDES)}")
        c.showPage()
    c.save()

    total = sum(len(t) for t in NARRATION)
    script = ["# 3 分钟论文演讲讲稿", "",
              f"语速提示：实测中文语音合成约 4.3 字/秒；全文 {total} 字，配合 {len(SLIDES)} 页幻灯片，"
              f"预计配音总时长约 {total / 4.3:.0f} 秒（实测 171 秒，约 2 分 51 秒，未超过 3 分钟）。",
              "每页结束稍作停顿（约 0.5 秒）再翻页；演讲时请以正常语速、不要逐字念稿。", ""]
    for i, t in enumerate(NARRATION):
        script += [f"## 第 {i + 1} 页｜{SLIDES[i]['title']}", "",
                   f"（本页约 {len(t)} 字）", "", t, ""]
    (OUT / "讲稿.md").write_text("\n".join(script), encoding="utf-8")
    print(f"已生成 {pdf}（{len(SLIDES)} 页）与 {OUT / '讲稿.md'}；讲稿 {total} 字，预计 {total / 4.3 / 60:.2f} 分钟。")


if __name__ == "__main__":
    build()
