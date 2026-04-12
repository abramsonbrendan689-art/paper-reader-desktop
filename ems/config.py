"""
叉车混合储能EMS参数配置模块
============================

集中管理叉车物理参数、电池特性参数和算法超参数。
所有参数均可修改，便于工程现场标定和学术对比实验。

【论文创新点注释】
本配置模块采用分层参数体系：
  Layer-1：叉车物理约束参数（不变量）
  Layer-2：电池特性参数（依据实验标定）
  Layer-3：算法控制超参数（可调优化）
"""

from dataclasses import dataclass, field
from typing import Dict, Tuple


# ---------------------------------------------------------------------------
# 电池配置
# ---------------------------------------------------------------------------

@dataclass
class BatteryConfig:
    """
    单节电池（锂电或钠电）配置参数。

    关键参数说明
    ------------
    capacity_kwh : 额定能量容量（kWh）
    power_max_kw : 最大放电功率（kW）
    regen_max_kw : 最大回充功率（kW），负值表示充电方向
    soc_min / soc_max : SOC工作安全范围
    soc_ref : SOC参考目标值（用于衰减最小化）
    eta_discharge : 放电效率
    eta_charge    : 充电效率（含再生制动）
    degradation_coeff : 循环衰减系数（每kWh吞吐量对应容量损失比例）
                        锂电典型值 ~0.0001，钠电 ~0.00007
    r_internal : 内阻（Ω），用于精确功率损耗计算
    """
    name: str = "battery"
    capacity_kwh: float = 30.0
    power_max_kw: float = 60.0
    regen_max_kw: float = 30.0
    soc_min: float = 0.20
    soc_max: float = 0.90
    soc_ref: float = 0.55
    eta_discharge: float = 0.95
    eta_charge: float = 0.92
    degradation_coeff: float = 1e-4   # kWh吞吐量→容量损失系数
    r_internal: float = 0.05          # Ω


# 锂电典型参数
LITHIUM_BATTERY_CONFIG = BatteryConfig(
    name="LiFePO4",
    capacity_kwh=24.0,
    power_max_kw=72.0,
    regen_max_kw=36.0,
    soc_min=0.20,
    soc_max=0.90,
    soc_ref=0.55,
    eta_discharge=0.95,
    eta_charge=0.92,
    degradation_coeff=1.0e-4,
    r_internal=0.04,
)

# 钠电典型参数（钠离子电池，循环寿命长、成本低）
SODIUM_BATTERY_CONFIG = BatteryConfig(
    name="Na-Ion",
    capacity_kwh=18.0,
    power_max_kw=54.0,
    regen_max_kw=27.0,
    soc_min=0.15,
    soc_max=0.92,
    soc_ref=0.55,
    eta_discharge=0.93,
    eta_charge=0.90,
    degradation_coeff=7.0e-5,   # 钠电衰减更慢
    r_internal=0.06,
)


# ---------------------------------------------------------------------------
# 叉车整车配置
# ---------------------------------------------------------------------------

