---
name: api-health-check
display_name: "API健康检查"
description: 验证 API 端点可用性、响应格式和基本功能正确性
layer: L2
metadata:
  emoji: "💓"
  tags: ["smoke", "api", "health", "verification"]
  applicable_roles: ["smoke"]
---

# API 健康检查

验证 API 端点的可用性、响应格式和基本功能正确性，作为部署后的快速验证手段。

## 输入

用户会提供：
- `base_url`（可选）：API 基础地址
- `endpoints`（可选）：需要检查的端点列表
- `auth`（可选）：认证信息

## 工作流

### Step 1：端点发现

使用 `search-codebase` 自动发现 API 端点：
- 搜索路由定义文件
- 提取所有注册的端点（method + path）
- 识别公开端点和需要认证的端点
- 确定健康检查端点（/health、/ping）

### Step 2：基础可用性验证

对每个端点执行基础检查：
- HTTP 状态码是否正确（2xx / 4xx）
- 响应时间是否在可接受范围（< 5s）
- Content-Type 是否正确
- CORS 头是否正确配置

### Step 3：响应格式验证

验证响应结构：
- JSON 格式是否有效
- 必要字段是否存在
- 字段类型是否正确
- 分页信息是否完整（如适用）

### Step 4：功能冒烟验证

对核心端点做轻量功能验证：
- GET 列表接口：返回数组、支持分页
- GET 详情接口：返回对象、字段完整
- POST 创建接口：返回 201、包含 id
- 错误处理：无效输入返回 400/422

### Step 5：生成报告

汇总所有检查结果。

## 输出格式

```markdown
## API 健康检查报告

### 检查概览
- 总端点数：{n}
- 通过：{n} ✅
- 警告：{n} ⚠️
- 失败：{n} ❌

### 详细结果

| # | Method | Path | 状态码 | 响应时间 | 结果 |
|---|--------|------|--------|----------|------|
| 1 | GET | /health | 200 | 12ms | ✅ |
| 2 | GET | /api/v1/tasks | 200 | 85ms | ✅ |
| 3 | POST | /api/v1/tasks | 201 | 120ms | ✅ |

### 问题详情
- **[❌]** {endpoint}：{问题描述}
- **[⚠️]** {endpoint}：{警告描述}

### 总体评估
{pass/fail 及说明}
```
