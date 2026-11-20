# -*- coding: utf-8 -*-
"""
《工资的年龄曲线：参数、非参数与半参数方法的比较研究》—— 完整可复现分析代码

数据来源：ISLR::Wage（Rdatasets 镜像），见 data/SOURCES.md
输出：results/ 下的表格(csv)、图形(png/pdf)、汇总结果(results.json)

方法清单
  参数：多元线性/多项式回归（OLS+HC3）、RESET 设定检验、JB 正态性检验、AIC/BIC
  非参：核密度估计(Silverman 与 LSCV 带宽)、KS/Mann-Whitney/Kruskal-Wallis 检验、
        Nadaraya-Watson 与局部线性估计(CV 选带宽)、wild bootstrap 逐点置信带、
        两样本经验似然(Owen/Jing)置信区间
  半参：部分线性模型(Robinson 1988 / Speckman 1988 的 profile 最小二乘)、
        广义似然比检验(GLR, Fan et al. 2001, bootstrap 校准)、
        分段多项式(样条筛法)可加部分线性模型、变系数模型(Hastie & Tibshirani 1993)

运行：python3 analysis.py
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats
from scipy.optimize import brentq
from statsmodels.regression.linear_model import OLS
from statsmodels.stats.diagnostic import linear_reset
from statsmodels.stats.stattools import jarque_bera

warnings.filterwarnings("ignore")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent if (HERE.parent / "results").exists() or (HERE.parent / "data").exists() else HERE
DATA = ROOT / "data" / "Wage.csv"
if not DATA.exists():
    DATA = HERE / "data" / "Wage.csv"
OUT = ROOT / "results" if ROOT != HERE else HERE / "results"
FIG = OUT / "figures"
OUT.mkdir(parents=True, exist_ok=True)
FIG.mkdir(parents=True, exist_ok=True)

SEED = 20261120
rng = np.random.default_rng(SEED)
N_BOOT = 600
N_GLR = 1000
plt.rcParams.update({
    "font.family": "Songti SC",
    "axes.unicode_minus": False,
    "axes.titlesize": 14,
    "axes.labelsize": 13,
    "xtick.labelsize": 12,
    "ytick.labelsize": 12,
    "legend.fontsize": 11,
    "figure.dpi": 110,
    "savefig.dpi": 190,
})
COLORS = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#17becf"]
R = {}

def savefig(name: str) -> None:
    plt.tight_layout()
    plt.savefig(FIG / f"{name}.png", bbox_inches="tight")
    plt.savefig(FIG / f"{name}.pdf", bbox_inches="tight")
    plt.close()

def put(key, value):
    if isinstance(value, (np.floating, np.integer)):
        value = value.item()
    elif isinstance(value, np.ndarray):
        value = value.tolist()
    elif isinstance(value, (np.bool_,)):
        value = bool(value)
    R[key] = value

# ---------------------------------------------------------------------------
# 0. 数据与设计矩阵
# ---------------------------------------------------------------------------
df = pd.read_csv(DATA)
y = df["logwage"].to_numpy(float)           # 响应：对数工资
u = df["age"].to_numpy(float)               # 非参数分量：年龄
n = len(y)
put("n", n)
put("n_age_unique", int(np.unique(u).size))

BASE_EDU = "HS Grad"

def build_Z(d: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    """不含截距的参数分量 Z（15 列），所有虚拟变量以高中毕业/白人/已婚为基准组。"""
    cols, names = [], []

    def dummy(col, levels, prefix=""):
        for lv in levels:
            cols.append((d[col] == lv).to_numpy(float))
            names.append(f"{prefix}{lv}")

    dummy("education", ["< HS Grad", "Some College", "College Grad", "Advanced Degree"])
    dummy("race", ["Black", "Asian", "Other"], "race=")
    dummy("maritl", ["Never Married", "Widowed", "Divorced", "Separated"], "maritl=")
    dummy("jobclass", ["Information"], "job=")
    dummy("health", [">=Very Good"], "health=")
    dummy("health_ins", ["Yes"], "ins=")
    cols.append((d["year"].to_numpy(float) - 2006.0))
    names.append("year_c")
    return np.column_stack(cols), names

Z, ZNAMES = build_Z(df)
p = Z.shape[1]
ac = (u - 40.0) / 10.0


def design_par(power: int = 1) -> tuple[np.ndarray, list[str]]:
    """参数模型设计阵：截距 + 年龄的 p 阶多项式 + Z。"""
    blocks = [np.ones((n, 1)), ac.reshape(-1, 1)]
    names = ["const", "age/10"]
    if power >= 2:
        blocks.append((ac ** 2).reshape(-1, 1)); names.append("(age/10)^2")
    if power >= 3:
        blocks.append((ac ** 3).reshape(-1, 1)); names.append("(age/10)^3")
    blocks.append(Z); names += ZNAMES
    return np.column_stack(blocks), names

# ---------------------------------------------------------------------------
# 1. 描述统计
# ---------------------------------------------------------------------------
desc = df.groupby("education").agg(n=("logwage", "size"), mean_logwage=("logwage", "mean"),
                                   sd_logwage=("logwage", "std"), mean_wage=("wage", "mean"),
                                   median_wage=("wage", "median"), mean_age=("age", "mean"))
desc = desc.reindex(["< HS Grad", BASE_EDU, "Some College", "College Grad", "Advanced Degree"])
desc.round(4).to_csv(OUT / "table_descriptive.csv", encoding="utf-8-sig")
put("desc", desc.reset_index().to_dict("records"))
put("wage_range", [float(df.wage.min()), float(df.wage.max())])
put("age_range", [float(u.min()), float(u.max())])
put("year_range", [int(df.year.min()), int(df.year.max())])

# ---------------------------------------------------------------------------
# 2. 参数方法：线性 / 二次 / 三次年龄效应
# ---------------------------------------------------------------------------
par_fits = {}
for pw in (1, 2, 3):
    X, XN = design_par(pw)
    fit = OLS(y, X).fit(cov_type="HC3")
    par_fits[pw] = (X, XN, fit)

X0, XN0, fit0 = par_fits[1]
X0inv = np.linalg.solve(X0.T @ X0, X0.T)
rss0 = float(np.sum(fit0.resid ** 2))
put("m0_age_slope_per10", float(fit0.params[XN0.index("age/10")]))
put("corr_age_edu", {nm: float(np.corrcoef(u, Z[:, ZNAMES.index(nm)])[0, 1])
                     for nm in ["< HS Grad", "Some College", "College Grad", "Advanced Degree"]})
tss = float(np.sum((y - y.mean()) ** 2))
reset = linear_reset(fit0, power=3, use_f=True)
jb_stat, jb_p, skew, kurt = jarque_bera(fit0.resid)
f3 = par_fits[3][2]
names3 = par_fits[3][1]
Rmat = np.eye(len(f3.params))[[names3.index("(age/10)^2"), names3.index("(age/10)^3")]]
ftest_quad = f3.f_test(Rmat)

put("par_r2", 1 - rss0 / tss)
put("par_adjr2", fit0.rsquared_adj)
put("par_sigma", float(np.sqrt(rss0 / (n - X0.shape[1]))))
put("par_reset_f", float(np.ravel(reset.fvalue)[0]))
put("par_reset_p", float(np.ravel(reset.pvalue)[0]))
put("par_jb", float(jb_stat)); put("par_jb_p", float(jb_p))
put("par_quad_f", float(np.ravel(ftest_quad.fvalue)[0]))
put("par_quad_p", float(np.ravel(ftest_quad.pvalue)[0]))


def coef_rows(fit, names, tag, cov=None):
    ci = fit.conf_int()
    out = []
    for j, nm in enumerate(names):
        se = float(np.sqrt(np.diag(fit.cov_params())[j]))
        lo, hi = (float(ci[j, 0]), float(ci[j, 1])) if cov is None else (np.nan, np.nan)
        out.append(dict(model=tag, term=nm, est=float(fit.params[j]), se=se, lo=lo, hi=hi))
    return out

coef_long = []
for pw, (X, XN, fit) in par_fits.items():
    coef_long += coef_rows(fit, XN, f"M{pw-1}")

# ---------------------------------------------------------------------------
# 3. 核工具：局部线性 / NW 光滑矩阵（利用年龄只有 61 个取值的低秩结构）
# ---------------------------------------------------------------------------
def kmat(u_eval, U, h):
    d = U[None, :] - np.asarray(u_eval, float)[:, None]
    return np.exp(-0.5 * (d / h) ** 2), d


def ll_weights(u_eval, U, h):
    """局部线性拟合值的权重矩阵 W（行和为 1），形状 (len(u_eval), len(U))。"""
    K, d = kmat(u_eval, U, h)
    s0, s1, s2 = K.sum(1), (K * d).sum(1), (K * d * d).sum(1)
    den = s0 * s2 - s1 * s1
    den = np.where(np.abs(den) < 1e-14, 1e-14, den)
    W = K * (s2[:, None] - d * s1[:, None]) / den[:, None]
    return W / W.sum(1, keepdims=True)


def nw_weights(u_eval, U, h):
    K, _ = kmat(u_eval, U, h)
    return K / K.sum(1, keepdims=True)


def ll_deriv(u_eval, U, h, v):
    K, d = kmat(u_eval, U, h)
    s0, s1, s2 = K.sum(1), (K * d).sum(1), (K * d * d).sum(1)
    den = np.where(np.abs(s0 * s2 - s1 * s1) < 1e-14, 1e-14, s0 * s2 - s1 * s1)
    return (s0[:, None] * (K * d) - s1[:, None] * K) @ v / den


class Smoother:
    def __init__(self, U, h, grid=None):
        self.U = np.asarray(U, float)
        self.h = float(h)
        self.grid = np.unique(self.U) if grid is None else np.asarray(grid, float)
        self.idx = np.searchsorted(self.grid, self.U)
        self.W = ll_weights(self.grid, self.U, h)
        self.trace = float(np.sum(self.W[self.idx, np.arange(len(self.U))]))

    def apply(self, v):
        return (self.W @ v)[self.idx]

    def tilde(self, v):
        return v - self.apply(v)

    def at(self, u_eval, v):
        return ll_weights(u_eval, self.U, self.h) @ v


H_GRID = [1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 15.0]
FOLDS = np.array_split(rng.permutation(n), 5)

# ---------------------------------------------------------------------------
# 4. 非参数方法之一：核密度估计 + 分布检验 + 经验似然
# ---------------------------------------------------------------------------
def lscv_bandwidth(x, hs):
    """高斯核最小二乘交叉验证带宽：CV(h)=∫f̂²-2/n Σ f̂_{-i}(X_i)。"""
    x = np.asarray(x, float); m = len(x)
    diff = x[:, None] - x[None, :]
    out = []
    for h in hs:
        K = np.exp(-0.5 * (diff / h) ** 2) / (h * np.sqrt(2 * np.pi))
        Kh2 = np.exp(-0.5 * (diff / (np.sqrt(2) * h)) ** 2) / (np.sqrt(2) * h * np.sqrt(2 * np.pi))
        int_f2 = Kh2.sum() / m ** 2
        loo = (K.sum(1) - np.diag(K)) / (m - 1)
        out.append(int_f2 - 2 * loo.mean())
    return hs[int(np.argmin(out))], np.array(out)


H_KDE = np.exp(np.linspace(np.log(0.03), np.log(0.35), 35))
grid_kde = np.linspace(3.5, 5.9, 300)
kde_info = {}
for edu in ["< HS Grad", BASE_EDU, "Some College", "College Grad", "Advanced Degree"]:
    x = df.loc[df.education == edu, "logwage"].to_numpy(float)
    q1, q3 = np.percentile(x, [25, 75])
    h_sil = 0.9 * min(x.std(ddof=1), (q3 - q1) / 1.349) * len(x) ** (-0.2)
    h_cv, _ = lscv_bandwidth(x, H_KDE)
    # 工资存在大量结点（全样本仅 508 个不同取值），LSCV 会退化为 h→0；
    # 故主分析采用 Silverman 规则带宽，LSCV 结果仅作为诊断列入讨论。
    K = np.exp(-0.5 * ((grid_kde[:, None] - x[None, :]) / h_sil) ** 2) / (h_sil * np.sqrt(2 * np.pi))
    kde_info[edu] = dict(h_silverman=float(h_sil), h_lscv=float(h_cv), dens=K.mean(1))
    put(f"kde_{edu.replace(' ', '_').replace('<', 'lt')}", dict(h_sil=float(h_sil), h_cv=float(h_cv)))
put("n_unique_wage", int(df.wage.nunique()))
put("max_duplicate_wage", int(df.wage.value_counts().max()))

hs = df.loc[df.education == BASE_EDU, "logwage"].to_numpy(float)
col = df.loc[df.education == "College Grad", "logwage"].to_numpy(float)
adv = df.loc[df.education == "Advanced Degree", "logwage"].to_numpy(float)
ks_ch = stats.ks_2samp(col, hs)
ks_center = stats.ks_2samp(col - col.mean(), hs - hs.mean())  # 去除位置差后检验形状差异
mw_ch = stats.mannwhitneyu(col, hs, alternative="two-sided")
kw = stats.kruskal(*[df.loc[df.education == e, "logwage"] for e in desc.index])
put("ks_college_hs", dict(stat=float(ks_ch.statistic), p=float(ks_ch.pvalue)))
put("ks_centered", dict(stat=float(ks_center.statistic), p=float(ks_center.pvalue)))
put("mw_college_hs", dict(stat=float(mw_ch.statistic), p=float(mw_ch.pvalue)))
put("kw_edu", dict(stat=float(kw.statistic), p=float(kw.pvalue)))
put("gap_college_hs_raw", float(col.mean() - hs.mean()))


def el2_minus2logR(theta, y1, y2):
    """两样本经验似然比：Jing(1995) 的对偶解，θ = μ1 - μ2。"""
    n1, n2 = len(y1), len(y2)
    y1, y2 = np.asarray(y1, float), np.asarray(y2, float)

    def solve_alpha(lam, arr, sign):
        # p_i = 1/(alpha + sign*lam*arr_i)，由 Σp=1 定 alpha
        c = sign * lam
        lo = float(np.max(-c * arr)) + 1e-10
        g = lambda a: np.sum(1.0 / (a + c * arr)) - 1.0
        hi = max(2.0 * n1, lo + 1.0)
        while g(hi) > 0:
            hi *= 2
        return brentq(g, lo, hi, xtol=1e-12)

    def diff_of_means(lam):
        a = solve_alpha(lam, y1, +1)
        b = solve_alpha(lam, y2, -1)
        p = 1.0 / (a + lam * y1)
        q = 1.0 / (b - lam * y2)
        return np.dot(p, y1) - np.dot(q, y2), np.log(n1 * p).sum() + np.log(n2 * q).sum()

    f0 = diff_of_means(0.0)[0] - theta
    if abs(f0) < 1e-12:
        return 0.0
    direction = -1.0 if f0 < 0 else 1.0       # θ>θ̂ 需 λ<0，θ<θ̂ 需 λ>0
    hi = direction * 0.01
    for _ in range(200):
        f1 = diff_of_means(hi)[0] - theta
        if f0 * f1 <= 0:
            break
        hi *= 1.6
    else:
        return np.inf
    lam = brentq(lambda t: diff_of_means(t)[0] - theta, min(0.0, hi), max(0.0, hi), xtol=1e-11)
    _, logR = diff_of_means(lam)
    return float(-2.0 * logR)


theta_hat = float(col.mean() - hs.mean())
cut = stats.chi2.ppf(0.95, 1)


def el_ci_edge(direction):
    step, edge = 0.02, theta_hat + direction * 1e-5
    while el2_minus2logR(edge, col, hs) < cut and step < 1.0:
        step *= 1.6
        edge = theta_hat + direction * step
    return brentq(lambda t: el2_minus2logR(t, col, hs) - cut,
                  min(edge, theta_hat - 1e-5 if direction < 0 else theta_hat + 1e-5),
                  max(edge, theta_hat - 1e-5 if direction < 0 else theta_hat + 1e-5))


el_lo, el_hi = el_ci_edge(-1), el_ci_edge(+1)
v1, v2 = col.var(ddof=1) / len(col), hs.var(ddof=1) / len(hs)
se_diff = np.sqrt(v1 + v2)
df_welch = (v1 + v2) ** 2 / (v1 ** 2 / (len(col) - 1) + v2 ** 2 / (len(hs) - 1))
welch = stats.ttest_ind(col, hs, equal_var=False)
tcrit = stats.t.ppf(0.975, df_welch)
put("el_gap", dict(est=theta_hat, lo=float(el_lo), hi=float(el_hi), cutoff=float(cut)))
put("welch_gap", dict(est=theta_hat, lo=float(theta_hat - tcrit * se_diff),
                      hi=float(theta_hat + tcrit * se_diff), t=float(welch.statistic), p=float(welch.pvalue)))

# ---------------------------------------------------------------------------
# 5. 非参数方法之二：Nadaraya-Watson / 局部线性估计 m(age)
# ---------------------------------------------------------------------------
def cv_h_nonparam(hs):
    errs = []
    for h in hs:
        e = 0.0
        for te in FOLDS:
            tr = np.setdiff1d(np.arange(n), te)
            Wte = nw_weights(np.unique(u[te]), u[tr], h)
            e += np.sum((y[te] - (Wte @ y[tr])[np.searchsorted(np.unique(u[te]), u[te])]) ** 2)
        errs.append(e / n)
    return hs[int(np.argmin(errs))], np.array(errs)

h_np, cv_np = cv_h_nonparam(H_GRID)
S_np = Smoother(u, h_np)
grid_age = np.linspace(20, 78, 120)
m_ll = ll_weights(grid_age, u, h_np) @ y
m_nw = nw_weights(grid_age, u, h_np) @ y
# 导数估计对带宽更敏感，按 h^{5/7} 阶的经验规则适度放大带宽
h_deriv = 8.0
m_deriv = ll_deriv(grid_age, u, h_deriv, y)
put("h_np", h_np); put("cv_np", dict(zip([str(h) for h in H_GRID], cv_np.round(6).tolist())))
put("h_deriv", h_deriv)
put("m_np_peak_age", float(grid_age[np.argmax(m_ll)]))
put("m_np_peak", float(m_ll.max()))
put("m_np_deriv_at_30", float(np.interp(30, grid_age, m_deriv) * 10))
put("m_np_deriv_at_60", float(np.interp(60, grid_age, m_deriv) * 10))

# wild bootstrap 逐点置信带（固定设计，残差乘 Rademacher 变量）
resid_np = y - S_np.apply(y)
W_grid_ll = ll_weights(grid_age, u, h_np)
boot_np = np.empty((N_BOOT, len(grid_age)))
for b in range(N_BOOT):
    eps = resid_np * rng.choice([-1.0, 1.0], size=n)
    boot_np[b] = W_grid_ll @ (y + eps)
band_np = np.percentile(boot_np, [2.5, 97.5], axis=0)
# 同时置信带（max-|t| 校准）
sd_np = boot_np.std(0, ddof=1)
crit_sim = np.percentile(np.max(np.abs((boot_np - boot_np.mean(0)) / np.maximum(sd_np, 1e-10)), axis=1), 95)
put("np_simul_crit", float(crit_sim))

# 参数线性设定残差中的年龄结构（用局部线性光滑残差）
resid_par = fit0.resid
resid_smooth = ll_weights(grid_age, u, h_np) @ resid_par
put("resid_curvature_range", [float(resid_smooth.min()), float(resid_smooth.max())])

# ---------------------------------------------------------------------------
# 6. 半参数方法之一：部分线性模型（Robinson / Speckman profile LS）
# ---------------------------------------------------------------------------
def plm_fit(U, Y, ZZ, h, grid=None):
    S = Smoother(U, h, grid)
    Zt = np.column_stack([S.tilde(ZZ[:, j]) for j in range(ZZ.shape[1])])
    yt = S.tilde(Y)
    beta = np.linalg.solve(Zt.T @ Zt, Zt.T @ yt)
    resid = yt - Zt @ beta
    mhat = S.W @ (Y - ZZ @ beta)                 # 网格上的非参数分量
    rss = float(resid @ resid)
    G = np.linalg.solve(Zt.T @ Zt, Zt.T)         # β 对 tilde(ε) 的影响矩阵
    return dict(S=S, beta=beta, Zt=Zt, yt=yt, resid=resid, mhat=mhat, rss=rss,
                G=G, fitted=ZZ @ beta + S.apply(Y - ZZ @ beta), h=h)


def cv_h_plm(hs):
    errs = []
    for h in hs:
        e = 0.0
        for te in FOLDS:
            tr = np.setdiff1d(np.arange(n), te)
            try:
                f = plm_fit(u[tr], y[tr], Z[tr], h)
            except np.linalg.LinAlgError:
                return h, np.full(len(hs), np.inf)
            ut = np.unique(u[te])
            Wte = ll_weights(ut, u[tr], h)
            mte = (Wte @ (y[tr] - Z[tr] @ f["beta"]))[np.searchsorted(ut, u[te])]
            e += np.sum((y[te] - Z[te] @ f["beta"] - mte) ** 2)
        errs.append(e / n)
    return hs[int(np.argmin(errs))], np.array(errs)

h_plm, cv_plm = cv_h_plm(H_GRID)
put("h_plm", h_plm); put("cv_plm", dict(zip([str(h) for h in H_GRID], cv_plm.round(6).tolist())))

plm = plm_fit(u, y, Z, h_plm)
S = plm["S"]; beta = plm["beta"]; Zt = plm["Zt"]
put("plm_rss", plm["rss"])
put("plm_r2", 1 - plm["rss"] / tss)
put("plm_traceS", S.trace)
put("plm_sigma", float(np.sqrt(plm["rss"] / (n - p - S.trace))))

# 渐近（HC3 型 sandwich）标准误
omega = plm["resid"] ** 2
Ainv = np.linalg.inv(Zt.T @ Zt)
meat = Zt.T @ (Zt * omega[:, None])
cov_beta = Ainv @ meat @ Ainv
se_plm_asy = np.sqrt(np.diag(cov_beta))

# wild bootstrap：β、非参数分量，以及「参数 − 半参数」教育溢价之差的联合抽样分布
EDU_TERMS = ["< HS Grad", "Some College", "College Grad", "Advanced Degree"]
idx_edu = {nm: ZNAMES.index(nm) for nm in EDU_TERMS}
idx_edu_x0 = {nm: XN0.index(nm) for nm in EDU_TERMS}
fit_plm = plm["fitted"]
resid_plm = y - fit_plm
W_grid = ll_weights(grid_age, u, h_plm)
boot_beta = np.empty((N_BOOT, p))
boot_m = np.empty((N_BOOT, len(grid_age)))
boot_diff = np.empty((N_BOOT, len(EDU_TERMS)))
for b in range(N_BOOT):
    eps = resid_plm * rng.choice([-1.0, 1.0], size=n)
    ystar = fit_plm + eps
    et = S.tilde(eps)
    bb = beta + plm["G"] @ et
    b_par = X0inv @ ystar
    boot_beta[b] = bb
    boot_m[b] = W_grid @ (ystar - Z @ bb)
    boot_diff[b] = [b_par[idx_edu_x0[nm]] - bb[idx_edu[nm]] for nm in EDU_TERMS]
se_plm_boot = boot_beta.std(0, ddof=1)
ci_plm_boot = np.percentile(boot_beta, [2.5, 97.5], axis=0)
band_m = np.percentile(boot_m, [2.5, 97.5], axis=0)
ci_diff = np.percentile(boot_diff, [2.5, 97.5], axis=0)
put("plm_se_boot", dict(zip(ZNAMES, se_plm_boot.round(5).tolist())))
put("diff_par_minus_plm", {
    nm: dict(est=float(fit0.params[idx_edu_x0[nm]] - beta[idx_edu[nm]]),
             se=float(boot_diff[:, k].std(ddof=1)),
             lo=float(ci_diff[0, k]), hi=float(ci_diff[1, k]))
    for k, nm in enumerate(EDU_TERMS)})
sd_m = boot_m.std(0, ddof=1)
put("plm_simul_crit", float(np.percentile(np.max(np.abs((boot_m - boot_m.mean(0)) /
                                                        np.maximum(sd_m, 1e-10)), axis=1), 95)))

# 半参数年龄效应的导数（每 10 岁的对数工资变化）
d_plm = ll_deriv(grid_age, u, h_plm, y - Z @ beta) * 10
put("plm_deriv_30", float(np.interp(30, grid_age, d_plm)))
put("plm_deriv_45", float(np.interp(45, grid_age, d_plm)))
put("plm_deriv_60", float(np.interp(60, grid_age, d_plm)))
put("plm_peak_age", float(grid_age[np.argmax(np.interp(grid_age, S.grid, plm["mhat"]))]))
for nm, j in idx_edu.items():
    put(f"plm_beta_{nm.replace(' ', '_').replace('<', 'lt')}",
        dict(est=float(beta[j]), se_asy=float(se_plm_asy[j]), se_boot=float(se_plm_boot[j]),
             lo=float(ci_plm_boot[0, j]), hi=float(ci_plm_boot[1, j])))
    j0 = XN0.index(nm)
    put(f"par_beta_{nm.replace(' ', '_').replace('<', 'lt')}",
        dict(est=float(fit0.params[j0]), se=float(fit0.bse[j0]),
             lo=float(fit0.conf_int()[j0, 0]), hi=float(fit0.conf_int()[j0, 1])))

coef_long += [dict(model="PLM", term=nm, est=float(beta[j]), se=float(se_plm_boot[j]),
                   lo=float(ci_plm_boot[0, j]), hi=float(ci_plm_boot[1, j])) for j, nm in enumerate(ZNAMES)]

# 带宽敏感性
sens = []
for h in H_GRID:
    f = plm_fit(u, y, Z, h)
    sens.append(dict(h=h, rss=f["rss"],
                     **{nm: float(f["beta"][j]) for nm, j in idx_edu.items()}))
pd.DataFrame(sens).round(5).to_csv(OUT / "table_bandwidth_sensitivity.csv", index=False, encoding="utf-8-sig")
put("h_sensitivity", sens)

# ---------------------------------------------------------------------------
# 7. 半参数方法之二：广义似然比检验 H0: m(age) 为线性
# ---------------------------------------------------------------------------
lam_obs = n / 2 * np.log(rss0 / plm["rss"])
lam_star = np.empty(N_GLR)
for b in range(N_GLR):
    eps = fit0.resid * rng.choice([-1.0, 1.0], size=n)
    et = S.tilde(eps)
    r1vec = et - Zt @ (plm["G"] @ et)            # profile 最小二乘残差
    r0vec = eps - X0 @ (X0inv @ eps)             # 参数原假设下的残差
    r1 = float(r1vec @ r1vec)
    r0 = float(r0vec @ r0vec)
    lam_star[b] = n / 2 * np.log(max(r0, 1e-12) / max(r1, 1e-12))
p_glr = (1 + np.sum(lam_star >= lam_obs)) / (N_GLR + 1)
put("glr", dict(stat=float(lam_obs), p=float(p_glr), B=N_GLR,
                boot_mean=float(lam_star.mean()), boot_q95=float(np.percentile(lam_star, 95)),
                rss0=rss0, rss1=plm["rss"]))
np.save(OUT / "glr_bootstrap.npy", lam_star)

# ---------------------------------------------------------------------------
# 8. 半参数方法之三：分段多项式(样条筛法)可加部分线性模型
# ---------------------------------------------------------------------------
KNOTS = np.array([-1.0, 0.0, 1.0, 2.0, 3.0])   # 对应年龄 30,40,50,60,70

def spline_basis(d: pd.DataFrame):
    a = (d["age"].to_numpy(float) - 40.0) / 10.0
    blocks = [a, a ** 2, a ** 3] + [np.maximum(a - k, 0) ** 3 for k in KNOTS]
    yr = d["year"].to_numpy(int)
    year_dum = [(yr == t).astype(float) for t in range(2004, 2010)]
    return np.column_stack(blocks + year_dum)

B = spline_basis(df)
X_sieve = np.column_stack([np.ones((n, 1)), Z, B])
fit_sieve = OLS(y, X_sieve).fit(cov_type="HC3")
rss_sieve = float(np.sum(fit_sieve.resid ** 2))
put("sieve_rss", rss_sieve)
put("sieve_r2", 1 - rss_sieve / tss)
for nm, j in idx_edu.items():
    put(f"sieve_beta_{nm.replace(' ', '_').replace('<', 'lt')}",
        dict(est=float(fit_sieve.params[1 + j]), se=float(fit_sieve.bse[1 + j])))
coef_long += [dict(model="Sieve-APLM", term=nm, est=float(fit_sieve.params[1 + j]),
                   se=float(fit_sieve.bse[1 + j]),
                   lo=float(fit_sieve.conf_int()[1 + j, 0]), hi=float(fit_sieve.conf_int()[1 + j, 1]))
              for j, nm in enumerate(ZNAMES)]

# ---------------------------------------------------------------------------
# 9. 半参数方法之四：变系数模型（教育溢价随年龄变化）
# ---------------------------------------------------------------------------
X_vcm = np.column_stack([np.ones((n, 1)), Z])
kv = X_vcm.shape[1]
grid_vcm = np.linspace(26, 70, 23)
h_vcm = 8.0
beta_vcm = np.empty((len(grid_vcm), kv))
se_vcm = np.empty_like(beta_vcm)
for a, ue in enumerate(grid_vcm):
    d = u - ue
    w = np.exp(-0.5 * (d / h_vcm) ** 2)
    Xa = np.column_stack([X_vcm, X_vcm * d[:, None]])
    XW = Xa * np.sqrt(w)[:, None]
    coef, *_ = np.linalg.lstsq(XW, y * np.sqrt(w), rcond=None)
    beta_vcm[a] = coef[:kv]
    e = y - Xa @ coef
    bread = np.linalg.pinv(XW.T @ XW)
    meat = (XW * (w * e ** 2)[:, None]).T @ XW
    cov = bread @ meat @ bread
    se_vcm[a] = np.sqrt(np.maximum(np.diag(cov)[:kv], 0))
put("h_vcm", h_vcm)
j_col = 1 + ZNAMES.index("College Grad")
j_adv = 1 + ZNAMES.index("Advanced Degree")
put("vcm_college_30", float(np.interp(30, grid_vcm, beta_vcm[:, j_col])))
put("vcm_college_60", float(np.interp(60, grid_vcm, beta_vcm[:, j_col])))
put("vcm_college_30_se", float(np.interp(30, grid_vcm, se_vcm[:, j_col])))
put("vcm_college_60_se", float(np.interp(60, grid_vcm, se_vcm[:, j_col])))

# ---------------------------------------------------------------------------
# 10. 五折交叉验证的样本外预测误差（统一比较）
# ---------------------------------------------------------------------------
cv_models = {}
for pw in (1, 2, 3):
    X, _ = design_par(pw)
    errs = []
    for te in FOLDS:
        tr = np.setdiff1d(np.arange(n), te)
        b = np.linalg.lstsq(X[tr], y[tr], rcond=None)[0]
        errs.append(np.sum((y[te] - X[te] @ b) ** 2))
    cv_models[f"M{pw-1}"] = sum(errs) / n
errs = []
for te in FOLDS:
    tr = np.setdiff1d(np.arange(n), te)
    b = np.linalg.lstsq(X_sieve[tr], y[tr], rcond=None)[0]
    errs.append(np.sum((y[te] - X_sieve[te] @ b) ** 2))
cv_models["Sieve-APLM"] = sum(errs) / n
errs = []
for te in FOLDS:
    tr = np.setdiff1d(np.arange(n), te)
    f = plm_fit(u[tr], y[tr], Z[tr], h_plm)
    ut = np.unique(u[te])
    Wte = ll_weights(ut, u[tr], h_plm)
    mte = (Wte @ (y[tr] - Z[tr] @ f["beta"]))[np.searchsorted(ut, u[te])]
    errs.append(np.sum((y[te] - Z[te] @ f["beta"] - mte) ** 2))
cv_models["PLM"] = sum(errs) / n
put("cv_mse", cv_models)

# 模型拟合汇总
fit_rows = []
for tag, rss, dff in [("M0 (线性年龄)", rss0, X0.shape[1]),
                      ("M1 (二次年龄)", float(np.sum(par_fits[2][2].resid ** 2)), par_fits[2][0].shape[1]),
                      ("M2 (三次年龄)", float(np.sum(par_fits[3][2].resid ** 2)), par_fits[3][0].shape[1]),
                      ("PLM (核光滑)", plm["rss"], p + S.trace),
                      ("Sieve-APLM (样条)", rss_sieve, X_sieve.shape[1])]:
    fit_rows.append(dict(model=tag, RSS=round(rss, 4), R2=round(1 - rss / tss, 5),
                         df=round(dff, 2),
                         AIC=round(n * np.log(rss / n) + 2 * dff, 2),
                         BIC=round(n * np.log(rss / n) + np.log(n) * dff, 2),
                         CV_MSE=round(cv_models.get({"M0 (线性年龄)": "M0", "M1 (二次年龄)": "M1",
                                                     "M2 (三次年龄)": "M2", "PLM (核光滑)": "PLM",
                                                     "Sieve-APLM (样条)": "Sieve-APLM"}[tag], np.nan), 6)))
pd.DataFrame(fit_rows).to_csv(OUT / "table_model_fit.csv", index=False, encoding="utf-8-sig")
put("fit_rows", fit_rows)
pd.DataFrame(coef_long).to_csv(OUT / "table_coefficients.csv", index=False, encoding="utf-8-sig")

test_rows = [
    dict(name="Ramsey RESET (M0)", stat=R["par_reset_f"], p=R["par_reset_p"]),
    dict(name="Jarque-Bera (M0 残差)", stat=R["par_jb"], p=R["par_jb_p"]),
    dict(name="F 检验：年龄二/三次项 (M2)", stat=R["par_quad_f"], p=R["par_quad_p"]),
    dict(name="KS：大学 vs 高中 (对数工资)", stat=R["ks_college_hs"]["stat"], p=R["ks_college_hs"]["p"]),
    dict(name="KS：去均值后（形状差异）", stat=R["ks_centered"]["stat"], p=R["ks_centered"]["p"]),
    dict(name="Mann-Whitney：大学 vs 高中", stat=R["mw_college_hs"]["stat"], p=R["mw_college_hs"]["p"]),
    dict(name="Kruskal-Wallis：五教育组", stat=R["kw_edu"]["stat"], p=R["kw_edu"]["p"]),
    dict(name="GLR：H0 年龄效应线性", stat=R["glr"]["stat"], p=R["glr"]["p"]),
]
pd.DataFrame(test_rows).to_csv(OUT / "table_tests.csv", index=False, encoding="utf-8-sig")
put("test_rows", test_rows)

np.savez_compressed(OUT / "curves.npz", grid_age=grid_age, m_ll=m_ll, m_nw=m_nw,
                    band_np=band_np, m_deriv=m_deriv, resid_smooth=resid_smooth,
                    plm_m=np.interp(grid_age, S.grid, plm["mhat"]), plm_band=band_m,
                    plm_deriv=d_plm,
                    grid_vcm=grid_vcm, beta_vcm=beta_vcm, se_vcm=se_vcm,
                    kde_grid=grid_kde, lam_star=lam_star,
                    **{f"kde_{k.replace(' ', '_').replace('<', 'lt')}": v["dens"] for k, v in kde_info.items()})

# ---------------------------------------------------------------------------
# 11. 图形
# ---------------------------------------------------------------------------
# 图 1：数据概览
fig, ax = plt.subplots(1, 2, figsize=(10.5, 4.0))
ax[0].scatter(u, y, s=5, alpha=0.22, color=COLORS[0], linewidths=0)
ax[0].set_xlabel("年龄"); ax[0].set_ylabel("对数工资"); ax[0].set_title("(a) 年龄与对数工资散点")
binned = df.assign(bin=pd.cut(u, np.arange(18, 82, 5))).groupby("bin", observed=True)["logwage"].mean()
ax[0].plot([iv.mid for iv in binned.index], binned.values, "o-", color=COLORS[1], lw=1.8, label="5 岁组均值")
ax[0].legend()
boxdata = [df.loc[df.education == e, "logwage"] for e in desc.index]
bp = ax[1].boxplot(boxdata, tick_labels=["<HS", "HS", "Some\nCol", "College", "Advanced"], showfliers=False,
                   patch_artist=True, widths=0.6)
for patch, c in zip(bp["boxes"], COLORS):
    patch.set_facecolor(c); patch.set_alpha(0.55)
ax[1].set_ylabel("对数工资"); ax[1].set_title("(b) 教育组的对数工资分布")
savefig("fig1_data")

# 图 7：参数模型残差中的年龄结构（设定诊断）
fig, ax = plt.subplots(figsize=(10.5, 3.7))
ax.scatter(u, resid_par, s=5, alpha=0.16, color=COLORS[0], linewidths=0)
ax.plot(grid_age, resid_smooth, color=COLORS[1], lw=2.5, label="残差的局部线性光滑")
ax.axhline(0, color="grey", lw=1, ls="--")
ax.set_xlabel("年龄"); ax.set_ylabel("M0 残差")
ax.set_title("参数线性模型的残差—年龄图：系统性曲率")
ax.legend(frameon=False)
savefig("fig7_residual")

# 图 2：核密度估计
fig, ax = plt.subplots(figsize=(10.5, 4.3))
for (edu, info), c in zip(kde_info.items(), COLORS):
    ax.plot(grid_kde, info["dens"], color=c, lw=2, label=f"{edu} (h={info['h_silverman']:.3f})")
ax.set_xlabel("对数工资"); ax.set_ylabel("核密度估计"); ax.set_title("各教育组对数工资的核密度估计（高斯核，Silverman 规则带宽）")
ax.legend(frameon=False); ax.set_xlim(3.5, 5.9)
savefig("fig2_kde")

# 图 3：非参数回归与置信带
fig, ax = plt.subplots(1, 2, figsize=(10.5, 4.0))
ax[0].plot(grid_age, m_ll, color=COLORS[0], lw=2.2, label="局部线性")
ax[0].plot(grid_age, m_nw, color=COLORS[2], lw=1.8, ls="--", label="Nadaraya–Watson")
b0 = np.polyfit(u, y, 1)
ax[0].plot(grid_age, np.polyval(b0, grid_age), color=COLORS[1], lw=1.6, ls=":", label="参数线性")
ax[0].fill_between(grid_age, band_np[0], band_np[1], color=COLORS[0], alpha=0.16, label="95% 逐点 bootstrap 带")
ax[0].set_xlabel("年龄"); ax[0].set_ylabel("对数工资"); ax[0].set_title(f"(a) 非参数回归 (h={h_np})")
ax[0].legend(frameon=False, loc="lower right")
ax[1].plot(grid_age, m_deriv * 10, color=COLORS[3], lw=2)
ax[1].axhline(0, color="grey", lw=0.8)
ax[1].set_xlabel("年龄"); ax[1].set_ylabel("每 10 岁的对数工资变化")
ax[1].set_title(f"(b) 局部线性导数估计 m'(age)×10 (h={h_deriv})")
savefig("fig3_nonparametric")

# 图 4：PLM 结果
plm_m_interp = np.interp(grid_age, S.grid, plm["mhat"])
fig, ax = plt.subplots(1, 2, figsize=(10.5, 4.0))
ax[0].fill_between(grid_age, band_m[0], band_m[1], color=COLORS[0], alpha=0.18, label="95% bootstrap 带")
ax[0].plot(grid_age, plm_m_interp, color=COLORS[0], lw=2.2, label="PLM: m̂(age)")
lin = fit0.params[XN0.index("const")] + fit0.params[XN0.index("age/10")] * (grid_age - 40) / 10
ax[0].plot(grid_age, lin + (plm_m_interp.mean() - lin.mean()), color=COLORS[1], lw=1.7, ls="--", label="M0: 线性年龄（平移对齐）")
ax[0].set_xlabel("年龄"); ax[0].set_ylabel("调整后对数工资")
ax[0].set_title(f"(a) 部分线性模型的年龄效应 (h={h_plm})"); ax[0].legend(frameon=False)
keys = ["< HS Grad", "Some College", "College Grad", "Advanced Degree"]
short = ["<HS", "Some Col", "College", "Advanced"]
vals_par = [fit0.params[XN0.index(k)] for k in keys]
vals_plm = [beta[ZNAMES.index(k)] for k in keys]
err_par = [1.96 * fit0.bse[XN0.index(k)] for k in keys]
err_plm = [1.96 * se_plm_boot[ZNAMES.index(k)] for k in keys]
xx = np.arange(len(keys)); w = 0.35
ax[1].bar(xx - w / 2, vals_par, w, yerr=err_par, capsize=3, color=COLORS[1], alpha=0.85, label="M0 参数线性")
ax[1].bar(xx + w / 2, vals_plm, w, yerr=err_plm, capsize=3, color=COLORS[0], alpha=0.85, label="PLM 半参数")
ax[1].set_xticks(xx); ax[1].set_xticklabels(short); ax[1].axhline(0, color="grey", lw=0.8)
ax[1].set_ylabel("相对高中毕业生的对数工资差"); ax[1].set_title("(b) 教育溢价：参数 vs 半参数估计")
ax[1].legend(frameon=False)
savefig("fig4_plm")

# 图 5：GLR 与经验似然
fig, ax = plt.subplots(1, 2, figsize=(10.5, 4.0))
ax[0].hist(lam_star, bins=35, color=COLORS[0], alpha=0.6, density=True, label="H0 下 bootstrap 分布")
ax[0].set_xlim(0, max(11.0, np.percentile(lam_star, 99.9) * 1.2))
ax[0].text(0.97, 0.90, f"观测 λ = {lam_obs:.1f}\n（远超零假设分布，箭头方向 →）",
           transform=ax[0].transAxes, ha="right", va="top", color=COLORS[1], fontsize=9)
ax[0].annotate("", xy=(0.99, 0.72), xytext=(0.78, 0.72), xycoords="axes fraction",
               arrowprops=dict(arrowstyle="->", color=COLORS[1], lw=2))
ax[0].set_xlabel("广义似然比统计量 λ"); ax[0].set_ylabel("密度")
ax[0].set_title(f"(a) GLR 检验 (p={p_glr:.4f})"); ax[0].legend(frameon=False)
tgrid = np.linspace(theta_hat - 0.09, theta_hat + 0.09, 90)
elcurve = np.array([el2_minus2logR(t, col, hs) for t in tgrid])
ax[1].plot(tgrid, elcurve, color=COLORS[0], lw=2, label="−2 log 经验似然比")
ax[1].axhline(cut, color=COLORS[1], ls="--", lw=1.4, label="χ²₁(0.95)")
ax[1].axvline(el_lo, color=COLORS[2], ls=":", lw=1.5)
ax[1].axvline(el_hi, color=COLORS[2], ls=":", lw=1.5)
ax[1].set_xlabel("大学 − 高中：对数工资均值差 θ"); ax[1].set_ylabel("−2 log R(θ)")
ax[1].set_title("(b) 两样本经验似然置信区间"); ax[1].legend(frameon=False)
savefig("fig5_tests")

# 图 6：变系数模型与带宽敏感性
fig, ax = plt.subplots(1, 2, figsize=(10.5, 4.0))
for j, nm, c in [(j_col, "College Grad", COLORS[0]), (j_adv, "Advanced Degree", COLORS[3])]:
    ax[0].plot(grid_vcm, beta_vcm[:, j], color=c, lw=2, label=nm)
    ax[0].fill_between(grid_vcm, beta_vcm[:, j] - 1.96 * se_vcm[:, j],
                       beta_vcm[:, j] + 1.96 * se_vcm[:, j], color=c, alpha=0.15)
ax[0].axhline(beta[ZNAMES.index("College Grad")], color=COLORS[1], ls="--", lw=1.3, label="PLM 常数 College 系数")
ax[0].set_xlabel("年龄"); ax[0].set_ylabel("相对高中毕业生的对数工资差")
ax[0].set_title(f"(a) 变系数模型 (h={h_vcm})"); ax[0].legend(frameon=False)
sens_df = pd.DataFrame(sens)
for nm, c in zip(["College Grad", "Advanced Degree"], [COLORS[0], COLORS[3]]):
    ax[1].plot(sens_df.h, sens_df[nm], "o-", color=c, lw=1.6, ms=4, label=nm)
ax[1].axvline(h_plm, color="grey", ls="--", lw=1)
ax[1].set_xscale("log"); ax[1].set_xlabel("带宽 h（对数刻度）"); ax[1].set_ylabel("教育溢价估计")
ax[1].set_title("(b) PLM 估计对带宽的敏感性"); ax[1].legend(frameon=False)
savefig("fig6_vcm_sensitivity")

# ---------------------------------------------------------------------------
# 12. 导出
# ---------------------------------------------------------------------------
def jsonable(o):
    if isinstance(o, dict): return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [jsonable(v) for v in o]
    if isinstance(o, np.ndarray): return o.tolist()
    if isinstance(o, (np.floating,)): return float(o)
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (np.bool_,)): return bool(o)
    if isinstance(o, float) and (np.isnan(o) or np.isinf(o)): return None
    return o

with open(OUT / "results.json", "w", encoding="utf-8") as f:
    json.dump(jsonable(R), f, ensure_ascii=False, indent=2)

print("=" * 72)
print(f"n={n}, 年龄取值数={int(np.unique(u).size)}, h_NP={h_np}, h_PLM={h_plm}")
print(f"M0: R2={R['par_r2']:.4f} RESET p={R['par_reset_p']:.3g}  JB p={R['par_jb_p']:.3g}")
print(f"GLR={lam_obs:.2f}, bootstrap p={p_glr:.4f}, RSS0={rss0:.2f}, RSS1={plm['rss']:.2f}")
print("教育溢价 (M0 / PLM):")
for k in ["< HS Grad", "Some College", "College Grad", "Advanced Degree"]:
    tag = k.replace(' ', '_').replace('<', 'lt')
    print(f"  {k:18s} {R['par_beta_'+tag]['est']:+.4f}  {R['plm_beta_'+tag]['est']:+.4f}"
          f"  (boot SE {R['plm_beta_'+tag]['se_boot']:.4f})")
print(f"EL CI: [{el_lo:.4f}, {el_hi:.4f}]  Welch CI: [{R['welch_gap']['lo']:.4f}, {R['welch_gap']['hi']:.4f}]")
print("CV MSE:", cv_models)
print(f"结果已写入 {OUT}")
print("=" * 72)
