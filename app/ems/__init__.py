"""
叉车混合储能能量管理系统（EMS）— 上层控制模块
Forklift Hybrid Energy Storage EMS — Upper-Layer Control Module

模块结构 / Module Structure:
    config.py               — 叉车参数化配置（功率表、电池规格、SOC限制）
    condition_recognizer.py — 基于有限状态机（FSM）的工况识别
    power_predictor.py      — 基于查表法的功率预测
    mode_optimizer.py       — 基于规则和动态规划的模式优化决策
    ems_controller.py       — 上层EMS主控制器（集成以上所有模块）

使用方式 / Quick Start:
    from app.ems import EMSController, ForkliftEMSConfig

    config = ForkliftEMSConfig()
    ems = EMSController(config)

    result = ems.step(
        speed=1.5,          # m/s
        acceleration=0.6,   # m/s²
        lift_velocity=0.3,  # m/s  (>0 上升, <0 下降)
        soc_li=0.75,        # 锂电SOC  [0,1]
        soc_na=0.68,        # 钠电SOC  [0,1]
    )
    print(result.condition)     # 当前工况
    print(result.predicted_power_kw)  # 预测功率 (kW)
    print(result.battery_mode)  # 选定的工作模式
    print(result.li_power_kw)   # 锂电分配功率 (kW)
    print(result.na_power_kw)   # 钠电分配功率 (kW)
"""

from app.ems.config import (
    ForkliftEMSConfig,
    ForkliftCondition,
    BatteryMode,
    ConditionPowerProfile,
    BatteryModeSpec,
)
from app.ems.condition_recognizer import ConditionRecognizer
from app.ems.power_predictor import PowerPredictor
from app.ems.mode_optimizer import ModeOptimizer
from app.ems.ems_controller import EMSController, EMSStepResult

__all__ = [
    "ForkliftEMSConfig",
    "ForkliftCondition",
    "BatteryMode",
    "ConditionPowerProfile",
    "BatteryModeSpec",
    "ConditionRecognizer",
    "PowerPredictor",
    "ModeOptimizer",
    "EMSController",
    "EMSStepResult",
]
