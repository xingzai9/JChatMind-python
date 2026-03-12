"""
Python 代码执行工具
允许 Agent 编写并执行 Python 代码，处理数据、转换文件格式、生成报表等。
生成的文件保存到 uploads/generated/ 目录，可通过 /api/files/download/ 接口下载。
"""
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# 生成文件存储目录
GENERATED_DIR = Path(__file__).resolve().parents[3] / "uploads" / "generated"
GENERATED_DIR.mkdir(parents=True, exist_ok=True)

# Skills 目录（脚本可 import 里面的模块）
SKILLS_DIR = Path(__file__).resolve().parents[3] / "Skills"


class PythonExecutorInput(BaseModel):
    code: str = Field(..., description="要执行的 Python 代码字符串")
    output_filename: str = Field(
        default="",
        description=(
            "代码将要生成的输出文件名（如 result.xlsx、data.csv、report.txt）。"
            "代码中可通过 OUTPUT_FILE 变量获取完整保存路径。不填则只返回标准输出。"
        ),
    )


class PythonExecutorTool(BaseTool):
    """
    Python 代码执行工具

    使用场景：
    - 数据处理和格式转换（CSV / Excel / JSON / 文本）
    - 调用 Skills 目录下的脚本处理文档（xlsx/docx/pdf/pptx）
    - 数学计算与数据分析
    - 生成报告或结构化文件

    代码执行后，若指定了 output_filename，工具会返回对应的下载链接。
    超时时间：30 秒。
    """

    name: str = "python_executor"
    description: str = (
        "执行 Python 代码，用于数据处理、文件格式转换、生成 Excel/CSV/文本报表等任务。"
        "如需生成文件，设置 output_filename（如 result.xlsx），代码中通过 OUTPUT_FILE 变量获取保存路径。"
        "代码执行完成后返回标准输出内容及文件下载链接。"
    )
    args_schema: type[BaseModel] = PythonExecutorInput

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _snapshot(directory: Path) -> dict[str, float]:
        """递归快照目录下所有文件的修改时间"""
        snap: dict[str, float] = {}
        if directory.exists():
            for p in directory.rglob("*"):
                if p.is_file():
                    snap[str(p)] = p.stat().st_mtime
        return snap

    @staticmethod
    def _collect_new_files(before: dict[str, float], directory: Path) -> list[Path]:
        """执行后找到所有新增/变更的文件"""
        new_files: list[Path] = []
        if directory.exists():
            for p in directory.rglob("*"):
                if p.is_file():
                    key = str(p)
                    if key not in before or p.stat().st_mtime > before[key] + 0.1:
                        new_files.append(p)
        return new_files

    @staticmethod
    def _safe_name(path: Path) -> str:
        """将路径转为安全文件名（去掉路径分隔符）"""
        return path.name.replace("..", "").strip()

    # ------------------------------------------------------------------ _run
    def _run(self, code: str, output_filename: str = "") -> str:
        try:
            gen_dir_str = str(GENERATED_DIR).replace("\\", "/")
            skills_dir_str = str(SKILLS_DIR).replace("\\", "/")

            # 注入 preamble
            preamble_lines = [
                "import sys, os, shutil",
                f"sys.path.insert(0, r'{skills_dir_str}')",
                f"GENERATED_DIR = r'{gen_dir_str}'",
                "os.makedirs(GENERATED_DIR, exist_ok=True)",
            ]

            # 若指定输出文件名，注入 OUTPUT_FILE（绝对路径到 GENERATED_DIR）
            declared_output: Path | None = None
            if output_filename.strip():
                safe = (
                    output_filename.strip()
                    .replace("..", "")
                    .replace("/", "_")
                    .replace("\\", "_")
                )
                declared_output = GENERATED_DIR / safe
                preamble_lines.append(f"OUTPUT_FILE = r'{str(declared_output)}'")
            else:
                preamble_lines.append("OUTPUT_FILE = ''")

            full_code = "\n".join(preamble_lines) + "\n\n" + code

            # 写入临时脚本
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            ) as f:
                f.write(full_code)
                tmp_path = f.name

            # --- 执行前快照 ---
            before_snap = self._snapshot(GENERATED_DIR)

            try:
                result = subprocess.run(
                    [sys.executable, tmp_path],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    cwd=str(GENERATED_DIR),
                )
            finally:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

            stdout = (result.stdout or "").strip()
            stderr = (result.stderr or "").strip()
            returncode = result.returncode

            # --- 执行后递归扫描新文件 ---
            new_files = self._collect_new_files(before_snap, GENERATED_DIR)

            # 将子目录中的新文件移动到 GENERATED_DIR 根（便于统一下载）
            promoted: list[Path] = []
            for nf in new_files:
                if nf.parent == GENERATED_DIR:
                    promoted.append(nf)          # 已在根目录
                else:
                    dest = GENERATED_DIR / nf.name
                    # 如果根目录已有同名文件则加前缀
                    if dest.exists():
                        dest = GENERATED_DIR / f"{nf.stem}_{nf.parent.name[:8]}{nf.suffix}"
                    try:
                        import shutil as _shutil
                        _shutil.copy2(str(nf), str(dest))
                        promoted.append(dest)
                    except Exception as copy_err:
                        logger.warning("复制文件 %s 失败: %s", nf, copy_err)
                        promoted.append(nf)      # fallback 原路径

            # --- 组装输出 ---
            parts: list[str] = []

            # 代码输出
            if stdout:
                parts.append(stdout)

            # 错误输出（非零退出码时严格报告）
            if returncode != 0:
                err_msg = stderr or "(无错误信息)"
                parts.append(f"\n❌ 代码执行失败（退出码 {returncode}）:\n{err_msg}")
                logger.warning("python_executor 退出码=%d stderr=%s", returncode, stderr[:300])
            elif stderr:
                # 零退出但有 stderr（库的警告等）
                parts.append(f"\n[warn]\n{stderr[:500]}")

            if not parts:
                parts.append("(代码执行完成，无标准输出)")

            combined = "\n".join(parts)

            # --- 下载链接 ---
            if promoted:
                link_lines = ["\n\n📁 已生成文件："]
                for pf in promoted:
                    fname = self._safe_name(pf)
                    dl = f"/api/files/download/{fname}"
                    link_lines.append(f"⬇ 下载链接: {dl}")
                combined += "\n".join(link_lines)
            elif returncode == 0 and output_filename.strip():
                # 期望有文件但没生成
                combined += (
                    f"\n\n⚠️ 代码执行成功，但预期文件 **{output_filename}** 未生成。"
                    "\n请检查代码中是否将结果保存到 OUTPUT_FILE 变量指定的路径。"
                )

            logger.info(
                "python_executor 完成: rc=%d new_files=%d output_len=%d",
                returncode, len(promoted), len(combined),
            )
            return combined[:5000]

        except subprocess.TimeoutExpired:
            return "⚠️ 代码执行超时（60 秒），请简化代码或拆分任务。"
        except Exception as e:
            logger.error("PythonExecutorTool 执行失败: %s", e, exc_info=True)
            return f"⚠️ 执行失败: {e}"

    async def _arun(self, code: str, output_filename: str = "") -> str:
        return self._run(code, output_filename)
