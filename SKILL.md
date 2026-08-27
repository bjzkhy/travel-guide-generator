---
name: travel-guide-generator
agent_created: true
description: 根据一份出行配置（YAML/JSON），生成结构一致、含 AI 照片、携程直链、天气标签的自包含旅行攻略 HTML。适用于亲子游/家庭游/普通出游的攻略制作，用户给出目的地、日期、航班、酒店等信息即可产出可分享的单文件攻略。
---

# 旅行攻略生成器

把出行信息变成一份**自包含**（图片 base64 内嵌、可手机离线打开）的精美攻略 HTML。
风格：天蓝(#0369a1)+珊瑚橘(#fb7186)清爽配色，含 8 大模块：整体路线图(节点-连线可视化)、城际交通推荐、酒店推荐、预算估算、完整时间轴、实用贴士、美食购物、亲子景点汇总。

整体路线图(`route`)为顶部总览：用「城市节点 → 交通连线」横向动线图，把每段交通的**具体班次/车次、出发→到达时间、时长、是否已出票**一目了然地标出来（飞机/高铁确定出行的统一显示「✅ 已出票」绿徽标）。

## 何时使用
用户说"做个旅游攻略/旅行计划""按这个模板出一份攻略""把出行信息做成攻略""出一份带整体路线图/动线图的攻略"，或提供目的地+日期+航班/酒店信息时。
示例："按沪杭亲子游的配置，生成一份带整体路线图的攻略 HTML" / "把天津→上海→杭州的航班和高铁画成顶部动线图，确定出行的都标已出票"。

## 输入
一份 YAML 或 JSON 配置（见 `references/config_example.yaml`）。核心字段：
- `meta`：标题、出发城市、城市列表、起止日期、出行人、交通方式、tabs、header 背景图 key、页脚
- `modules`：8 个布尔开关（route/transport/hotels/budget/timeline/tips/food/highlights），按需勾选；`route` 默认开
- `route`：整体路线图配置
  - `note`：副标题文案（如"四日动线总图：飞机往返 + 高铁 G1377 复兴号串联"）
  - `nodes`：城市节点列表 `（city/code/when/img/accent）`，顺序即动线；`accent: hz` 给该节点绿色环（如目的地杭州）
  - `links`：交通连线列表，**长度 = nodes 数量 − 1**，每项接在 nodes[i] 与 nodes[i+1] 之间：
    - `mode`：图标（飞机 `✈️` / 高铁 `🚄`）
    - `carrier`：航班号或车次（含运营方/车型，如 `国航 CA2839`、`G1377 复兴号`）
    - `dur`：出发→到达时间 · 时长（如 `08:15→10:45 · 2h30m`）
    - `ticketed`：省略时自动取对应 `transport[].confirmed`（城市对+类型匹配），显式 `true` 显示「✅ 已出票」绿徽标
    - `line_cls`：连线配色，`""` 去程(蓝) / `"hz"` 高铁(蓝绿) / `"back"` 返程(绿蓝)
  - `stats`（可选）：4 格统计条 `（value/label）`，如总里程/天数/城市数/打卡点
- `transport`：城际交通列表（飞机/高铁），含 from/to/date/航班号/舱位/是否确定出行/图片 key
- `hotels`：酒店列表（城市/是否确定出行/位置/参考价/图片 key/hotel_id）
- `budget`：预算行列表（类别/金额/说明），合计自动累加
- `timeline`：按天的行程（day/city/date/weather/items），每个 item 可带 photo key 与 price
- `tips`：带娃专项/预约提醒/防暑/避坑 四组列表
- `food`：多个子板块（标题 + 名称/特色 列表）

## 工作流（agent 执行）
1. **读配置**：解析用户给的 YAML/JSON（若无配置，先用 AskUserQuestion 收集核心字段再生成配置）。
2. **实时数据（按需）+ 信息完整度三态**：
   按用户提供的信息量走默认分支（核心：`confirmed` 三态——`true`已订 / `false`候选 / 省略或`null`待确认）：
   - **给全具体航班/酒店** → 写 `confirmed: true`，渲染「✅ 确定出行/已出票」，顶部无初稿横幅。
   - **仅给目的地+日期+人数（简单信息）** → 走**混合策略**：
     * 交通：用 `ctrip-wendao` 查候选班次回填 `transport`，`confirmed: false`（标「备选」），不强制下单；
     * 酒店：**不联网查**，留空 → 自动触发顶部「初稿」横幅 + 「⏳ 待确认」占位卡；
   - **缺出发地/日期** → 用 `AskUserQuestion` 追问关键项后再生成。
   - 天气：WebSearch 抓目的地预报，写入各 `timeline[].weather`。
   - route 连线 `ticketed` 自动取对应 `transport[].confirmed`（按 城市对+类型 匹配），不需手工双填；配置显式写 `ticketed` 可覆盖。
3. **出图（modules 涉及且 photos 未关时）**：用 ImageGen 生成下列图片，保存到 `assets/img/{key}.jpg`（key 见配置）：
   - `header_airplane`：飞机起飞背景（header 用）
   - 整体路线图节点地标：`tianjin_landmark` / `shanghai_landmark` / `hangzhou_landmark`（按 `route.nodes[].img`）
   - 交通卡目的地地标：`shanghai_landmark` / `hangzhou_landmark` / `tianjin_landmark`（按 `to` 城市）
   - 酒店：`portman` / `jingan_shangri` / `atour` / `liuyingli` / `orange_crystal` / `city_shangri`（按酒店 img 字段）
   - 时间轴景点/机场/酒店：按各 item 的 `photo` 字段
   - 同一 key 只出一次，重复引用自动复用（省信用点）。
4. **渲染**：运行
   ```
   python scripts/build.py --config <你的配置>.yaml --out guide.html --imgdir assets/img
   ```
   - 默认模板在 `assets/template.html`；`--template` 可覆盖。
   - 缺图时 build.py 会告警并跳过该图（不会报错中断）。
5. **呈现**：`present_files` 打开预览，交付用户。

## 携程链接规则（固化经验）
- **机票**：携程无"按航班号直订"公开 URL（行业限制）。链接为搜索页预填：
  `https://flights.ctrip.com/online/list/oneway-{出发3字码}-{到达3字码}?depdate=YYYY-MM-DD`
  城市 3 字码见 build.py `CITY_CODE`，可在 `meta.city_codes` 覆盖。
- **高铁**：`https://trains.ctrip.com/trainbooking/search?from={出发}&to={到达}&day={日期}`（中文城市名）。
- **酒店**：配置有 `hotel_id` → 详情页直链
  `https://hotels.ctrip.com/hotels/{hotel_id}.html?checkIn={入住}&checkOut={离店}`；
  无 `hotel_id` → 搜索页 `https://hotels.ctrip.com/hotels/list?city={城市ID}&checkin={入住}&checkout={离店}`。
  城市 ID 见 build.py `CITY_ID`，可在 `meta.city_ids` 覆盖。入住/离店取 `meta.start_date`/`meta.end_date`。

## 关键经验（从实战踩坑固化）
- **图片必须内嵌 base64**：相对路径图片在手机上打不开。build.py 默认将 `assets/img` 全部转 JPEG(质量85) 内嵌，HTML 完全自包含。
- **时间轴按天断开**：每天一个 `.timeline` 段，DAY 标题在段外，竖线不贯通。
- **信息完整度三态徽章**：`confirmed: true` →「✅ 确定出行」绿徽章；`confirmed: false` →「备选」灰徽章；`confirmed` 省略/`null` →「⏳ 待确认」黄徽章（框架态/初稿）。酒店留空时自动渲染「🏨 酒店待确认 ⏳ 待确认」占位卡。
- **整体路线图交通连线**：`ticketed` 省略时自动取对应 `transport[].confirmed`（城市对+类型匹配），任一已订即显示「✅ 已出票」绿徽标（与城际交通推荐呼应）；配置显式写 `ticketed` 可覆盖。连线文案统一为 `图标 运营方+班次/车次` + `出发→到达 · 时长`，如 `🚄 G1377 复兴号` / `09:30→10:25 · 55分钟`、`✈️ 国航 CA2839` / `08:15→10:45 · 2h30m`。
- **天气标签**加在 DAY 标题后，副标题附"天气为客观预报，临近出发请以实时预报为准"。
- **机票无法精准直订**，文案标注已订航班号即可；酒店可精准直链（需真实 hotel_id）。

## 依赖
- Python 3 + `PyYAML`（解析 YAML；JSON 配置无需）。缺则 `pip install pyyaml`。
- `Pillow`（图片转 JPEG；缺则 `pip install pillow`）。
- ImageGen 工具（出图）、ctrip-wendao connector（实时数据，可选）、WebSearch（天气，可选）。
