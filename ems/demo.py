"""
叉车EMS算法综合演示与对比实验
================================

本脚本演示四种算法在叉车能量管理场景下的完整运行流程，
并生成论文可用的性能对比表格（Markdown 格式）。

运行方式
--------
直接执行本脚本（无需额外依赖，仅需 numpy / scipy）：
    python -m ems.demo

或在 Python 环境中导入：
    from ems import ForkLiftEMSDemo
    demo = ForkLiftEMSDemo()
    demo.run_comparison()

输出内容
--------
1. 各算法初始化与单轮评估结果
2. Markdown 格式的性能对比表格（可直接插入论文）
3. Pareto 前沿摘要（NSGA-II 输出）

Simulink 接口示例
-----------------
见本文件末尾的 `simulink_interface_example()` 函数。
"""

from __future__ import annotations

import numpy as np
from typing import Dict

from ems.config import ForkLiftConfig, SACConfig, MPCConfig, NSGA2Config, HybridConfig
from ems.forklift_env import ForkLiftEnv
from ems.algorithms.sac_ems import SACForkLiftEMS
from ems.algorithms.mpc_ems import MPCForkLiftEMS
from ems.algorithms.nsga2_ems import NSGA2ForkLiftEMS
from ems.algorithms.hybrid_ems import HybridLSTMMPCEMS
from ems.utils.metrics import EMSMetrics


class ForkLiftEMSDemo:
    """
    叉车EMS四算法演示与对比评估器。

    用法
    ----
    >>> demo = ForkLiftEMSDemo()
    >>> results = demo.run_comparison(quick=True)
    >>> print(demo.generate_paper_table(results))
    """

    def __init__(self, seed: int = 42):
        self.seed   = seed
        self.config = ForkLiftConfig()

    # ------------------------------------------------------------------
    # 规则基线（对比用）
    # ------------------------------------------------------------------

    def _run_rule_baseline(self) -> Dict:
        """
        规则策略基线：简单 SOC 比例分配（无优化）。
        用于论文对比实验的 Baseline。
        """
        env = ForkLiftEnv(config=self.config, wc_mode="cycle", seed=0)
        obs = env.reset()
        done    = False
        metrics = EMSMetrics()

        while not done:
            soc_li  = env.battery_li.soc
            soc_na  = env.battery_na.soc
            # 简单规则：按 SOC 比例分配（不考虑工况差异）
            soc_total = soc_li + soc_na + 1e-9
            alpha = float(2.0 * (soc_li / soc_total) - 1.0)
            obs, reward, done, info = env.step(np.array([alpha]))
            info["reward"]      = reward
            info["p_demand_kw"] = env._demand_power
            metrics.record(info)

        return metrics.summary()

    # ------------------------------------------------------------------
    # 各算法快速评估（quick模式，减少仿真步数便于快速验证）
    # ------------------------------------------------------------------

    def run_sac(self, quick: bool = True) -> Dict:
        """运行 SAC 算法评估（quick=True 时跳过训练，直接用随机初始化策略评估）。"""
        print("\n>>> 算法一：SAC 深度强化学习（工况感知状态空间 + 双目标奖励塑造）")
        cfg = ForkLiftConfig()
        if quick:
            cfg.episode_steps = 60   # 快速验证
        agent = SACForkLiftEMS(config=cfg, sac_config=SACConfig(), seed=self.seed)

        if not quick:
            print("  训练中（100轮）...")
            agent.train(n_episodes=100, verbose=True)
        else:
            print("  Quick模式：使用随机初始化策略（正式使用请先调用 train()）")

        result = agent.evaluate_episode(wc_mode="cycle")
        print(f"  评估结果：{result}")
        return result

    def run_mpc(self, quick: bool = True) -> Dict:
        """运行改进型 MPC（TSC-MPC）评估。"""
        print("\n>>> 算法二：改进型MPC（任务序列约束 + 能量回收预测）")
        cfg = ForkLiftConfig()
        if quick:
            cfg.episode_steps = 60
        controller = MPCForkLiftEMS(
            config=cfg,
            mpc_config=MPCConfig(N_pred=10, N_ctrl=3),
            seed=self.seed,
        )
        result = controller.evaluate_episode(wc_mode="cycle")
        print(f"  评估结果：{result}")
        return result

    def run_nsga2(self, quick: bool = True) -> Dict:
        """运行 NSGA-II 多目标优化，返回膝点解的仿真结果。"""
        print("\n>>> 算法三：NSGA-II 多目标演化算法（能效 + 衰减双目标优化）")
        cfg = ForkLiftConfig()
        if quick:
            cfg.episode_steps = 60
        nsga2_cfg = NSGA2Config(pop_size=10, n_gen=5) if quick else NSGA2Config()
        optimizer = NSGA2ForkLiftEMS(config=cfg, nsga2_config=nsga2_cfg, seed=self.seed)

        print(f"  种群规模={nsga2_cfg.pop_size}, 代数={nsga2_cfg.n_gen}")
        optimizer.optimize(verbose=True)

        knee = optimizer.get_knee_point()
        print(f"  Pareto前沿大小：{len(optimizer.pareto_front)} 个解")
        print(f"  膝点参数：{np.round(knee, 3)}")

        # 使用膝点参数运行仿真评估
        env = ForkLiftEnv(config=cfg, wc_mode="cycle", seed=0)
        obs = env.reset()
        done    = False
        metrics = EMSMetrics()

        (soc_ref_li, soc_ref_na, alpha_lift,
         alpha_drive, alpha_recover,
         p_switch_thresh, soc_imbal_w) = knee

        while not done:
            cond   = env._condition
            soc_li = env.battery_li.soc
            soc_na = env.battery_na.soc
            soc_diff = soc_li - soc_na

            if cond == 1:
                base = alpha_lift
            elif cond == 2:
                base = alpha_drive
            elif cond in (3, 4):
                base = alpha_recover
            else:
                base = 0.5
            alpha = float(np.clip(2 * (base - soc_imbal_w * soc_diff * 0.1) - 1,
                                  -1, 1))
            obs, reward, done, info = env.step(np.array([alpha]))
            info["reward"]      = reward
            info["p_demand_kw"] = env._demand_power
            metrics.record(info)

        result = metrics.summary()
        print(f"  评估结果：{result}")
        return result

    def run_hybrid(self, quick: bool = True) -> Dict:
        """运行 LSTM-MPC 混合框架评估。"""
        print("\n>>> 算法四：LSTM-MPC混合框架（长期功率预测 + 在线约束优化）")
        cfg = ForkLiftConfig()
        if quick:
            cfg.episode_steps = 60
        controller = HybridLSTMMPCEMS(
            config=cfg,
            hybrid_config=HybridConfig(lstm_seq_len=10, mpc_N=5),
            seed=self.seed,
        )
        result = controller.evaluate_episode(wc_mode="cycle")
        print(f"  评估结果：{result}")
        return result

    # ------------------------------------------------------------------
    # 综合对比实验
    # ------------------------------------------------------------------

    def run_comparison(self, quick: bool = True) -> Dict[str, Dict]:
        """
        运行所有算法并生成对比结果。

        Parameters
        ----------
        quick : True 时使用短仿真（适合快速验证），
                False 时使用完整仿真（适合论文实验）

        Returns
        -------
        results : {算法名: 指标字典}
        """
        print("=" * 60)
        print("叉车混合储能EMS上层控制策略 — 算法对比实验")
        print("=" * 60)
        print(f"仿真模式：{'Quick（快速验证）' if quick else '完整（论文实验）'}")
        print(f"控制步长：{self.config.dt_s}s")

        results: Dict[str, Dict] = {}

        results["规则基线（Baseline）"] = self._run_rule_baseline()
        results["SAC-DRL（WCAS+DORS）"] = self.run_sac(quick=quick)
        results["TSC-MPC（任务序列约束）"]  = self.run_mpc(quick=quick)
        results["NSGA-II（多目标优化）"] = self.run_nsga2(quick=quick)
        results["LMHF（LSTM+MPC混合）"]  = self.run_hybrid(quick=quick)

        print("\n" + "=" * 60)
        print("性能对比表格（Markdown格式，可直接插入论文）：")
        print("=" * 60)
        table = EMSMetrics.compare(results)
        print(table)

        return results

    def generate_paper_table(self, results: Dict[str, Dict]) -> str:
        """生成论文用 Markdown 格式对比表格。"""
        return EMSMetrics.compare(results)


