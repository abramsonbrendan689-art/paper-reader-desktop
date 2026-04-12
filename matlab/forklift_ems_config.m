%% forklift_ems_config.m
% 叉车混合储能EMS — 参数初始化脚本
% Forklift Hybrid Energy Storage EMS — Parameter Initialization Script
%
% 在Simulink模型打开或仿真开始前运行此脚本，将参数加载到工作区（workspace）。
% Run this script before opening the Simulink model or starting simulation
% to load all parameters into the MATLAB workspace.
%
% 使用方式 / Usage:
%   forklift_ems_config   % 在MATLAB命令窗口运行
%
% 所有参数均存储在结构体 EMSConfig 中，供 MATLAB Function Block 直接引用。
% All parameters are stored in the struct EMSConfig for use in MATLAB
% Function Blocks.

clear EMSConfig;

%% ======================================================================
%% 1. 工况识别阈值 / Condition Recognition Thresholds
%% ======================================================================

% 速度阈值 (m/s)
EMSConfig.speed_standby_max     = 0.05;  % 低于此速度且无举升 → 待机
EMSConfig.speed_driving_min     = 0.30;  % 高于此速度 → 行驶

% 加速度阈值 (m/s²)
EMSConfig.accel_acc_min         = 0.50;  % 正加速 → 加速工况
EMSConfig.accel_dec_max         = -0.30; % 负加速 → 辅助下降判断

% 举升速度阈值 (m/s)
EMSConfig.lift_vel_lifting_min  = 0.05;   % 上升 → 举升工况
EMSConfig.lift_vel_desc_max     = -0.05;  % 下降 → 下降工况

% FSM防抖最小停留时间 (s)
EMSConfig.min_dwell_s               = 0.5;

%% ======================================================================
%% 2. 叉车工况功率特性表 / Condition Power Profile Table
%% ======================================================================
% 各工况对应：平均功率(kW) | 峰值功率(kW) | 典型持续时间(s)
% 负值 = 制动回收
%
%  条目顺序（工况编号）：
%  1 = LIFTING     举升
%  2 = DRIVING     行驶
%  3 = DESCENDING  下降（回收）
%  4 = STANDBY     待机
%  5 = ACCELERATING 加速
%
%  格式：[mean_kw, peak_kw, duration_s]

EMSConfig.power_table = [
%  mean_kw  peak_kw  duration_s
    15.0,    25.0,    20.0;   % 1 LIFTING
     8.0,    15.0,   120.0;   % 2 DRIVING
    -5.0,   -10.0,    15.0;   % 3 DESCENDING
     1.0,     2.0,   300.0;   % 4 STANDBY
    20.0,    30.0,     5.0;   % 5 ACCELERATING
];

% 工况编号映射常量（在MATLAB Function Block中使用整数代替字符串）
EMSConfig.COND_LIFTING      = 1;
EMSConfig.COND_DRIVING      = 2;
EMSConfig.COND_DESCENDING   = 3;
EMSConfig.COND_STANDBY      = 4;
EMSConfig.COND_ACCELERATING = 5;

%% ======================================================================
%% 3. 电池工作模式规格 / Battery Mode Specifications
%% ======================================================================
% 模式编号：
%  1 = PURE_LITHIUM  纯锂电
%  2 = PURE_SODIUM   纯钠电
%  3 = HYBRID        混合模式
%  4 = REGEN         制动回收

EMSConfig.MODE_PURE_LITHIUM = 1;
EMSConfig.MODE_PURE_SODIUM  = 2;
EMSConfig.MODE_HYBRID       = 3;
EMSConfig.MODE_REGEN        = 4;

% 各模式规格：[max_discharge_kw, max_charge_kw, efficiency]
% max_charge_kw 为负值（充电）
EMSConfig.mode_specs = [
%  max_disch  max_charge  efficiency
    30.0,      -20.0,      0.96;   % 1 PURE_LITHIUM
    20.0,      -15.0,      0.93;   % 2 PURE_SODIUM
    45.0,      -30.0,      0.95;   % 3 HYBRID
     0.0,      -30.0,      0.90;   % 4 REGEN
];

% 工况-模式偏好矩阵 (cond x mode)：1=偏好，0=非偏好
% Condition × Mode preference matrix
EMSConfig.mode_preference = [
%  Li  Na  Hyb  Regen
    0,  0,   1,   0;   % 1 LIFTING
    1,  1,   0,   0;   % 2 DRIVING
    0,  0,   0,   1;   % 3 DESCENDING
    1,  1,   0,   0;   % 4 STANDBY
    0,  0,   1,   0;   % 5 ACCELERATING
];

%% ======================================================================
%% 4. SOC管理边界 / SOC Management Boundaries
%% ======================================================================

EMSConfig.soc_min          = 0.20;  % 硬下限
EMSConfig.soc_max          = 0.95;  % 硬上限
EMSConfig.soc_optimal_low  = 0.30;  % 软下限
EMSConfig.soc_optimal_high = 0.85;  % 软上限

%% ======================================================================
%% 5. 混合模式分配参数 / Hybrid Mode Split Parameters
%% ======================================================================

% 混合模式锂电基础分配比例（SOC充足时使用）
EMSConfig.hybrid_lithium_ratio = 0.60;  % 锂电60%，钠电40%

% 系统效率裕量（考虑线路/变换器损耗）
EMSConfig.system_efficiency_margin = 0.98;

%% ======================================================================
%% 显示配置确认 / Display Confirmation
%% ======================================================================

fprintf('=== 叉车EMS参数已加载到工作区 / EMS Config Loaded ===\n');
fprintf('  工况数量 / Conditions: %d\n', size(EMSConfig.power_table, 1));
fprintf('  模式数量 / Modes:      %d\n', size(EMSConfig.mode_specs, 1));
fprintf('  SOC范围 / SOC range:   [%.2f, %.2f]\n', EMSConfig.soc_min, EMSConfig.soc_max);
fprintf('=====================================================\n');
