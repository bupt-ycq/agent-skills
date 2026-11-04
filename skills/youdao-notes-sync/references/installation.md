# 安装与已知兼容问题

先检查现有安装，避免重复克隆和覆盖用户配置。使用用户指定目录；否则为项目与笔记选择分开的目录。

1. 获取官方项目源码，读取 README、requirements.txt 和适用的 AGENTS.md。
2. 创建项目独立 `.venv`，用该解释器安装依赖，不使用 `sudo pip` 修改系统 Python。
3. 将配置的四个 key 保持顺序：`local_dir`、`ydnote_dir`、`smms_secret_token`、`is_relative_path`。前者为目标绝对路径，第二项空字符串代表全部顶层笔记，第三项空字符串使图片只下载本地，第四项为 `true`。
4. Cookie 文件仅保存在项目外发范围之外，权限 `0600`。启动器先 `cd` 到项目目录，再调用 `.venv/bin/python pull.py`；若 Cookie 仍是占位符，提示配置而不尝试导出。
5. 运行项目现有 `test/test.py`、`pip check`，并做一次只读取笔记根目录的登录检查。安装任务不自动导出或推送。

## Python 3.12

本次实测原始 requirements 导入失败：`No module named 'urllib3.packages.six.moves'`。局部更新到兼容的 Requests/urllib3 即可；当时验证通过的版本是 `requests==2.34.2`、`urllib3==2.8.0`，其余顶层依赖保持原要求。将实际安装版本记入 requirements/锁定清单。未来版本不要盲目套用旧锁定值；按目标 Python 和实际测试选择。

## 新版列表转换

`core/covert.py` 的 `JsonConvert.convert_l_func` 中，无序列表可能包含 `"ll": null`。原代码直接执行 `level - 1` 会失败。修正为：

```python
level = content.get("4").get("ll") or 1
return "\t" * (level - 1) + "- {text}".format(text=text)
```

仅在源码仍含这个缺陷且实际格式相符时应用。验证缺省/null/正常二级列表，并运行已有测试。仅重试失败项；程序捕获异常后仍可能以 0 退出。

## GitHub CLI

优先使用本机已有 `gh`。缺失时，从 `cli/cli` 官方发行版取得适合本机平台的二进制；若发行元数据提供 SHA-256，先校验，再执行。安装位置应稳定，避免 Git credential helper 指向会被清除的临时目录。无需把工具、源码或虚拟环境上传到笔记仓库。
