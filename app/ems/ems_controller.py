"""
叉车EMS — 上层主控制器
Forklift EMS — Upper-Layer Main Controller

集成工况识别、功率预测和模式优化三个子模块，
对外暴露统一的单步执行接口 ``step()``，
使其可直接被 Simulink S-Function 或 MATLAB Function Block 调用。

典型调用流程：
    ems = EMSController(config, dt=0.1)
    result = ems.step(speed, acceleration, lift_velocity, soc_li, soc_na)
    # result.condition / result.predicted_power_kw / result.battery_mode
    # result.li_power_kw / result.na_power_kw
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.ems.condition_recognizer import ConditionRecognizer
from app.ems.config import ForkliftEMSConfig
from app.ems.mode_optimizer import ModeOptimizer
from app.ems.power_predictor import PowerPredictor


@dataclass
class EMSStepResult:
    """
    单步EMS决策结果，包含完整的上层控制输出。

    Attributes
    ----------
    condition : str
        当前确认的工况标识符。
    predicted_power_kw : float
        预测的系统需求总功率 (kW)。
    battery_mode : str
        选定的电池工作模式标识符。
    li_power_kw : float
        分配给锂电的功率 (kW)，正=放电，负=充电。
    na_power_kw : float
        分配给钠电的功率 (kW)，正=放电，负=充电。
    timestamp_s : float
        当前仿真时间 (s)。
    """

    condition: str
    predicted_power_kw: float
    battery_mode: str
    li_power_kw: float
    na_power_kw: float
    timestamp_s: float = 0.0


class EMSController:
    """
    叉车混合储能上层EMS控制器。

    Parameters
    ----------
    config : ForkliftEMSConfig, optional
        EMS配置，若不传入则使用默认配置。
    dt : float
        控制采样周期 (s)，默认 0.1 s（10 Hz）。
    """

    def __init__(
        self,
        config: Optional[ForkliftEMSConfig] = None,
        dt: float = 0.1,
    ) -> None:
        self._cfg = config or ForkliftEMSConfig()
        self._dt = dt
        self._t = 0.0

        self._recognizer = ConditionRecognizer(self._cfg, dt=dt)
        self._predictor = PowerPredictor(self._cfg)
        self._optimizer = ModeOptimizer(self._cfg)

    # ------------------------------------------------------------------
    # 公开接口 / Public API
    # ------------------------------------------------------------------

    def step(
        self,
        speed: float,
        acceleration: float,
        lift_velocity: float,
        soc_li: float,
        soc_na: float,
        load_factor: float = 0.7,
    ) -> EMSStepResult:
        """
        执行单步EMS上层决策。

        Parameters
        ----------
        speed : float
            叉车行驶速度 (m/s)，须 ≥ 0。
        acceleration : float
            叉车纵向加速度 (m/s²)，正=加速，负=减速。
        lift_velocity : float
            叉臂速度 (m/s)，正=上升，负=下降，0=停止。
        soc_li : float
            锂电当前SOC [0, 1]。
        soc_na : float
            钠电当前SOC [0, 1]。
        load_factor : float
            当前负载因子 [0, 1]，影响功率预测插值比例，默认 0.7。

        Returns
        -------
        EMSStepResult
            本步决策结果，包含工况、预测功率、工作模式和功率分配。
        """
        # 1. 工况识别
        condition = self._recognizer.update(speed, acceleration, lift_velocity)

        # 2. 功率预测
        predicted_power = self._predictor.predict(
            condition, soc_li, soc_na, load_factor
        )

        # 3. 模式优化决策
        mode = self._optimizer.select_mode(predicted_power, condition, soc_li, soc_na)

        # 4. 功率分配
        li_p, na_p = self._optimizer.compute_power_split(
            mode, predicted_power, soc_li, soc_na
        )

        result = EMSStepResult(
            condition=condition,
            predicted_power_kw=predicted_power,
            battery_mode=mode,
            li_power_kw=li_p,
            na_power_kw=na_p,
            timestamp_s=self._t,
        )

        self._t += self._dt
        return result

    def reset(self) -> None:
        """重置控制器内部状态（仿真重启时调用）。"""
        self._recognizer.reset()
        self._t = 0.0

    @property
    def config(self) -> ForkliftEMSConfig:
        """返回当前使用的配置对象。"""
        return self._cfg

    @property
    def current_time_s(self) -> float:
        """返回当前仿真时间 (s)。"""
        return self._t
