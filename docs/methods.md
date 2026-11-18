# 方法与计算口径

本文件定义 `aggcarbon` 的全部计算、单位、假设与局限。报告模板中的公式与此处一致；若修改代码，必须同步修改本文件与测试夹具。

## 1. 适用场景与单位

输入为湿筛法获得的团聚体粒级质量与化学分析结果。典型流程：田间分层采样 → 室内湿筛分级 → 各粒级 SOC / POC / MAOC 测定 → 本工具计算稳定性与碳库指标。

| 符号 | 含义 | 单位 |
|---|---|---|
| m_i | 第 i 粒级烘干质量 | g |
| p_i | 第 i 粒级质量比例 | 0–1 |
| d_i | 第 i 粒级平均直径 | mm |
| BD | 容重 | g/cm3 |
| depth | 采样层厚度 | cm |
| M | 单位面积土壤质量 | Mg/ha |
| SOC_i, POC_i, MAOC_i | 粒级碳浓度 | g C / kg 土 |
| stock_i | 粒级碳储量 | Mg C / ha |
| M_ref | ESM 参照土壤质量 | Mg/ha |

粒级固定为 `>2`、`1-2`、`0.25-1`、`<0.25` mm，平均直径 d_i 依次取 4、1.5、0.625、0.125 mm。这是文献常用的**名义平均直径**，不是每个样品的实测中值。

## 2. 公式

对样品 s（同一 `sample_id` 的四行）：

1. 质量比例

   p_i = m_i / Σ_j m_j

2. 平均重量直径（MWD，mm）

   MWD = Σ_i p_i · d_i

3. 几何平均直径（GMD，mm）

   GMD = exp( Σ_i p_i · ln d_i )，仅对 p_i > 0 的粒级求和

4. 大团聚体比例（R>0.25，无量纲）

   R>0.25 = Σ_{d_i > 0.25 mm} p_i，即 `>2`、`1-2`、`0.25-1` 三类之和

5. 单位面积土壤质量（Mg/ha）

   M = BD(g/cm3) × depth(cm) × 100

   推导：1 ha = 10 000 m2；depth cm = 0.01 × depth m；体积 = 100 × depth m3/ha；BD 以 t/m3 计，故质量 = BD × depth × 100 t/ha = 同数值 Mg/ha。

6. 粒级与总 SOC 储量（Mg/ha）

   stock_i = M · p_i · SOC_i / 1000

   SOC_stock = Σ_i stock_i

   因子 1/1000 把 g/kg 换算为 kg/Mg。

7. 等效土壤质量校正（ESM；给出 `--reference-mass` 时）

   factor_ESM = M_ref / M_sample

   stock_i,ESM = stock_i · factor_ESM

   POC、MAOC 储量按同样倍率缩放；浓度、MWD、GMD、R>0.25、POC/MAOC 比值不变。`--reference-mass` 应与比较目标层（通常为参照处理）的实测土壤质量一致。

8. 碳库与活性指标（参照处理 r）

   CPI = POC_stock,treat / POC_stock,r

   CMI = CPI × (SOC_stock,treat / SOC_stock,r) × 100

   LI = POC_stock,sample / SOC_stock,sample

   参照处理的 CPI 定义为 1，CMI 定义为 100。CPI 是无量纲比值；CMI 是以 100 为基准的指数。LI（lability index，活性指数）为该样品 POC 占 SOC 的比例（0–1），数值越高表示碳库越以易分解组分主导；它是样品内比值，不受 ESM 缩放影响，也不依赖参照处理。

9. 不确定区间

   在处理内按 `block` 有放回重采样，每个 replicate 抽取与原 block 数相同的 block（整块内样品全部纳入），重算处理均值；2000 次后取 2.5 与 97.5 百分位。随机种子默认 42，可复现。CPI/CMI 的区间由同一 replicate 的处理与参照储量均值相除得到。

## 3. 手算校核例

两粒级样品：m = (70, 30) g，对应 d = (4, 0.125) mm，BD = 1.5 g/cm3，depth = 20 cm，SOC = 10 g/kg。

