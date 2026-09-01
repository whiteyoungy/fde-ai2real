# 构建文档

## 构建依赖清单

### 必需依赖

以下工具对构建成功至关重要：

- **pandoc** >= 2.19：Markdown 转 PDF 的核心工具
- **texlive-xetex**：支持中文的 TeX 排版引擎
- **texlive-lang-chinese**：中文语言包
- **fonts-noto-cjk**：CJK 字体库，确保中文字体正确渲染

### 可选依赖

**上下两册正文里的全部插图都是 TikZ 直绘（`build/figures.tex`），不再经过 Mermaid。**
下面这两个依赖只对将来新写的 mermaid 代码块有意义；
当前四本书都不含 mermaid 代码块，缺了它们也能正常构建出完整 PDF。

以下工具用于增强 Mermaid 图表渲染，缺一则图表以源码形式渲染：

- **@mermaid-js/mermaid-cli**（即 `mmdc` 命令）：将 Mermaid 代码转换为 SVG
- **librsvg2-bin**（提供 `rsvg-convert` 命令）：将 SVG 嵌入 PDF

**注意**：两个可选依赖必须成对使用。如果仅有 `mmdc` 而缺 `rsvg-convert`，构建会自动降级为源码渲染并打印警告，而非在 xelatex 阶段失败。

### 安装命令

#### Ubuntu/Debian 系统

```bash
# 安装必需依赖
apt-get update
apt-get install -y pandoc texlive-xetex texlive-lang-chinese fonts-noto-cjk

# 安装可选依赖（用于 Mermaid 图形渲染）
apt-get install -y npm librsvg2-bin
npm install -g @mermaid-js/mermaid-cli
```

#### macOS（使用 Homebrew）

```bash
# 安装必需依赖
brew install pandoc mactex

# 安装可选依赖
brew install npm librsvg
npm install -g @mermaid-js/mermaid-cli
```

## 构建方法

从项目根目录执行：

```bash
./build/build.sh
```

脚本将：
1. 收集 `book/*.md` 中的所有章节文件（按字典序）
2. 预处理 Mermaid 代码块（若依赖完整则转为 SVG，否则保留源码）。
   **这一步现在还有一个不能省的副作用**：它顺手剥掉 emoji 变体选择符 U+FE0F。
   那个字符会让 xelatex 报缺字，而在 LaTeX 层给它空替换会和 microtype 冲突，
   所以只能在这里去掉。即使一张 mermaid 图都没有，这一步也必须跑
3. 使用 pandoc + xelatex 分册合并：上册、下册、三本别册各一个 PDF
4. 输出 PDF 页数和文件大小

输出文件位于 `build/` 下，文件名见 `build.sh` 的 `build_one` 调用。

## 常见故障排查

### 1. 中文显示为方块或缺字

**症状**：PDF 中中文字符显示为空白方块或根本未出现。

**排查步骤**：

1. 检查 CJK 字体是否安装：
   ```bash
   fc-list | grep "Noto Sans CJK"
   ```
   如果无输出，安装字体：
   ```bash
   apt-get install fonts-noto-cjk
   ```

2. 检查 texlive 语言包：
   ```bash
   tlmgr list | grep "lang-chinese"
   ```
   如果未安装，运行：
   ```bash
   tlmgr install texlive-lang-chinese
   ```

3. 确保 pandoc 版本 >= 2.19：
   ```bash
   pandoc --version
   ```

### 2. Mermaid 图表没有渲染出来

**症状**：PDF 中 Mermaid 图显示为纯代码块，而非图形。

**排查步骤**：

1. 检查脚本输出中的日志。如果看到以下警告，说明 mmdc 或 rsvg-convert 缺失：
   ```
   [mermaid] 警告：未检测到 mmdc（@mermaid-js/mermaid-cli）
   [mermaid] 警告：检测到 mmdc，但未检测到 rsvg-convert
   ```

2. 验证 mmdc 可用：
   ```bash
   mmdc --version
   ```
   如果不可用，安装：
   ```bash
   npm install -g @mermaid-js/mermaid-cli
   ```

3. 验证 rsvg-convert 可用：
   ```bash
   rsvg-convert --version
   ```
   如果不可用，安装：
   ```bash
   apt-get install librsvg2-bin
   ```

### 3. xelatex 报 svg 相关错误

**症状**：构建失败，错误信息包含 `svg-tex.pdf is missing` 或类似 SVG 相关的 LaTeX 错误。

**原因**：环境中有 `mmdc` 但缺 `rsvg-convert`，导致 SVG 无法被 LaTeX 处理。

**解决方案**：

1. 检查 rsvg-convert 是否安装：
   ```bash
   which rsvg-convert
   ```

