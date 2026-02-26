---
name: dependency-audit
display_name: "依赖审计"
description: 扫描项目依赖的安全漏洞、许可证合规性和版本健康度
layer: L2
metadata:
  emoji: "📦"
  tags: ["review", "dependencies", "security", "audit"]
  applicable_roles: ["review"]
---

# 依赖审计

扫描项目依赖的安全漏洞、许可证合规性和版本健康度，确保供应链安全。

## 输入

用户会提供：
- `project_path`：项目根目录
- `focus`（可选）：重点关注领域（security / license / outdated）

## 工作流

### Step 1：依赖清单收集

使用 `read` 工具获取依赖文件：
- Python：`requirements.txt` / `pyproject.toml` / `Pipfile`
- Node.js：`package.json` / `package-lock.json`
- 识别直接依赖和间接依赖

### Step 2：安全漏洞扫描

检查已知漏洞：
- 使用 `execute` 工具运行安全扫描命令（pip-audit / npm audit）
- 分析 CVE 编号和严重等级
- 评估是否有可用的修复版本
- 判断漏洞是否在实际使用路径上

### Step 3：版本健康度检查

评估依赖状态：
- 是否有过期的大版本（落后 2+ 个主版本）
- 是否有不再维护的包
- 是否有已废弃的 API 使用
- 锁文件是否与声明文件一致

### Step 4：许可证合规

检查许可证兼容性：
- 识别所有依赖的许可证类型
- 标记 copyleft 许可证（GPL 系列）
- 检查与项目许可证的兼容性
- 标记缺失许可证的依赖

### Step 5：升级建议

为需要更新的依赖制定升级方案：
- 安全修复优先级最高
- 评估 breaking changes 风险
- 建议分批升级策略

## 输出格式

```markdown
## 依赖审计报告

### 依赖概览
- 直接依赖：{n} 个
- 间接依赖：{n} 个
- 扫描工具：{tool}

### 安全漏洞

| # | 包名 | 当前版本 | 漏洞 | 严重性 | 修复版本 |
|---|------|----------|------|--------|----------|
| 1 | {pkg} | {ver} | {CVE} | {Critical/High/...} | {ver} |

### 版本健康度

| 状态 | 数量 | 示例 |
|------|------|------|
| 最新 | {n} | {pkg list} |
| 落后1个大版本 | {n} | {pkg list} |
| 落后2+个大版本 | {n} | {pkg list} |
| 不再维护 | {n} | {pkg list} |

### 许可证分析
| 许可证 | 数量 | 风险 |
|--------|------|------|
| MIT | {n} | 低 |
| Apache-2.0 | {n} | 低 |
| GPL-3.0 | {n} | 高 |

### 升级建议
1. **[紧急]** {包名} {当前} → {目标}：{原因}
2. **[建议]** {包名} {当前} → {目标}：{原因}
```
