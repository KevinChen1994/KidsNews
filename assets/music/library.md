# 可复用音乐库

共 27 段，约 22.9 分钟。一次性建库完成；每天只选库存，不再自动生成。

音频已通过解码和目标时长检查。前25段用户已认可，新曲仍待听审，状态见目录。以下中文曲名和用途描述来自生成意图。

## 怎么用

- 片头固定使用 01-opening（最初的温暖钢琴与马林巴），片尾按需选择。转场每期少量使用。
- 主底乐按叙事情绪选，避免连续几期用同一首；优先避开最近3期的主底乐，记录在每期 production.md。不要把音乐风格绑定到固定新闻领域。
- 一期通常选1–3段底乐即可，讲关键解释、等待回答和需要专注时留白，不要求铺满十分钟。
- 60–90秒底乐可以按段落截取。确需延长时做交叉淡化并听接点；当前曲目未验收为无缝循环，不能直接硬拼后宣称自然。
- 缺合适配乐时留白或报告缺口，不自动请求新音乐。用户以后明确要求扩充，才修改 config/music-library.json。
- 同时改变乐器、段落位置与音乐密度，比单纯堆曲目更能减少重复感；保持人声清楚。

## 开场

| 曲目 | 时长 | 试听 |
|---|---:|---|
| 01-opening | 15秒 | [01-opening](01-opening.mp3) |
| 钢琴晨光 | 20秒 | [06-opening-piano](06-opening-piano.mp3) |
| 木吉他问候 | 20秒 | [07-opening-guitar](07-opening-guitar.mp3) |

## 好奇

| 曲目 | 时长 | 试听 |
|---|---:|---|
| 02-curiosity | 30秒 | [02-curiosity](02-curiosity.mp3) |
| 钢琴小问号 | 90秒 | [08-curiosity-piano](08-curiosity-piano.mp3) |
| 马林巴线索 | 90秒 | [09-curiosity-marimba](09-curiosity-marimba.mp3) |
| 竖琴发现 | 90秒 | [10-curiosity-harp](10-curiosity-harp.mp3) |
| 陶笛线索 | 90秒 | [26-bed-26](26-bed-26.mp3) |
| 木管小问号 | 90秒 | [27-bed-27](27-bed-27.mp3) |

## 轻快

| 曲目 | 时长 | 试听 |
|---|---:|---|
| 03-light | 30秒 | [03-light](03-light.mp3) |
| 吉他小步走 | 90秒 | [11-light-guitar](11-light-guitar.mp3) |
| 拨弦散步 | 90秒 | [12-light-pizzicato](12-light-pizzicato.mp3) |
| 木琴新发现 | 90秒 | [13-light-mallets](13-light-mallets.mp3) |

## 安静

| 曲目 | 时长 | 试听 |
|---|---:|---|
| 04-calm | 30秒 | [04-calm](04-calm.mp3) |
| 钢琴晚风 | 90秒 | [14-calm-piano](14-calm-piano.mp3) |
| 吉他夜灯 | 90秒 | [15-calm-guitar](15-calm-guitar.mp3) |
| 竖琴月光 | 60秒 | [16-calm-harp](16-calm-harp.mp3) |

## 思考

| 曲目 | 时长 | 试听 |
|---|---:|---|
| 大提琴慢想 | 60秒 | [17-reflection-cello](17-reflection-cello.mp3) |
| 钢琴留白 | 60秒 | [18-reflection-piano](18-reflection-piano.mp3) |

## 叙事

| 曲目 | 时长 | 试听 |
|---|---:|---|
| 温暖叙事 | 60秒 | [19-neutral-acoustic](19-neutral-acoustic.mp3) |

## 转场

| 曲目 | 时长 | 试听 |
|---|---:|---|
| 马林巴翻页 | 8秒 | [20-transition-marimba](20-transition-marimba.mp3) |
| 钢琴翻页 | 8秒 | [21-transition-piano](21-transition-piano.mp3) |
| 吉他翻页 | 8秒 | [22-transition-guitar](22-transition-guitar.mp3) |
| 竖琴转身 | 8秒 | [23-transition-harp](23-transition-harp.mp3) |

## 收尾

| 曲目 | 时长 | 试听 |
|---|---:|---|
| 05-ending | 15秒 | [05-ending](05-ending.mp3) |
| 晚安钢琴 | 20秒 | [24-ending-piano](24-ending-piano.mp3) |
| 晚安吉他 | 20秒 | [25-ending-guitar](25-ending-guitar.mp3) |

## 制作数据

[机器可读目录](catalog.json)保存角色、时长、听审状态。各MP3同名JSON保存原提示词、模型、状态和生成ID；保留原始文件，剪辑另存。
