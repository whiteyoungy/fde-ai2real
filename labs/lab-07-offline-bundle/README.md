# Lab-07 · 自包含离线部署包

**关联章节**：下册第 7 章 §7.2（自包含离线部署包）、上册第 14 章第一则（物理隔离主权 AI）
**预计耗时**：6–8 小时
**前置**：Docker、约 1GB 磁盘、`unshare` 可用（验收要靠它模拟断网）

## 这个 Lab 要解决什么

客户现场没有外网。不能 `pip install`，不能 `docker pull`，不能访问任何 SaaS。你要带一个 U 盘进去，插上，跑一个脚本，服务起来。

这件事的难点不在打包，在于**你以为不需要联网的那些步骤，其实在偷偷联网**。而这类问题只有到了现场才会暴露，那时候补救的余地非常小。

## 核心实测：cosign 的"签能离线、验不能"

本书初稿在 13.2 节留了一句待查：「cosign 在完全离线场景下的官方 air-gapped signing 指南未查到，Lab-07 实现前需要专门补查」。这个 Lab 就是来关掉它的。查完的结论比预想的复杂：

**一、书上那三行命令在 cosign v3.1.3 上跑不通。** `--tlog-upload=false` 已被弃用并直接报错，v3 默认走 signing config。

**二、签名能离线，验签默认不能。** 这条最反直觉：

```
Error: getting trusted root from TUF ...
  Get "https://tuf-repo-cdn.sigstore.dev/15.root.json": network is unreachable
```

明明用的是自己生成的密钥对，`verify-blob` 却仍然要去 sigstore.dev 拉 TUF 信任根。**失败发生在验签之前**——连"签名对不对"都还没开始算。

**三、要随包多带一件东西。** 用 `cosign trusted-root create` 生成一份本地信任根（实测只有 73 字节），验签时用 `--trusted-root` 指过去，再加 `--insecure-ignore-tlog` 跳过透明日志核对。实测跑通的完整链路：

```bash
# 构建侧
cosign generate-key-pair
cosign sign-blob --key cosign.key --yes --new-bundle-format \
  --bundle image.bundle image.tar
cosign trusted-root create --out trusted-root.json    # 73 字节，要随包交付

# 客户现场（完全断网）
cosign verify-blob --key cosign.pub \
  --bundle image.bundle --new-bundle-format \
  --trusted-root trusted-root.json --insecure-ignore-tlog image.tar
```

**这个交换是有代价的，要向客户安全团队讲明白。** `--insecure-ignore-tlog` 会打出一行醒目的 WARNING。透明日志的价值在于"这个签名什么时候被谁登记过"是公开可查的；跳过它之后，一份由私钥泄露者伪造的签名，你在现场无从察觉。物理隔离场景通常认为这笔交换划算（网络本来就不通，公开日志也查不了），但它是一个需要讲清楚的取舍，不是技术细节。

**一般教训比 cosign 本身重要**：「这个工具支持离线」要拆成「签能不能离线」和「验能不能离线」两问分别验。**交付现场断网的是客户那一侧，也就是验签那一侧**——恰恰是更容易出问题的一半。

验证方法：别读文档，用 `unshare -rn`（或 `docker run --network none`）把命令扔进一个完全没有网络的命名空间里跑一遍。本 Lab 的验收就是这么做的。

## 离线包要装哪八样

缺一样，客户现场就会卡住：

| 产物 | 作用 | 少了会怎样 |
|---|---|---|
| `image.tar` | `docker save` 导出的镜像 | 没镜像可加载 |
| `image.bundle` | cosign 签名 | 无法确认镜像没被掉包 |
| `cosign.pub` | 验签公钥 | 同上 |
| `trusted-root.json` | 本地信任根 | **验签时会去联网拉 TUF，断网直接失败** |
| `sbom-spdx.json` | SPDX 格式物料清单 | 客户安全审计过不了 |
| `sbom-cyclonedx.json` | CycloneDX 格式 | 不同审计工具消费的格式不同，通常两种都要留 |
| `chart.tgz` | 打包好的 Helm Chart | 装不了 |
| `manifest.txt` | 清单与校验和 | 出问题时说不清交付了什么版本 |

## 目录结构

```
lab-07-offline-bundle/
├── README.md
├── verify.sh
├── fixtures/
│   ├── get_tools.sh             # 下载 cosign / helm / syft 到 tools/（需联网）
│   ├── app/                     # 被交付的服务：server.py + 多阶段 Dockerfile
│   └── chart/                   # Helm Chart 源码
├── src/                         # 你要实现的部分
│   ├── build_bundle.sh          # 构建离线包（构建侧，允许联网）
│   └── install_offline.sh       # 离线安装（客户侧，全程断网）
├── tools/                       # 工具二进制（已 gitignore）
└── results/                     # 运行产物（已 gitignore）
```

