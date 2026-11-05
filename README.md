# 世界小报 · Kids-News

面向约6–8岁儿童的晚间中文新闻音频工作流。优先国内近期热点，国内没有适合儿童、事实可靠且能讲清的事件时，再选国际新闻。每期讲一件真实的事、解释一个核心理解、留下一个开放问题。使用火山豆包 TTS 配音，从已有音乐库挑选配乐，用 ffmpeg 编排停顿和转场。

## 开始使用

需要 Python 3.9+；音频生成使用标准库，混音和音频检查另需 `ffmpeg` / `ffprobe`。所有命令从项目根目录运行。

```bash
cp .env.example .env
# 可选：需要个性化称呼、听众信息或私人归档目标时建立本机配置
cp config/local.example.json config/local.json
```

在 `.env` 填写 API 凭据；在 `config/local.json` 填写节目名、称呼、年龄、兴趣、收听场景及归档目标。两者均由 Git 忽略，配置文件不能通过 shell source 执行。未建立个人配置时使用通用示例值。兴趣只影响讲述和解释方式，选题仍跟随近期时事。

公开模板先离线生成最终朗读稿，再配音：

```bash
python3 scripts/prepare_script.py --template examples/voice-preview.txt --output samples/public-demo.txt
python3 scripts/audio.py tts --text-file samples/public-demo.txt --output samples/public-demo.mp3 --speaker zh_female_vv_uranus_bigtts
```

准备脚本不会调用付费接口，也不会覆盖已有正文。模板支持 `{{program_name}}`、`{{listener_name}}`、`{{audience_age}}`、`{{interests}}`、`{{listening_context}}`。配音读取生成后的文本；归档也使用这份正文，保证文字与音频一致。个人配置变化后，已有成品保持原样；新版本须另选输出路径。`--dry-run` 会显示请求正文，个人内容的输出仅留在本机。

## 每日创作入口

项目只有一个创作 skill：[$kids-news-editor](.agents/skills/kids-news-editor/SKILL.md)，负责新闻选题、事实核查、口播与家长底稿。先读 skill 与[编辑规范](.agents/skills/kids-news-editor/references/editorial.md)。

新稿使用[固定片头](examples/episode-opening.txt)：短句口号、听众专属的节目身份，再直接进入新闻；不再说“晚上好”等问候。个人称呼由本机配置渲染，固定音乐仍为 `01-opening`。用户要求修正已交付节目时，独立保存修正版并同步正文、音频和当前归档入口；原成品及付费缓存保留，避免只改规则却漏改交付。

[固定结束语](examples/episode-ending.txt)在节目身份后直接说“我们下次再见”，不追加“晚安”等时段或睡眠祝福。片头、结束语均随当前交付同步核对。

先浏览国内综合新闻，优先当天及近72小时发生或有新进展的热点，必要时扩至近7天并说明理由。国内没有合适题时，再选国际新闻，并在底稿记录国内候选不合适的原因。比较候选时记录真实日期、关注度依据及儿童切口，不为补国际比例跳过合适国内题。核实一件事后，先讲清“谁遇到什么困难、做了什么、这次有什么变化”，再解释一个核心理解；前一分钟交代事件，以真实过程、递进追问、不同处境和角色选择展开，类比只作辅助。默认约15分钟（通常14–16分钟，实测为准），不靠重复、慢速或静默凑时长。参考节目有整集杂志与头条问题链两层；本项目沿用一个主事件，借鉴头条推进，不机械加入其他新闻或虚构留言。每期在 `episodes/YYYY-MM-DD/` 保存 `brief.md`、`script.txt`、`production.md` 和技术检查报告；同日换题或重制用该日下独立子目录，沿用当日声线，保留旧稿及付费缓存，归档按日期与题目/版本查重。来源及其待评审状态见 [新闻信息源](docs/新闻信息源.md) 与 `config/news-sources.json`；当前未启用正式每日采集，不得把历史试播当作当日新闻。

```bash
# 保存该日声线；不调用付费接口
python3 scripts/select_voice.py --episode-date YYYY-MM-DD

# 先准备好对应日期的最终正文，再生成音频
python3 scripts/audio.py tts --episode-date YYYY-MM-DD --text-file episodes/YYYY-MM-DD/script.txt --output episodes/YYYY-MM-DD/voice.mp3

# 按制作计划加入停顿和库存配乐
python3 scripts/assemble_episode.py --plan episodes/YYYY-MM-DD/mix-plan.json --output episodes/YYYY-MM-DD/final.mp3
```

日期参数须替换为实际节目日期。主持声线默认从 Vivi 与云舟中等概率随机选择，保存于 `state/voices/`；同日重跑复用，允许连续多天相同。片头固定 `01-opening`。配音、缓存恢复和混音见 [音频制作](docs/音频制作.md)，声线规则见 [声线选择](docs/声线选择.md)。

事实核查、正文与音频一致性、完整解码、时长、响度和停顿检查完成后，直接标记“已通过”，不设人工听审门槛，也不虚构已人工试听。

## 音乐与缓存

音乐库一次性准备27段，目录及用途见 [音乐库](assets/music/library.md) 和 `assets/music/catalog.json`。库存MP3已纳入Git版本管理；来源和授权限制见[配乐授权说明](assets/music/NOTICE.md)，本地提交不代表已获公开素材库分发授权。供应商任务侧车与批次结果仍只保存在本机，迁移时另行保留，避免重复计费。缺少合适库存时留白或报告缺口。`config/music-library.json` 保持 `reuse-only`，只有用户明确授权扩充才可修改并调用生成接口。

