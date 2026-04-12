"""
算法三：带精英策略的非支配排序遗传算法（NSGA-II）— 叉车EMS多目标参数优化
==========================================================================

【论文创新点 — 叉车适应性多目标演化优化框架】
-------------------------------------------------
标准 NSGA-II (Deb et al., 2002) 是经典的多目标演化算法，
广泛用于工程优化问题。本文将其应用于叉车EMS参数优化，
并进行以下叉车专属改进：

改进1：双目标函数设计（能效 + 衰减）
    目标1 (f1)：最小化全任务周期能量消耗（节能）
    目标2 (f2)：最小化电池循环寿命衰减量（延寿）
    两目标相互竞争，NSGA-II 求解 Pareto 最优前沿，
    为工程师提供"节能-延寿"权衡的决策空间。

改进2：叉车专属染色体编码（EMS参数向量）
    每个个体编码为叉车EMS规则策略的参数集：
    chromosome = [
        soc_ref_li,      # 锂电SOC目标参考值 ∈ [0.3, 0.7]
        soc_ref_na,      # 钠电SOC目标参考值 ∈ [0.3, 0.7]
        alpha_lift,      # 举升工况锂电分配比例 ∈ [0.2, 0.8]
        alpha_drive,     # 行驶工况锂电分配比例 ∈ [0.2, 0.8]
        alpha_recover,   # 回收工况锂电回充比例 ∈ [0.2, 0.8]
        p_switch_thresh, # 高功率判断阈值（kW）∈ [20, 60]
        soc_imbal_weight,# SOC不均衡惩罚权重 ∈ [0.1, 2.0]
    ]

改进3：精英保留与拥挤度排序（NSGA-II标准 + 叉车适应性初始化）
    使用叉车典型工况数据初始化部分种群（知识引导初始化），
    加速收敛，减少无效探索。

算法流程图
----------
```
初始化种群 P(0)（含知识引导个体）
│
└─ 主循环（代数 g = 0, 1, ..., N_gen）：
   ├─ 1. 评估适应度：对每个个体 x ∈ P(g)，
   │      运行叉车仿真，计算 (f1_energy, f2_degradation)
   ├─ 2. 非支配排序：将 P(g) 分层为 F_1, F_2, ...
   ├─ 3. 拥挤度计算：计算每层中个体的拥挤距离
   ├─ 4. 选择：二元锦标赛选择（优先非支配秩，次优拥挤度）
   ├─ 5. 交叉：模拟二进制交叉（SBX）
   ├─ 6. 变异：多项式变异（PM）
   ├─ 7. 合并后代与父代：R = P(g) ∪ Q(g)
   └─ 8. 精英保留：从 R 中按非支配秩+拥挤度选取 N 个精英 → P(g+1)

输出：Pareto 最优前沿（能效 vs 电池寿命 权衡解集）
      → 工程师从中选取满足实际需求的最优参数
```
"""

from __future__ import annotations

import numpy as np
from typing import Optional, List, Tuple, Dict

from ems.config import ForkLiftConfig, NSGA2Config
from ems.forklift_env import ForkLiftEnv
from ems.utils.metrics import EMSMetrics


# ---------------------------------------------------------------------------
# 染色体（个体）
# ---------------------------------------------------------------------------

CHROMOSOME_DIM = 7   # 参数向量维度

# 各基因的下界和上界
GENE_BOUNDS = np.array([
    [0.30, 0.70],   # soc_ref_li
    [0.30, 0.70],   # soc_ref_na
    [0.20, 0.80],   # alpha_lift
    [0.20, 0.80],   # alpha_drive
    [0.20, 0.80],   # alpha_recover
    [20.0, 60.0],   # p_switch_thresh (kW)
    [0.10,  2.0],   # soc_imbal_weight
])


# ---------------------------------------------------------------------------
# 知识引导初始化种群
# ---------------------------------------------------------------------------

