from __future__ import annotations

from pathlib import Path


class GrobidService:
    """
    GROBID 扩展接口（MVP 预留）:
    - 后续可接入本地/远程 GROBID 服务提取结构化元数据
    - 当前版本使用 MetadataService 本地规则提取
    """

    def extract_metadata(self, pdf_path: str | Path) -> dict[str, str]:
        raise NotImplementedError("GROBID 接口尚未实现。")

