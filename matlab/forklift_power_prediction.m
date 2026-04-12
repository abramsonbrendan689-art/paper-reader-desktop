function predicted_power_kw = forklift_power_prediction(condition, soc_li, soc_na, load_factor, cfg)
%FORKLIFT_POWER_PREDICTION  叉车功率预测（查表法）— 适用于 Simulink MATLAB Function Block
%
%  predicted_power_kw = forklift_power_prediction(condition, soc_li, soc_na, load_factor, cfg)
%
%  输入 / Inputs:
%    condition     — 工况编号（由 forklift_condition_recognition 输出）
%    soc_li        — 锂电SOC [0, 1]
%    soc_na        — 钠电SOC [0, 1]
%    load_factor   — 负载因子 [0, 1]；0=轻载取平均值，1=满载取峰值
%    cfg           — EMSConfig 结构体
%
%  输出 / Output:
%    predicted_power_kw — 预测功率 (kW)；正=放电，负=充电/回收
%
%  算法 / Algorithm:
%    1. 从 cfg.power_table 按工况编号查找 [mean_kw, peak_kw]
%    2. 线性插值：P = mean + load_factor * (peak - mean)
%    3. 根据综合SOC对功率进行保护性修正

%% 参数校验
load_factor = max(0.0, min(1.0, load_factor));

%% 1. 查表 + 插值
if condition < 1 || condition > size(cfg.power_table, 1)
    predicted_power_kw = 0.0;
    return;
end

mean_kw = cfg.power_table(condition, 1);
peak_kw = cfg.power_table(condition, 2);

base_power = mean_kw + load_factor * (peak_kw - mean_kw);

%% 2. SOC修正
avg_soc = (soc_li + soc_na) / 2.0;

if base_power > 0
    %% 放电场景：硬下限优先检查，再检查软下限
    if avg_soc <= cfg.soc_min
        % 低于硬下限，禁止放电
        predicted_power_kw = 0.0;
        return;
    elseif avg_soc < cfg.soc_optimal_low
        % 低于软下限，限制放电深度
        ratio = avg_soc / cfg.soc_optimal_low;
        base_power = base_power * max(0.5, ratio);
    end
else
    %% 回收/充电场景：硬上限优先检查，再检查软上限
    if avg_soc >= cfg.soc_max
        % 超过硬上限，禁止充电
        predicted_power_kw = 0.0;
        return;
    elseif avg_soc > cfg.soc_optimal_high
        % 高于软上限，限制回收功率
        ratio = (cfg.soc_max - avg_soc) / (cfg.soc_max - cfg.soc_optimal_high);
        base_power = base_power * max(0.1, ratio);
    end
end

predicted_power_kw = base_power;

end
