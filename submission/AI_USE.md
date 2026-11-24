# AI-use declaration — Group 35, GlossX

**Tools and models used**

| Tool | Models | What it helped with |
| --- | --- | --- |
| Claude Code (claude.ai projects and local CLI) | Anthropic Claude (Opus / Sonnet families) | Writing and refactoring backend, frontend, desktop and mobile code; unit tests; evaluation harness (`eval/`); reliability scenarios; README and report drafts; debugging CI |
| Codex CLI | OpenAI GPT models (`gpt-5.6-sol`, `gpt-6.1-sol`, `gpt-6.2-sol`) | Code changes and reviews in team members' branches; also the *system under test* and the Codex baseline in the evaluation |
| DeepSeek API | `deepseek-flash` | Base model in the DeepSeek / DSH pilot (system under test, not authoring) |

All reported numbers come from running the code. The team reviewed the AI-written code and text, checked
results against the saved outputs, and is responsible for every claim. Model calls made *by GlossX itself*
at run time are part of the product, not AI assistance, and are described in the report.

**Prompt records.** Below are the project-related prompts the contact member (Cai Jiechao) gave to Claude in
the shared Claude project, in time order, copied verbatim (Chinese originals kept). Claude's responses are
not included, as allowed by the guideline. No credentials or personal data appear in them.

Missing records (declared): prompts given in local Claude Code / Codex CLI sessions on members' own
computers, and the prompts other members used for PRs #10, #11 and #12, are not in this file. Members:
add yours under "Other members" before submission, or state that they are unavailable.

## Cai Jiechao — Claude project "glossX"

### 2026-10-10 · project set-up
- Help me connect the tools I use for this work. Ask me where the work lives, tell me which of those tools you can already reach from this project and what each one would let you do, and link me to where I connect the rest. Don't set anything up until I say go.
- Help me set up this new project from my recent work. Look through my recent sessions and repositories, identify the main thread of work, and propose a project setup … Show me the proposal before changing anything.
- 你能看的到最新的吗，刚刚又更新了 / 是gloss仓库里的代码

### 2026-10-10 · desktop shell, browser, title bar
- 但是现在有不少bug，比如浏览器访问显示的是这样子 没有响应式布局看的很不协调，还有右上角的叉叉按钮点击关闭不了窗口。还有你对比下我的proposal，基本的框架搭建好了吗。
- 现在还是这样有问题，这个浏览器 / 还有左边状态栏不用显示浏览器标志
- 当前浏览器的原理是怎么样的呢
- 但是我要的是融入一个内置浏览器（你可以参考有关codex等agent是如何内置浏览器的）。这样如果用户本地没有浏览器，那不就用不了了
- 还有你顶部状态栏能不能做成参考这个样（切换按钮类似这样，但是当前的也不错，融合一下，有gloss和glossX的字样的），不要像被一个框框框在里面那样（windows版本这样，然后npm的就也可以参考，但是两个版本不一样的吧）。此外要支持像新增窗口那样，像vscode/cursor可以同时开很多个。

