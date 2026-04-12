"""
叉车混合储能EMS — 参数化配置模块
Forklift Hybrid Energy Storage EMS — Parameterized Configuration Module

包含叉车典型工况功率表、电池规格参数及SOC管理边界。
Contains forklift typical operating-condition power profiles, battery specs,
and SOC management boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple


# ---------------------------------------------------------------------------
# 工况常量 / Operating Condition Constants
# ---------------------------------------------------------------------------

class ForkliftCondition:
    """叉车工况标识符（字符串常量）"""

    LIFTING = "LIFTING"            # 举升：大功率、短时间（10-30 s）
    DRIVING = "DRIVING"            # 行驶：中等功率、较长时间
    DESCENDING = "DESCENDING"      # 下降/制动：可回收能量（负功率）
    STANDBY = "STANDBY"            # 待机：低功率、长时间（电器负载）
    ACCELERATING = "ACCELERATING"  # 加速：功率突变


# ---------------------------------------------------------------------------
# 工作模式常量 / Battery Mode Constants
# ---------------------------------------------------------------------------

class BatteryMode:
    """电池工作模式标识符（字符串常量）"""

    PURE_LITHIUM = "PURE_LITHIUM"  # 纯锂电模式
    PURE_SODIUM = "PURE_SODIUM"    # 纯钠电模式
    HYBRID = "HYBRID"              # 混合模式（锂电+钠电）
    REGEN = "REGEN"                # 制动能量回收模式


# ---------------------------------------------------------------------------
# 数据类 / Data Classes
# ---------------------------------------------------------------------------

@dataclass
class ConditionPowerProfile:
    """单一工况功率特性参数"""

    mean_kw: float    # 平均功率 (kW)；负值 = 回收
    peak_kw: float    # 峰值功率 (kW)；负值 = 回收
    typical_duration_s: float  # 典型持续时间 (s)


@dataclass
class BatteryModeSpec:
    """单一工作模式的规格参数"""

    max_discharge_kw: float    # 最大放电功率 (kW)
    max_charge_kw: float       # 最大充电功率 (kW)，负值表示充电
    efficiency: float          # 充放电效率 [0, 1]
    # 可支持的工况列表（空列表 = 不限制）
    preferred_conditions: Tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# 主配置类 / Main Configuration Class
# ---------------------------------------------------------------------------

@dataclass
class ForkliftEMSConfig:
    """
    叉车混合储能EMS完整配置。

    所有数值均针对典型5吨内燃叉车改电动叉车场景设定，
    可根据实际车型和电池规格进行覆盖。
    """

    # -------------------------------------------------------------------
    # 工况识别阈值 / Condition Recognition Thresholds
    # -------------------------------------------------------------------

    # 速度阈值 (m/s)
    speed_standby_max: float = 0.05   # 低于此速度且无举升 → 待机
    speed_driving_min: float = 0.3    # 高于此速度 → 行驶

    # 加速度阈值 (m/s²)
    accel_accelerating_min: float = 0.5   # 正加速 → 加速工况
    accel_decelerating_max: float = -0.3  # 负加速 → 减速/下降辅助判断

    # 举升速度阈值 (m/s)：叉臂速度正值=上升，负值=下降
    lift_velocity_lifting_min: float = 0.05   # 高于此值 → 举升
    lift_velocity_descending_max: float = -0.05  # 低于此值 → 下降

    # FSM最小停留时间 (s)：防止工况频繁切换（抖动）
    min_dwell_time_s: float = 0.5

    # -------------------------------------------------------------------
    # 叉车典型工况功率特性表 / Forklift Condition Power Profile Table
    # -------------------------------------------------------------------

    condition_power_profiles: Dict[str, ConditionPowerProfile] = field(
        default_factory=lambda: {
            ForkliftCondition.LIFTING: ConditionPowerProfile(
                mean_kw=15.0,
                peak_kw=25.0,
                typical_duration_s=20.0,
            ),
            ForkliftCondition.DRIVING: ConditionPowerProfile(
                mean_kw=8.0,
                peak_kw=15.0,
                typical_duration_s=120.0,
            ),
            ForkliftCondition.DESCENDING: ConditionPowerProfile(
                mean_kw=-5.0,   # 负值 = 回收
                peak_kw=-10.0,
                typical_duration_s=15.0,
            ),
            ForkliftCondition.STANDBY: ConditionPowerProfile(
                mean_kw=1.0,
                peak_kw=2.0,
                typical_duration_s=300.0,
            ),
            ForkliftCondition.ACCELERATING: ConditionPowerProfile(
                mean_kw=20.0,
                peak_kw=30.0,
                typical_duration_s=5.0,
            ),
        }
    )

    # -------------------------------------------------------------------
    # 电池工作模式规格 / Battery Mode Specifications
    # -------------------------------------------------------------------

    battery_mode_specs: Dict[str, BatteryModeSpec] = field(
        default_factory=lambda: {
            BatteryMode.PURE_LITHIUM: BatteryModeSpec(
                max_discharge_kw=30.0,
                max_charge_kw=-20.0,
                efficiency=0.96,
                preferred_conditions=(
                    ForkliftCondition.DRIVING,
                    ForkliftCondition.STANDBY,
                ),
            ),
            BatteryMode.PURE_SODIUM: BatteryModeSpec(
                max_discharge_kw=20.0,
                max_charge_kw=-15.0,
                efficiency=0.93,
                preferred_conditions=(
                    ForkliftCondition.STANDBY,
                    ForkliftCondition.DRIVING,
                ),
            ),
            BatteryMode.HYBRID: BatteryModeSpec(
                max_discharge_kw=45.0,  # 锂电30 + 钠电20，留裕量
                max_charge_kw=-30.0,
                efficiency=0.95,
                preferred_conditions=(
                    ForkliftCondition.LIFTING,
                    ForkliftCondition.ACCELERATING,
                ),
            ),
            BatteryMode.REGEN: BatteryModeSpec(
                max_discharge_kw=0.0,
                max_charge_kw=-30.0,
                efficiency=0.90,
                preferred_conditions=(ForkliftCondition.DESCENDING,),
            ),
        }
    )

    # -------------------------------------------------------------------
    # SOC管理边界 / SOC Management Boundaries
    # -------------------------------------------------------------------

    soc_min: float = 0.20   # 硬下限：低于此值禁止放电
    soc_max: float = 0.95   # 硬上限：高于此值禁止充电
    soc_optimal_low: float = 0.30   # 软下限：低于此值优先充电
    soc_optimal_high: float = 0.85  # 软上限：高于此值优先减少充电

    # -------------------------------------------------------------------
    # 功率平衡裕量 / Power Balance Margins
    # -------------------------------------------------------------------

    # 功率预测前瞻步数（用于查表法均值平滑）
    prediction_horizon_steps: int = 1

    # 功率分配时的附加效率裕量（考虑线路/转换损耗）
    system_efficiency_margin: float = 0.98

    # 锂电优先分配比例（混合模式下）
    hybrid_lithium_ratio: float = 0.60  # 锂电承担60%，钠电承担40%