同名 JSON 保存请求、任务 ID、状态、时间戳和摘要，可能含完整个性化正文。保留这些缓存才能避免重复计费：成功结果复用；TTS 超时重跑原命令只查询既有任务；音乐请求结果不确定时停止重发。不同参数不能覆盖同一输出。`.lock` 仅在确认原进程结束后手动移除。不要因准备发布仓库而删除本地缓存。

历史维护方法见 [音乐生成记录](docs/音乐生成记录.md)，技术验证概况见 [制作记录](docs/制作记录.md)。

## 交付与归档

支持将成品放入百度网盘固定分享文件夹，并将音频、逐字稿及核验来源归档到 Notion。私人网盘地址、云端目录、Notion database / data source / view ID 仅放 `config/local.json` 的 `delivery`，不要写入公开文档或代码。凭据仅放 `.env`。百度自有应用OAuth授权、API上传与重跑查重已通过单次实测；Notion可由连接工具归档，尚无独立定时归档脚本。当前未配置无人值守任务、定时任务或额外消息推送。

百度网盘新增文件名建议为 `YYYY-MM-DD｜节目标题.mp3`。正式使用前验证原分享链接能看到后续新增文件、有效期和手机播放体验；不要假定转存副本会自动更新。

`delivery.baidu_remote_dir` 应填写原固定分享文件夹对应的实际云端路径，并确认可写；分享URL不能直接当上传路径。应用目录的连通性测试不等于原分享目录交付成功，测试目录不能自动设为日常默认目标。目标未确认时保持该字段为空，先记录缺口。

`/apps/应用名`只是常见示例，不应据此假定所有授权都只能写该目录。先核对用户已有目录，再按实际授权测试写入；不要擅自换掉固定分享目录。

### 百度网盘 API

在根目录 `.env` 配置自有应用的 `BAIDU_NETDISK_APPKEY`、`BAIDU_NETDISK_SECRETKEY`；兼容已有的 `AppKey`、`SecretKey` 大小写形式。应用凭据不能代替账号授权，账号持有人须亲自在百度官方页面确认应用与账号。

```bash
python3 scripts/baidu_auth.py status
python3 scripts/baidu_auth.py start
# 按输出的官方页面和设备码完成授权，再执行：
python3 scripts/baidu_auth.py poll

# 在config/local.json的delivery.baidu_remote_dir填写获准写入的绝对路径
python3 scripts/baidu_upload.py --file 'delivery/YYYY-MM-DD/YYYY-MM-DD｜节目标题.mp3' --create-dir
```

授权令牌仅写回被Git忽略的根目录 `.env`，不输出其值，文件权限600；上传脚本在令牌到期时使用refresh_token刷新。`SignKey`不是此OAuth上传流程所需的登录凭据。云端目录可使用应用专属目录，实际权限以应用授权为准；`--create-dir`仅在指定目录不存在时尝试创建，不会自动选择其他位置。

上传采用预上传、4MiB分片、创建文件三步；核对分片MD5，完成后查询云端文件ID、大小和元数据。`state/uploads/`保存不含令牌的任务状态；失败保留已完成分片，不无条件重试。重跑先查询既有文件，内容与缓存一致则直接复用；同名冲突不覆盖、不自动改名。API上传成功与原分享链接可见、手机可播放分别记录，不能相互代替。

这条路径由用户创建自有应用并亲自授予OAuth权限，不使用浏览器Cookie；此前浏览器工具的站点访问限制仍保留。迁移机器时安全保留 `.env`、`config/local.json` 和 `state/uploads/`，不要随公开仓库提交。

Notion 每期一条记录，建议字段如下：

| 字段 | 类型 | 内容 |
| --- | --- | --- |
| 节目标题 | 标题 | 本期标题 |
| 节目日期 | 日期 | 节目日期 |
| 音频文件 | 文件与媒体 | 最终混音 MP3 附件 |
| 信息来源 | 文本 | 标题、机构、发布日期、原始链接 |
| 百度网盘链接 | URL | 本机配置的收听入口 |
| 音频时长（分钟） | 数字 | 实测时长 |
| 状态 | 单选 | 技术检查后设为“已通过”；反馈后可记“需修改” |
| 核心理解 | 文本 | 一个核心理解 |
| 开放问题 | 文本 | 一个开放问题 |

完整逐字稿与详细事实依据只放该期页面正文，不另建“逐字稿”字段。网盘和 Notion 使用同一交付版 MP3，上传前确认实际文件大小与目标服务上限。重跑先按日期、题目/版本及该期本地 `notion-archive.json` 查重；同日换题独立归档，不覆盖旧期；两个渠道分别记录结果，失败时复用成功音频。

## 公开仓库与个人数据

可提交：通用代码、编辑规范、新闻来源清单、无个人信息的配置示例和模板。`.gitignore` 排除：

- `.env` 等凭据和 `config/local.json` 等本机设置。
- `private/`、`episodes/`、`delivery/`、`samples/`、`state/` 中的个人材料及运行记录。
- `assets/music/` 库存MP3以外的音频、音乐供应商侧车、批次结果和本机音频检查输出。

忽略规则只影响 Git，不会删除本机文件；迁移制作环境时须另外安全备份个人配置、成品、音乐素材、缓存与声线状态。不要把含个人信息的音频当作公开示例。若文件已经被其他仓库跟踪或提交，单加 `.gitignore` 不会移除旧记录，发布前还须检查暂存区与历史。

[参考节目分析](docs/参考节目分析.md) 保留通用叙事研究；原始材料和个人信息不随仓库发布。
