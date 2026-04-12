"""
叉车混合储能仿真环境模型
=========================

本模块实现了用于强化学习训练和MPC验证的叉车混合储能仿真环境。
环境遵循 OpenAI Gym 接口规范，可直接对接 Stable-Baselines3 等框架。

【论文创新点 1 — 基于工况感知的叉车专属状态空间（WCAS）】
-------------------------------------------------------------
传统EMS状态空间通常仅包含 [SOC_li, SOC_na, P_demand]，
本环境将叉车工况编码（one-hot）、负载率、历史功率梯度
共同纳入状态空间，使智能体具备"前馈预判"能力：

  state = [
      SOC_li,          # 锂电SOC（归一化到[0,1]）
      SOC_na,          # 钠电SOC（归一化到[0,1]）
      P_demand_norm,   # 归一化需求功率
      wc_0,...,wc_4,   # 工况one-hot编码（5维）
      load_ratio,      # 负载率（实际载重/最大载重）
      dP_dt_norm,      # 功率变化率（归一化）
  ]  →  dim = 10

【论文创新点 2 — 电池寿命-能效双目标奖励塑造（DORS）】
---------------------------------------------------------
奖励函数同时考虑：
  r = w_eff * r_efficiency
    - w_deg * r_degradation
    - w_soc * r_soc_imbalance
    + r_recover_bonus

其中 r_recover_bonus 在能量回收工况（LOWERING/BRAKING）
额外给予正奖励，鼓励智能体优先利用再生制动能量。
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple, List

from ems.config import ForkLiftConfig, SACConfig


# ---------------------------------------------------------------------------
# 电池单体动力学模型
# ---------------------------------------------------------------------------

class BatteryModel:
    """
    简化等效电路电池模型（一阶 RC 模型简化版）。

    SOC 更新方程：
        dSOC/dt = -P_batt / (capacity * eta)

    衰减模型（基于半经验安时积分法）：
        degradation += |P_batt| * dt / capacity * deg_coeff
    """

    def __init__(self, config, dt: float):
        self.cfg = config
        self.dt = dt
        self.soc: float = config.soc_ref
        self.degradation: float = 0.0    # 累计容量损失（归一化）
        self.cumulative_throughput: float = 0.0  # 累计吞吐量（kWh）

    def reset(self, soc_init: Optional[float] = None) -> None:
        self.soc = soc_init if soc_init is not None else self.cfg.soc_ref
        self.degradation = 0.0
        self.cumulative_throughput = 0.0

    def step(self, power_kw: float) -> Tuple[float, float, bool]:
        """
        执行一步仿真。

        Parameters
        ----------
        power_kw : 注入功率（正=放电，负=充电）

        Returns
        -------
        soc_new : 更新后 SOC
        deg_step : 本步衰减量
        violated : 是否违反 SOC 约束
        """
        if power_kw >= 0:
            eta = self.cfg.eta_discharge
        else:
            eta = self.cfg.eta_charge

        # SOC 更新（Ah 积分法）
        delta_soc = -(power_kw * self.dt) / (self.cfg.capacity_kwh * 3600.0 / 3600.0)
        if power_kw >= 0:
            delta_soc /= eta
        else:
            delta_soc *= eta

        soc_new = np.clip(self.soc + delta_soc, 0.0, 1.0)
        violated = (soc_new < self.cfg.soc_min) or (soc_new > self.cfg.soc_max)
        self.soc = soc_new

        # 衰减计算（半经验安时积分法）
        throughput = abs(power_kw) * self.dt / 3600.0   # kWh
        deg_step = throughput * self.cfg.degradation_coeff
        self.degradation += deg_step
        self.cumulative_throughput += throughput

        return soc_new, deg_step, violated


# ---------------------------------------------------------------------------
# 工况发生器
# ---------------------------------------------------------------------------

class WorkingConditionGenerator:
    """
    叉车工况序列生成器。

    支持两种模式：
    1. 按典型任务周期循环（`mode='cycle'`）
    2. 随机工况切换（`mode='random'`，用于强化学习探索）
    """

    # 各工况之间的转移概率矩阵（行=当前，列=下一工况）
    TRANSITION_MATRIX = np.array([
        # IDLE  LIFT   DRIVE  LOWER  BRAKE
        [0.10, 0.30,  0.50,  0.05,  0.05],   # IDLE
        [0.10, 0.05,  0.10,  0.70,  0.05],   # LIFTING
        [0.10, 0.20,  0.40,  0.10,  0.20],   # DRIVING
        [0.15, 0.05,  0.60,  0.10,  0.10],   # LOWERING
        [0.20, 0.10,  0.60,  0.05,  0.05],   # BRAKING
    ])

    def __init__(self, config: ForkLiftConfig, mode: str = "random", seed: int = 42):
        self.cfg = config
        self.mode = mode
        self.rng = np.random.default_rng(seed)
        self._cycle = list(config.typical_task_cycle)
        self._cycle_idx = 0
        self._remaining = self._cycle[0][1]
        self.current_condition: int = 0

    def reset(self) -> int:
        self.current_condition = 0
        self._cycle_idx = 0
        self._remaining = self._cycle[0][1]
        return self.current_condition

    def step(self, dt: float) -> Tuple[int, float]:
        """
        推进一步，返回当前工况编号及对应需求功率（kW）。
        """
        if self.mode == "cycle":
            self._remaining -= dt
            if self._remaining <= 0:
                self._cycle_idx = (self._cycle_idx + 1) % len(self._cycle)
                cond, dur = self._cycle[self._cycle_idx]
                self.current_condition = cond
                self._remaining = dur
        else:
            # 随机马尔可夫切换
            probs = self.TRANSITION_MATRIX[self.current_condition]
            if self.rng.random() < 0.05:    # 5%概率切换工况
                self.current_condition = int(self.rng.choice(5, p=probs))

        # 在工况功率范围内随机采样需求功率
        p_min, p_max = self.cfg.condition_power_range[self.current_condition]
        power = float(self.rng.uniform(p_min, p_max))
        return self.current_condition, power


# ---------------------------------------------------------------------------
# 叉车EMS仿真环境（Gym-compatible）
# ---------------------------------------------------------------------------

class ForkLiftEnv:
    """
    叉车混合储能EMS仿真环境。

    状态空间（dim=11）
    ------------------
    [SOC_li, SOC_na, P_demand_norm, wc_0..4, load_ratio, dP_dt_norm]

    动作空间（dim=1，连续）
    -----------------------
    alpha ∈ [-1, 1]：
        alpha > 0 → 锂电提供比例 = alpha，钠电提供 (1 - alpha)
        alpha < 0 → 能量回收时，abs(alpha) 比例回充锂电，其余回充钠电

    奖励函数（双目标奖励塑造 DORS）
    --------------------------------
    r = w_eff * r_efficiency
      - w_deg * (r_deg_li + r_deg_na)
      - w_soc * r_soc_imbalance
      + r_recover_bonus
      - penalty_violation

    Simulink 集成接口
    -----------------
    调用 `env.step_interface(obs, action)` 可直接嵌入 MATLAB S-Function。
    """

    STATE_DIM = 10
    ACTION_DIM = 1

    def __init__(
        self,
        config: Optional[ForkLiftConfig] = None,
        sac_config: Optional[SACConfig] = None,
        wc_mode: str = "random",
        seed: int = 42,
    ):
        self.cfg = config or ForkLiftConfig()
        self.sac_cfg = sac_config or SACConfig()
        dt = self.cfg.dt_s

        self.battery_li = BatteryModel(self.cfg.lithium, dt)
        self.battery_na = BatteryModel(self.cfg.sodium, dt)
        self.wc_gen = WorkingConditionGenerator(self.cfg, mode=wc_mode, seed=seed)

        self._step_count: int = 0
        self._prev_power: float = 0.0
        self._load_kg: float = 0.0
        self._demand_power: float = 0.0
        self._condition: int = 0

        # 功率归一化基准（最大总功率）
        self._p_norm = self.cfg.lithium.power_max_kw + self.cfg.sodium.power_max_kw

    # ------------------------------------------------------------------
    # Gym-style 接口
    # ------------------------------------------------------------------

    def reset(self, soc_li_init: float = None, soc_na_init: float = None) -> np.ndarray:
        """重置环境，返回初始状态向量。"""
        self.battery_li.reset(soc_li_init)
        self.battery_na.reset(soc_na_init)
        self._condition = self.wc_gen.reset()
        self._step_count = 0
        self._prev_power = 0.0
        self._load_kg = float(np.random.uniform(0, self.cfg.max_load_kg))
        self._condition, self._demand_power = self.wc_gen.step(self.cfg.dt_s)
        return self._build_state()

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, dict]:
        """
        执行一步控制。

        Parameters
        ----------
        action : shape (1,)，功率分配系数 alpha ∈ [-1, 1]

        Returns
        -------
        next_state, reward, done, info
        """
        alpha = float(np.clip(action[0], -1.0, 1.0))
        p_total = self._demand_power

        # 功率分配
        p_li, p_na = self._allocate_power(alpha, p_total)

        # 电池仿真
        soc_li, deg_li, viol_li = self.battery_li.step(p_li)
        soc_na, deg_na, viol_na = self.battery_na.step(p_na)

        # 计算奖励
        reward = self._compute_reward(p_li, p_na, deg_li, deg_na, viol_li or viol_na)

        self._step_count += 1
        done = self._step_count >= self.cfg.episode_steps

        # 更新下一步工况
        self._prev_power = p_total
        self._condition, self._demand_power = self.wc_gen.step(self.cfg.dt_s)

        info = {
            "soc_li": soc_li,
            "soc_na": soc_na,
            "p_li": p_li,
            "p_na": p_na,
            "condition": self._condition,
            "deg_li": deg_li,
            "deg_na": deg_na,
        }
        return self._build_state(), reward, done, info

    # ------------------------------------------------------------------
    # Simulink S-Function 集成接口
    # ------------------------------------------------------------------

    def step_interface(
        self,
        soc_li: float,
        soc_na: float,
        p_demand_kw: float,
        condition_id: int,
        load_kg: float,
        alpha: float,
    ) -> dict:
        """
        单步接口，适用于 MATLAB S-Function 或外部调用。

        Parameters
        ----------
        soc_li      : 锂电当前 SOC
        soc_na      : 钠电当前 SOC
        p_demand_kw : 当前需求功率（kW）
        condition_id: 当前工况编号（0-4）
        load_kg     : 当前载重（kg）
        alpha       : 控制动作，功率分配系数 ∈ [-1, 1]

        Returns
        -------
        dict with keys: p_li, p_na, soc_li_new, soc_na_new
        """
        self.battery_li.soc = soc_li
        self.battery_na.soc = soc_na
        self._condition = condition_id
        self._load_kg = load_kg
        self._demand_power = p_demand_kw

        p_li, p_na = self._allocate_power(alpha, p_demand_kw)
        soc_li_new, _, _ = self.battery_li.step(p_li)
        soc_na_new, _, _ = self.battery_na.step(p_na)

        return {
            "p_li_kw": p_li,
            "p_na_kw": p_na,
            "soc_li_new": soc_li_new,
            "soc_na_new": soc_na_new,
        }

    # ------------------------------------------------------------------
    # 内部辅助方法
    # ------------------------------------------------------------------

    def _allocate_power(self, alpha: float, p_total: float) -> Tuple[float, float]:
        """
        根据分配系数 alpha 将总功率分配到锂电和钠电。

        alpha ∈ [0, 1]  → 放电分配比例（正功率）
        alpha ∈ [-1, 0) → 充电分配比例（负功率/能量回收）
        """
        if p_total >= 0:
            ratio = (alpha + 1.0) / 2.0   # 映射 [-1,1] → [0,1]
            p_li = np.clip(p_total * ratio, 0, self.cfg.lithium.power_max_kw)
            p_na = np.clip(p_total * (1.0 - ratio), 0, self.cfg.sodium.power_max_kw)
        else:
            ratio = (alpha + 1.0) / 2.0
            p_li = np.clip(p_total * ratio, -self.cfg.lithium.regen_max_kw, 0)
            p_na = np.clip(p_total * (1.0 - ratio), -self.cfg.sodium.regen_max_kw, 0)
        return float(p_li), float(p_na)

    def _compute_reward(
        self,
        p_li: float,
        p_na: float,
        deg_li: float,
        deg_na: float,
        violated: bool,
    ) -> float:
        """
        双目标奖励塑造（DORS）函数。

        能效奖励：系统总效率（考虑电池内阻损耗）
        衰减惩罚：本步循环衰减量加权求和
        SOC平衡：两电池 SOC 与参考值的偏差
        回收奖励：下降/制动工况额外正奖励
        违约惩罚：SOC 越界大惩罚
        """
        w = self.sac_cfg

        # 1. 能效奖励（1 - 损耗/需求）
        p_demand = self._demand_power
        p_loss_li = (p_li ** 2) * self.cfg.lithium.r_internal / 1000.0
        p_loss_na = (p_na ** 2) * self.cfg.sodium.r_internal / 1000.0
        p_loss_total = p_loss_li + p_loss_na
        if abs(p_demand) > 1e-3:
            r_efficiency = w.w_efficiency * (1.0 - p_loss_total / (abs(p_demand) + 1e-6))
        else:
            r_efficiency = 0.0

        # 2. 电池衰减惩罚
        r_degradation = w.w_degradation * (deg_li + deg_na) * 1e4

        # 3. SOC 平衡惩罚
        soc_dev_li = abs(self.battery_li.soc - self.cfg.lithium.soc_ref)
        soc_dev_na = abs(self.battery_na.soc - self.cfg.sodium.soc_ref)
        r_soc = w.w_soc_balance * (soc_dev_li + soc_dev_na)

        # 4. 能量回收奖励（叉车特有工况）
        r_recover = 0.0
        if self._condition in (3, 4) and p_demand < 0:
            r_recover = 0.2   # 成功回收额外奖励

        # 5. 约束违约惩罚
        penalty = -5.0 if violated else 0.0

        reward = r_efficiency - r_degradation - r_soc + r_recover + penalty
        return float(reward * w.reward_scale)

    def _build_state(self) -> np.ndarray:
        """构建状态向量（dim=11）"""
        soc_li = self.battery_li.soc
        soc_na = self.battery_na.soc
        p_norm = self._demand_power / self._p_norm

        # 工况 one-hot 编码（5维）
        wc_onehot = np.zeros(5, dtype=np.float32)
        wc_onehot[self._condition] = 1.0

        load_ratio = self._load_kg / self.cfg.max_load_kg
        dp_dt = (self._demand_power - self._prev_power) / (self._p_norm + 1e-6)

        state = np.array([
            soc_li, soc_na, p_norm,
            *wc_onehot,
            load_ratio, dp_dt,
        ], dtype=np.float32)
        return state

    @property
    def observation_space_shape(self) -> Tuple[int]:
        return (self.STATE_DIM,)

    @property
    def action_space_bounds(self) -> Tuple[float, float]:
        return (-1.0, 1.0)

    def get_episode_summary(self) -> dict:
        """返回本轮仿真统计摘要（用于论文结果记录）"""
        return {
            "total_degradation_li": self.battery_li.degradation,
            "total_degradation_na": self.battery_na.degradation,
            "throughput_li_kwh": self.battery_li.cumulative_throughput,
            "throughput_na_kwh": self.battery_na.cumulative_throughput,
            "final_soc_li": self.battery_li.soc,
            "final_soc_na": self.battery_na.soc,
        }
