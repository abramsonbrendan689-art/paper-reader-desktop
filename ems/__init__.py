"""
叉车混合储能能量管理系统（EMS）上层控制策略模块
=======================================================

本模块实现了面向锂电/钠电混合储能叉车的创新型能量管理系统（EMS）上层控制策略，
包含以下四种主流算法的叉车适应性改进版本：

算法一：软演员-评论家（SAC）深度强化学习
    - 针对叉车离散-连续混合工况的自适应状态空间设计
    - 考虑电池寿命衰减的多目标奖励函数

算法二：改进型模型预测控制（MPC）
    - 融合叉车任务序列约束的滚动优化框架
    - 内置下降工况能量回收实时预测机制

算法三：带精英策略的非支配排序遗传算法（NSGA-II）
    - 能量效率与电池衰减双目标优化
    - 叉车典型工况适应性参数编码

算法四：混合框架（LSTM功率预测 + MPC在线微调）
    - 长时域功率序列预测
    - 短时域在线约束优化

论文创新点摘要
--------------
1. 基于工况感知的叉车专属状态空间（WCAS）
2. 电池寿命-能效双目标奖励塑造（DORS）
3. 带能量回收预测的任务序列约束MPC（TSC-MPC）
4. LSTM-MPC串级混合框架（LMHF）

使用示例
--------
>>> from ems import ForkLiftEMSDemo
>>> demo = ForkLiftEMSDemo()
>>> demo.run_comparison()
"""

from ems.algorithms.sac_ems import SACForkLiftEMS
from ems.algorithms.mpc_ems import MPCForkLiftEMS
from ems.algorithms.nsga2_ems import NSGA2ForkLiftEMS
from ems.algorithms.hybrid_ems import HybridLSTMMPCEMS
from ems.forklift_env import ForkLiftEnv
from ems.config import ForkLiftConfig, BatteryConfig
from ems.demo import ForkLiftEMSDemo

__all__ = [
    "SACForkLiftEMS",
    "MPCForkLiftEMS",
    "NSGA2ForkLiftEMS",
    "HybridLSTMMPCEMS",
    "ForkLiftEnv",
    "ForkLiftConfig",
    "BatteryConfig",
    "ForkLiftEMSDemo",
]
