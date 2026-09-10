# 附录 A · 落地清单（按档位分三段）

这份清单按导读里的三档拆开了。**从上往下做，做到你那一档为止就停。**

| 段 | 谁做 | 用时 | 需要 root |
|---|---|---|---|
| **轻档五步** | 所有人 | 约 10 分钟 | 不需要 |
| **中档三步** | 团队协作、有 CI | 再 15 分钟 | 不需要 |
| **重档三步** | 客户现场、要过安全评审 | 再 30 分钟 | **需要** |

> **重档读者请注意**：你的第 0 步不是下面的第 1 步，
> 而是**重档第 9 步（现场验沙箱）**。先去把那三条命令跑了，
> 打不出 `ok` 的话后面配什么都是白配。

---

# 轻档五步

十分钟，不需要 root，不需要写策略脚本。**做完这五步，收益已经拿到八成。**

## 第 1 步：确认装好了

```bash
codex doctor
```

这条命令检查本地安装、配置、登录状态和运行环境 [1]。有报错先解决报错。

## 第 2 步：写 `AGENTS.md`

在你项目的根目录建一个 `AGENTS.md`。**这是全套里性价比最高的一个文件**——
Codex 每次干活都会读它。

```bash
cat > AGENTS.md <<'EOF'
# 项目约定

## 环境事实（AI 猜不到，必须写）
- 语言／版本：
- 依赖怎么装：
- 有没有不能联网的限制：

## 硬约束（写"不要做什么"最有效）
- 密钥只从环境变量读，禁止写进任何文件
- 
- 

## 干活方式
- 改代码前先跑：
- 提交信息格式：
EOF
```

把空格填上。**填不出来的那几行，说明你自己也没想清楚，那正是最容易出事的地方。**

如果项目里有“不要顺手重构”的历史包袱目录，
在那个目录下再单独放一份 `AGENTS.md` 写明原因——
近的会覆盖远的（第 3 章 3.1 节）。

## 第 3 步：定沙箱档位

```bash
mkdir -p ~/.codex
cat >> ~/.codex/config.toml <<'EOF'
sandbox_mode    = "workspace-write"
approval_policy = "on-request"

[sandbox_workspace_write]
network_access = false
EOF
```

三个值的意思：**只能改工作区里的文件**、**越界时问你一声**、**默认不联网**。

需要联网装依赖的话把 `network_access` 改成 `true`，
但**建议先按 `false` 用一阵子**，你会发现绝大多数任务根本不需要联网。

## 第 4 步：加一个拦密钥的钩子

这一步是唯一需要写点代码的，十几行，抄就行。

```bash
mkdir -p .codex/hooks
cat > .codex/hooks/check_secrets.py <<'EOF'
#!/usr/bin/env python3
import json, sys, re
BANNED = re.compile(r'\.env|id_rsa|\.pem$|credentials|secrets\.ya?ml')
event = json.load(sys.stdin)
cmd = str(event.get("tool_input", {}).get("command", ""))
if BANNED.search(cmd):
    print("禁止读取凭据文件。需要配置项请读 config.example.toml，"
          "或告诉我需要哪个键，我给脱敏后的值。", file=sys.stderr)
    sys.exit(2)
EOF
chmod +x .codex/hooks/check_secrets.py

cat >> ~/.codex/config.toml <<'EOF'

[[hooks.PreToolUse]]
matcher = "^Bash$"

[[hooks.PreToolUse.hooks]]
type = "command"
command = 'python3 .codex/hooks/check_secrets.py'
timeout = 30
statusMessage = "检查是否触碰凭据文件"
EOF
```

**装完立刻验一次**：开一个 Codex 会话，让它“看看 `.env` 里写了什么”。
应该被拦下来，而且给出的理由是你写的那句话。

**没验过的护栏等于没有护栏。** 这句话在这份清单里会出现三次。

## 第 5 步：把重复的活儿打包成技能

```bash
mkdir -p .agents/skills/交付前检查
cat > .agents/skills/交付前检查/SKILL.md <<'EOF'
---
name: 交付前检查
description: 出版本／交付前跑一遍完整检查。当用户说"要交付了""打包""出版本""发布前检查"时使用。
---

# 交付前检查

按顺序执行，任何一步失败都停下来报告，不要自己继续：

1. 跑全量测试，确认全绿
2. 扫描仓库里有没有硬编码的密钥、内网地址、真实数据
3. 确认依赖清单和实际安装的一致
4. 生成本次变更清单（对比上一个 tag）
5. 输出一份结论：能不能发 / 阻塞项是什么
EOF
```

`SKILL.md` 开头那段 `---` 中间的内容叫 **frontmatter**（元数据头），
是给程序读的。其中 `description` 最重要——**它决定这个技能什么时候会被自动用上**，
所以要把触发场景写进去，别只写“用于检查”。

用的时候：在 Codex 里打 `$交付前检查`，或者直接说“准备交付了”。

## 轻档做完，你现在有

```
项目根/
├── AGENTS.md                          第 2 步
├── .agents/skills/交付前检查/SKILL.md   第 5 步
└── .codex/hooks/check_secrets.py      第 4 步

~/.codex/config.toml                   第 3、4 步
```

**没有合规压力的话，到这里就可以停了。** 下面两段是给有额外要求的人准备的。

---

# 中档三步

再花十五分钟。适合团队一起用、有 CI、有不想被 AI 碰的东西。

## 第 6 步：命令白名单

第 4 步的钩子拦的是“读了什么文件”，这一步拦的是“跑了什么命令”。

