# 瀑布最终光照 Shader 补充说明

## 结论先说

反馈是对的：瀑布三个 DrawIndexed（9135、9143、9150）里导出的 PS，只负责把材质属性写进 GBuffer，并不在这里算最终灯光。

这一帧采用延迟渲染，光照是在瀑布 DrawIndexed 之后，以全屏 Draw/Compute 的形式统一完成的。这里不是“一个最终光照 Shader”，而是至少拆成下面几段：

1. **9135 / 9143 / 9150：瀑布材质阶段**——计算水流、泡沫、法线、粗糙度和材质遮罩，并写入 GBuffer。
2. **10526：太阳直射光与阴影阶段**——读取 GBuffer，采样级联和远距离太阳阴影，计算直射光 BRDF。
3. **11111：环境光、反射与间接光阶段**——读取 GBuffer、AO、SSR、环境 Cubemap 和局部光照体积，并累加到 HDR 光照缓冲。
4. **11297 等后续阶段：体积雾、光柱、云和后处理合成**——这部分才继续走向屏幕最终画面。

因此，正确说法应当是：**瀑布材质 Shader 只输出光照所需的属性；最终可见颜色由后续直射光、阴影、环境光、反射和体积效果共同合成。**

## 太阳直射光与阴影：Event 10526

- 类型：全屏 `DrawInstanced(4)` 的 Pixel Shader
- Shader：`ResourceId::5403`
- 反编译规模：830 行 DXBC
- 主要输入：Albedo、两通道压缩法线、Reflectance、Motion/Roughness、场景深度
- 阴影输入：两张 2048×2048 阴影图、一张 1024×1024 远距阴影图，以及屏幕空间阴影历史/辅助纹理
- 主要工作：从深度重建位置，解码法线和材质参数，使用大量 `sample_c_lz` 做阴影比较采样，再执行粗糙度相关的微表面高光、Fresnel 和漫反射计算
- 输出：直射光颜色 `o0.xyz`，以及一份辅助光照数据 `o1.xyzw`

可直接查看：

- [完整 DXBC 反编译](evidence/shaders/direct_sun_lighting_ps_5403_event10526.txt)
- [带注释的语义 HLSL](evidence/hlsl/direct_sun_lighting_ps_5403_event10526.hlsl)
- [完整资源与管线绑定](evidence/shaders/direct_sun_lighting_event10526_pipeline.json)

注意：RenderDoc 反射出的部分资源变量名与实际绑定用途不一致，判断依据不能只看名称。本结论同时核对了纹理格式、绑定槽、DXBC 的 `ld_indexable` 读取位置以及比较采样指令。

## 环境光、反射与间接光：Event 11111

- 类型：`[numthreads(8,8,1)]` 的 Compute Shader
- Shader：`ResourceId::3487`
- 反编译规模：1549 行 DXBC
- 主要输入：Albedo、Normal、Reflectance、Motion/Roughness、Depth、AO、SSR、环境 Cubemap、局部 Cubemap 和 SH/辐照度体积
- 主要工作：重建世界位置与法线，计算环境漫反射、GGX 环境高光、屏幕空间反射回退、局部反射探针和辐照度体积
- 输出：以“读取旧值 + 新光照”的方式累加到 `ResourceId::28483`，格式为 `R11G11B10_FLOAT` 的 HDR 光照缓冲

可直接查看：

- [完整 DXBC 反编译](evidence/shaders/deferred_lighting_cs_3487_event11111.txt)
- [带注释的语义 HLSL](evidence/hlsl/deferred_lighting_cs_3487_event11111.hlsl)
- [完整资源与管线绑定](evidence/shaders/deferred_lighting_event11111_pipeline.json)

这里要特别纠正：Event 11111 是**环境/间接光和反射累积**，不能单独称为“全部最终光照”。太阳直射光和阴影已经由 Event 10526 等前序光照 Pass 计算。

## 和瀑布三个 DrawIndexed 的关系

瀑布的 9135、9143、9150 都先写入同一套场景 GBuffer。后面的 Event 10526 和 Event 11111 是全屏光照，不再按“瀑布 Mesh”单独 Draw；它们会对屏幕上包括瀑布在内的有效像素统一着色。

也就是说，瀑布最终颜色的链路可以简化成：

`瀑布材质/GBuffer → 太阳直射光与阴影 → 环境光/反射/间接光累积 → 体积雾与后处理 → 屏幕画面`

## HLSL 文件的准确性说明

两个 `.hlsl` 是根据 DXBC 指令和 RenderDoc 管线绑定整理出的**语义还原版**，目的是让人快速读懂算法、输入和输出，并不是游戏原始源码，也不能保证直接编译得到完全相同的二进制。

需要逐指令核对时，以对应的完整 `.txt` DXBC 为准；需要阅读实现逻辑时，看带注释的 `.hlsl`。