# ---------------------------------------------------------------------------
# Simulink 接口示例
# ---------------------------------------------------------------------------

def simulink_interface_example() -> None:
    """
    演示如何在 Simulink S-Function 中调用本模块。

    MATLAB S-Function 调用示例
    -------------------------
    ```matlab
    function [p_li, p_na] = ems_controller(soc_li, soc_na, cond, p_dem, load)
        % 调用Python EMS模块（需在MATLAB中配置Python环境）
        persistent ctrl;
        if isempty(ctrl)
            ctrl = py.ems.algorithms.mpc_ems.MPCForkLiftEMS();
        end
        result = ctrl.step(soc_li, soc_na, int32(cond), p_dem, []);
        p_li = double(result{1});
        p_na = double(result{2});
    end
    ```

    Python 直接调用示例
    --------------------
    """
    print("\n=== Simulink/外部接口示例 ===")
    cfg  = ForkLiftConfig()
    env  = ForkLiftEnv(config=cfg, wc_mode="cycle", seed=0)
    ctrl = MPCForkLiftEMS(config=cfg)

    obs = env.reset()
    print("单步 step_interface 调用示例：")
    result = env.step_interface(
        soc_li      = 0.55,
        soc_na      = 0.55,
        p_demand_kw = 45.0,     # 举升工况
        condition_id= 1,
        load_kg     = 2000.0,
        alpha       = 0.3,
    )
    print(f"  输入：SOC_li=0.55, SOC_na=0.55, P_dem=45kW, 工况=LIFTING")
    print(f"  输出：p_li={result['p_li_kw']:.2f}kW, "
          f"p_na={result['p_na_kw']:.2f}kW, "
          f"SOC_li_new={result['soc_li_new']:.4f}, "
          f"SOC_na_new={result['soc_na_new']:.4f}")

    print("\nMPC step() 调用示例：")
    p_li, p_na = ctrl.step(
        soc_li      = 0.55,
        soc_na      = 0.55,
        condition   = 1,
        p_demand_kw = 45.0,
    )
    print(f"  MPC分配结果：p_li={p_li:.2f}kW, p_na={p_na:.2f}kW")


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    demo = ForkLiftEMSDemo(seed=42)

    # 运行对比实验（quick=True 用于快速验证，论文实验请用 quick=False）
    results = demo.run_comparison(quick=True)

    # 演示 Simulink 接口
    simulink_interface_example()

    print("\n✅ 演示完成！请查看上方 Markdown 表格作为论文初始性能对比结果。")
    print("   如需完整训练（SAC）或完整优化（NSGA-II），")
    print("   请将 run_comparison(quick=False) 并调整各算法迭代次数。")
