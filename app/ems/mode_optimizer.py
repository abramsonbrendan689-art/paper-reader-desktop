"""
叉车EMS — 工作模式优化决策模块
Forklift EMS — Battery Mode Optimization Decision Module

决策层次：
1. **硬约束过滤**：排除不满足功率范围约束的模式；
2. **规则基础预筛**：优先选择与当前工况匹配的模式；
3. **代价函数最小化**：综合考虑效率、SOC均衡、电池老化的加权代价；
4. **兜底策略**：若所有模式均不满足，选择 HYBRID（最大功率范围）。

代价函数（最小化）：
    cost = P_req / η - SOC_balance_bonus - mode_preference_bonus

其中：
    η             — 当前模式效率
    SOC_balance_bonus — SOC偏离理想区间的惩罚
    mode_preference_bonus — 工况-模式匹配的奖励
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from app.ems.config import BatteryMode, ForkliftCondition, ForkliftEMSConfig


class ModeOptimizer:
    """
    基于代价函数的叉车电池工作模式优化器。

    Parameters
    ----------
    config : ForkliftEMSConfig
        EMS全局配置对象。
    """

    def __init__(self, config: ForkliftEMSConfig) -> None:
        self._cfg = config

    # ------------------------------------------------------------------
    # 公开接口 / Public API
    # ------------------------------------------------------------------

    def select_mode(
        self,
        predicted_power_kw: float,
        condition: str,
        soc_li: float,
        soc_na: float,
    ) -> str:
        """
        根据预测功率、当前工况和电池状态选择最优工作模式。

        Parameters
        ----------
        predicted_power_kw : float
            上层预测的系统需求功率 (kW)，正=放电，负=充电/回收。
        condition : str
            当前工况标识符（ForkliftCondition 中的常量）。
        soc_li : float
            锂电当前SOC [0, 1]。
        soc_na : float
            钠电当前SOC [0, 1]。

        Returns
        -------
        str
            选定的工作模式标识符（BatteryMode 中的常量）。
        """
        candidates = self._filter_feasible_modes(predicted_power_kw, soc_li, soc_na)

        if not candidates:
            # 兜底：无论如何使用 HYBRID
            return BatteryMode.HYBRID

        if len(candidates) == 1:
            return candidates[0]

        # 从候选中选代价最小者
        best_mode, _ = self._minimize_cost(
            candidates, predicted_power_kw, condition, soc_li, soc_na
        )
        return best_mode

    def compute_power_split(
        self,
        mode: str,
        required_power_kw: float,
        soc_li: float,
        soc_na: float,
    ) -> Tuple[float, float]:
        """
        根据工作模式将总功率分配到锂电和钠电。

        Parameters
        ----------
        mode : str
            当前工作模式。
        required_power_kw : float
            系统需求总功率 (kW)。
        soc_li : float
            锂电SOC [0, 1]。
        soc_na : float
            钠电SOC [0, 1]。

        Returns
        -------
        Tuple[float, float]
            (li_power_kw, na_power_kw) — 锂电和钠电各自承担的功率 (kW)。
        """
        cfg = self._cfg
        spec_li = cfg.battery_mode_specs[BatteryMode.PURE_LITHIUM]
        spec_na = cfg.battery_mode_specs[BatteryMode.PURE_SODIUM]

        if mode == BatteryMode.PURE_LITHIUM:
            li_p = self._clamp(required_power_kw, spec_li.max_charge_kw, spec_li.max_discharge_kw)
            return li_p, 0.0

        if mode == BatteryMode.PURE_SODIUM:
            na_p = self._clamp(required_power_kw, spec_na.max_charge_kw, spec_na.max_discharge_kw)
            return 0.0, na_p

        if mode == BatteryMode.REGEN:
            # 按SOC余量比例分配回收功率（SOC低的电池多充）
            li_p, na_p = self._split_regen(required_power_kw, soc_li, soc_na)
            return li_p, na_p

        # HYBRID：按配置比例分配，并根据SOC做微调
        li_p, na_p = self._split_hybrid(required_power_kw, soc_li, soc_na)
        return li_p, na_p

    # ------------------------------------------------------------------
    # 内部实现 / Internal Implementation
    # ------------------------------------------------------------------

    def _filter_feasible_modes(
        self,
        power_kw: float,
        soc_li: float,
        soc_na: float,
    ) -> List[str]:
        """过滤掉不满足功率约束或SOC边界的模式，返回可行模式列表。"""
        cfg = self._cfg
        feasible: List[str] = []

        for mode_name, spec in cfg.battery_mode_specs.items():
            # 功率范围检查
            if power_kw > 0:
                # 放电：需求不超过最大放电能力
                if power_kw > spec.max_discharge_kw:
                    continue
                # SOC硬下限检查（锂电或钠电不足时排除依赖该电池的模式）
                if mode_name == BatteryMode.PURE_LITHIUM and soc_li <= cfg.soc_min:
                    continue
                if mode_name == BatteryMode.PURE_SODIUM and soc_na <= cfg.soc_min:
                    continue
                if mode_name == BatteryMode.HYBRID and (
                    soc_li <= cfg.soc_min and soc_na <= cfg.soc_min
                ):
                    continue
            else:
                # 充电/回收：回收功率不超过最大充电能力（注意两者均为负值）
                if power_kw < spec.max_charge_kw:
                    continue
                # SOC硬上限检查
                if mode_name == BatteryMode.PURE_LITHIUM and soc_li >= cfg.soc_max:
                    continue
                if mode_name == BatteryMode.PURE_SODIUM and soc_na >= cfg.soc_max:
                    continue
                if mode_name == BatteryMode.REGEN and (
                    soc_li >= cfg.soc_max and soc_na >= cfg.soc_max
                ):
                    continue

            feasible.append(mode_name)

        return feasible

    def _minimize_cost(
        self,
        candidates: List[str],
        power_kw: float,
        condition: str,
        soc_li: float,
        soc_na: float,
    ) -> Tuple[str, float]:
        """在候选模式中选代价最小者。"""
        best_mode = candidates[0]
        best_cost = float("inf")

        for mode_name in candidates:
            cost = self._compute_cost(mode_name, power_kw, condition, soc_li, soc_na)
            if cost < best_cost:
                best_cost = cost
                best_mode = mode_name

        return best_mode, best_cost

    def _compute_cost(
        self,
        mode_name: str,
        power_kw: float,
        condition: str,
        soc_li: float,
        soc_na: float,
    ) -> float:
        """
        计算单一模式的综合代价（越小越优）。

        代价 = 能量消耗代价 + SOC不均衡惩罚 - 工况匹配奖励
        """
        cfg = self._cfg
        spec = cfg.battery_mode_specs[mode_name]

        # 1. 能量消耗代价：P_req / η（效率越高代价越小）
        energy_cost = abs(power_kw) / max(spec.efficiency, 1e-6)

        # 2. SOC均衡惩罚：综合SOC偏离理想区间越远惩罚越大
        avg_soc = (soc_li + soc_na) / 2.0
        ideal_soc = (cfg.soc_optimal_low + cfg.soc_optimal_high) / 2.0
        soc_penalty = abs(avg_soc - ideal_soc) * 10.0

        # 3. 工况-模式匹配奖励
        preference_bonus = 0.0
        if condition in spec.preferred_conditions:
            preference_bonus = 5.0  # 匹配时降低代价

        # 4. 钠电护体惩罚：钠电低SOC时避免纯钠电放电
        if mode_name == BatteryMode.PURE_SODIUM and soc_na < cfg.soc_optimal_low:
            soc_penalty += 8.0

        # 5. 锂电护体惩罚：锂电低SOC时避免纯锂电放电
        if mode_name == BatteryMode.PURE_LITHIUM and soc_li < cfg.soc_optimal_low:
            soc_penalty += 8.0

        return energy_cost + soc_penalty - preference_bonus

    def _split_hybrid(
        self,
        power_kw: float,
        soc_li: float,
        soc_na: float,
    ) -> Tuple[float, float]:
        """
        混合模式功率分配：基础比例 + SOC动态修正。

        若两个电池SOC均充足，按 hybrid_lithium_ratio 分配；
        否则向SOC较高的电池倾斜。
        """
        cfg = self._cfg
        spec_li = cfg.battery_mode_specs[BatteryMode.PURE_LITHIUM]
        spec_na = cfg.battery_mode_specs[BatteryMode.PURE_SODIUM]

        # 基础比例
        li_ratio = cfg.hybrid_lithium_ratio
        na_ratio = 1.0 - li_ratio

        # SOC动态修正：根据SOC比值调整分配
        total_soc = soc_li + soc_na
        if total_soc > 1e-6:
            li_ratio = soc_li / total_soc
            na_ratio = soc_na / total_soc

        li_p = power_kw * li_ratio
        na_p = power_kw * na_ratio

        # 各自裁剪至可行范围
        if power_kw >= 0:
            li_p = min(li_p, spec_li.max_discharge_kw)
            na_p = min(na_p, spec_na.max_discharge_kw)
        else:
            li_p = max(li_p, spec_li.max_charge_kw)
            na_p = max(na_p, spec_na.max_charge_kw)

        return li_p, na_p

    def _split_regen(
        self,
        power_kw: float,
        soc_li: float,
        soc_na: float,
    ) -> Tuple[float, float]:
        """
        制动回收模式功率分配：SOC余量大的电池少充，SOC余量小的电池多充。
        """
        cfg = self._cfg
        spec_li = cfg.battery_mode_specs[BatteryMode.PURE_LITHIUM]
        spec_na = cfg.battery_mode_specs[BatteryMode.PURE_SODIUM]

        # 剩余容量（距上限距离）越大，可以接收更多回收功率
        headroom_li = max(cfg.soc_max - soc_li, 0.0)
        headroom_na = max(cfg.soc_max - soc_na, 0.0)
        total_headroom = headroom_li + headroom_na

        if total_headroom < 1e-6:
            # 两个电池都满了，无法回收
            return 0.0, 0.0

        li_ratio = headroom_li / total_headroom
        na_ratio = headroom_na / total_headroom

        li_p = power_kw * li_ratio  # 负值
        na_p = power_kw * na_ratio  # 负值

        li_p = max(li_p, spec_li.max_charge_kw)
        na_p = max(na_p, spec_na.max_charge_kw)

        return li_p, na_p

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))
