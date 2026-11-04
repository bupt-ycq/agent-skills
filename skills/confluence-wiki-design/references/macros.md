# 布局与宏目录

这里列出本技能覆盖的常用组件，不代表每个站点都有的完整宏清单。真实可用性由站点探测决定；实例实测结果见 [站点记录](verified-server-profile.md)。

## 组件选择

| 组件 | 适用场景 | 美化方式 | 边界 |
|---|---|---|---|
| 原生标题、列表、链接 | 所有页面的结构骨架 | h2/h3 分层；列表承载并列/步骤 | 不用字号假装标题 |
| 原生 layout | 摘要卡、并排方案、导航 | single、two_equal、three_equal 等布局 | 本站实测 three_equal；其他布局需验证；宽表/代码保持单列 |
| panel | 摘要、指标、主题块 | 标题 + 浅背景 + 细边框 | 普通内容分组，不代表风险等级 |
| info | 范围、定义、读者说明 | 一两段简短蓝色提示 | 不把全部正文放进提示框 |
| tip | 已有依据的建议、技巧 | 绿色建议框 | 不把未验证建议伪装成成功 |
| note | 条件、容易忽略的信息 | 黄色提示 | 与 warning 区分严重性 |
| warning | 风险、限制、操作前注意 | 放在相关内容之前 | 关键风险不折叠 |
| status | 通过、待验证、草案等短状态 | colour/title/subtle | 状态来自事实；颜色参数可能因版本不同 |
| toc | 长文导航 | 限制 h2–h3，减少噪声 | API 可能只给容器，需要浏览器 JS |
| expand | 日志、方法、复现细节 | 明确的折叠标题 | 不隐藏结论和重要限制；少嵌套 |
| code | 命令、源码、配置、输出 | language、title、linenumbers、collapse | 使用 plain-text-body |
| 原生 table | 精确数据、配置/方案比较 | 数字右对齐、表头单位、单列高亮 | 保留数据含义；避免复杂合并 |
| chart | 定量比较 | 简单配色、清楚标题/单位 | 参数和方向需实图验证 |
| 原生图片/附件链接 | 架构图、下载资料 | 图片宽度、说明、可读的附件名 | 上传后核验引用；临时图链接不是永久附件 |
| PlantUML 插件 | 时序/架构/流程图 | 简洁节点、短标签 | 需插件；先验证最小图 |
| draw.io 插件 | 可编辑复杂图 | 有效 diagram 附件 + 宏引用 | 只有宏名被识别还不够 |
| Markdown 插件 | 导入简短 Markdown | 保留已有文本语法 | 非原生通用能力；复杂布局优先 storage |
| Mermaid / HTML 插件 | 仅已验证支持的站点 | 按该插件文档使用 | 本站探针未识别 |
| children / page tree / page properties / excerpt / task 等 | 导航、汇总、复用、任务 | 按需求定向调查 | 本技能未验证，不提供“已可用”承诺 |

## Storage 写法

REST 接收 storage 片段，不是整张 HTML 页面；不要包 html/head 或插入 JS。`ac`/`ri` 前缀是 Confluence storage 语法。本地 XML 校验可以在临时外层补 namespace，不把该包装提交给 API。

### 原生布局与 panel

```xml
<ac:layout>
  <ac:layout-section ac:type="three_equal">
    <ac:layout-cell><p>结论</p></ac:layout-cell>
    <ac:layout-cell><p>验证范围</p></ac:layout-cell>
    <ac:layout-cell><p>下一步</p></ac:layout-cell>
  </ac:layout-section>
  <ac:layout-section ac:type="single">
    <ac:layout-cell><h2>详细结果</h2><p>正文</p></ac:layout-cell>
  </ac:layout-section>
</ac:layout>
```

单张卡可以用 panel 放进 layout-cell：

```xml
<ac:structured-macro ac:name="panel" ac:schema-version="1">
  <ac:parameter ac:name="title">推荐方案</ac:parameter>
  <ac:parameter ac:name="borderStyle">solid</ac:parameter>
  <ac:parameter ac:name="borderColor">#DFE1E6</ac:parameter>
  <ac:parameter ac:name="bgColor">#F4F5F7</ac:parameter>
  <ac:parameter ac:name="titleBGColor">#DEEBFF</ac:parameter>
  <ac:rich-text-body><p><strong>方案 B</strong></p><p>适用范围和依据。</p></ac:rich-text-body>
</ac:structured-macro>
```

### 提示、状态和折叠

