"""快速验证 PythonExecutorTool"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.tools.python_executor_tool import PythonExecutorTool

tool = PythonExecutorTool()

# Test 1: 基础执行
print("=== Test 1: 基础代码执行 ===")
result = tool._run(code='print("Hello from PythonExecutorTool!"); print(2+2)')
print(result)

# Test 2: 生成 CSV 文件
print("\n=== Test 2: 生成 CSV 文件 ===")
code_csv = """
import csv
data = [["Name","Score","Grade"],["Alice",95,"A"],["Bob",82,"B"],["Charlie",78,"B"]]
with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows(data)
print("CSV 写入成功")
"""
result = tool._run(code=code_csv, output_filename="test_scores.csv")
print(result)

# Test 3: 调用 Skills 目录（import Skills 里的工具）
print("\n=== Test 3: 列出 Skills 子目录内容 ===")
code_skills = """
import os
from pathlib import Path
skills_dir = Path(GENERATED_DIR).parent.parent / "Skills"
print("Skills 路径:", skills_dir)
print("子目录:", [d.name for d in skills_dir.iterdir() if d.is_dir()])
xlsx_scripts = list((skills_dir / "xlsx" / "scripts").glob("*.py"))
print("xlsx 脚本:", [f.name for f in xlsx_scripts])
"""
result = tool._run(code=code_skills)
print(result)

print("\n=== 全部验证通过 ===")
