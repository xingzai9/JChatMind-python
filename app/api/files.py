"""
文件下载接口
提供 Agent 生成文件和用户上传文件的下载服务
"""
import mimetypes
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()

UPLOADS_ROOT = Path(__file__).resolve().parents[2] / "uploads"
GENERATED_DIR = UPLOADS_ROOT / "generated"
GENERATED_DIR.mkdir(parents=True, exist_ok=True)


def _find_file(raw_name: str) -> Path | None:
    """
    查找文件：优先 uploads/generated/（含子目录），其次 uploads/ 下所有 session 子目录。
    支持 URL 编码文件名（%XX）和中文名。
    """
    from urllib.parse import unquote
    name = unquote(raw_name).replace("..", "").replace("/", "").replace("\\", "").strip()
    if not name:
        return None

    # 1. generated 根目录
    p = GENERATED_DIR / name
    if p.exists():
        return p

    # 2. generated 子目录（递归）
    for sub in GENERATED_DIR.rglob(name):
        if sub.is_file():
            return sub

    # 3. session 子目录（uploads/{uuid}/filename）
    if UPLOADS_ROOT.exists():
        for child in UPLOADS_ROOT.iterdir():
            if child.is_dir() and child.name != "generated":
                candidate = child / name
                if candidate.exists():
                    return candidate
    return None


@router.get("/download/{filename:path}")
async def download_file(filename: str):
    """下载 Agent 生成文件或用户上传文件"""
    safe_name = filename.replace("..", "").replace("/", "").replace("\\", "")
    if not safe_name:
        raise HTTPException(status_code=400, detail="无效的文件名")

    file_path = _find_file(safe_name)
    if file_path is None:
        raise HTTPException(status_code=404, detail=f"文件不存在: {safe_name}")

    media_type, _ = mimetypes.guess_type(safe_name)
    if not media_type:
        media_type = "application/octet-stream"

    return FileResponse(
        path=str(file_path),
        filename=safe_name,
        media_type=media_type,
    )


_IGNORE_PREFIXES = ("test_", ".")
_IGNORE_SUFFIXES = (".tmp", ".pyc", ".log")


def _should_ignore(name: str) -> bool:
    low = name.lower()
    return any(low.startswith(p) for p in _IGNORE_PREFIXES) or any(low.endswith(s) for s in _IGNORE_SUFFIXES)


@router.get("/list")
async def list_files():
    """
    列出所有可下载文件（generated/ 优先，按文件名去重）。
    generated/ 中的文件优先级高于 session 上传的原始文件，
    同名文件只保留一条（mtime 最新的那条）。
    """
    seen: dict[str, dict] = {}  # name -> file_info

    def _add(name: str, path: Path, source: str):
        if _should_ignore(name):
            return
        try:
            stat = path.stat()
        except OSError:
            return
        entry = {
            "name": name,
            "size": stat.st_size,
            "source": source,
            "download_url": f"/api/files/download/{name}",
            "mtime": stat.st_mtime,
            "priority": 0 if source == "generated" else 1,
        }
        existing = seen.get(name)
        if existing is None or entry["priority"] < existing["priority"] or (
            entry["priority"] == existing["priority"] and entry["mtime"] > existing["mtime"]
        ):
            seen[name] = entry

    if UPLOADS_ROOT.exists():
        # 1. generated/ 目录（含子目录）
        if GENERATED_DIR.exists():
            for f in GENERATED_DIR.rglob("*"):
                if f.is_file():
                    _add(f.name, f, "generated")

        # 2. session 上传目录
        for child in UPLOADS_ROOT.iterdir():
            if child.is_dir() and child.name != "generated":
                for f in child.iterdir():
                    if f.is_file():
                        _add(f.name, f, child.name)

    files = sorted(seen.values(), key=lambda x: x["mtime"], reverse=True)
    for f in files:
        f.pop("mtime")
        f.pop("priority")
    return {"files": files}
