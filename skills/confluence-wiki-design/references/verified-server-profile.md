# Confluence Server 实例兼容性记录

- 站点：已授权的私有 Confluence 实例；公开版本不包含内网地址。
- 验证日期：2026-10-28。
- HTML meta 识别为 Confluence 7.4.5 / build 8401。
- 依据：已认证 REST API，16 组 storage → view 最小样例；一次真实报告的发布回读；柱状图 PNG 的中文和类别视觉检查。
- 适用边界：当时的实例配置；插件、权限和版本升级后可能变化。不是完整插件清单，也不是全站宏穷举。

| 组件 | 实测状态 | 证据及使用边界 |
|---|---|---|
| 三列布局 `three_equal` | 已渲染 | view 有 `columnLayout three-equal`，真实报告已使用 |
| info / tip / note / warning | 已渲染 | 4 类提示框均生成 HTML |
| panel | 已渲染 | 标题、边框色、背景色、标题背景参数生效 |
| status | 已渲染 | Green、Yellow 已测试；其他颜色未逐一测试 |
| expand | 已渲染 | view 有 expand 容器；真实报告使用 5 处 |
| toc | 已渲染容器 | 依赖浏览器脚本填充/跳转，API 不等于交互验证 |
| code | 已渲染 | 语言、标题、行号、折叠参数已提交测试；浏览器交互未逐项验收 |
| 原生表格 | 已渲染 | 背景色、对齐、列宽、colspan；真实报告用高亮列 |
| chart | 已渲染并检查图片 | 原生柱状图返回临时 PNG；中文正常，四类别方向正确 |
| PlantUML | 已渲染 | 简单时序图生成 inline SVG；复杂图和其他语法未逐项测试 |
| Markdown 插件宏 | 已渲染 | 简单标题、加粗；发布仍优先原生 storage |
| draw.io | 仅识别，依赖附件 | 返回 Diagram attachment access error；没有有效 diagram 附件，不能说端到端可用 |
| Mermaid | 不支持本次调用方式 | view 返回 `wysiwyg-unknown-macro`，不要直接发表 Mermaid 宏 |
| HTML 插件宏 | 不支持本次调用方式 | 未识别 `html` 宏；这不影响原生 storage XHTML |
| 原生文字样式 / hr / blockquote | 已渲染 | span 颜色、字号，分割线、引用块 |
| 附件链接 | 已渲染 | `ri:attachment` 链接可用；报告附件另有下载/hash 核验 |

API 观察：

- Basic auth 在当时已授权会话中有效；技能不存用户名或密码。
- `GET /rest/macro-browser/1.0/macros?detailed=true` 返回 404。
- `GET /rest/api/settings/systemInfo` 返回 404。
- 上述接口失败后，采用 content API、页面 HTML meta 和逐个 render 探针；不能把 404 当成没有任何插件。
- 未认证请求可能返回 404，而不是显式 401；判断权限需要结合会话状态。
- `/download/temp/chart*.png` 下载响应 Content-Type 可能是 `application/x-download`，实际内容是 PNG。用文件签名识别，不要仅凭 MIME 拒绝。
- 页面可能被用户移动。更新前读取当前祖先链，保存后与本次 before 对照；不要断言它永远位于首次创建时的父页面。

升级或另一个空间中出现差异时，重新跑涉及的最小探针并更新证据，保留不确定项。
