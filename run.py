from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent


def _print_missing_dependency(error: ModuleNotFoundError) -> None:
    print("启动失败：缺少依赖模块 ->", error.name)
    print("请先安装依赖：")
    print("  python -m pip install -r requirements.txt")
    print("推荐直接运行：")
    print("  powershell -ExecutionPolicy Bypass -File .\\launch.ps1")


def _ensure_project_env() -> None:
    try:
        from app.core.config import ensure_project_env_file

        env_path = ensure_project_env_file()
        if env_path.exists():
            print(f"[提示] 当前使用配置文件：{env_path}")
    except Exception:
        # .env 初始化失败不阻断启动，后续会在 UI 中提示。
        pass


def _print_deepseek_hint_if_needed() -> None:
    try:
        from app.core.config import get_config

        cfg = get_config()
        if not (cfg.deepseek_api_key or "").strip():
            print("[提示] DEEPSEEK_API_KEY 未配置：程序仍可启动，但 AI 翻译/摘要功能不可用。")
            print("[提示] 可在设置页中填写并保存，程序会写入项目根目录 .env。")
    except Exception:
        pass


def main() -> None:
    _ensure_project_env()

    try:
        from app.main import main as app_main
    except ModuleNotFoundError as exc:
        _print_missing_dependency(exc)
        raise SystemExit(1) from exc

    _print_deepseek_hint_if_needed()
    app_main()


if __name__ == "__main__":
    main()
