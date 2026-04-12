function [condition, predicted_power_kw, mode, li_power_kw, na_power_kw] = ...
    forklift_ems_upper(speed, acceleration, lift_velocity, soc_li, soc_na, load_factor, cfg)
%FORKLIFT_EMS_UPPER  叉车混合储能EMS上层控制总入口
%                    Forklift Hybrid EMS — Upper-Layer Control Entry Point
%
%  适用于 Simulink MATLAB Function Block / S-Function
%  Designed for use as a Simulink MATLAB Function Block or S-Function.
%
%  -----------------------------------------------------------------------
%  输入信号 / Input Signals（连接 Simulink 信号线）:
%    speed             — 叉车行驶速度 (m/s)，须 >= 0
%    acceleration      — 纵向加速度 (m/s²)，正=加速，负=减速
%    lift_velocity     — 叉臂速度 (m/s)，正=上升，负=下降
%    soc_li            — 锂电当前SOC [0, 1]
%    soc_na            — 钠电当前SOC [0, 1]
%    load_factor       — 负载因子 [0, 1]（0=轻载，1=满载，推荐0.7）
%    cfg               — EMSConfig 结构体（由 forklift_ems_config.m 初始化）
%
%  输出信号 / Output Signals（连接下层功率分配模块）:
%    condition         — 工况编号 [1..5]：
%                          1=举升  2=行驶  3=下降  4=待机  5=加速
%    predicted_power_kw— 预测系统需求功率 (kW)，正=放电，负=充电/回收
%    mode              — 工作模式编号 [1..4]：
%                          1=纯锂电  2=纯钠电  3=混合  4=制动回收
%    li_power_kw       — 锂电分配功率 (kW)
%    na_power_kw       — 钠电分配功率 (kW)
%
%  -----------------------------------------------------------------------
%  在Simulink中的集成步骤 / Simulink Integration Steps:
%
%  方法A（推荐）— MATLAB Function Block:
%    1. 拖入 "MATLAB Function" 模块（Simulink → User-Defined Functions）
%    2. 将此函数的内容粘贴到 MATLAB Function Block 编辑器
%    3. 在模型回调（Model Callbacks → InitFcn）中添加：
%         forklift_ems_config   % 加载参数到工作区
%    4. 用 "Data Store Read" 块将 EMSConfig 结构体传入 cfg 输入端口
%    5. 连接传感器信号和输出总线
%
%  方法B — S-Function:
%    参见 matlab/ 目录下的 forklift_ems_sfun.m（可扩展实现）
%
%  -----------------------------------------------------------------------
%  注意事项 / Notes:
%    - 此函数为无状态（stateless）实现，防抖逻辑需在调用层（Simulink Memory
%      模块）维护，或将防抖直接集成到 MATLAB Function Block 的持久变量中。
%    - 下层功率分配模块接收 (mode, li_power_kw, na_power_kw) 作为参考值。
%  -----------------------------------------------------------------------

%% ======================================================================
%% 1. 工况识别 / Condition Recognition
%% ======================================================================
condition = forklift_condition_recognition(speed, acceleration, lift_velocity, cfg);

%% ======================================================================
%% 2. 功率预测 / Power Prediction
%% ======================================================================
predicted_power_kw = forklift_power_prediction(condition, soc_li, soc_na, load_factor, cfg);

%% ======================================================================
%% 3. 模式优化与功率分配 / Mode Optimization & Power Split
%% ======================================================================
[mode, li_power_kw, na_power_kw] = forklift_mode_optimizer( ...
    predicted_power_kw, condition, soc_li, soc_na, cfg);

end
