# 论文配套代码说明

本目录为 Canvas 提交 zip 中的 `code/`，与 GitHub 仓库中的 `code/` 一致，并额外附带
`data/Wage.csv` 与 `results/` 的关键输出，使代码在解压后可独立运行。

## 文件

| 文件 | 作用 |
|---|---|
| `analysis.py` | **主分析脚本**：参数 / 非参数 / 半参数全部方法，输出表格、图形与 `results.json` |
| `make_paper.py` | 由 `results/results.json` 自动排版生成 `paper/论文.pdf` 与 `paper/论文.md` |
| `make_slides.py` | 3 分钟演讲的 6 页幻灯片与讲稿（仓库 `presentation/`） |
| `make_video.py` | 可选：macOS 下用 `say` + ffmpeg 合成演讲 mp4 |
| `make_submission.py` | 重新打包 Canvas 提交 zip（仅仓库中使用） |
| `requirements.txt` | Python 依赖 |
| `data/Wage.csv` | 清洗后的公开数据（来源与字段见 `data/SOURCES.md`） |
| `results/` | 预生成的表格、图形 PNG 与 `results.json`，便于直接运行排版脚本 |

## 运行顺序

```bash
python3 -m pip install -r requirements.txt
python3 analysis.py       # 重新计算全部结果（约 20 秒）
python3 make_paper.py     # 重新生成论文 PDF / Markdown
```

若在仓库根目录运行，请把路径换成 `python3 code/analysis.py`、`python3 code/make_paper.py`；
脚本会自动向上查找 `data/` 与 `results/`。

## 可复现性

- 随机种子固定为 `20261120`；置信区间 600 次 wild bootstrap，GLR 检验 1000 次。
- 五折交叉验证划分在所有模型间共用。
- 论文中的每一个数值均从 `results/results.json` 读取，正文与代码输出不会不一致。
- 数据来源：ISLR `Wage`（Rdatasets 公开镜像），见 `data/SOURCES.md` 与论文第 2 节。

## 环境提示

`make_paper.py` 与 `make_slides.py` 默认使用 macOS 自带中文字体
`/System/Library/Fonts/Supplemental/Songti.ttc` 与 `/System/Library/Fonts/STHeiti Medium.ttc`。
在 Windows / Linux 上请把 `make_paper.py`、`make_slides.py` 顶部的字体路径替换为本地中文字体
（如 `SimSun.ttf`、`NotoSansCJK-Regular.ttc`），其余代码无需改动。
