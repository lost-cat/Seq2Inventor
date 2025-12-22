# Seq2Inventor 项目说明

将 Autodesk Inventor 零件（`.ipt`）的建模特征序列化为 JSON、进行统计分析与向量编码，并支持从 JSON 逐步或一次性重建模型，外加批处理数据准备与 STEP 转换。本项目适用于 Windows + 安装了 Autodesk Inventor 的环境。

## 功能概览

- 特征提取：从 `.ipt` 读取建模特征并导出为 JSON（支持批处理）。
- 模型重建：
  - 一次性重建：从特征 JSON 直接生成新零件。
  - 逐步重建：按特征一步步重建，每步保存一个 `.ipt` 以便定位问题。
- 特征统计：扫描 JSON 文件，输出特征类型的统计与复杂度分布，并可保存图表。
- 向量编码：将特征 JSON 编码为固定维度的指令向量（便于后续模型训练）。
- 数据准备：从压缩包/目录中收集 `.ipt`，规范化命名，形成数据集。
- 批量转换：将 `.ipt` 批量转换为 STEP（`.step`）。
- 训练脚本：对 28 维指令向量序列进行因果 Transformer 训练（可选）。

## 运行环境与依赖

- 操作系统：Windows（需支持 COM）。
- 必须安装：Autodesk Inventor（可通过 COM 接口调用）。
- Python：建议 3.10+。
- 依赖：
  - 核心：`pip install -r requirements.txt`（包含 `numpy`、`h5py` 等）。
  - Windows COM：`pip install pywin32`（提供 `win32com.client`）。
  - 训练（可选）：`pip install -r training/requirements-training.txt`。

建议使用 Conda 创建环境：

```powershell
# 创建并激活环境（示例）
conda create -n seq2inventor python=3.10 -y
conda activate seq2inventor

# 安装依赖
pip install -r requirements.txt
pip install pywin32
```

## 快速上手

### 1) 批量提取特征为 JSON

脚本：`batch_sequence_extract.py`

```powershell
python batch_sequence_extract.py --part_dir .\data\inventor_parts --out_dir .\data\output --start 0 --count -1
```

- `--part_dir`：包含 `.ipt` 的目录（递归扫描）。
- `--out_dir`：输出 JSON 目录；默认在 `part_dir` 同级创建 `output`。
- `--start`/`--count`：可控制从第几个文件开始、最多处理多少个。

说明：脚本会通过 COM 启动 Inventor，逐个打开 `.ipt`，读取特征并写出例如 `0001_features.json`。

若仅需单文件示例，可参考 `sequence_extract.py`（内含路径示例，适用于快速验证）。

### 2) 从 JSON 重建模型

两种方式：

- 一次性重建（`reconstruct_from_json.py`）：

```powershell
python reconstruct_from_json.py .\data\wished.json
```

- 逐步重建（`reconstruct_models_step_by_step.py`）：对每个特征落地一个 `step_###.ipt`。

```powershell
# 重建单个 JSON（输出与 JSON 同目录下的子文件夹中）
python reconstruct_models_step_by_step.py --source .\data\output\0001_features.json

# 批量重建一个目录下的所有 JSON（可指定输出根目录与起始索引）
python reconstruct_models_step_by_step.py --source .\data\output --output_root .\data\examples\rebuild --start 0
```

当前重建能力（持续演进）：
- 轮廓几何：直线、圆、圆弧、样条（BSpline）。
- 特征类型：`ExtrudeFeature`、`RectangularPatternFeature`、`SweepFeature` 等，具体可见`feature_wrappers.py`。
- 扩展设置：距离拉伸、方向（正/负）、操作（默认缺失时按 Join）。

### 3) 统计特征分布（可选）

脚本：`analyze_features_stats.py`

```powershell
python analyze_features_stats.py .\data\output --charts --out .\data\output\stats
```

输出：聚合计数、每文件出现情况、复杂度分桶，以及 PNG 图表（若启用 `--charts`）。

### 4) 将特征 JSON 编码为向量（可选）

脚本：`json2vec.py`

```powershell
python json2vec.py --in .\data\output\0001_features.json --out .\data\output\0001_vec.json --pretty
```

用途：将特征序列转为固定维度的指令向量序列，供训练或下游算法使用。

### 5) 数据准备与 STEP 转换（可选）

- 从压缩包/目录收集 `.ipt` 并顺序命名：`extract_parts.py`

```powershell
python extract_parts.py --src .\data\inventor_parts --dst .\data\parts --also-scan-dirs --seq-width 4
```

- 批量转换 `.ipt` 为 `.step`：`scripts/batch_convert_to_stp.py`

```powershell
python scripts\batch_convert_to_stp.py --ipt_dir .\data\parts --output_dir .\data\output_step
```

## 训练模块(可选目前只是测试代码没有实际作用)

参见 `training/README.md`。核心脚本：`training/train_vectors.py`。


## 常见问题

- Inventor 未能通过 COM 打开：确认已安装 Autodesk Inventor 并能正常启动；以管理员权限运行终端可能有助于初始化 COM。
- `win32com.client` 找不到：请安装 `pywin32`。
- 大批量处理建议：启用 `--start`/`--count` 分批运行；避免一次性打开过多文档。

## 项目结构提示

- `inventor_utils/`：与 Inventor 的 COM 交互与几何/索引辅助。
- `cad_utils/`：CAD 指令/宏与序列相关工具。
- 关键脚本：
  - 提取：`batch_sequence_extract.py`、`sequence_extract.py`
  - 重建：`reconstruct_from_json.py`、`reconstruct_models_step_by_step.py`
  - 统计：`analyze_features_stats.py`
  - 编码：`json2vec.py`
  - 数据：`extract_parts.py`、`scripts/batch_convert_to_stp.py`
  - 训练：`training/` 目录下脚本与说明

---

