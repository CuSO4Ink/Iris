// =============================================================
// Pass1_ComputeLocalAABB.hlsl
// 用途：Reduction 路径第 1 趟 —— 分组求局部 AABB（树形归约，无 atomic）
// 挂载：Simulation Stage，Iteration Count = G，iteration source = G（不是 Particles）
// Enabled 绑定：BoundsSource == Reduction
// 输入：ExecIndex, NumParticles, G(常量,如128)
// 输出 buffer：PartialMin[G], PartialMax[G]（每组写自己槽位，零冲突）
// =============================================================

int g     = ExecIndex;                      // 当前组号 0..G-1
int chunk = (NumParticles + G - 1) / G;     // 每组处理的粒子数（向上取整）
int begin = g * chunk;
int end   = min(begin + chunk, NumParticles);

float3 lo = float3( 3.402823e38,  3.402823e38,  3.402823e38);  // +FLT_MAX
float3 hi = float3(-3.402823e38, -3.402823e38, -3.402823e38);  // -FLT_MAX

for (int i = begin; i < end; ++i)
{
    // Particle Attribute Reader：读取方与被读 Emitter 的 sim target(CPU/GPU)必须一致
    float3 p = ReadParticlePosition(i);
    lo = min(lo, p);
    hi = max(hi, p);
}

PartialMin[g] = lo;   // 每组写各自独立的 g 槽位 → 无地址冲突 → 不需要原子
PartialMax[g] = hi;
