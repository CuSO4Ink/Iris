// =============================================================
// Pass2_MergeAABB.hlsl
// 用途：Reduction 路径第 2 趟 —— 归并 G 个局部 AABB 成全局 AABB
// 挂载：Simulation Stage，Iteration Count = 1（单线程）
// Enabled 绑定：BoundsSource == Reduction
// 输入 buffer：PartialMin[G], PartialMax[G]；常量 G
// 输出：Emitter.AABBMin, Emitter.AABBMax（persistent，供下一帧 Emitter Update 读取）
// 注意：本 Stage 跑在 Emitter Update 之后 → 结果隔帧生效（结构性一帧延迟，Padding 补偿）
// =============================================================

float3 lo = float3( 3.402823e38,  3.402823e38,  3.402823e38);  // +FLT_MAX
float3 hi = float3(-3.402823e38, -3.402823e38, -3.402823e38);  // -FLT_MAX

for (int g = 0; g < G; ++g)
{
    lo = min(lo, PartialMin[g]);
    hi = max(hi, PartialMax[g]);
}

OutAABBMin = lo;   // 接到 Emitter.AABBMin
OutAABBMax = hi;   // 接到 Emitter.AABBMax
