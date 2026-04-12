function condition = forklift_condition_recognition(speed, acceleration, lift_velocity, cfg)
%FORKLIFT_CONDITION_RECOGNITION  叉车工况识别 — 适用于 Simulink MATLAB Function Block
%
%  condition = forklift_condition_recognition(speed, acceleration, lift_velocity, cfg)
%
%  输入 / Inputs:
%    speed         — 叉车行驶速度 (m/s)，须 >= 0
%    acceleration  — 纵向加速度 (m/s²)，正=加速，负=减速
%    lift_velocity — 叉臂速度 (m/s)，正=上升，负=下降
%    cfg           — EMSConfig 结构体（由 forklift_ems_config.m 初始化）
%
%  输出 / Output:
%    condition — 工况编号 (整数)：
%                  1 = LIFTING      举升
%                  2 = DRIVING      行驶
%                  3 = DESCENDING   下降/回收
%                  4 = STANDBY      待机
%                  5 = ACCELERATING 加速
%
%  使用方式 / Usage in Simulink:
%    将此函数放入 MATLAB Function Block，Inputs 连接传感器信号，
%    cfg 通过 "Data Store Read" 或 "Constant" 块从工作区读取。
%
%  优先级规则（高→低）：举升 > 下降 > 加速 > 行驶 > 待机

%% 优先级分类规则
if lift_velocity >= cfg.lift_vel_lifting_min
    % 规则1：举升
    condition = cfg.COND_LIFTING;

elseif lift_velocity <= cfg.lift_vel_desc_max
    % 规则2：下降/制动能量回收
    condition = cfg.COND_DESCENDING;

elseif acceleration >= cfg.accel_acc_min
    % 规则3：加速（正向加速度超阈值）
    condition = cfg.COND_ACCELERATING;

elseif speed >= cfg.speed_driving_min
    % 规则4：行驶
    condition = cfg.COND_DRIVING;

else
    % 规则5：待机（默认）
    condition = cfg.COND_STANDBY;
end

end
