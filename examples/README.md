# 示例数据说明

`aggregates_demo.csv` 是**合成演示数据（SYNTHETIC）**，不是实测观测。

- 结构：3 个处理（CK 对照 / NPK 化肥 / M 有机肥）× 3 个 block × 2 个伪重复 = 18 个样品，每样品 4 个粒级。
- 生成规则：固定基准质量比例与 SOC/POC 梯度，叠加对称的 block 与重复扰动；容重 1.21–1.31 g/cm3，深度统一 20 cm。
- 用途：跑通 `validate` / `compute`、检查输出格式与图，不代表处理效应的真实大小。
- 参照：README 与测试均以 `CK` 为 `--reference`。

CSV 顶部三行注释与 README 均标注合成属性。替换为实测数据时，保持列名、粒级取值与单位不变。
