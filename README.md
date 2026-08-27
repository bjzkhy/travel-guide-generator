# travel-guide-generator

WorkBuddy 技能：根据一份出行配置（YAML/JSON），生成结构一致、图片 base64 内嵌、可离线打开的自包含旅游攻略 HTML。

## 特性
- 8 大模块：整体路线图 / 城际交通 / 酒店 / 预算 / 时间轴 / 实用贴士 / 美食 / 亲子景点
- 整体路线图：城市节点 → 交通连线的横向动线可视化，标注班次/车次/是否已出票
- 携程深链（机票/高铁/酒店）、天气标签、信息完整度三态徽章

## 使用
```bash
python scripts/build.py --config references/config_example.yaml --out guide.html --imgdir assets/img
```
详见 [SKILL.md](SKILL.md)。`assets/img` 含示例图片；配置中的图片 key 需对应到 `assets/img/{key}.jpg/png`。

## 注意
`references/` 下的配置均为**演示数据**（日期已平移、家庭信息已泛化），非真实行程。
