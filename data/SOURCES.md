# 数据来源与清洗说明

## 1. 数据集

- 名称：`Wage`（Mid-Atlantic Wage Data），R 包 **ISLR** 内置数据。
- 官方描述：Wage and other data for a group of 3000 male workers in the Mid-Atlantic region.
- 原始整理者：Steve Miller（Inquidia Consulting，原 Open BI）；依据 **2011 年 3 月美国当前人口调查（CPS）补充调查** 手工整理。
- 教材出处：James G., Witten D., Hastie T., Tibshirani R. *An Introduction to Statistical Learning with Applications in R*. Springer, 2013（第 7 章用于演示样条与广义可加模型）。
- 本仓库下载来源（公开镜像）：Rdatasets
  `https://raw.githubusercontent.com/vincentarelbundock/Rdatasets/master/csv/ISLR/Wage.csv`
  数据文档：`https://raw.githubusercontent.com/vincentarelbundock/Rdatasets/master/doc/ISLR/Wage.html`
- 下载日期：2026-11-20。文件 `Wage_raw.csv` 为原始下载内容（含 Rdatasets 附带的 `rownames` 列）。

## 2. 清洗步骤

1. 删除 `rownames`（仅为索引，无统计含义）。
2. 删除 `region`：样本内恒为 `2. Middle Atlantic`，无变异。
3. 对 6 个因子变量去除文档中的数字前缀（如 `1. White` → `White`），便于编码与作图。
4. 保留 `logwage` 与 `wage`，并核对 `logwage == ln(wage)`（逐条最大绝对偏差为 0）。
5. 结果文件 `Wage.csv`：3000 行、10 列，无缺失值。

清洗代码等价于：

```python
import pandas as pd
d = pd.read_csv("Wage_raw.csv").drop(columns=["rownames", "region"])
for c in ["maritl", "race", "education", "jobclass", "health", "health_ins"]:
    d[c] = d[c].str.replace(r"^\d+\.\s*", "", regex=True)
d.to_csv("Wage.csv", index=False)
```

## 3. 变量字典

| 变量 | 含义 | 取值 |
|---|---|---|
| `year` | 工资记录年份 | 2003–2009 |
| `age` | 年龄 | 18–80（61 个不同取值） |
| `maritl` | 婚姻状况 | Never Married / Married / Widowed / Divorced / Separated |
| `race` | 种族 | White / Black / Asian / Other |
| `education` | 教育程度 | `< HS Grad` / `HS Grad` / `Some College` / `College Grad` / `Advanced Degree` |
| `jobclass` | 行业 | Industrial / Information |
| `health` | 自评健康 | `<=Good` / `>=Very Good` |
| `health_ins` | 是否有医疗保险 | Yes / No |
| `logwage` | 对数工资 | `ln(wage)` |
| `wage` | 原始工资（教材以千美元计） | 20.09–318.34 |

## 4. 值得注意的数据特征

- 3000 条工资记录只有 **508 个不同取值**，出现最多的取值重复 120 次，说明工资被明显离散化。
  这使得连续型核密度估计的**最小二乘交叉验证（LSCV）带宽失效**（CV 偏向 h → 0）。
  论文 4.2 节如实报告了这一现象，主分析改用 Silverman 规则带宽。
- 数据为横截面观测，没有个体标识，无法识别同一工人是否被重复观测；论文 5.2 节讨论了由此带来的独立性假定与因果解释限制。

## 5. 引用

使用本数据时请引用 ISLR 教材与数据集官方文档（见论文参考文献 [1]、[2]）。
