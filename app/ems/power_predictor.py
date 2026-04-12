"""
叉车EMS — 基于查表法的功率预测模块
Forklift EMS — Lookup-Table Based Power Predictor

实现方式：
- 根据当前工况从配置表中读取平均/峰值功率；
- 可选择在平均功率和峰值功率之间线性插值（通过负载因子 load_factor）；
- 根据电池SOC状态对预测功率做微调（SOC低时适当降低放电功率）；
- 提供前瞻预测接口：基于当前工况和历史统计估计未来功率序列。

查表法是叉车EMS功率预测的推荐方案，因为：
  1. 叉车工况边界清晰、可重复性高；
  2. 无需大量训练数据；
  3. 计算开销极小，适合嵌入式/实时控制。
"""

from __future__ import annotations

from typing import List

from app.ems.config import ForkliftCondition, ForkliftEMSConfig


class PowerPredictor:
    """
    基于工况-功率查表的叉车功率预测器。

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

    def predict(
        self,
        condition: str,
        soc_li: float,
        soc_na: float,
        load_factor: float = 0.7,
    ) -> float:
        """
        预测当前工况下的需求功率（kW）。

        Parameters
        ----------
        condition : str
            当前工况标识符（ForkliftCondition 中的常量）。
        soc_li : float
            锂电当前SOC [0, 1]。
        soc_na : float
            钠电当前SOC [0, 1]。
        load_factor : float
            负载因子 [0, 1]，0 = 轻载（取平均功率），1 = 满载（取峰值功率）。
            默认 0.7，对应叉车中度工作负载。

        Returns
        -------
        float
            预测的系统需求功率 (kW)。正值=放电，负值=充电/回收。
        """
        load_factor = max(0.0, min(1.0, load_factor))
        base_power = self._lookup_power(condition, load_factor)
        adjusted = self._apply_soc_correction(base_power, soc_li, soc_na)
        return adjusted

    def predict_horizon(
        self,
        condition: str,
        soc_li: float,
        soc_na: float,
        load_factor: float = 0.7,
        steps: int = 1,
    ) -> List[float]:
        """
        返回未来 ``steps`` 步的功率预测序列。

        当前实现：对当前工况功率重复 steps 次（零阶保持法）。
        可扩展为时间序列预测（LSTM/GRU）而不影响接口。

        Parameters
        ----------
        condition : str
            当前工况标识符。
        soc_li : float
            锂电当前SOC [0, 1]。
        soc_na : float
            钠电当前SOC [0, 1]。
        load_factor : float
            负载因子 [0, 1]。
        steps : int
            预测步数，须 ≥ 1。

        Returns
        -------
        List[float]
            长度为 ``steps`` 的功率预测序列 (kW)。
        """
        p = self.predict(condition, soc_li, soc_na, load_factor)
        return [p] * max(1, steps)

    def get_condition_mean_power(self, condition: str) -> float:
        """返回指定工况的配置平均功率 (kW)，不考虑SOC修正。"""
        profile = self._cfg.condition_power_profiles.get(condition)
        if profile is None:
            return 0.0
        return profile.mean_kw

    def get_condition_peak_power(self, condition: str) -> float:
        """返回指定工况的配置峰值功率 (kW)，不考虑SOC修正。"""
        profile = self._cfg.condition_power_profiles.get(condition)
        if profile is None:
            return 0.0
        return profile.peak_kw

    # ------------------------------------------------------------------
    # 内部实现 / Internal Implementation
    # ------------------------------------------------------------------

    def _lookup_power(self, condition: str, load_factor: float) -> float:
        """
        从工况功率表中按负载因子线性插值得到基础功率。

        base_power = mean + load_factor * (peak - mean)
        """
        profile = self._cfg.condition_power_profiles.get(condition)
        if profile is None:
            return 0.0

        mean_p = profile.mean_kw
        peak_p = profile.peak_kw

        # 对于回收工况，峰值比均值功率绝对值更大（更负），保持插值方向一致
        base_power = mean_p + load_factor * (peak_p - mean_p)
        return base_power

    def _apply_soc_correction(
        self,
        base_power: float,
        soc_li: float,
        soc_na: float,
    ) -> float:
        """
        根据电池SOC状态对基础功率进行修正：
        - 放电工况：若综合SOC偏低，适当降低功率请求（保护电池）；
        - 回收工况：若综合SOC偏高，降低回收功率（避免过充）。
        """
        cfg = self._cfg
        avg_soc = (soc_li + soc_na) / 2.0

        if base_power > 0:
            # 放电场景：硬下限优先检查，再检查软下限
            if avg_soc <= cfg.soc_min:
                # 低于硬下限，禁止放电（返回0）
                return 0.0
            if avg_soc < cfg.soc_optimal_low:
                # SOC低于软下限，限制最大放电深度
                ratio = avg_soc / cfg.soc_optimal_low
                return base_power * max(0.5, ratio)
        else:
            # 回收/充电场景（base_power ≤ 0）：硬上限优先检查，再检查软上限
            if avg_soc >= cfg.soc_max:
                # 超过硬上限，禁止充电
                return 0.0
            if avg_soc > cfg.soc_optimal_high:
                # SOC高于软上限，限制回收功率
                ratio = (cfg.soc_max - avg_soc) / (cfg.soc_max - cfg.soc_optimal_high)
                return base_power * max(0.1, ratio)

        return base_power
