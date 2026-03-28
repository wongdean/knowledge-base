---
title: 5张图看懂OpenClaw的Harness设计
author: 诗与沅方
date: "2026-03-24 08:33:04"
source: "https://mp.weixin.qq.com/s/JtECR8pMopRSec_FF3S20g"
---

# 5张图看懂OpenClaw的Harness设计

诗与沅方

![Image](images/img_001.jpg)

   知行合一

近来Harness这个词非常火，而且Claude Code最近也在龙虾化，我就想深扒下OpenClaw的Harness是如何设计的呢？

于是，从OpenClaw的源码入手，深度拆解了其架构设计、运行链路、记忆系统，以及内外部Tools/Skills调用逻辑...

在做OpenClaw类项目的小伙伴，千万不要错过如下5张图：

**1. 整体架构图**

OpenClaw整体分层架构：从用户交互层、网关控制层、能力层与扩展层，以及底层状态存储。

![Image](images/img_002.png)

由图可见，OpenClaw是个Gateway-First的项目。

它上接多渠道入口，下连会话路由、插件扩展、记忆系统和运行时，中间是一条统一的执行主链路。

那么OpenClaw是如何与LLM协作的呢？也就是它的 Harness 层。

可以把Harness理解成 OpenClaw面向LLM的结构化运行壳：

它负责组装 prompt、挂载 tools、接入 skills 和 memory、处理策略与安全限制，再通过 Provider Adapter 与不同厂商的 LLM API 交互。

因为有Harness，OpenClaw才不是“直接把文本丢给模型”，而是真正具备了可扩展、可控制、可落地的Agent运行能力。

![Image](images/img_003.png)

  输入与上下文

Harness的原料层，包括用户消息/命令/会话历史/工作区文件/bootstrap上下文，以及插件提供的tools/skills等能力。

  Prompt装配器

将system prompt、skills prompt、docs、bootstrap文件、运行时信息等拼成最终给模型的提示词。

  模型解析与策略

这一层决定到底用哪个模型、什么thinking档位、哪个认证身份。

同时也处理模型fallback、部分hooks对模型选择和prompt的干预等。

  工具与安全壳

限制模型可调用能力边界，避免直接乱碰系统，增强安全性。

  Agent会话与执行循环

这是Agent Loop的执行层，负责创建Agent Session、接收流式输出、处理Tool Call，再把工具结果回灌给模型。

  厂商适配器

将不同模型厂商的API调用统一封装，免除上层为每家模型重写一套运行逻辑。

  传输与认证

负责连上模型服务，包括HTTP、SSE、WebSocket等传输方式与认证机制。

  LLM API

OpenClaw的Prompt、Tools、参数都会在这里给大模型，模型返回的内容也从这里返回。

  会话持久化与回传

结果落地层，把transcript、stream delta、最终回复写回会话，并将结果继续投递到飞书、WebChat、CLI等上层入口。

**2. 核心运行链路**

消息为什么能跨渠道共享上下文？

无论消息来自CLI、WebChat还是外部渠道，最终都会落到同一条执行主线：先找Session，再跑Agent，再决定如何回传。

![Image](images/img_004.png)

各模块的配合如下：

- Telegram/Slack/飞书等渠道负责接消息
- Routing负责找到正确的Agent和Session
- 编排层负责将消息组织成一次可执行任务（包括上下文整理、状态反馈等）
- Agent负责生成内容，结合prompt/memory/skills等完成推理
- outbound/channel plugin 负责将结果按对应渠道返回

3. 消息传递时序图

展示当一条消息从“收进来”到“发回去”的全过程，各个核心组件之间的交互顺序。

![Image](images/img_005.png)

OpenClaw收到消息后，会先完成去重、顺序控制和基础校验，再结合账号、会话和话题线程，定位到正确的Agent和Session。

接下来，系统会把正文、媒体、回复引用这些信息统一整理成上下文，再交给Agent Runtime执行。这个过程中，策略判断、hooks、typing 状态、skills、工具调用和记忆检索都会参与进来。

等Agent 产出结果后，系统再根据replyTo和线程关系，选择正确的投递目标，把回复发回Telegram等渠道。

4. 记忆系统

OpenClaw的记忆不是单一模块，而是由「工作区里的记忆文件」、「Agent运行时里的记忆工具」、「后台索引与检索层」三部分共同组成。

![Image](images/img_006.png)

如图所示：

- 在工作区，MEMORY.md 和 memory/\*.md是记忆本体，属于长期记忆。
- 在Agent Runtime中，MEMORY.md直接注入上下文，只覆盖会话启动时的上下文，而memory/\*.md 是通过memory\_search / memory\_get按需读取。
- 后台还有个Memory索引与检索层，会把 MEMORY.md 和 memory/\*.md 建成每个 agent 一份的 SQLite 索引，索引层负责chunk/embedding/检索，不是记忆内容本身。

另外，关于小龙虾的人设文件（SOUL.md / IDENTITY.md / USER.md）等，虽然也是bootstrap persona上下文，但不在memory\_search索引体系，不属于严格意义上的记忆，属于persona/identity注入。

![Image](images/img_007.png)

5. 插件系统设计

Gateway为中枢，插件系统是小龙虾的无限能力扩展。

下图展示了插件从“发现、加载、注册到运行时激活”的生命周期，以及Plugin SDK如何支持不同类型的插件。

![Image](images/img_008.png)

OpenClaw 的插件不是把能力写死在主流程里。

系统会先发现插件、校验声明文件，再按配置决定哪些插件真正进入运行时。

进入运行时后，插件能力不会直接散落在系统各处，而是先汇总到“运行时激活注册表”。

- 渠道插件：负责接消息入口；
- 平台插件：负责扩展tools、hooks、providers和skills；
- Gateway注入点：负责将这些能力接到methods、routes、services上。

最后，如果你也对Agent感兴趣，欢迎添加我的微信floracat2025（备注“公众号”）。
