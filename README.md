# travel-guide-generator

一个用于 WorkBuddy 的技能（Skill）：根据一份出行配置（YAML / JSON），生成**结构一致、自包含**的旅行攻略 HTML。

> 自包含 = 图片 base64 内嵌、可手机离线打开、单文件可分享。

适用场景：亲子游 / 家庭游 / 普通出游的攻略制作。用户给出目的地、日期、航班、酒店等信息，即可产出一份美观、可直接转发给家人的攻略。

---

## 功能特性

- **8 大模块**：整体路线图（节点-连线动线图）、城际交通推荐、酒店推荐、预算估算、完整时间轴、实用贴士、美食购物、亲子景点汇总（可按需开关）。
- **整体路线图（route）**：顶部总览，用「城市节点 → 交通连线」横向动线图，把每段交通的具体班次/车次、出发→到达时间、时长、是否已出票一目了然标出（确定出行的显示「✅ 已出票」绿徽标）。
- **清爽配色**：天蓝 `#0369a1` + 珊瑚橘 `#fb7186`。
- **可配置**：目的地、日期、航班、酒店、预算、时间轴、贴士、美食、景点全部通过一份 YAML/JSON 配置驱动，无需改代码。

## 安装（WorkBuddy 用户）

将本仓库克隆 / 解压到 WorkBuddy 的技能目录：

```bash
# 方式一：克隆
git clone https://github.com/<你的用户名>/travel-guide-generator.git ~/.workbuddy/skills/travel-guide-generator

# 方式二：下载 zip 解压后放入
#   解压后目录结构应为 travel-guide-generator/SKILL.md、/assets、/scripts、/references
```

依赖（用于本地 `build.py` 渲染）：

```bash
pip install pillow pyyaml
```

重启 WorkBuddy 后，说"做个旅游攻略"即可触发。

## 使用方法

准备一份配置（参考 `references/config_example.yaml`），然后对 WorkBuddy 说：

> 按 `config_example.yaml` 的配置，生成一份带整体路线图的攻略 HTML。

或通过 `scripts/build.py` 本地渲染：

```bash
python scripts/build.py references/config_example.yaml output.html
```

## 目录结构

```
travel-guide-generator/
├── SKILL.md                  # 技能定义与使用指引（必读）
├── assets/
│   ├── template.html         # 攻略 HTML 模板（同构、可二次开发）
│   └── img/                  # 48 张内置素材图（地标/机场/景点等）
├── references/               # 配置样例（北京-港澳 / 天津-首尔 / 通用模板）
│   ├── config_example.yaml
│   ├── config_bj_hk_mo.yaml
│   └── config_tianjin_seoul.yaml
├── scripts/
│   └── build.py              # 本地渲染脚本
├── LICENSE                   # MIT
└── README.md
```

## 配置示例（精简）

```yaml
meta:
  title: "沪杭亲子四日游"
  from: "北京"
  cities: ["上海", "杭州"]
  start: "2026-10-01"
  end: "2026-10-04"
  travelers: "2 大 1 小"
  transport: "飞机 + 高铁"
  tabs: ["路线", "酒店", "时间轴", "美食"]
  header_img: "victoria_harbour"
  footer: "祝旅途愉快 ✈️"
modules:
  route: true
  transport: true
  hotels: true
  budget: true
  timeline: true
  tips: true
  food: true
  highlights: true
route:
  note: "四日动线总图：飞机往返 + 高铁 G1377 复兴号串联"
  nodes:
    - { city: "上海", code: "SHA", when: "Day1-3", img: "beijing_landmark", accent: "" }
    - { city: "杭州", code: "HGH", when: "Day3-4", img: "hongkong_landmark", accent: "hz" }
  links:
    - { mode: "🚄", carrier: "G1377 复兴号", dur: "09:00→10:30 · 1h30m", ticketed: true, line_cls: "hz" }
```

更多字段说明见 `SKILL.md` 与 `references/` 下的样例。

## 开源许可

[MIT](LICENSE) © 2026 bjzkh
