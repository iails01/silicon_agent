---
name: implement-api
display_name: "API实现"
description: 根据 API 设计文档实现完整的接口端点，包括路由、校验、业务逻辑和错误处理
layer: L1
metadata:
  emoji: "🔌"
  tags: ["coding", "api", "implementation"]
  applicable_roles: ["coding"]
---

# API 端点实现

根据 API 设计文档实现完整的接口端点，包括路由定义、请求校验、业务逻辑和错误处理。

## 输入

用户会提供：
- `api_spec`：API 设计文档（路由、请求/响应格式、状态码）
- `project_context`（可选）：项目现有的 API 模式和约定

## 工作流

### Step 1：分析 API 规范

从设计文档中提取：
- 端点列表（method + path）
- 请求参数和 body schema
- 响应格式和状态码
- 认证/授权要求
- 分页/过滤需求

### Step 2：搜索现有模式

使用 `search-codebase` 查找项目中的：
- 现有路由定义方式（FastAPI router / Express router 等）
- Pydantic Schema / DTO 模式
- 依赖注入模式（Depends chain）
- 错误处理约定（HTTPException / 自定义异常）
- 中间件和装饰器用法

### Step 3：Schema 层实现

为每个端点生成请求/响应 Schema：
- Request Schema：字段类型、校验规则、默认值
- Response Schema：返回格式、嵌套关系
- 查询参数 Schema：分页、过滤、排序

### Step 4：Service 层实现

实现业务逻辑：
- CRUD 操作封装
- 事务管理
- 权限校验逻辑
- 错误处理和异常转换

### Step 5：Router 层实现

组装路由：
- 路由定义和 HTTP 方法
- 依赖注入配置
- 请求参数绑定
- 响应状态码
- OpenAPI 文档注解

### Step 6：注册路由

将新路由注册到应用：
- 添加到 router 模块
- 配置路由前缀和标签

## 输出格式

```markdown
## API 实现报告

### 实现端点
| Method | Path | 说明 | Status |
|--------|------|------|--------|
| {GET} | {/api/v1/xxx} | {描述} | {200/201/...} |

### 生成文件
| 文件 | 类型 | 说明 |
|------|------|------|
| {path} | Schema | {描述} |
| {path} | Service | {描述} |
| {path} | Router | {描述} |

### 实现要点
- {要点1}
- {要点2}

### 待办事项
- [ ] {需要后续完善的事项}
```
