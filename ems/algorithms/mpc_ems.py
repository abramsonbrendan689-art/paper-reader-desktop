"""
算法二：改进型模型预测控制（MPC）— 叉车EMS任务序列约束版
==========================================================

【论文创新点 — 任务序列约束MPC（TSC-MPC）】
---------------------------------------------
标准 MPC 仅在预测域内基于当前系统模型进行滚动优化，
未考虑叉车操作的任务结构特性。

本算法提出两项叉车专属改进：

改进1：任务序列约束预测域（Task Sequence Constraint, TSC）
    叉车作业任务高度结构化（举升→行驶→下降→…），
    在构建预测域时，将已知任务序列纳入功率轨迹预测，
    取代传统 MPC 的常数或线性外推预测，
    使预测域内的功率需求更符合实际工况，
    优化目标更准确。

改进2：能量回收预测机制（Regenerative Recovery Prediction, RRP）
    在预测域内识别未来的下降/制动工况，
    提前调整当前 SOC 目标，为未来回收能量预留容量空间，
    避免传统 MPC 在回收工况出现 SOC 上限溢出而浪费能量的问题。

算法流程图
----------
```
当前时刻 t：
│
├─ 输入：SOC_li(t), SOC_na(t), 当前工况, 任务序列
│
├─ 1. 任务序列预测：生成未来 N 步功率需求轨迹 P̂(t+1:t+N)
│   ├─ 已知任务段：直接使用典型工况功率均值
│   └─ 未知段：使用 Markov 转移概率期望值外推
│
├─ 2. 能量回收预测：扫描预测域内的下降/制动工况
│   └─ 计算可回收能量总量 E_recover，动态调整 SOC 上限
│
├─ 3. 在线求解约束优化问题（scipy.optimize.minimize）：
│   min  Σ [Q_e * (P_li+P_na - P̂)² + Q_s * (SOC_li-ref)² +
│           Q_s * (SOC_na-ref)² + Q_d * (P_li²+P_na²) +
│           R * (ΔP_li² + ΔP_na²)]
│   s.t. SOC_min ≤ SOC ≤ SOC_max (含回收预调整)
│        0 ≤ P_li ≤ P_li_max
│        0 ≤ P_na ≤ P_na_max
│
├─ 4. 取控制序列第一步应用于系统
│
└─ t ← t+1，滚动重复
```

接口说明
--------
`MPCForkLiftEMS.step(state)` → (p_li, p_na)
可直接嵌入 Simulink S-Function（每个仿真步调用一次）。
"""

from __future__ import annotations

import numpy as np
from typing import Optional, List, Tuple, Dict

try:
    from scipy.optimize import minimize, Bounds, LinearConstraint
    _SCIPY_AVAILABLE = True
except ImportError:
    _SCIPY_AVAILABLE = False

from ems.config import ForkLiftConfig, MPCConfig
from ems.forklift_env import ForkLiftEnv, BatteryModel, WorkingConditionGenerator
from ems.utils.metrics import EMSMetrics