- p = (0.7, 0.3)
- MWD = 0.7×4 + 0.3×0.125 = **2.8375 mm**
- GMD = exp(0.7×ln4 + 0.3×ln0.125) = **1.4143 mm**
- R>0.25 = **0.7**
- M = 1.5×20×100 = 3000 Mg/ha
- SOC_stock = 3000×1×10/1000 = **30 Mg/ha**
- 若 M_ref = 2000 Mg/ha：factor = 0.6667，SOC_stock,ESM = **20 Mg/ha**

另一组处理 POC = 3、SOC = 30 Mg/ha，参照 POC = 2、SOC = 20 Mg/ha：CPI = 1.5，CMI = 1.5×1.5×100 = **225**；参照处理自身 CPI = 1、CMI = 100。

上述数值均作为 `tests/test_compute.py` 的独立夹具。

## 4. 输入校验

- 每样品必须恰好覆盖四个粒级各一次；质量非负且总和 > 0。
- BD 限定 0.5–2.0 g/cm3，SOC 限定 0–200 g/kg，depth > 0，POC/MAOC 非负。
- 同一 `sample_id` 的 treatment/block/BD/depth 必须一致；`sample_id` 全表唯一。
- 参照处理必须存在；参照为空或不存在时报错并以非零码退出。
- block 少于 2 个时给出警告，区间仍输出但视为退化。

## 5. 假设

1. 四类粒级的直径可用固定的名义均值代表，且样品间可比。
2. 湿筛流程（前处理、振荡、筛组、时间）在处理间一致。
3. 每样品四行的容重与深度相同，代表同一采样层。
4. SOC、POC、MAOC 是该粒级混合样的浓度，可直接按质量比例加权。
5. ESM 参照质量代表目标比较层；未提供时不作质量校正。
6. 处理均值是关注量，block 是重采样单元。

## 6. 局限

- 名义平均直径对粒径分布偏斜敏感；MWD/GMD 不能替代完整的粒级分布。
- 单一容重与固定深度忽略压实、砾石与层间差异；ESM 只能部分缓解，不能替代分层实测。
- 湿筛法本身会破坏部分团聚体，结果依赖操作一致性（ISO 11277）。
- POC/MAOC 的物理分组回收率与分散强度会系统影响 CPI/CMI；两者之和未必等于 SOC。
- CMI 强依赖参照处理选择，100 只在选定参照下有意义；跨试验比较需谨慎。
- bootstrap 假设 block 间可交换，block 少或空间自相关时区间偏窄。
- 储量未扣除 >2 mm 砾石与根系，也未外推到深层。

## 7. 出处

- 湿筛与稳定性：ISO 11277:2009；Kemper, W.D. & Rosenau, R.C. (1986). Aggregate stability and size distribution. In: *Methods of Soil Analysis, Part 1*, 2nd ed., ASA, 425–442.
- 团聚体与碳保护：Six, J., Elliott, E.T. & Paustian, K. (2000). Soil macroaggregate turnover and microaggregate formation. *Soil Biology and Biochemistry* 32, 2099–2103. Six, J., Conant, R.T., Paul, E.A. & Paustian, K. (2002). Stabilization mechanisms of soil organic matter. *Plant and Soil* 241, 155–176.
- 物理分组 POC/MAOC：Cambardella, C.A. & Elliott, E.T. (1992). Particulate soil organic-matter changes across a grassland cultivation sequence. *Soil Science Society of America Journal* 56, 777–783.
- ESM：Ellert, B.H. & Bettany, J.R. (1995). Calculation of organic matter and nutrients stored in soils under contrasting management regimes. *Canadian Journal of Soil Science* 75, 529–538. Wendt, J.W. & Hauser, S. (2013). An equivalent soil mass procedure for monitoring soil organic carbon in multiple soil layers. *European Journal of Soil Science* 64, 58–65.
- CPI/CMI：Blair, G.J., Lefroy, R.D.B. & Lisle, L. (1995). Soil carbon fractions based on their degree of oxidation, and the development of a carbon management index for agricultural systems. *Australian Journal of Agricultural Research* 46, 1459–1466.

## 8. 结果解读约定

- CMI > 100 表示相对参照改善，< 100 表示退化；区间跨过 100 时不宣称显著。
- 报告同时给出粒级分布、MWD、GMD、R>0.25，避免单一指数误读。
- 所有储量注明是否 ESM 校正；未校正结果只用于容重与深度相近的样品。
