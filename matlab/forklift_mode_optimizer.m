function [mode, li_power_kw, na_power_kw] = forklift_mode_optimizer(predicted_power_kw, condition, soc_li, soc_na, cfg)
%FORKLIFT_MODE_OPTIMIZER  叉车工作模式优化决策 — 适用于 Simulink MATLAB Function Block
%
%  [mode, li_power_kw, na_power_kw] = forklift_mode_optimizer(
%      predicted_power_kw, condition, soc_li, soc_na, cfg)
%
%  输入 / Inputs:
%    predicted_power_kw — 上层预测的系统需求功率 (kW)
%    condition          — 当前工况编号
%    soc_li             — 锂电SOC [0, 1]
%    soc_na             — 钠电SOC [0, 1]
%    cfg                — EMSConfig 结构体
%
%  输出 / Outputs:
%    mode         — 选定的工作模式编号：
%                     1=PURE_LITHIUM  2=PURE_SODIUM  3=HYBRID  4=REGEN
%    li_power_kw  — 锂电分配功率 (kW)，正=放电，负=充电
%    na_power_kw  — 钠电分配功率 (kW)，正=放电，负=充电
%
%  算法 / Algorithm:
%    1. 过滤不满足功率/SOC约束的模式
%    2. 计算各候选模式的综合代价
%    3. 选代价最小者
%    4. 执行功率分配计算

%% ======================================================================
%% 步骤1：可行模式过滤 / Step 1: Feasible Mode Filtering
%% ======================================================================

n_modes = size(cfg.mode_specs, 1);
feasible = zeros(1, n_modes);  % 1=可行，0=不可行

for m = 1:n_modes
    max_disch  = cfg.mode_specs(m, 1);
    max_charge = cfg.mode_specs(m, 2);  % 负值

    if predicted_power_kw > 0
        % 放电场景
        if predicted_power_kw > max_disch
            continue;  % 超出放电能力
        end
        % SOC下限检查
        if m == cfg.MODE_PURE_LITHIUM && soc_li <= cfg.soc_min; continue; end
        if m == cfg.MODE_PURE_SODIUM  && soc_na <= cfg.soc_min; continue; end
        if m == cfg.MODE_HYBRID && (soc_li <= cfg.soc_min && soc_na <= cfg.soc_min); continue; end
    else
        % 充电/回收场景
        if predicted_power_kw < max_charge
            continue;  % 超出充电能力
        end
        % SOC上限检查
        if m == cfg.MODE_PURE_LITHIUM && soc_li >= cfg.soc_max; continue; end
        if m == cfg.MODE_PURE_SODIUM  && soc_na >= cfg.soc_max; continue; end
        if m == cfg.MODE_REGEN && (soc_li >= cfg.soc_max && soc_na >= cfg.soc_max); continue; end
    end

    feasible(m) = 1;
end

%% 兜底：无可行模式时强制使用HYBRID
if ~any(feasible)
    feasible(cfg.MODE_HYBRID) = 1;
end

%% ======================================================================
%% 步骤2：代价计算与最优选择 / Step 2: Cost Computation & Selection
%% ======================================================================

best_mode = cfg.MODE_HYBRID;
best_cost = Inf;

avg_soc   = (soc_li + soc_na) / 2.0;
ideal_soc = (cfg.soc_optimal_low + cfg.soc_optimal_high) / 2.0;

for m = 1:n_modes
    if ~feasible(m); continue; end

    eta = cfg.mode_specs(m, 3);

    % 能量消耗代价
    energy_cost = abs(predicted_power_kw) / max(eta, 1e-6);

    % SOC偏差惩罚
    soc_penalty = abs(avg_soc - ideal_soc) * 10.0;

    % SOC护体惩罚
    if m == cfg.MODE_PURE_LITHIUM && soc_li < cfg.soc_optimal_low
        soc_penalty = soc_penalty + 8.0;
    end
    if m == cfg.MODE_PURE_SODIUM && soc_na < cfg.soc_optimal_low
        soc_penalty = soc_penalty + 8.0;
    end

    % 工况-模式匹配奖励
    preference_bonus = 0.0;
    if condition >= 1 && condition <= size(cfg.mode_preference, 1)
        if cfg.mode_preference(condition, m) == 1
            preference_bonus = 5.0;
        end
    end

    cost = energy_cost + soc_penalty - preference_bonus;

    if cost < best_cost
        best_cost = cost;
        best_mode = m;
    end
end

mode = best_mode;

%% ======================================================================
%% 步骤3：功率分配 / Step 3: Power Split
%% ======================================================================

li_spec_disch  = cfg.mode_specs(cfg.MODE_PURE_LITHIUM, 1);
li_spec_charge = cfg.mode_specs(cfg.MODE_PURE_LITHIUM, 2);
na_spec_disch  = cfg.mode_specs(cfg.MODE_PURE_SODIUM,  1);
na_spec_charge = cfg.mode_specs(cfg.MODE_PURE_SODIUM,  2);

switch mode
    case cfg.MODE_PURE_LITHIUM
        li_power_kw = max(li_spec_charge, min(li_spec_disch, predicted_power_kw));
        na_power_kw = 0.0;

    case cfg.MODE_PURE_SODIUM
        li_power_kw = 0.0;
        na_power_kw = max(na_spec_charge, min(na_spec_disch, predicted_power_kw));

    case cfg.MODE_REGEN
        % 回收：按SOC余量比例分配（余量大的多充）
        headroom_li = max(cfg.soc_max - soc_li, 0.0);
        headroom_na = max(cfg.soc_max - soc_na, 0.0);
        total_hr    = headroom_li + headroom_na;
        if total_hr < 1e-6
            li_power_kw = 0.0;
            na_power_kw = 0.0;
        else
            li_power_kw = max(li_spec_charge, predicted_power_kw * headroom_li / total_hr);
            na_power_kw = max(na_spec_charge, predicted_power_kw * headroom_na / total_hr);
        end

    otherwise  % HYBRID
        % 按SOC比例动态分配
        total_soc = soc_li + soc_na;
        if total_soc < 1e-6
            li_ratio = cfg.hybrid_lithium_ratio;
            na_ratio = 1.0 - li_ratio;
        else
            li_ratio = soc_li / total_soc;
            na_ratio = soc_na / total_soc;
        end

        li_power_kw = predicted_power_kw * li_ratio;
        na_power_kw = predicted_power_kw * na_ratio;

        % 裁剪至可行范围
        if predicted_power_kw >= 0
            li_power_kw = min(li_power_kw, li_spec_disch);
            na_power_kw = min(na_power_kw, na_spec_disch);
        else
            li_power_kw = max(li_power_kw, li_spec_charge);
            na_power_kw = max(na_power_kw, na_spec_charge);
        end
end

end