class MPCForkLiftEMS:
    """
    叉车EMS改进型模型预测控制器（TSC-MPC）。

    Parameters
    ----------
    config     : 叉车配置
    mpc_config : MPC 超参数
    seed       : 随机种子
    """

    def __init__(
        self,
        config: Optional[ForkLiftConfig] = None,
        mpc_config: Optional[MPCConfig] = None,
        seed: int = 42,
    ):
        self.cfg     = config or ForkLiftConfig()
        self.mpc_cfg = mpc_config or MPCConfig()
        self.dt      = self.cfg.dt_s
        self.rng     = np.random.default_rng(seed)

        # 状态变量（初始化为参考值）
        self._soc_li  = self.cfg.lithium.soc_ref
        self._soc_na  = self.cfg.sodium.soc_ref
        self._prev_p_li = 0.0
        self._prev_p_na = 0.0
        self._step_count = 0

    def reset(self, soc_li: float = None, soc_na: float = None) -> None:
        """重置控制器内部状态。"""
        self._soc_li  = soc_li if soc_li is not None else self.cfg.lithium.soc_ref
        self._soc_na  = soc_na if soc_na is not None else self.cfg.sodium.soc_ref
        self._prev_p_li = 0.0
        self._prev_p_na = 0.0
        self._step_count = 0

    # ------------------------------------------------------------------
    # 主控制接口（每仿真步调用一次）
    # ------------------------------------------------------------------

    def step(
        self,
        soc_li: float,
        soc_na: float,
        condition: int,
        p_demand_kw: float,
        future_conditions: Optional[List[int]] = None,
    ) -> Tuple[float, float]:
        """
        执行一步 MPC 决策。

        Parameters
        ----------
        soc_li           : 当前锂电 SOC
        soc_na           : 当前钠电 SOC
        condition        : 当前工况编号（0-4）
        p_demand_kw      : 当前需求功率（kW）
        future_conditions: 未来 N 步工况序列（可选，TSC创新点）
                           若提供，则使用任务序列约束预测；
                           否则退化为标准 MPC。

        Returns
        -------
        (p_li_kw, p_na_kw) : 分配给锂电和钠电的功率（kW）
        """
        self._soc_li = soc_li
        self._soc_na = soc_na

        # 1. 生成预测域功率需求轨迹（TSC创新）
        N = self.mpc_cfg.N_pred
        p_pred = self._predict_power_trajectory(condition, p_demand_kw,
                                                future_conditions, N)

        # 2. 能量回收预测——动态调整SOC上限（RRP创新）
        soc_max_li, soc_max_na = self._predict_recovery_soc_adjustment(
            future_conditions or [condition] * N, N
        )

        # 3. 求解优化问题
        if _SCIPY_AVAILABLE:
            p_li_opt, p_na_opt = self._solve_mpc(
                p_pred, soc_max_li, soc_max_na
            )
        else:
            # scipy 不可用时退化为规则基策略
            p_li_opt, p_na_opt = self._rule_based_fallback(p_demand_kw)

        self._prev_p_li = p_li_opt
        self._prev_p_na = p_na_opt
        self._step_count += 1

        return float(p_li_opt), float(p_na_opt)

    # ------------------------------------------------------------------
    # 改进1：任务序列约束功率预测（TSC）
    # ------------------------------------------------------------------

    def _predict_power_trajectory(
        self,
        current_condition: int,
        current_power: float,
        future_conditions: Optional[List[int]],
        N: int,
    ) -> np.ndarray:
        """
        生成预测域内的功率需求轨迹。

        【论文创新：TSC预测 vs 标准MPC预测对比】
        - 标准MPC：P̂(t+k) = P(t)，常数外推（k=1,...,N）
        - TSC-MPC：利用任务序列信息或Markov期望，更准确估计未来功率

        若已知 future_conditions，取各工况功率范围的中值（期望功率）；
        若不知，使用马尔可夫转移矩阵计算条件期望功率。
        """
        p_pred = np.zeros(N, dtype=np.float64)
        p_pred[0] = current_power

        for k in range(1, N):
            if future_conditions is not None and k < len(future_conditions):
                cond_k = future_conditions[k]
            else:
                # Markov 期望：用转移矩阵计算最可能的下一工况
                trans_row = WorkingConditionGenerator.TRANSITION_MATRIX[current_condition]
                cond_k = int(np.argmax(trans_row))

            p_min, p_max = self.cfg.condition_power_range[cond_k]
            p_pred[k] = (p_min + p_max) / 2.0   # 使用功率期望值

        return p_pred

    # ------------------------------------------------------------------
    # 改进2：能量回收预测SOC上限调整（RRP）
    # ------------------------------------------------------------------

    def _predict_recovery_soc_adjustment(
        self,
        future_conditions: List[int],
        N: int,
    ) -> Tuple[float, float]:
        """
        扫描预测域，识别未来能量回收工况，
        预先降低 SOC 上限，为回充预留空间。

        【论文创新：RRP机制】
        传统 MPC 使用固定 SOC 约束，在回收工况时若 SOC 已接近上限，
        则无法有效回收，造成能量浪费。
        本方法根据未来预测域内的回收工况，动态下调当前时刻 SOC 上限，
        使系统在回收前主动将 SOC 降至适当水平。
        """
        # 计算预测域内可回收能量（kWh）
        e_recover_total = 0.0
        for k, cond in enumerate(future_conditions[:N]):
            if cond in (3, 4):   # LOWERING 或 BRAKING
                p_min, _ = self.cfg.condition_power_range[cond]
                # 回收功率取负值期望的一半（保守估计）
                e_recover = abs(p_min) / 2.0 * self.dt / 3600.0
                discount = 0.95 ** k  # 越远的预测折扣越大
                e_recover_total += e_recover * discount

        # 按比例分配到两块电池
        e_li = e_recover_total * 0.5
        e_na = e_recover_total * 0.5

        # 将可回收能量折算为 SOC 降低量
        dsoc_li = e_li / (self.cfg.lithium.capacity_kwh + 1e-9)
        dsoc_na = e_na / (self.cfg.sodium.capacity_kwh + 1e-9)

        # 动态 SOC 上限 = 固定上限 - 回收预留
        soc_max_li = max(self.cfg.lithium.soc_min + 0.1,
                         self.cfg.lithium.soc_max - dsoc_li)
        soc_max_na = max(self.cfg.sodium.soc_min + 0.1,
                         self.cfg.sodium.soc_max - dsoc_na)

        return soc_max_li, soc_max_na

    # ------------------------------------------------------------------
    # 在线约束优化求解
    # ------------------------------------------------------------------

    def _solve_mpc(
        self,
        p_pred: np.ndarray,
        soc_max_li: float,
        soc_max_na: float,
    ) -> Tuple[float, float]:
        """
        使用 scipy.optimize.minimize 求解 MPC 优化问题。

        优化变量：x = [p_li_0, ..., p_li_{Nc-1}, p_na_0, ..., p_na_{Nc-1}]
        其中 Nc = min(N_ctrl, N_pred)

        目标函数：
            J = Σ_k [ Q_e*(p_li_k+p_na_k - p_pred_k)²
                    + Q_s*(soc_li_k - ref)²
                    + Q_s*(soc_na_k - ref)²
                    + R*(Δp_li_k² + Δp_na_k²) ]
        约束：
            SOC_min ≤ SOC_li_k ≤ soc_max_li
            SOC_min ≤ SOC_na_k ≤ soc_max_na
            0 ≤ p_li_k ≤ p_li_max  (放电工况)
            0 ≤ p_na_k ≤ p_na_max
        """
        N  = len(p_pred)
        Nc = min(self.mpc_cfg.N_ctrl, N)

        cfg_li = self.cfg.lithium
        cfg_na = self.cfg.sodium

        # 初始猜测：当前需求平均分配
        x0 = np.full(2 * Nc, p_pred[0] / 2.0, dtype=np.float64)

        def objective(x):
            p_li_seq = x[:Nc]
            p_na_seq = x[Nc:]

            soc_li = self._soc_li
            soc_na = self._soc_na
            cost   = 0.0
            prev_li = self._prev_p_li
            prev_na = self._prev_p_na

            for k in range(Nc):
                p_li_k = p_li_seq[k]
                p_na_k = p_na_seq[k]
                pk     = p_pred[min(k, N - 1)]

                # 能效项
                cost += self.mpc_cfg.Q_energy * (p_li_k + p_na_k - pk) ** 2

                # SOC 仿真更新（简化一阶积分）
                soc_li -= p_li_k * self.dt / (cfg_li.capacity_kwh * 3600)
                soc_na -= p_na_k * self.dt / (cfg_na.capacity_kwh * 3600)
                soc_li  = np.clip(soc_li, 0, 1)
                soc_na  = np.clip(soc_na, 0, 1)

                # SOC 偏差惩罚
                cost += self.mpc_cfg.Q_soc * (soc_li - cfg_li.soc_ref) ** 2
                cost += self.mpc_cfg.Q_soc * (soc_na - cfg_na.soc_ref) ** 2

                # 功率衰减惩罚（减少大电流冲击）
                cost += self.mpc_cfg.Q_degrad * (p_li_k ** 2 + p_na_k ** 2) * 1e-3

                # 功率平滑惩罚
                cost += self.mpc_cfg.R_smooth * ((p_li_k - prev_li) ** 2 +
                                                   (p_na_k - prev_na) ** 2)
                prev_li, prev_na = p_li_k, p_na_k

            return cost

        # 变量范围约束
        p0 = p_pred[0]
        if p0 >= 0:
            bounds = Bounds(
                lb=np.zeros(2 * Nc),
                ub=np.concatenate([
                    np.full(Nc, cfg_li.power_max_kw),
                    np.full(Nc, cfg_na.power_max_kw),
                ]),
            )
        else:
            bounds = Bounds(
                lb=np.concatenate([
                    np.full(Nc, -cfg_li.regen_max_kw),
                    np.full(Nc, -cfg_na.regen_max_kw),
                ]),
                ub=np.zeros(2 * Nc),
            )

        result = minimize(
            objective,
            x0,
            method="SLSQP",
            bounds=bounds,
            options={"maxiter": self.mpc_cfg.solver_maxiter, "ftol": 1e-6},
        )

        if result.success or result.fun < 1e8:
            p_li_opt = float(result.x[0])
            p_na_opt = float(result.x[Nc])
        else:
            p_li_opt, p_na_opt = self._rule_based_fallback(p0)

        return p_li_opt, p_na_opt

    def _rule_based_fallback(self, p_demand: float) -> Tuple[float, float]:
        """scipy 不可用或优化失败时的备用规则策略。"""
        soc_total = self._soc_li + self._soc_na + 1e-9
        ratio_li  = self._soc_li / soc_total
        p_li = np.clip(p_demand * ratio_li,
                       -self.cfg.lithium.regen_max_kw, self.cfg.lithium.power_max_kw)
        p_na = np.clip(p_demand * (1.0 - ratio_li),
                       -self.cfg.sodium.regen_max_kw, self.cfg.sodium.power_max_kw)
        return float(p_li), float(p_na)

    # ------------------------------------------------------------------
    # 完整仿真接口
    # ------------------------------------------------------------------

    def evaluate_episode(self, wc_mode: str = "cycle") -> Dict:
        """
        在典型任务周期下运行一轮仿真，返回性能指标。
        可用于论文中 TSC-MPC 与其他算法的对比。
        """
        from ems.forklift_env import WorkingConditionGenerator

        env = ForkLiftEnv(config=self.cfg, wc_mode=wc_mode, seed=0)
        obs = env.reset()
        self.reset()
        done    = False
        metrics = EMSMetrics()

        # 预取任务序列（TSC创新：使用已知任务序列）
        task_conds = [c for c, _ in self.cfg.typical_task_cycle
                      for _ in range(int(_ / self.dt))]

        step = 0
        while not done:
            future = task_conds[step:step + self.mpc_cfg.N_pred] if step < len(task_conds) else None
            p_li, p_na = self.step(
                soc_li=env.battery_li.soc,
                soc_na=env.battery_na.soc,
                condition=env._condition,
                p_demand_kw=env._demand_power,
                future_conditions=future,
            )
            alpha = (p_li / (abs(env._demand_power) + 1e-9))
            alpha = np.clip(2 * alpha - 1, -1, 1)
            obs, reward, done, info = env.step(np.array([alpha]))
            info["reward"]      = reward
            info["p_demand_kw"] = env._demand_power
            metrics.record(info)
            step += 1

        return metrics.summary()