def _knowledge_guided_individuals() -> List[np.ndarray]:
    """
    提供几组叉车工程先验知识参数作为初始种群的一部分，
    加速算法收敛（叉车专属改进）。

    先验1：节能优先（多用钠电，钠电成本低衰减慢）
    先验2：延寿优先（SOC保持在中间安全区间，均衡分配）
    先验3：均衡策略（常规EMS默认参数）
    """
    return [
        np.array([0.50, 0.50, 0.30, 0.30, 0.30, 35.0, 0.5]),  # 节能优先
        np.array([0.55, 0.55, 0.50, 0.50, 0.50, 40.0, 1.0]),  # 均衡
        np.array([0.60, 0.60, 0.70, 0.70, 0.70, 45.0, 1.5]),  # 延寿优先
    ]


# ---------------------------------------------------------------------------
# NSGA-II 核心算子
# ---------------------------------------------------------------------------

def _fast_non_dominated_sort(F: np.ndarray) -> List[List[int]]:
    """
    快速非支配排序（NSGA-II 核心步骤）。

    Parameters
    ----------
    F : shape (N, n_obj)，目标函数值矩阵（最小化）

    Returns
    -------
    fronts : List of lists，fronts[0] 为 Pareto 前沿索引
    """
    N = len(F)
    domination_count = np.zeros(N, dtype=int)    # 被支配个数
    dominated_set    = [[] for _ in range(N)]    # 支配的个体集合
    fronts           = [[]]

    for i in range(N):
        for j in range(i + 1, N):
            if _dominates(F[i], F[j]):
                dominated_set[i].append(j)
                domination_count[j] += 1
            elif _dominates(F[j], F[i]):
                dominated_set[j].append(i)
                domination_count[i] += 1

        if domination_count[i] == 0:
            fronts[0].append(i)

    current_front = 0
    while fronts[current_front]:
        next_front = []
        for i in fronts[current_front]:
            for j in dominated_set[i]:
                domination_count[j] -= 1
                if domination_count[j] == 0:
                    next_front.append(j)
        current_front += 1
        fronts.append(next_front)

    return [f for f in fronts if f]


def _dominates(f1: np.ndarray, f2: np.ndarray) -> bool:
    """f1 支配 f2（最小化：f1 的每一维 ≤ f2 且至少一维 <）"""
    return bool(np.all(f1 <= f2) and np.any(f1 < f2))


def _crowding_distance(F: np.ndarray, front: List[int]) -> np.ndarray:
    """计算一层 front 中每个个体的拥挤距离。"""
    n = len(front)
    dist = np.zeros(n)
    if n <= 2:
        dist[:] = np.inf
        return dist

    n_obj = F.shape[1]
    for m in range(n_obj):
        sorted_idx = np.argsort(F[front, m])
        dist[sorted_idx[0]]  = np.inf
        dist[sorted_idx[-1]] = np.inf
        f_range = F[front[sorted_idx[-1]], m] - F[front[sorted_idx[0]], m]
        if f_range < 1e-12:
            continue
        for k in range(1, n - 1):
            dist[sorted_idx[k]] += (
                F[front[sorted_idx[k + 1]], m] - F[front[sorted_idx[k - 1]], m]
            ) / f_range

    return dist


def _sbx_crossover(
    p1: np.ndarray, p2: np.ndarray, eta_c: float, prob: float, rng
) -> Tuple[np.ndarray, np.ndarray]:
    """
    模拟二进制交叉（SBX）。

    eta_c 越大，子代越接近父代（开发）；越小越具探索性。
    """
    c1, c2 = p1.copy(), p2.copy()
    for i in range(len(p1)):
        if rng.random() > prob:
            continue
        if abs(p1[i] - p2[i]) < 1e-10:
            continue
        u = rng.random()
        if u <= 0.5:
            beta = (2 * u) ** (1.0 / (eta_c + 1))
        else:
            beta = (1.0 / (2 * (1 - u))) ** (1.0 / (eta_c + 1))
        c1[i] = 0.5 * ((1 + beta) * p1[i] + (1 - beta) * p2[i])
        c2[i] = 0.5 * ((1 - beta) * p1[i] + (1 + beta) * p2[i])
        c1[i] = np.clip(c1[i], GENE_BOUNDS[i, 0], GENE_BOUNDS[i, 1])
        c2[i] = np.clip(c2[i], GENE_BOUNDS[i, 0], GENE_BOUNDS[i, 1])
    return c1, c2