## 探针 CLI 契约

- `bash src/build_bundle.sh --out results/bundle`
  → 产出上表八样，打印 `bundle=<路径> size=<MB>`
- `bash src/install_offline.sh --bundle results/bundle --name lab07-svc`
  → 验签 → 校验 SBOM → 加载镜像 → 起服务（`--network none`），打印 `service=up`

`install_offline.sh` 会被放在 `unshare -rn` 里执行，**它内部不允许有任何出站网络请求**。

## 验收标准

跑 `bash verify.sh`，7 项全部 OK 且退出码 0。

1. **工具链就位** — cosign / helm / syft 三个版本
2. **离线包产出完整** — 八样产物齐备
3. **SBOM 真实可解析** — 两种格式都能解析且组件数达到量级（空壳 SBOM 也是合法 JSON）
4. **断网验签通过** — 在 `unshare -rn` 无网络命名空间里验签成功
5. **篡改必被拒** — 改一个字节即报 `invalid signature`
6. **断网安装能起服务** — 安装脚本全程在无网络命名空间内完成，服务容器以 `--network none` 运行且健康检查通过
7. **manifest 符合离线约束** — `helm template` 渲染出的结果里 `imagePullPolicy: Never`、`runAsNonRoot: true`、有 `startupProbe`

**第 4、5 项必须一起看。** 没有第 5 项，第 4 项什么也证明不了——一个永远返回成功的验签也能过。**验签走过场比不验更危险**，因为它给了你一种已经验过的错觉。

第 6 项的服务容器用 `--network none` 起，健康检查靠 `docker exec` 从容器内部发起——容器压根没有网络接口，从外面根本够不着。

## 可替换组件

| 本 Lab 用的 | 可换成 | 注意 |
|---|---|---|
| cosign key-based | GPG 签名 / 客户内部 PKI | 信创环境常要求用国密算法，cosign 不支持 SM2 |
| syft | trivy / tern | SBOM 格式是标准的，工具可换 |
| Helm | Kustomize / 裸 manifest | 客户没装 Helm 是常见情况 |
| `unshare -rn` 模拟断网 | `docker run --network none` / 真实隔离机 | 前两者都只是模拟，最终仍要在客户环境实测 |
| Docker 起服务 | K8s（kind/k3s）真实部署 | 本 Lab 用 Docker 是为了在 2 核 3GB 机器上跑得动；`helm template` 渲染的正确性单独验 |

## 运行

```bash
bash fixtures/get_tools.sh     # 首次运行，需联网
bash verify.sh
```

`verify.sh` 会自己构建离线包、模拟断网安装、并在退出时清理容器。

测退出码不要放进管道：`bash verify.sh > /tmp/v.log 2>&1; echo $?`

## 故障排查

**第 4 项：`getting trusted root from TUF ... network is unreachable`**
没带 `--trusted-root`，或者带了但文件不在包里。这正是本 Lab 要教的那一条。

**第 4 项：`not enough verified log entries from transparency log: 0 < 1`**
带了 trusted root 但没加 `--insecure-ignore-tlog`。签名时没上传透明日志，验签却默认要求有。

**第 5 项：篡改后竟然通过了**
多半是验签命令的退出码被吞了，或者比对的不是同一个文件。**这一项失败比第 4 项失败严重得多。**

**第 6 项：容器网络不是 `none`**
`docker run` 少了 `--network none`。带网络起来的服务，证明不了它在断网环境能跑。

**syft 报 `failed to fetch latest version`**
它在查自己有没有新版本，不影响 SBOM 生成。设 `SYFT_CHECK_FOR_APP_UPDATE=false` 可以消掉这行噪声。

## 延伸练习

1. 实测中 SPDX 报了 96 个包、CycloneDX 报了 2747 个组件，同一个镜像差了一个数量级。查清楚差在哪（提示：看两者收录的粒度），并说明交给客户审计时该给哪一份。
2. 把 `--insecure-ignore-tlog` 去掉，改成在离线包里自带一份透明日志的离线副本。做得到吗？做不到的话，该怎么向客户安全团队解释这个缺口？
3. 故意在 `install_offline.sh` 里加一行 `curl https://example.com`，跑一次第 6 项，确认它真的会失败。**一个不会失败的检查等于没有这个检查。**
