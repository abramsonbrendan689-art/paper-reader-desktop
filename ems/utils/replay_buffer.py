"""
经验回放缓冲区（用于 SAC 等离策略深度强化学习算法）
=====================================================

实现标准均匀采样经验池，支持：
- numpy 数组存储（无需 PyTorch 依赖即可运行）
- 可选优先经验回放（PER）扩展接口
"""

from __future__ import annotations

import numpy as np
from typing import Tuple


class ReplayBuffer:
    """
    环形经验回放缓冲区。

    存储 (state, action, reward, next_state, done) 五元组。
    满容量后自动覆盖最旧经验（FIFO）。

    Parameters
    ----------
    state_dim  : 状态向量维度
    action_dim : 动作向量维度
    max_size   : 缓冲区最大容量
    """

    def __init__(self, state_dim: int, action_dim: int, max_size: int = 100_000):
        self.max_size = max_size
        self.ptr = 0       # 写入指针
        self.size = 0      # 当前存储量

        self.states      = np.zeros((max_size, state_dim),  dtype=np.float32)
        self.actions     = np.zeros((max_size, action_dim), dtype=np.float32)
        self.rewards     = np.zeros((max_size, 1),          dtype=np.float32)
        self.next_states = np.zeros((max_size, state_dim),  dtype=np.float32)
        self.dones       = np.zeros((max_size, 1),          dtype=np.float32)

    def add(
        self,
        state: np.ndarray,
        action: np.ndarray,
        reward: float,
        next_state: np.ndarray,
        done: bool,
    ) -> None:
        """向缓冲区添加一条经验。"""
        self.states[self.ptr]      = state
        self.actions[self.ptr]     = action
        self.rewards[self.ptr]     = reward
        self.next_states[self.ptr] = next_state
        self.dones[self.ptr]       = float(done)

        self.ptr  = (self.ptr + 1) % self.max_size
        self.size = min(self.size + 1, self.max_size)

    def sample(self, batch_size: int) -> Tuple[np.ndarray, ...]:
        """
        随机采样一批经验。

        Returns
        -------
        (states, actions, rewards, next_states, dones) 各形状为 (batch, dim)
        """
        idx = np.random.randint(0, self.size, size=batch_size)
        return (
            self.states[idx],
            self.actions[idx],
            self.rewards[idx],
            self.next_states[idx],
            self.dones[idx],
        )

    def __len__(self) -> int:
        return self.size

    def is_ready(self, min_size: int) -> bool:
        """判断缓冲区是否已积累足够经验可以开始训练。"""
        return self.size >= min_size