@dataclass
class ForkLiftConfig:
    """
    叉车整车及工况配置参数。

    工况定义（Working Condition）
    ----------------------------
    0 - IDLE        : 待机/空转，辅助负载为主
    1 - LIFTING     : 货叉举升，大功率消耗
    2 - DRIVING     : 行驶（含空载/重载细分）
    3 - LOWERING    : 货叉下降，可回收制动能量
    4 - BRAKING     : 行走制动，可回收制动能量

    功率范围（叉车典型值，可由现场标定替换）
    ------------------------------------------
    每个工况的（最小功率，最大功率）以kW表示，
    负值代表向储能回充方向（能量回收）。

    【论文创新点】基于工况感知的叉车专属状态空间（WCAS）：
    将工况类型作为独立维度加入状态空间，允许智能体/控制器
    根据工况提前调整储能功率分配策略，区别于通用EMS。
    """
    # 整车物理参数
    max_load_kg: float = 3000.0       # 最大载重（kg）
    mass_empty_kg: float = 4500.0     # 空车质量（kg）
    max_speed_ms: float = 6.0         # 最高行走速度（m/s）
    max_lift_height_m: float = 5.0    # 最大举升高度（m）
    lift_motor_power_kw: float = 15.0 # 举升电机额定功率（kW）
    drive_motor_power_kw: float = 18.0 # 行走电机额定功率（kW）
    regen_efficiency: float = 0.75    # 制动/下降能量回收效率

    # 工况功率范围 (P_min_kW, P_max_kW)
    condition_power_range: Dict[int, Tuple[float, float]] = field(default_factory=lambda: {
        0: (1.0,   4.0),    # IDLE
        1: (20.0,  80.0),   # LIFTING
        2: (8.0,   35.0),   # DRIVING
        3: (-30.0, -5.0),   # LOWERING（负号=能量回收）
        4: (-20.0, -3.0),   # BRAKING（负号=能量回收）
    })

    # 工况名称映射
    condition_names: Dict[int, str] = field(default_factory=lambda: {
        0: "IDLE",
        1: "LIFTING",
        2: "DRIVING",
        3: "LOWERING",
        4: "BRAKING",
    })

    # 典型任务周期（秒）：用于MPC预测域构建
    # 格式：[(工况编号, 持续时间_s), ...]
    typical_task_cycle: list = field(default_factory=lambda: [
        (0, 5),    # 待机5s
        (2, 15),   # 行驶15s（空载）
        (1, 20),   # 举升20s
        (3, 10),   # 下降10s（回收）
        (2, 15),   # 行驶15s（重载）
        (4, 5),    # 制动5s（回收）
        (0, 5),    # 待机5s
    ])

    # 电池配置
    lithium: BatteryConfig = field(default_factory=lambda: LITHIUM_BATTERY_CONFIG)
    sodium:  BatteryConfig = field(default_factory=lambda: SODIUM_BATTERY_CONFIG)

    # 控制周期
    dt_s: float = 0.1        # 控制步长（s）
    episode_steps: int = 600  # 单轮仿真步数（即60s）


# ---------------------------------------------------------------------------
# 算法超参数
# ---------------------------------------------------------------------------

@dataclass
class SACConfig:
    """SAC深度强化学习超参数（论文对比实验可调）"""
    lr_actor: float = 3e-4
    lr_critic: float = 3e-4
    lr_alpha: float = 3e-4
    gamma: float = 0.99       # 折扣因子
    tau: float = 0.005        # 目标网络软更新系数
    buffer_size: int = 100_000
    batch_size: int = 256
    hidden_dim: int = 256     # 神经网络隐层维度
    reward_scale: float = 1.0
    # 奖励函数权重（论文创新：双目标奖励塑造DORS）
    w_efficiency: float = 1.0    # 能效权重
    w_degradation: float = 0.5   # 衰减惩罚权重
    w_soc_balance: float = 0.3   # SOC平衡权重


@dataclass
class MPCConfig:
    """改进型MPC超参数"""
    N_pred: int = 20          # 预测域步数
    N_ctrl: int = 5           # 控制域步数
    Q_energy: float = 1.0     # 能效优化权重
    Q_soc: float = 2.0        # SOC偏差惩罚权重
    Q_degrad: float = 0.5     # 衰减惩罚权重
    R_smooth: float = 0.1     # 功率平滑权重（防抖）
    solver_maxiter: int = 100  # 优化器最大迭代次数


@dataclass
class NSGA2Config:
    """NSGA-II多目标演化算法超参数"""
    pop_size: int = 60        # 种群规模
    n_gen: int = 100          # 最大代数
    crossover_prob: float = 0.9
    mutation_prob: float = 0.1
    eta_c: float = 10.0       # 模拟二进制交叉参数
    eta_m: float = 20.0       # 多项式变异参数


@dataclass
class HybridConfig:
    """LSTM-MPC混合框架超参数"""
    lstm_seq_len: int = 30    # LSTM输入序列长度（时间步）
    lstm_hidden: int = 64     # LSTM隐层维度
    lstm_layers: int = 2      # LSTM层数
    lstm_lr: float = 1e-3
    lstm_epochs: int = 50
    mpc_N: int = 10           # 在线MPC预测步数
    mpc_Q: float = 1.0
    mpc_R: float = 0.1
