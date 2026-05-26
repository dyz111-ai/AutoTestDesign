# AutoTestDesign

基于大模型的测试设计辅助工具：从 PRD/需求文本出发，自动完成需求结构化、风险分析、覆盖项识别、测试策略选择与测试用例生成，并支持在 Web 界面中人工审查与修改。

## 流程概览

```
需求文本 → 结构化需求 → 风险分析 → 覆盖项 → 测试策略 → 测试用例 → 导出报告
```

测试策略支持等价类划分、边界值分析、决策表、状态转换测试等黑盒方法。

## 环境要求

- Python 3.8+
- DeepSeek API Key（通过 OpenAI 兼容接口调用）

## 快速开始

### 1. 安装依赖

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
```

### 2. 配置 API Key

在项目根目录创建 `.env`：

```
DEEPSEEK_API_KEY=你的密钥
```

可选指定模型（默认 `deepseek-v4-flash`）：

```
DEEPSEEK_MODEL=deepseek-chat
```

### 3. 运行

**命令行（一键跑完整流水线，使用示例 PRD）：**

```bash
python main.py
```

结果输出到 `output/` 目录（CSV）。

**交互界面（推荐，可逐步生成并编辑）：**

```bash
streamlit run streamlit_app.py
```

浏览器打开后按步骤操作：输入应用名称与需求 → 解析 → 风险 → 覆盖项 → 策略 → 用例 → 导出 CSV / JSON / Excel。

## 项目结构

```
app/
├── core/       # LLM 客户端、PRD 读取
├── pipeline/   # 需求提取、风险、覆盖项、策略、用例生成
└── export/     # CSV 导出

main.py           # 命令行入口
streamlit_app.py  # Web 交互入口
sample_prd/       # 示例需求文档
output/           # 运行结果（自动生成）
```

## 说明

- `.env` 请勿提交到 Git。
- API 连通性可用 `python test/test_api.py` 简单验证。