### 2026-10-10 – 10-11 · workbench usability
- 当前有一个thread正在工作，你同时再新增一个thread，完成以下任务 … 1.大小切换，按ctrl+滚轮 … 2.还有终端历史要有记录，即融合入tmux那样的。3.agent聊天除了有复制和分支按钮之外，还要有一个返回箭头即回到对应会话位置的按钮
- 还有现在交互逻辑有点乱，聊天agent相关的 都放在右边。此外agent发送对话那里，添加上推理强度，此外模型渠道切换在左下角 …
- glossX的logo要保留光亮的，X加在左上角，还有Windows右键点击任务栏的图标，加上参考vscode这样的（不过你看成research/study相关的）
- 思考中。。。 还有这个在工作的时候，能不能点击展开查看具体步骤，像各个agent一样
- 还有claude code和codex加上对应登录配对了的账号的额度查看（5h额度 周额度等等的）
- 还有当前agent是不是没办法读ppt/word/excel，把这些都支持上 / 就是可以打开这些常用的格式文件。哦对还有goodnote笔记格式的文件 / 还有logo更新了 readme也要更新
- 还有我当前glossX中的智能体会话和论文对话 在一起是不是有点冲突 … 重复选择论文的话，论文上下文会不会被重复添加到对话中 挤占上下文窗口这样的问题
- 还有论文工作区的分类也加上，比如这样就可以把单独某一个方向的论文，合在一起一起看
- logo还是有点丑，主要X还是放在右下角比较好 … / X要大一点 和上面的太阳对齐 / 我来说哪个好 / D最好
- 你看看当前最新的代码，我添加了个左右箭头和打开文件夹。接下来还有两个改的：这个研究项目 也和搜索一起放在中间，还有在浏览器上访问的也要可以有各种拖动的。你完成
- 还有我才看到，你agent会话也没一个新增会话的操作 … 主页窗口如果什么都没打开，默认为没东西的而不是欢迎页（参照vscode）/ 新会话按钮有点小就是说 / 还有之前是另一个agent做的 然后workflow是不是有问题 你一起解决了
- 还有为什么我用api给agent 会显示这样 / 还有对话中有这些渲染展示没展示好，此外要做到流式输出，以及处理好如果中断等 问题
- 还有现在的highlight 不准，此外还要可以去除掉 / 还有 文件要可以直接拖动这样子添加到工作区中 / 还有文件夹也是 / 高亮要还随着文件缩放等等 而变化
- 还有底部有这样的bug，显示消失了，你修复然后增强鲁棒性，即拖动窗口这些也没事
- 还有工作区要加上ctrl+f等等的快捷键 / 还有加上智能体正在工作时候，同时也可以发送信息，然后到等待队列 … / 参照codex，也可以重新编辑队列中的信息 / 还有现在聊天怎么 没办法发送图片等等其他文档格式 / 还是有这样偏移的问题你看

### 2026-10-10 – 10-11 · proposal gap analysis and evaluation
- 然后你对比下当前的和proposal，即最初的设计，看看有哪些没实现的（插件什么可以先不管），把主体软件框架先搞好。还有有哪些可以测试对比我们效果更好的方式与任务（对比比如codex pi 等agent）,证明我们的agent在科研/学习上更好。你这个做好方案先，我再决定要不要测
- 那我要怎么做，接下来
- 评测具体模型我来接吧，不用你的额度来，你现在在用什么模型评测的

### 2026-10-11 · mobile and website
- 还有你能不能帮我新增一个thread，帮我开发一个ipad/iphone/android版的glossX的（不用接codex/claudecode了，而是直接连接cli）。你选那种general的即多平台能同步的 而不是每个版本一份代码那样
- ios的我要怎么下载和测试 … / 没有mac，我也不想买Apple 开发者账号，方法b的话，电脑的ip是开放的吗 / 我如果不想装tailscale呢，就直接电脑和手机 扫码就能配对（你也可以参考下dsh的）
- 为什么我现在没找到远程连接在哪打开 / 不用设置第一项 而是左侧状态栏有 / 在搜索的下面
- 还有你参考gloss site 也给glossX创造一个新网页，展示这个agent产品和结构的，还有比如有关结果（暂时为空但预留上）的 / GitHub仓库给你建好了 … / 我跑了 现在怎么报错 / 还是不行 / 我这样做了，但是还是不行

### 2026-11-24 · final submission
- 这个glossX其实是我一个课程project，你帮我开一个thread 专门完成完整project 的内容的
- 这是project的要求 (links to the COMP7608B guideline PDFs)
- 我有搭档 提交的pr的一些结果 / 还有这是我们之前的proposal
- 不是重写 是之前的只是一个proposal 但是现在要最终的

## Other members

- Cai Zhuorui: _add prompts or state unavailable_
- Sun Zhiwei: _add prompts or state unavailable_
- Zhang Guanyi: _add prompts or state unavailable_
