"""
叉车EMS — 基于有限状态机（FSM）的工况识别模块
Forklift EMS — FSM-Based Operating Condition Recognizer

工况转移规则（优先级从高到低）：
1. 举升速度 > lifting_min              → LIFTING
2. 举升速度 < descending_max           → DESCENDING
3. 加速度 ≥ accelerating_min           → ACCELERATING
4. 行驶速度 ≥ driving_min              → DRIVING
5. 否则                                → STANDBY

每个工况均设有最小停留时间，防止短暂扰动导致状态抖动。
"""

from __future__ import annotations

from app.ems.config import ForkliftCondition, ForkliftEMSConfig


class ConditionRecognizer:
    """
    基于规则优先级 + 最小停留时间的叉车工况 FSM 识别器。

    Parameters
    ----------
    config : ForkliftEMSConfig
        EMS全局配置对象。
    dt : float
        控制采样周期 (s)，用于计时最小停留时间。
    """

    def __init__(self, config: ForkliftEMSConfig, dt: float = 0.1) -> None:
        self._cfg = config
        self._dt = dt
        self._current = ForkliftCondition.STANDBY
        self._candidate: str | None = None
        self._candidate_timer: float = 0.0

    # ------------------------------------------------------------------
    # 公开接口 / Public API
    # ------------------------------------------------------------------

    @property
    def current_condition(self) -> str:
        """返回当前已确认的工况标识符。"""
        return self._current

    def update(
        self,
        speed: float,
        acceleration: float,
        lift_velocity: float,
    ) -> str:
        """
        根据最新传感器数据更新工况识别状态机。

        Parameters
        ----------
        speed : float
            叉车行驶速度 (m/s)，须 ≥ 0。
        acceleration : float
            叉车纵向加速度 (m/s²)，正值=加速，负值=减速。
        lift_velocity : float
            叉臂速度 (m/s)，正值=上升，负值=下降，0=停止。

        Returns
        -------
        str
            当前确认的工况标识符（ForkliftCondition 中的常量）。
        """
        raw = self._classify(speed, acceleration, lift_velocity)
        self._current = self._debounce(raw)
        return self._current

    def reset(self) -> None:
        """重置状态机到初始待机状态。"""
        self._current = ForkliftCondition.STANDBY
        self._candidate = None
        self._candidate_timer = 0.0

    # ------------------------------------------------------------------
    # 内部实现 / Internal Implementation
    # ------------------------------------------------------------------

    def _classify(
        self,
        speed: float,
        acceleration: float,
        lift_velocity: float,
    ) -> str:
        """
        按优先级规则对当前传感器数据进行分类，返回"原始"工况标签。

        优先级（高→低）：举升 > 下降 > 加速 > 行驶 > 待机
        """
        cfg = self._cfg

        # 1. 举升：叉臂以足够速度上升
        if lift_velocity >= cfg.lift_velocity_lifting_min:
            return ForkliftCondition.LIFTING

        # 2. 下降：叉臂以足够速度下降（制动能量可回收）
        if lift_velocity <= cfg.lift_velocity_descending_max:
            return ForkliftCondition.DESCENDING

        # 3. 加速：正向加速度超过阈值
        if acceleration >= cfg.accel_accelerating_min:
            return ForkliftCondition.ACCELERATING

        # 4. 行驶：速度超过行驶阈值
        if speed >= cfg.speed_driving_min:
            return ForkliftCondition.DRIVING

        # 5. 默认：待机
        return ForkliftCondition.STANDBY

    def _debounce(self, raw: str) -> str:
        """
        最小停留时间防抖：只有候选工况连续保持超过 min_dwell_time_s 才被确认。
        """
        min_dwell = self._cfg.min_dwell_time_s

        if raw == self._current:
            # 仍在当前工况，重置候选计时器
            self._candidate = None
            self._candidate_timer = 0.0
            return self._current

        if raw == self._candidate:
            self._candidate_timer += self._dt
            if self._candidate_timer >= min_dwell:
                # 候选工况已保持足够长，正式切换
                confirmed = self._candidate
                self._candidate = None
                self._candidate_timer = 0.0
                return confirmed
        else:
            # 新的候选工况，重新计时
            self._candidate = raw
            self._candidate_timer = self._dt

        return self._current
