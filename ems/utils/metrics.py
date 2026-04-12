"""
EMS 性能评估指标模块
====================

提供叉车EMS论文常用的评估指标计算工具，
支持单次仿真和多轮对比实验的统计汇总。

指标体系
--------
1. 能量效率（Energy Efficiency, EE）
2. 电池循环衰减量（Battery Degradation, BD）
3. SOC 均衡度（SOC Balance Index, SBI）
4. 能量回收率（Regenerative Recovery Rate, RRR）
5. 功率分配平滑度（Power Smoothness, PS）
"""

from __future__ import annotations

import numpy as np
from typing import List, Dict, Any


class EMSMetrics:
    """
    能量管理系统性能评估器。

    用法示例
    --------
    >>> metrics = EMSMetrics()
    >>> for step_info in episode_log:
    ...     metrics.record(step_info)
    >>> summary = metrics.summary()
    """

    def __init__(self):
        self._records: List[Dict[str, Any]] = []

    def reset(self) -> None:
        """清空历史记录，开始新一轮评估。"""
        self._records.clear()

    def record(self, info: Dict[str, Any]) -> None:
        """
        记录单步仿真数据。

        info 字段说明
        -------------
        p_demand_kw  : 需求功率（kW）
        p_li_kw      : 锂电实际功率（kW）
        p_na_kw      : 钠电实际功率（kW）
        deg_li       : 锂电本步衰减量
        deg_na       : 钠电本步衰减量
        soc_li       : 锂电 SOC
        soc_na       : 钠电 SOC
        condition    : 工况编号
        reward       : 本步奖励
        """
        self._records.append(info)

    def summary(self) -> Dict[str, float]:
        """计算并返回全部性能指标的汇总字典。"""
        if not self._records:
            return {}

        n = len(self._records)
        p_demand = np.array([r.get("p_demand_kw", 0.0) for r in self._records])
        p_li     = np.array([r.get("p_li_kw", r.get("p_li", 0.0)) for r in self._records])
        p_na     = np.array([r.get("p_na_kw", r.get("p_na", 0.0)) for r in self._records])
        deg_li   = np.array([r.get("deg_li",      0.0) for r in self._records])
        deg_na   = np.array([r.get("deg_na",      0.0) for r in self._records])
        soc_li   = np.array([r.get("soc_li",      0.5) for r in self._records])
        soc_na   = np.array([r.get("soc_na",      0.5) for r in self._records])
        cond     = np.array([r.get("condition",    0)   for r in self._records])
        rewards  = np.array([r.get("reward",       0.0) for r in self._records])

        # 1. 能量效率：实际交付能量 / 理论需求能量（考虑功率满足率）
        energy_demand    = np.sum(np.abs(p_demand))
        energy_delivered = np.sum(np.abs(p_li) + np.abs(p_na))
        # EE = 满足率（交付量/需求量），上限1.0；>1说明过供
        if energy_demand > 1e-6:
            ee = min(energy_delivered / (energy_demand + 1e-9), 1.0)
        else:
            ee = 1.0

        # 2. 总电池衰减
        total_deg = float(np.sum(deg_li) + np.sum(deg_na))

        # 3. SOC 均衡度（两电池与各自参考值的均方根偏差之和）
        sbi = float(np.sqrt(np.mean((soc_li - 0.55) ** 2)) +
                    np.sqrt(np.mean((soc_na - 0.55) ** 2)))

        # 4. 能量回收率（LOWERING/BRAKING工况回收电量 / 理论可回收量）
        regen_mask = np.isin(cond, [3, 4])
        regen_available = np.abs(p_demand[regen_mask]).sum() if regen_mask.any() else 0.0
        regen_actual    = np.abs((p_li + p_na)[regen_mask]).sum() if regen_mask.any() else 0.0
        rrr = regen_actual / (regen_available + 1e-9)

        # 5. 功率分配平滑度（功率变化量的标准差）
        p_total = p_li + p_na
        ps = float(np.std(np.diff(p_total))) if n > 1 else 0.0

        # 6. 平均奖励
        mean_reward = float(np.mean(rewards))

        return {
            "energy_efficiency":        round(float(ee),         4),
            "total_degradation":        round(total_deg,          6),
            "soc_balance_index":        round(float(sbi),         4),
            "regen_recovery_rate":      round(float(rrr),         4),
            "power_smoothness_std":     round(float(ps),          4),
            "mean_reward":              round(mean_reward,         4),
            "episode_steps":            n,
        }

    @staticmethod
    def compare(results: Dict[str, Dict[str, float]]) -> str:
        """
        生成多算法对比表格（Markdown 格式，可直接粘贴到论文附录）。

        Parameters
        ----------
        results : {算法名: summary字典}

        Returns
        -------
        Markdown 格式对比表格字符串
        """
        if not results:
            return ""

        metrics_order = [
            "energy_efficiency",
            "total_degradation",
            "soc_balance_index",
            "regen_recovery_rate",
            "power_smoothness_std",
            "mean_reward",
        ]
        metric_labels = {
            "energy_efficiency":    "能量效率 EE",
            "total_degradation":    "总衰减量 BD",
            "soc_balance_index":    "SOC均衡度 SBI",
            "regen_recovery_rate":  "能量回收率 RRR",
            "power_smoothness_std": "功率平滑度 PS (std)",
            "mean_reward":          "平均奖励",
        }

        algo_names = list(results.keys())
        header = "| 指标 | " + " | ".join(algo_names) + " |"
        sep    = "|------|" + "|".join(["------"] * len(algo_names)) + "|"
        rows = [header, sep]

        for key in metrics_order:
            label = metric_labels.get(key, key)
            vals = [str(results[a].get(key, "N/A")) for a in algo_names]
            rows.append(f"| {label} | " + " | ".join(vals) + " |")

        return "\n".join(rows)
