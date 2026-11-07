"""将项目全部源码打包为单个 Markdown 文件（含文件树与完整代码内容）.

用法：python bundle_source.py
输出：PROJECT_BUNDLE.md
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "PROJECT_BUNDLE.md"

# 排除依赖与二进制/生成物目录
EXCLUDE_DIRS = {
    "node_modules", ".venv", "__pycache__", ".git",
    "data", "dist", ".idea", ".vscode", "logs",
}
EXCLUDE_FILES = {"package-lock.json", ".env", "PROJECT_BUNDLE.md", "bundle_source.py"}
EXCLUDE_EXT = {".db", ".log", ".pyc", ".ico", ".png", ".jpg", ".jpeg", ".gif"}

LANG_MAP = {
    ".py": "python",
    ".ts": "typescript",
    ".vue": "vue",
    ".scss": "scss",
    ".css": "css",
    ".json": "json",
    ".html": "html",
    ".md": "markdown",
    ".bat": "bat",
    ".txt": "text",
    ".example": "dotenv",
    ".svg": "xml",
}


def iter_source_files():
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        rel_parts = p.relative_to(ROOT).parts
        if any(part in EXCLUDE_DIRS for part in rel_parts):
            continue
        if p.name in EXCLUDE_FILES or p.suffix in EXCLUDE_EXT:
            continue
        yield p


def build_tree() -> str:
    lines = []

    def walk(dirp: Path, prefix: str = "") -> None:
        entries = sorted(
            [
                e for e in dirp.iterdir()
                if not (e.is_dir() and e.name in EXCLUDE_DIRS)
                and not (e.is_file() and (e.name in EXCLUDE_FILES or e.suffix in EXCLUDE_EXT))
            ],
            key=lambda e: (e.is_file(), e.name.lower()),
        )
        for i, e in enumerate(entries):
            last = i == len(entries) - 1
            lines.append(
                prefix + ("└── " if last else "├── ") + e.name + ("/" if e.is_dir() else "")
            )
            if e.is_dir():
                walk(e, prefix + ("    " if last else "│   "))

    walk(ROOT)
    return "\n".join(lines)


def main() -> None:
    files = sorted(iter_source_files(), key=lambda p: str(p.relative_to(ROOT)).lower())
    tree = build_tree()

    print(tree)
    print(f"\n源文件总数: {len(files)}")

    buf = [
        "# 智学 Agent（StudyFlow Agent）· 完整源码打包\n",
        "> 本文件由 `bundle_source.py` 自动生成，包含项目**文件树结构**与**全部源码内容**。\n",
        f"\n- 源文件数量：**{len(files)}**\n",
        "- 已排除：`node_modules`、`.venv`、`__pycache__`、`.git`、`data/`（数据库与日志）、"
        "`package-lock.json`、`.env`（本地密钥）\n",
        "\n## 一、文件树结构\n\n```text\n",
        tree,
        "\n```\n\n## 二、全部源码内容\n",
    ]

    for f in files:
        rel = f.relative_to(ROOT).as_posix()
        lang = LANG_MAP.get(f.suffix, "")
        try:
            content = f.read_text(encoding="utf-8")
        except Exception:
            content = f.read_text(encoding="utf-8", errors="ignore")
        buf.append(f"\n### `{rel}`\n\n```{lang}\n{content}\n```\n")

    OUTPUT.write_text("\n".join(buf), encoding="utf-8")
    print(f"\n已生成打包文件: {OUTPUT}")


if __name__ == "__main__":
    main()
