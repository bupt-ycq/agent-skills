# 下载、整理与私有 Git 同步

以下 `<...>` 是参数说明，实际执行时使用已核实的绝对路径。脚本位于当前技能目录；不要把技能的安装目录误当工作目录。所有运行状态、快照、归档和日志放在导出目录及 Git 工作区之外。

## 1. 建立本次状态

创建一个新的运行目录，保存上次成功的云端清单为 `previous.json`，并记录远端默认分支 SHA。不要覆盖旧清单后才尝试比较变化。保存本地原始导出快照：

```text
python3 <skill>/scripts/sync_state.py snapshot --root <导出目录> --output <本次运行目录>/before
```

首次下载可以先建立空导出目录并快照；没有 previous.json 时，不执行 archive，不传 `--previous`。此时如果远端已有同名且内容不同的文件，先调查基线而不是覆盖。

下一轮应比较“上次成功同步时的原始导出快照”与当前导出目录，识别用户在本地的新修改。若云端和本地同时改同一篇，在导出前保留双方副本并解决，不用时间戳猜测哪份应覆盖。本次 before 快照仍用于保护本次运行前的实际内容。

## 2. 导出和云端清单

用项目虚拟环境运行现有 `run.sh` 或在项目目录执行 `.venv/bin/python pull.py`，将 stdout/stderr 写入本次日志。适当设置请求超时。可以并行读取目录清单：

```text
<项目>/.venv/bin/python <skill>/scripts/sync_state.py inventory --project <项目> --output <本次运行目录>/current.json
```

清单遵循项目配置中的 `ydnote_dir` 范围；schema：`folders` 为 `{path,id,returned,count,total}`；`files` 为 `{folder,id,name,modified,created}`。用 ID 对比新增、消失、移动/改名和修改，不按标题猜测身份。若 count/total 大于 entries 数量，helper 停止，先处理 API 分页。

检查日志的实际错误标记，如 `可能失败！`、`Traceback`、`已终止执行`；不要只统计“失败”一词，用户笔记标题可能含这个词。一次明确网络错误可有限重试，转换器缺陷先修复后重试对应 ID。不能在仍有未解释的错误时报告完整成功。

```text
python3 <skill>/scripts/sync_state.py audit --root <导出目录> --inventory <本次运行目录>/current.json --report <本次运行目录>/audit.json
```

audit 输出计数，详情只写 report。缺失、未转换原件、断链或残留有道图片 URL 会返回 2；空白文件单列，不直接认定错误。新出现的空白笔记应读取其云端原件，检查正文和媒体是否确实为空。历史已确认空白且未变的内容不用重复请求。若原始文件本来就应该保留原格式，检查后解释未转换项，不盲目改扩展名。

## 3. 可恢复地反映改名、移动和删除

只有有 previous 清单、完整 current 清单，且本次要求同步当前结构时才整理。先生成计划：

```text
python3 <skill>/scripts/sync_state.py archive --root <导出目录> --before <运行目录>/before --previous <运行目录>/previous.json --current <运行目录>/current.json --destination <运行目录>/archived-local --report <运行目录>/archive.json
```

核对计划与 ID 差异相符，再在同一命令追加 `--apply`。此开关是工具的写入选择，不额外制造用户审批：已有同步授权足够时直接执行；文件系统权限按实际环境处理。

脚本只移动旧清单支持的过时文件及未再引用的相关 images/attachments。与快照不同的文件留在原位并记录。归档之后重新 audit。不要使用 `rm -rf` 或无条件 `rsync --delete` 镜像整个用户目录。

## 4. 从最新远端合并

核实 GitHub 账号和 PRIVATE。目标不存在且本次已授权创建/上传时，可创建指定账号下的私有仓库；不要先建公开仓库再改私有，也不把不相关既有公开仓库擅自改为私有。对现有仓库 fetch，记录确切 SHA，建立干净工作区。仓库的本地 `main` 不一定等于远端。

```text
python3 <skill>/scripts/prepare_git.py --root <导出目录> --before <运行目录>/before --repo <干净发布工作区> --previous <运行目录>/previous.json --current <运行目录>/current.json --archive-report <运行目录>/archive.json --report <运行目录>/git-preparation.json
```

没有清理旧文件时省略 `--archive-report`。脚本只暂存，不提交、不联网、不推送；要求工作区初始干净。它按 ID 识别改名笔记，保留仓库侧修改，必要时做文本三方合并。二进制双方修改、合并冲突、远端删除或新路径碰撞需要先解决。远端自有文件保留；ignore 规则导致笔记未暂存时停止检查，不自动 `git add --force`。

对发布工作区再次运行 audit。结合实际仓库已做过的清理检查不要重新引入凭据；尤其不能把 cookies.json、CLI 登录配置、快照、归档和日志复制进仓库。若 GitHub push protection 拦截实际凭据，先保留本地原件，核实并处理具体匹配项，不绕过保护或对整份笔记做无关改写。

## 5. 提交、推送和状态提交

只在有差异时提交；Git 身份使用已验证账号及其已有设置。推送前核对 `private=true`、owner 和当前远端 SHA。使用普通 push 到已确认分支，不强推。遇到 non-fast-forward，重新 fetch 并合并其他提交；不要覆盖它们。

推送后核对 GitHub 的分支 SHA 等于本地提交，仓库仍 private，递归 tree 未截断且 blob 数量等于本地 `git ls-files` 数量。仓库可能额外有 `.gitignore`，因此仓库文件数不必等于云端笔记数。

最后保存报告、current 清单和本次完成后的**原始本地导出**快照。原始快照不能用已经保留 GitHub 侧脱敏修改的发布工作区代替。将最近成功状态指向本次运行目录。若仅本地同步成功而推送失败，分别记录状态，不能把它写成完整 GitHub 同步成功。

## 修改 helper 后的验证

运行 `PYTHONDONTWRITEBYTECODE=1 python3 <skill>/scripts/test_sync.py`。测试只使用临时模拟文件和本地 Git 仓库，不读取真实账号、不联网；Cookie 格式测试需要系统 Python 的 `cryptography`。常规同步无需重复运行这些回归测试。