def _polynomial_mutation(
    x: np.ndarray, eta_m: float, prob: float, rng
) -> np.ndarray:
    """多项式变异（PM）"""
    y = x.copy()
    for i in range(len(x)):
        if rng.random() > prob:
            continue
        delta = GENE_BOUNDS[i, 1] - GENE_BOUNDS[i, 0]
        u = rng.random()
        if u < 0.5:
            delta_q = (2 * u) ** (1.0 / (eta_m + 1)) - 1
        else:
            delta_q = 1 - (2 * (1 - u)) ** (1.0 / (eta_m + 1))
        y[i] = np.clip(y[i] + delta_q * delta,
                       GENE_BOUNDS[i, 0], GENE_BOUNDS[i, 1])
    return y


# ---------------------------------------------------------------------------
# NSGA-II 主类
# ---------------------------------------------------------------------------

class NSGA2ForkLiftEMS:
    """
    叉车EMS多目标参数优化 — NSGA-II 实现。

    优化目标
    --------
    f1 (最小化)：全仿真周期总能量消耗（kWh）
    f2 (最小化)：全仿真周期总电池衰减量（归一化）

    Parameters
    ----------
    config      : 叉车配置
    nsga2_config: NSGA-II 超参数
    seed        : 随机种子
    """

    def __init__(
        self,
        config: Optional[ForkLiftConfig] = None,
        nsga2_config: Optional[NSGA2Config] = None,
        seed: int = 42,
    ):
        self.cfg        = config or ForkLiftConfig()
        self.nsga2_cfg  = nsga2_config or NSGA2Config()
        self.rng        = np.random.default_rng(seed)
        self.population: Optional[np.ndarray] = None
        self.objectives: Optional[np.ndarray] = None
        self.pareto_front: Optional[np.ndarray] = None
        self.pareto_objectives: Optional[np.ndarray] = None
        self.history: List[Dict] = []

    # ------------------------------------------------------------------
    # 适应度评估（叉车EMS仿真）
    # ------------------------------------------------------------------

    def _evaluate(self, chromosome: np.ndarray) -> Tuple[float, float]:
        """
        将染色体解码为EMS规则策略参数，运行叉车仿真，
        返回双目标函数值 (f1_energy_kwh, f2_degradation)。

        染色体解码
        ----------
        [soc_ref_li, soc_ref_na, alpha_lift, alpha_drive,
         alpha_recover, p_switch_thresh, soc_imbal_weight]
        """
        (soc_ref_li, soc_ref_na, alpha_lift,
         alpha_drive, alpha_recover,
         p_switch_thresh, soc_imbal_w) = chromosome

        env = ForkLiftEnv(config=self.cfg, wc_mode="cycle", seed=0)
        obs = env.reset(soc_li_init=soc_ref_li, soc_na_init=soc_ref_na)
        done = False
        total_energy_kwh = 0.0
        total_degradation = 0.0

        while not done:
            cond   = env._condition
            p_dem  = env._demand_power
            soc_li = env.battery_li.soc
            soc_na = env.battery_na.soc

            # 基于染色体参数的规则策略
            alpha = self._rule_policy(
                cond, p_dem, soc_li, soc_na,
                alpha_lift, alpha_drive, alpha_recover,
                p_switch_thresh, soc_imbal_w,
            )

            obs, reward, done, info = env.step(np.array([alpha]))

            # 累计能耗（kWh）
            p_total = abs(info["p_li"]) + abs(info["p_na"])
            total_energy_kwh += p_total * self.cfg.dt_s / 3600.0

            # 累计衰减
            total_degradation += info["deg_li"] + info["deg_na"]

        return float(total_energy_kwh), float(total_degradation)

    def _rule_policy(
        self,
        condition: int,
        p_demand: float,
        soc_li: float,
        soc_na: float,
        alpha_lift: float,
        alpha_drive: float,
        alpha_recover: float,
        p_switch_thresh: float,
        soc_imbal_w: float,
    ) -> float:
        """根据染色体参数实现的规则策略，返回功率分配系数 alpha。"""
        # 基础分配比例
        if condition == 1:   # LIFTING
            base_alpha = alpha_lift
        elif condition in (2,):  # DRIVING
            base_alpha = alpha_drive
        elif condition in (3, 4):  # LOWERING/BRAKING
            base_alpha = alpha_recover
        else:
            base_alpha = 0.5

        # SOC 不均衡修正
        soc_diff = soc_li - soc_na
        alpha_adj = base_alpha - soc_imbal_w * soc_diff * 0.1

        return float(np.clip(2 * alpha_adj - 1, -1.0, 1.0))

    # ------------------------------------------------------------------
    # NSGA-II 主循环
    # ------------------------------------------------------------------

    def optimize(self, verbose: bool = True) -> np.ndarray:
        """
        运行 NSGA-II 优化，返回 Pareto 最优参数集。

        Returns
        -------
        pareto_front : shape (n_pareto, CHROMOSOME_DIM)，Pareto 最优个体
        """
        cfg  = self.nsga2_cfg
        N    = cfg.pop_size

        # 初始化种群（含知识引导个体）
        pop = np.zeros((N, CHROMOSOME_DIM), dtype=np.float64)
        guided = _knowledge_guided_individuals()
        for i, g in enumerate(guided[:N]):
            pop[i] = g
        for i in range(len(guided), N):
            pop[i] = self.rng.uniform(GENE_BOUNDS[:, 0], GENE_BOUNDS[:, 1])

        # 评估初始种群
        F = self._eval_population(pop, verbose, gen=0)

        for gen in range(1, cfg.n_gen + 1):
            # 生成子代
            offspring = self._generate_offspring(pop, F, cfg)

            # 合并父子代
            combined_pop = np.vstack([pop, offspring])
            combined_F   = np.vstack([F, self._eval_population(offspring, False)])

            # 精英选择
            pop, F = self._elite_selection(combined_pop, combined_F, N)

            # 记录当前 Pareto 前沿
            fronts = _fast_non_dominated_sort(F)
            pareto_idx = fronts[0]
            self.history.append({
                "gen": gen,
                "pareto_size": len(pareto_idx),
                "best_energy": float(F[pareto_idx, 0].min()),
                "best_degrad": float(F[pareto_idx, 1].min()),
            })

            if verbose and gen % 10 == 0:
                print(
                    f"[NSGA-II] Gen {gen:4d}/{cfg.n_gen} | "
                    f"Pareto={len(pareto_idx):3d} | "
                    f"Best Energy={F[pareto_idx, 0].min():.4f} kWh | "
                    f"Best Degrad={F[pareto_idx, 1].min():.6f}"
                )

        # 提取最终 Pareto 前沿
        fronts = _fast_non_dominated_sort(F)
        pareto_idx = fronts[0]
        self.population     = pop
        self.objectives     = F
        self.pareto_front   = pop[pareto_idx]
        self.pareto_objectives = F[pareto_idx]

        return self.pareto_front

    def _eval_population(
        self, pop: np.ndarray, verbose: bool = False, gen: int = -1
    ) -> np.ndarray:
        """评估整个种群的双目标函数值。"""
        N = len(pop)
        F = np.zeros((N, 2), dtype=np.float64)
        for i, chrom in enumerate(pop):
            F[i, 0], F[i, 1] = self._evaluate(chrom)
        if verbose:
            print(f"[NSGA-II] Gen {gen:4d} | Population evaluated ({N} individuals)")
        return F

    def _generate_offspring(
        self, pop: np.ndarray, F: np.ndarray, cfg: NSGA2Config
    ) -> np.ndarray:
        """通过选择、交叉、变异生成子代。"""
        N        = len(pop)
        fronts   = _fast_non_dominated_sort(F)
        ranks    = np.zeros(N, dtype=int)
        for r, front in enumerate(fronts):
            for idx in front:
                ranks[idx] = r
        crowding = np.zeros(N)
        for front in fronts:
            if len(front) > 2:
                cd = _crowding_distance(F, front)
                for i, idx in enumerate(front):
                    crowding[idx] = cd[i]
            else:
                for idx in front:
                    crowding[idx] = np.inf

        offspring = []
        while len(offspring) < N:
            # 二元锦标赛选择
            i1, i2 = self.rng.integers(0, N, 2)
            p1_idx = i1 if (ranks[i1] < ranks[i2] or
                            (ranks[i1] == ranks[i2] and crowding[i1] >= crowding[i2])) else i2
            i3, i4 = self.rng.integers(0, N, 2)
            p2_idx = i3 if (ranks[i3] < ranks[i4] or
                            (ranks[i3] == ranks[i4] and crowding[i3] >= crowding[i4])) else i4

            c1, c2 = _sbx_crossover(
                pop[p1_idx], pop[p2_idx],
                cfg.eta_c, cfg.crossover_prob, self.rng
            )
            c1 = _polynomial_mutation(c1, cfg.eta_m, cfg.mutation_prob, self.rng)
            c2 = _polynomial_mutation(c2, cfg.eta_m, cfg.mutation_prob, self.rng)
            offspring.extend([c1, c2])

        return np.array(offspring[:N], dtype=np.float64)

    def _elite_selection(
        self, pop: np.ndarray, F: np.ndarray, N: int
    ) -> Tuple[np.ndarray, np.ndarray]:
        """精英保留选择：按非支配秩和拥挤度选取 N 个精英。"""
        fronts = _fast_non_dominated_sort(F)
        selected, selected_F = [], []
        for front in fronts:
            if len(selected) + len(front) <= N:
                selected.extend(front)
                selected_F.extend(F[front])
            else:
                # 当前层不能全部放入，按拥挤度排序选取剩余名额
                needed = N - len(selected)
                cd     = _crowding_distance(F, front)
                sorted_cd = np.argsort(-cd)[:needed]
                for idx in sorted_cd:
                    selected.append(front[idx])
                    selected_F.append(F[front[idx]])
                break

        return pop[selected], np.array(selected_F)

    # ------------------------------------------------------------------
    # 结果展示与接口
    # ------------------------------------------------------------------

    def get_knee_point(self) -> np.ndarray:
        """
        从 Pareto 前沿中选取"膝点"（最均衡的折中解）。

        膝点定义：到两个极端点（最优节能和最优延寿）连线距离最大的点。
        适合工程实际中快速选取单一最优方案。
        """
        if self.pareto_objectives is None:
            raise RuntimeError("请先调用 optimize() 方法。")

        F = self.pareto_objectives
        # 归一化
        F_min, F_max = F.min(0), F.max(0)
        F_norm = (F - F_min) / (F_max - F_min + 1e-9)

        # 到 Pareto 前沿两端点连线的距离
        line = F_norm[-1] - F_norm[0]
        line_len = np.linalg.norm(line) + 1e-9
        distances = np.array([
            np.linalg.norm(np.cross(line, F_norm[0] - f)) / line_len
            for f in F_norm
        ])
        knee_idx = int(np.argmax(distances))
        return self.pareto_front[knee_idx]

    def summary_table(self) -> str:
        """输出 Pareto 前沿结果的 Markdown 表格（可直接插入论文附录）。"""
        if self.pareto_front is None:
            return "尚未运行优化，请先调用 optimize()。"

        header = ("| 序号 | SOC_ref_Li | SOC_ref_Na | α_举升 | α_行驶 | "
                  "α_回收 | 阈值(kW) | 均衡权重 | 能耗(kWh) | 衰减量 |")
        sep = "|" + "|".join(["------"] * 10) + "|"
        rows = [header, sep]
        for i, (chrom, obj) in enumerate(zip(self.pareto_front, self.pareto_objectives)):
            row = (f"| {i+1} | {chrom[0]:.3f} | {chrom[1]:.3f} | "
                   f"{chrom[2]:.3f} | {chrom[3]:.3f} | {chrom[4]:.3f} | "
                   f"{chrom[5]:.1f} | {chrom[6]:.2f} | "
                   f"{obj[0]:.4f} | {obj[1]:.6f} |")
            rows.append(row)
        return "\n".join(rows)
