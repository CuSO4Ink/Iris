// ============================================================
// PP_CyberScan — 直接粘贴到 Custom 节点的代码
// ============================================================
// 
// 【UE 材质搭建步骤】
// 
// 1. 新建 Material:
//    - Material Domain = Post Process
//    - Blendable Location = After Tonemapping
//
// 2. 添加节点：
//    - ScalarParameter "Progress" (Default=0, 范围 0~1)
//    - ScalarParameter "MaxDepth" (Default=50000)
//    - SceneTexture (PostProcessInput0) → 取 Color 输出
//    - SceneTexture (SceneDepth) 
//    - ScreenPosition → 取 ViewportUV 输出
//    - Time
//
// 3. Custom 节点设置：
//    - Output Type: CMOT_Float3
//    - 添加 5 个输入引脚（见下）
//    - 输出连接到 → Emissive Color
//
// 4. 使用：
//    - 放到 PostProcessVolume 的 Blendables 里
//    - 或通过 MID (动态材质实例) 驱动 Progress 参数
//    - Progress=0 无效果，Progress=1 扫描到最远
//
// ============================================================
// Custom Node 输入引脚：
//   Input 0: SceneColor (float3) — SceneTexture:PostProcessInput0 的 RGB
//   Input 1: Depth (float)       — SceneTexture:SceneDepth
//   Input 2: UV (float2)         — ScreenPosition (ViewportUV)
//   Input 3: Progress (float)    — ScalarParameter "Progress"
//   Input 4: Time (float)        — Time 节点
// ============================================================

// -- 可调参数（可提为 ScalarParameter）--
float ScanWidth = 0.06;
float ChromaStr = 0.008;
float DistortStr = 0.01;
float EdgeGlow = 12.0;
float GridDensity = 150.0;
float MaxDist = 50000.0;

// -- 深度归一化 --
float depthN = saturate(Depth / MaxDist);

// -- 扫描带 --
float dist = abs(depthN - Progress);
float mask = exp(-dist * dist / (ScanWidth * ScanWidth));
float edge = exp(-dist * dist / (ScanWidth * ScanWidth * 0.08));

// -- 噪声 --
float n1 = frac(sin(dot(UV * 127.1 + Time * 2.7, float2(12.9898, 78.233))) * 43758.5453);
float n2 = frac(sin(dot(UV * 311.7 + Time * 3.1, float2(39.346, 11.135))) * 43758.5453);

// -- 色散（通道偏移模拟）--
float ca = ChromaStr * mask;
float3 aberColor = float3(
    SceneColor.r * (1.0 + ca * 3.0),
    SceneColor.g * (1.0 + ca * 0.5),
    SceneColor.b * (1.0 - ca * 2.5)
);

// -- UV 扰动 --
float3 distColor = lerp(SceneColor, aberColor, mask);
distColor += (n1 - 0.5) * DistortStr * mask;

// -- 前沿辉光 --
float3 scanTint = float3(0.05, 0.85, 1.0);
float3 glow = scanTint * edge * EdgeGlow;

// -- 赛博网格 --
float2 gUV = UV * GridDensity;
float gLine = max(
    step(frac(gUV.x), 0.03),
    step(frac(gUV.y), 0.03)
);
// 网格只在扫描区域内显示，且半透明
float3 gridCol = scanTint * gLine * mask * 0.25;

// -- 水平扫描干扰线 --
float hLine = step(0.97, frac(UV.y * 400.0 + Time * 8.0)) * mask * 0.2;

// -- 深度轮廓增强（扫描区 Sobel-like 边缘检测近似）--
// 简化：基于深度差检测边缘
float edgeDetect = saturate(fwidth(depthN) * 500.0) * mask;
float3 edgeCol = scanTint * edgeDetect * 2.0;

// -- 合成 --
float3 result = distColor + glow + gridCol + hLine + edgeCol;

// -- 扫描区外保持原色 --
result = lerp(SceneColor, result, saturate(mask * 1.5 + edge * 0.5));

return result;