2. 如果缺失，安装 librsvg2-bin：
   ```bash
   apt-get install librsvg2-bin
   ```

3. 重新运行构建：
   ```bash
   ./build/build.sh
   ```

如果问题仍存在，尝试清理缓存后重新构建：
```bash
rm -rf build/.tmp
./build/build.sh
```

## 正文插图（TikZ）

上下两册正文里的插图全在 `build/figures.tex`，**共 62 张**，
通过两册 metadata 的 `header-includes` 里一行 `\input{build/figures.tex}` 加载。
（别册三也引了这个文件，为了第 1 章那张 13 周时间线图。）

其中两张是**题词页**（`\fdmaximvolone` / `\fdmaximvoltwo`），排在两册导读之前、
独占一页，版式由 `\fdmaximplate` 给出：上下双线收口、正中一句大字、下面一段解释、
末行给出处。**题词页不上底色也不上色块——一上颜色就变成广告。**
第 5 个参数是金句多出来的高度：一句话的金句和三句话的金句共用固定坐标，
单行那版会在金句和菱形之间空出一大块。
Markdown 里的调用方式是一个 raw LaTeX 块：

````markdown
```{=latex}
\fdfig{\fdgatesrail}
```
````

### 为什么从 Mermaid 换过来

Mermaid 的判定节点是菱形。中文标签进菱形之后，为了容下四五个字，菱形要撑到很大，
整张图被迫纵向拉长——「模型选型五问」那张实测宽高比 1:2.2，压进 16cm 版心之后
字号只剩 5pt，印出来看不清。而且 Mermaid 一套淡紫色打天下：
「一票否决」和「附加约束，不阻断」长得一模一样，图里最该传达的那层语义反而丢了。

换成 TikZ 之后，判定类的图统一走「判定阶梯」：问题排成一条竖脊，岔出去的结果
甩到右边一列，用底色区分岔路的性质（红＝一票否决，琥珀＝返工重来，青＝继续但带约束）。
同样的信息，高度掉到三分之一，语义还多了一层。

### 改图之前先读这几条

`build/figures.tex` 文件头有四条踩过的坑和一条版式规矩，都写在注释里。
最容易再犯的两条：

- `\foreach` 的循环变量不要取 `\dp` `\pt` `\path` `\note` 这类名字。
  `\dp` 是 TeX 原语（取盒子深度），`\path` 是 TikZ 核心命令，撞上之后报的是
  「Missing number」，跟真正的错处差着十万八千里。
- 整框宽度用 `minimum width`，不用 `text width`。后者会把节点变成定宽段落盒，
  中文行内的可伸缩胶被拉开，「业务口提出需求」会渲染成「业 务 口 提 出 需 求」。
  只有确实要自动折行的多行文本才用 `text width`，而且必须同时写 `align=left`。

### 三类图，收录判据不同

| 类别 | 张数 | 画的是什么 | 收录判据 |
|---|---|---|---|
| 流程图 | 14 | 原来的 Mermaid 图改绘 | 原样保留信息，换画法 |
| 方法论图 | 39 | 正文里已经在描述、但只用文字描述的形状 | 见下 |
| 比喻图 | 7 | 书里自己用过的比喻 | 只画原文有的，不新编 |

**方法论图的收录判据**：图要替正文扛一段说不清的论证。够格的四种形状 ——
两轴权衡（三角、象限、对角线）、顺序与累积、层次与缺口、分布与趋势。
不够格的三种 —— 已经是好表格的（表更适合查）、没有内在关系的并列清单、
画出来只是「把清单装进方框」的。按这条筛，不是每个例子都配图。

**比喻图的自律**：只画书里自己已经用过的比喻。
「原型就像西部片里的小镇布景」「如果他被公交车撞了怎么办」都是正文原话，
图只是把它们画出来。新编一个比喻很容易，但那是给书加东西，不是给书配图。

### 单独预览全部插图

```bash
xelatex -output-directory=build/.tmp build/preview_figures.tex
```

一页一张，A4 版心与正文一致，改完图先看这个再整册构建。
这个工装不进任何一册的构建。

### 改图之前还有一条最容易再犯的

节点里的换行 `\\` 必须留在节点文本的顶层，而且节点必须写 `align=`。
两种写法都会炸，而且报的错跟换行毫无关系：

- `\\` 嵌进 `{\scriptsize ...}` 这种组里 → 报 `\tikzscope@linewidth undefined`
- 节点没写 `align=` 就用 `\\` → 报 `missing \item`

要分行又分字号，就每行各写一次字号：
`{{\bfseries 标题}\\{\scriptsize 第一行}\\{\scriptsize 第二行}}`