```xml
<ac:structured-macro ac:name="info" ac:schema-version="1">
  <ac:parameter ac:name="title">验证范围</ac:parameter>
  <ac:rich-text-body><p>这里只比较指定组件，尚未验证完整服务吞吐。</p></ac:rich-text-body>
</ac:structured-macro>
<ac:structured-macro ac:name="status" ac:schema-version="1">
  <ac:parameter ac:name="colour">Yellow</ac:parameter>
  <ac:parameter ac:name="title">待验证</ac:parameter>
  <ac:parameter ac:name="subtle">false</ac:parameter>
</ac:structured-macro>
<ac:structured-macro ac:name="expand" ac:schema-version="1">
  <ac:parameter ac:name="title">实验方法与完整数据</ac:parameter>
  <ac:rich-text-body><p>方法正文、表格或 code 宏。</p></ac:rich-text-body>
</ac:structured-macro>
```

`info` 可按语义改成 `tip`、`note` 或 `warning`，不只为了换颜色。不要误写 `colour` 为 `color`。

### 目录和代码

```xml
<ac:structured-macro ac:name="toc" ac:schema-version="1">
  <ac:parameter ac:name="minLevel">2</ac:parameter>
  <ac:parameter ac:name="maxLevel">3</ac:parameter>
</ac:structured-macro>
<ac:structured-macro ac:name="code" ac:schema-version="1">
  <ac:parameter ac:name="language">bash</ac:parameter>
  <ac:parameter ac:name="title">复现命令</ac:parameter>
  <ac:parameter ac:name="linenumbers">true</ac:parameter>
  <ac:parameter ac:name="collapse">true</ac:parameter>
  <ac:plain-text-body><![CDATA[python benchmark.py --help]]></ac:plain-text-body>
</ac:structured-macro>
```

若代码包含 `]]>`，拆分为 `]]]]><![CDATA[>`，防止提前结束 CDATA。普通文字/属性用 XML 转义，与代码路径分开。

### 表格

```xml
<table class="wrapped"><colgroup><col style="width: 180px;"/><col style="width: 140px;"/></colgroup>
<tbody><tr><th>方案</th><th>耗时（μs）</th></tr>
<tr><td>A</td><td style="text-align: right;">120.0</td></tr>
<tr><td style="background-color: #E3FCEF;">B（推荐）</td>
<td style="background-color: #E3FCEF; text-align: right;"><strong>80.0</strong></td></tr>
</tbody></table>
```

### 柱状图

示例数据仅演示结构，不是性能证据。图表旁保留精确表格与口径。

```xml
<ac:structured-macro ac:name="chart" ac:schema-version="1">
  <ac:parameter ac:name="type">bar</ac:parameter>
  <ac:parameter ac:name="title">演示：组件耗时（μs，越低越好）</ac:parameter>
  <ac:parameter ac:name="width">760</ac:parameter>
  <ac:parameter ac:name="height">340</ac:parameter>
  <ac:parameter ac:name="legend">false</ac:parameter>
  <ac:parameter ac:name="displayData">false</ac:parameter>
  <ac:parameter ac:name="showIn3D">false</ac:parameter>
  <ac:parameter ac:name="colors">#4C9AFF</ac:parameter>
  <ac:parameter ac:name="rangeAxisLowerBound">0</ac:parameter>
  <ac:parameter ac:name="dataOrientation">horizontal</ac:parameter>
  <ac:rich-text-body><table><tbody>
    <tr><th>方案</th><th>A</th><th>B</th><th>C</th></tr>
    <tr><td>耗时</td><td>120</td><td>80</td><td>60</td></tr>
  </tbody></table></ac:rich-text-body>
</ac:structured-macro>
```

检查实际图片中的 A/B/C 是否是横轴类别、是否只有一组系列。默认图形可能保留渐变/阴影，不能承诺关闭 3D 就得到完全扁平的绘图样式。若需精确出版风格，可生成静态图片并上传附件。

### 图片、附件、PlantUML

```xml
<ac:image ac:width="760"><ri:attachment ri:filename="architecture.png"/></ac:image>
<p><ac:link><ri:attachment ri:filename="reproduction.zip"/>
<ac:plain-text-link-body><![CDATA[下载复现资料]]></ac:plain-text-link-body></ac:link></p>
<ac:structured-macro ac:name="plantuml" ac:schema-version="1">
  <ac:plain-text-body><![CDATA[@startuml
Client -> Service: Request
Service --> Client: Response
@enduml]]></ac:plain-text-body>
</ac:structured-macro>
```

图片/附件引用需当前页面已有对应附件。PlantUML 是插件宏，不要假定所有实例都支持。draw.io 绑定附件的细节依插件而异，优先读取同站点有效页面的 storage 作为依据。