```bash
mkdir -p .codex/rules
cat > .codex/rules/project.rules <<'EOF'
prefix_rule(
    pattern = ["git", ["status", "log", "diff", "show"]],
    decision = "allow",
    justification = "只读 git 操作",
    match = ["git status", "git log --oneline"],
    not_match = ["git push"],
)

prefix_rule(
    pattern = ["git", "push"],
    decision = "prompt",
    justification = "推送到远端需人工确认",
    match = ["git push origin main"],
)

prefix_rule(
    pattern = [["rm", "shred"], "-rf"],
    decision = "forbidden",
    justification = "禁止递归强删。清理请先用 `git clean -n` 预览。",
    match = ["rm -rf build"],
)
EOF
```

语法看着陌生，其实只有四个字段：**匹配什么命令**（`pattern`，
列表里再套列表表示“任选其一”）、**放行还是拦**（`decision`：
`allow` 放行 / `prompt` 问一声 / `forbidden` 禁止）、
**为什么**（`justification`，会显示给使用者看）、
**举两个例子**（`match` / `not_match`，加载时会自动校验，写错了规则加载不进去）。

**验一次**：

```bash
codex execpolicy check --rules .codex/rules/project.rules -- git push origin main
codex execpolicy check --rules .codex/rules/project.rules -- rm -rf /
```

## 第 7 步：打开留痕

```bash
mkdir -p audit
echo "audit/" >> .gitignore    # 里面可能有路径等敏感信息，不要入库

codex exec --json "确认当前仓库的测试基线是绿的" | tee "audit/$(date +%F-%H%M).jsonl"
```

想看“它到底跑了哪些命令”（需要 `jq`，用包管理器装一下）：

```bash
jq -r 'select(.type=="item.started")
       | select(.item.type=="command_execution")
       | [.item.id, .item.command] | @tsv' audit/*.jsonl
```

## 第 8 步：进 CI

在流水线里加一步。**两个开关必加**：CI 里没人能点确认，所以要 `never`；
不该让它改东西，所以要 `read-only`。

```bash
codex exec "根据本次 diff 生成变更说明草稿" \
  --sandbox read-only \
  --ask-for-approval never \
  --json
```

要让下游脚本判断结果，加一份 JSON Schema（就是描述“返回的 JSON 长什么样”的一份 JSON）：

```bash
codex exec "检查这个仓库的交付就绪度" --output-schema ./schema.json -o ./readiness.json
```

**密钥别设成整个 job 的环境变量**，只在调用这一步注入（第 6 章 6.1 节）。

---

# 重档三步

需要目标机器的 root。适合客户现场、要过安全评审的场景。

## 第 9 步：现场验沙箱（重档读者的第 0 步）

**这一步要在进场当天做，不是上线前才做。**

```bash
# 1. user namespace 能不能建？输出 0 就是被关了
cat /proc/sys/user/max_user_namespaces
sysctl kernel.unprivileged_userns_clone 2>/dev/null   # 有的发行版才有这个键

# 2. bwrap 在不在，什么版本
command -v bwrap && bwrap --version

# 3. 直接试一次真的隔离
bwrap --unshare-all --ro-bind / / --dev /dev echo ok
```

**第三条打不出 `ok`，就说明这台机器上的沙箱是形同虚设的。**
Codex 不会报错，只会打一条警告——你以为沙箱开着，其实没开（第 5 章 5.3 节）。

把这几条的输出和 `codex doctor` 的输出一起留档，作为环境勘察记录。

跑不起来时的三个降级方案在第 5 章 5.3 节末尾。

## 第 10 步：管理员锁死

```bash
sudo mkdir -p /etc/codex
sudo tee /etc/codex/requirements.toml >/dev/null <<'EOF'
allowed_sandbox_modes     = ["read-only", "workspace-write"]
allowed_approval_policies = ["on-request"]

[rules]
prefix_rules = [
  { pattern = [{ any_of = ["bash", "sh", "zsh"] }], decision = "prompt" },
]
EOF
```

这份文件和第 3 步那份 `config.toml` 的区别是：**用户改不了它**。

**验证它真的锁住了**——用普通用户跑：

```bash
codex --sandbox danger-full-access    # 应该被拒绝
```

拒绝不了就是没生效，回第 2 章 2.4 节查配置层。

## 第 11 步：网络策略与上报

网络策略代理（第 2 章 2.2 节）：

```toml
default_permissions = "workspace"

[permissions.workspace.network]
enabled     = true
proxy_url   = "http://127.0.0.1:3128"
mode        = "limited"     # 只读网络：能拉，不能推
dangerously_allow_non_loopback_proxy = false
```

要接客户监控的话，再配 OTLP 端点（第 4 章 4.2 节），
然后**去客户的监控界面上确认真的看到了数据**——配了不等于通了。

## 重档做完，交付包里应该多出这些

| 交给谁 | 是什么 |
|---|---|
| 跟代码一起交 | `AGENTS.md`、`.agents/skills/`、`.codex/rules/`、`.codex/hooks/` |
| 交给客户 IT 部门 | `requirements.toml` + 一段说明 |
| 进制品归档 | `audit/*.jsonl`、环境勘察记录、`codex doctor` 输出 |

---

## 最后一条，不分档位

**每一条护栏装完都要现场验一次。**

这份清单里，第 1、4、6、9、10、11 步都带了验证命令，不是装饰。

上册第 14 章讲第 5 关上线的那句结论在这里同样成立：
**“签字只能证明文档收到了，证明不了出事的时候处理得了。”**
