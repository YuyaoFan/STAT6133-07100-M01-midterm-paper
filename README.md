# 期中论文｜工资的年龄曲线：参数、非参数与半参数回归方法的比较研究

《非参和半参回归》课程期中作业仓库。论文以 ISLR `Wage` 公开数据（3000 名美国中大西洋地区男性工人）为例，
在同一份数据上比较参数线性模型、非参数核方法与半参数部分线性模型，回答「年龄—工资曲线是否线性」以及
「线性设定是否扭曲教育回报」两个问题。

---

## 一、提交物

| 项目 | 位置 | 说明 |
|---|---|---|
| Canvas 提交 zip | `submission/期中论文_submission.zip` | 内含 `论文.pdf` 与 `code/`（含 `analysis.py`、`make_paper.py`、`data/Wage.csv` 等） |
| 论文 PDF | `paper/论文.pdf` | 12 页，含数据来源、方法、结果、讨论、参考文献与 AI 使用说明 |
| 论文 Markdown 源文 | `paper/论文.md` | 由排版脚本同步生成，便于查阅/修改 |
| 课程群演讲材料 | `presentation/` | 3 分钟讲稿、幻灯片 PDF、可选的演讲视频 mp4 |

> 注：课程群内的演讲需要由本人（作者）自行发送/上传；本仓库只负责生成并保存待提交的文件。

---

## 二、快速复现

```bash
python3 -m pip install -r code/requirements.txt
python3 code/analysis.py       # 约 20 秒，输出 results/ 下全部表格、图形、results.json
python3 code/make_paper.py     # 由 results.json 自动生成 paper/论文.pdf 与 论文.md
python3 code/make_slides.py    # 生成 presentation/slides.pdf
python3 code/make_submission.py  # 重新打包 Canvas zip
```

`code/analysis.py` 固定随机种子 `20261120`：置信区间用 600 次 wild bootstrap，GLR 检验用 1000 次；
五折交叉验证划分在所有模型间保持一致。论文中所有数值均由 `make_paper.py` 以 f-string 从
`results/results.json` 读取，因此**正文数字与代码输出严格一致**。

---

## 三、目录结构

```
.
├── README.md                     仓库说明（本文件）
├── .gitignore
├── data/
│   ├── Wage_raw.csv              原始下载（含 rownames）
│   ├── Wage.csv                  清洗后分析数据
│   └── SOURCES.md                数据来源、变量字典、清洗步骤
├── code/
│   ├── analysis.py               ★ 全部统计计算
│   ├── make_paper.py             ★ 论文 PDF / Markdown 排版
│   ├── make_slides.py            3 分钟演讲幻灯片
│   ├── make_video.py             可选：讲稿 TTS + 幻灯片合成 mp4（macOS）
│   ├── make_submission.py        打包 Canvas zip
│   ├── requirements.txt
│   └── data/Wage.csv             随 zip 附带的数据副本（保证代码可独立运行）
├── results/                     表格(csv)、图形(png/pdf)、曲线(npz)、results.json
├── paper/
│   ├── 论文.pdf
│   └── 论文.md
├── presentation/
│   ├── 讲稿.md                  ≤3 分钟、按幻灯片分段
│   ├── slides.pdf
│   └── 演讲.mp4                 可选
├── submission/
│   └── 期中论文_submission.zip
└── course_file/Chapter5.pdf     课程讲义（方法路线依据，原文件，未改动）
```

---

## 四、方法路线（对齐课程讲义目录）

| 类别 | 本文使用的方法 | 讲义对应章节 |
|---|---|---|
| 参数 | 多元线性回归 / 二次·三次年龄多项式、OLS + HC3、Wald/F/RESET/JB 检验、AIC/BIC | 1 回归模型简介 |
| 非参数 | 高斯核密度估计（Silverman 与 LSCV 带宽）、NW 与局部线性估计、CV 选带宽、KS/Mann–Whitney/Kruskal–Wallis、wild bootstrap 置信带、两样本经验似然 | 3 核密度估计；4 非参数回归；5 经验似然 |
| 半参数 | 部分线性模型（Robinson/Speckman profile 核估计）、广义似然比检验、分段多项式（样条筛法）可加部分线性模型、变系数模型 | 6 部分线性模型；10–12 可加/可加部分线性模型；9 变系数模型 |

---

## 五、主要结论（摘要）

1. 年龄效应显著非线性、非单调：控制协变量后对数工资约在 **44 岁**见顶，30 岁附近每增龄 10 岁约 +0.111，
   45 岁后趋零并转负；线性模型却给出恒定 +0.025。GLR 统计量 40.40，bootstrap **p ≤ 0.001**。
2. 半参数模型把五折 CV 预测 MSE 从 0.078084 降至 0.076194（约 2.4%），R² 从 0.3752 升至 0.3918。
3. 教育溢价对年龄设定**稳健**：大学毕业生相对高中毕业生的对数工资溢价 0.2006（参数）vs 0.1948（半参数），
   配对 bootstrap 差值 0.0058，95% 区间 [0.0035, 0.0070] —— 统计可检出但经济幅度不足 3%。
4. 教育组工资分布差异主要是位置平移（去均值后 KS 检验 p = 0.311）；经验似然 95% 区间
   [0.2199, 0.2815] 与 Welch 区间几乎重合。
5. 诚实记录的两个「反面」发现：Ramsey RESET 未能拒绝线性模型（p = 0.447），说明全局设定检验功效有限；
   工资仅有 508 个不同取值，使 LSCV 带宽选择退化为 h → 0，故主分析改用规则带宽。

---

## 六、AI 工具使用说明

论文第 6 节有完整说明（选题/检索、编程、写作与阐述、图表与校对、演讲材料、学术诚信声明）。
简要而言：使用 CodeBuddy（腾讯混元大模型驱动）辅助资料检索、代码编写与调试、论文初稿起草、
PDF/图表排版与校对；全部数值来自可复现代码实算，文献经人工核对，作者本人对全文负责。

---

## 七、许可与引用

课程作业代码与文本仅供本课程使用。数据引用见 `data/SOURCES.md` 与论文参考文献 [1]、[2]；
方法依据的课程讲义见参考文献 [23]。
# STAT6133-07100-M01-midterm-paper
