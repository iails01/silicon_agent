---
name: readme-gen
display_name: "README生成"
description: 根据项目代码和结构自动生成或更新 README 文档
layer: L1
metadata:
  emoji: "📖"
  tags: ["doc", "readme", "documentation"]
  applicable_roles: ["doc"]
---

# README 文档生成

根据项目代码结构、配置文件和已有文档自动生成或更新 README.md。

## 输入

用户会提供：
- `project_path`：项目根目录
- `style`（可选）：README 风格（minimal / standard / detailed）
- `existing_readme`（可选）：现有 README 内容（用于更新）

## 工作流

### Step 1：项目分析

使用 `search-codebase` 和 `read` 分析项目：
- 项目名称和描述（从 package.json / pyproject.toml / Cargo.toml）
- 技术栈和框架
- 目录结构和模块划分
- 入口文件和配置文件
- 已有文档（CHANGELOG、CONTRIBUTING、LICENSE）

### Step 2：内容规划

根据项目类型确定 README 章节：
- **应用项目**：功能介绍、安装、配置、启动、部署
- **库项目**：安装、快速开始、API 文档、示例
- **CLI 工具**：安装、用法、命令列表、配置

### Step 3：内容提取

从代码中自动提取信息：
- 安装命令（from 包管理器配置）
- 环境变量列表（from .env.example 或 settings）
- API 端点列表（from 路由定义）
- CLI 命令列表（from 命令注册）
- 脚本命令（from package.json scripts / Makefile）

### Step 4：文档生成

生成 README.md 内容：
- 项目标题和简介
- 功能特性列表
- 快速开始指南
- 详细使用说明
- 配置参考
- 开发指南
- 贡献指南链接
- 许可证信息

### Step 5：格式优化

确保文档质量：
- Markdown 格式正确
- 代码块指定语言
- 链接有效
- 目录结构树对齐
- 中英文间加空格

## 输出格式

使用 `write` 工具写入 README.md，同时输出摘要：

```markdown
## README 生成报告

### 生成章节
| # | 章节 | 行数 | 来源 |
|---|------|------|------|
| 1 | 项目简介 | {n} | pyproject.toml |
| 2 | 快速开始 | {n} | 自动提取 |
| 3 | 配置参考 | {n} | .env.example |

### 待人工补充
- [ ] {需要手动补充的内容}
```
