// Copyright 2026 Violina. All Rights Reserved.

#include "GaussianVolumeSceneViewExtension.h"
#include "GaussianVolumeShaders.h"
#include "GaussianVolumeTypes.h"
#include "HAL/IConsoleManager.h"
#include "CommonRenderResources.h"
#include "PipelineStateCache.h"
#include "RenderGraphBuilder.h"
#include "RenderGraphUtils.h"
#include "ShaderParameterStruct.h"
#include "SceneView.h"
#include "SceneTexturesConfig.h"
#include "SceneRenderTargetParameters.h"
#include "RHIResources.h"
#include "ScreenPass.h"
#include "PostProcess/PostProcessMaterialInputs.h"
#include "ProfilingDebugging/RealtimeGPUProfiler.h"
#include "SceneRendering.h"  // FViewInfo::ViewRect (primary/scaled render rect for SceneDepth)
#include "SystemTextures.h"

DEFINE_LOG_CATEGORY_STATIC(LogGaussianVolumeCandidates, Log, All);
DECLARE_GPU_STAT_NAMED(GaussianVolume, TEXT("GaussianVolume"));
DECLARE_GPU_STAT_NAMED(GaussianVolumePoolFree, TEXT("GaussianVolumePoolFree"));
DECLARE_GPU_STAT_NAMED(NanoVDBBaseline, TEXT("NanoVDBBaseline"));

static TAutoConsoleVariable<int32> CVarGaussianVolumeCandidatePoolCapacity(
	TEXT("r.GaussianVolume.CandidatePoolCapacity"),
	0,
	TEXT("Total candidate IDs shared by all 32x32 tiles. 0 allocates the exact worst-case tile matrix."),
	ECVF_RenderThreadSafe);

static TAutoConsoleVariable<int32> CVarGaussianVolumeLogCandidateStats(
	TEXT("r.GaussianVolume.LogCandidateStats"),
	0,
	TEXT("Set to 1 for one asynchronous log of requested/granted candidate IDs."),
	ECVF_RenderThreadSafe);

static TAutoConsoleVariable<int32> CVarGaussianVolumeTightPBF(
	TEXT("r.GaussianVolume.TightPBF"),
	1,
	TEXT("Use exact conservative ellipsoid projection bounds for tile coverage. 0 restores support spheres."),
	ECVF_RenderThreadSafe);

static TAutoConsoleVariable<int32> CVarGaussianVolumePoolFreeRaster(
	TEXT("r.GaussianVolume.PoolFreeRaster"),
	0,
	TEXT("A/B only: draw uniform-medium analytic proxies without a candidate pool."),
	ECVF_RenderThreadSafe);

static TAutoConsoleVariable<float> CVarGaussianVolumePoolFreeResolutionScale(
	TEXT("r.GaussianVolume.PoolFreeResolutionScale"),
	0.5f,
	TEXT("Internal linear resolution of pool-free optical-depth rasterization [0.25, 1]."),
	ECVF_RenderThreadSafe);

static TAutoConsoleVariable<int32> CVarGaussianVolumeInPlaceComposite(
	TEXT("r.GaussianVolume.InPlaceComposite"),
	1,
	TEXT("Composite directly when scene color supports UAV; otherwise use the copy fallback."),
	ECVF_RenderThreadSafe);

FGaussianVolumeSceneViewExtension::FGaussianVolumeSceneViewExtension(const FAutoRegister& AutoReg, UWorld* InWorld)
	: FWorldSceneViewExtension(AutoReg, InWorld)
{
}

void FGaussianVolumeSceneViewExtension::UpdateGaussianData_GameThread(
	TArray<GaussianVolumeGPU::FPackedPrimitive> HighPackedData,
	TArray<GaussianVolumeGPU::FPackedPrimitive> MediumPackedData,
	TArray<GaussianVolumeGPU::FPackedPrimitive> LowPackedData,
	TArray<GaussianVolumeGPU::FPackedInstance> HighInstances,
	TArray<GaussianVolumeGPU::FPackedInstance> MediumInstances,
	TArray<GaussianVolumeGPU::FPackedInstance> LowInstances,
	FVector BoundsCenter,
	float BoundsRadius,
	bool bEnableScreenSizeLod,
	float HighMinScreenRadius,
	float MediumMinScreenRadius,
	float LodHysteresis)
{
	const bool bHighUniform = GaussianVolumeGPU::HasUniformAppearance(HighPackedData);
	const bool bMediumUniform = GaussianVolumeGPU::HasUniformAppearance(MediumPackedData);
	const bool bLowUniform = GaussianVolumeGPU::HasUniformAppearance(LowPackedData);
	const bool bHighDirectionalLightTau = GaussianVolumeGPU::HasDirectionalLightTau(HighPackedData);
	const bool bMediumDirectionalLightTau = GaussianVolumeGPU::HasDirectionalLightTau(MediumPackedData);
	const bool bLowDirectionalLightTau = GaussianVolumeGPU::HasDirectionalLightTau(LowPackedData);
	const FVector4f HighAppearance = bHighUniform ? GaussianVolumeGPU::GetAppearance(HighPackedData[0]) : FVector4f(1, 1, 1, 0);
	const FVector4f MediumAppearance = bMediumUniform ? GaussianVolumeGPU::GetAppearance(MediumPackedData[0]) : FVector4f(1, 1, 1, 0);
	const FVector4f LowAppearance = bLowUniform ? GaussianVolumeGPU::GetAppearance(LowPackedData[0]) : FVector4f(1, 1, 1, 0);
	ENQUEUE_RENDER_COMMAND(GaussianVolumeUpdateData)(
		[this,
		 High = MoveTemp(HighPackedData), Medium = MoveTemp(MediumPackedData), Low = MoveTemp(LowPackedData),
		 HighInstanceData = MoveTemp(HighInstances),
		 MediumInstanceData = MoveTemp(MediumInstances),
		 LowInstanceData = MoveTemp(LowInstances),
		 BoundsCenter, BoundsRadius, bEnableScreenSizeLod, HighMinScreenRadius, MediumMinScreenRadius, LodHysteresis,
		 bHighUniform, bMediumUniform, bLowUniform,
		 bHighDirectionalLightTau, bMediumDirectionalLightTau, bLowDirectionalLightTau,
		 HighAppearance, MediumAppearance, LowAppearance](FRHICommandListImmediate&) mutable
		{
			for (int32 Lod = 0; Lod < 3; ++Lod)
			{
				LightTauPooled_RT[Lod].SafeRelease();
				bLightTauDirty_RT[Lod] = true;
			}
			PackedGaussianData_RT[0] = MoveTemp(High);
			PackedGaussianData_RT[1] = MoveTemp(Medium);
			PackedGaussianData_RT[2] = MoveTemp(Low);
			PackedInstanceData_RT[0] = MoveTemp(HighInstanceData);
			PackedInstanceData_RT[1] = MoveTemp(MediumInstanceData);
			PackedInstanceData_RT[2] = MoveTemp(LowInstanceData);
			bUniformAppearance_RT[0] = bHighUniform;
			bUniformAppearance_RT[1] = bMediumUniform;
			bUniformAppearance_RT[2] = bLowUniform;
			bDirectionalLightTau_RT[0] = bHighDirectionalLightTau;
			bDirectionalLightTau_RT[1] = bMediumDirectionalLightTau;
			bDirectionalLightTau_RT[2] = bLowDirectionalLightTau;
			UniformAppearance_RT[0] = HighAppearance;
			UniformAppearance_RT[1] = MediumAppearance;
			UniformAppearance_RT[2] = LowAppearance;
			LodBoundsCenter_RT = BoundsCenter;
			LodBoundsRadius_RT = BoundsRadius;
			bEnableScreenSizeLod_RT = bEnableScreenSizeLod;
			HighLodMinScreenRadius_RT = HighMinScreenRadius;
			MediumLodMinScreenRadius_RT = MediumMinScreenRadius;
			LodHysteresis_RT = LodHysteresis;
		});
}

void FGaussianVolumeSceneViewExtension::UpdateLighting_GameThread(
	FVector InLightDir, FLinearColor InLightColor, FLinearColor InAmbientColor,
	float InPowderFactor, float InMaxRayDistance, bool bInUseSceneDepth, uint32 InDebugView)
{
	ENQUEUE_RENDER_COMMAND(GaussianVolumeUpdateLighting)(
		[this, InLightDir, InLightColor, InAmbientColor, InPowderFactor, InMaxRayDistance, bInUseSceneDepth, InDebugView](FRHICommandListImmediate&)
		{
			const FVector4f NewLightDir(
				static_cast<float>(InLightDir.X), static_cast<float>(InLightDir.Y),
				static_cast<float>(InLightDir.Z), 0.0f);
			if (!LightDir_RT.Equals(NewLightDir, 1e-4f)
				|| !FMath::IsNearlyEqual(MaxRayDistance_RT, InMaxRayDistance))
			{
				bLightTauDirty_RT[0] = bLightTauDirty_RT[1] = bLightTauDirty_RT[2] = true;
			}
			LightDir_RT = NewLightDir;
			LightColor_RT = FVector4f(InLightColor.R, InLightColor.G, InLightColor.B, InLightColor.A);
			AmbientColor_RT = FVector4f(InAmbientColor.R, InAmbientColor.G, InAmbientColor.B, InAmbientColor.A);
			PowderFactor_RT = InPowderFactor;
			MaxRayDistance_RT = InMaxRayDistance;
			bUseSceneDepth_RT = bInUseSceneDepth ? 1u : 0u;
			DebugView_RT = InDebugView;
		});
}

void FGaussianVolumeSceneViewExtension::UpdateNanoVdbData_GameThread(
	TArray<uint32> GridWords,
	const FMatrix44f& WorldToNanoLocal,
	FLinearColor Albedo,
	float DensityScale,
	float StepSizeVoxels,
	uint32 MaxSteps,
	bool bUseSceneDepth)
{
	const FVector4f PackedAlbedo(Albedo.R, Albedo.G, Albedo.B, Albedo.A);
	ENQUEUE_RENDER_COMMAND(GaussianVolumeUpdateNanoVdb)(
		[this,
		 Words = MoveTemp(GridWords),
		 WorldToNanoLocal,
		 PackedAlbedo,
		 DensityScale,
		 StepSizeVoxels,
		 MaxSteps,
		 bUseSceneDepth](FRHICommandListImmediate&) mutable
		{
			NanoVdbWords_RT = MoveTemp(Words);
			NanoWorldToLocal_RT = WorldToNanoLocal;
			NanoAlbedo_RT = PackedAlbedo;
			NanoDensityScale_RT = DensityScale;
			NanoStepSizeVoxels_RT = StepSizeVoxels;
			NanoMaxSteps_RT = MaxSteps;
			bNanoUseSceneDepth_RT = bUseSceneDepth ? 1u : 0u;
		});
}

FScreenPassTexture FGaussianVolumeSceneViewExtension::PostProcessCallback_RenderThread(
	FRDGBuilder& GraphBuilder,
	const FSceneView& InView,
	const FPostProcessMaterialInputs& Inputs)
{
	// SceneColor here is HDR scene-linear, BEFORE bloom & tonemap (we hook the MotionBlur /
	// BL_SceneColorBeforeBloom point). Writing values > 1 is fine (float format); the overshoot
	// from overlapping emissive arcs then gets filmic rolloff + bloom downstream instead of a
	// hard white clamp. It is post-TSR, so at OUTPUT resolution (SceneDepth stays primary).
	const FScreenPassTexture SceneColor = FScreenPassTexture::CopyFromSlice(
		GraphBuilder, Inputs.GetInput(EPostProcessMaterialInput::SceneColor));

	if (!SceneColor.IsValid())
	{
		return SceneColor;
	}
	const bool bInPlaceComposite =
		CVarGaussianVolumeInPlaceComposite.GetValueOnRenderThread() != 0
		&& EnumHasAnyFlags(SceneColor.Texture->Desc.Flags, TexCreate_UAV);

	if (CVarGaussianVolumeLogCandidateStats.GetValueOnRenderThread() == 0)
	{
		bCandidateStatsRequestConsumed_RT = false;
		CandidateStatsDelayFrames_RT = 0;
	}
	else if (!bCandidateStatsRequestConsumed_RT
		&& !bCandidateStatsReadbackPending_RT
		&& CandidateStatsDelayFrames_RT < 8)
	{
		++CandidateStatsDelayFrames_RT;
	}
	if (bCandidateStatsReadbackPending_RT
		&& CandidateStatsReadback_RT
		&& CandidateStatsReadback_RT->IsReady())
	{
		constexpr uint32 StatsBytes = 6 * sizeof(uint32);
		const uint32* Stats = static_cast<const uint32*>(CandidateStatsReadback_RT->Lock(StatsBytes));
		const uint32 Requested = Stats[0];
		const uint32 Granted = Stats[1];
		const uint32 Capacity = Stats[2];
		const uint32 MaxTileRequested = Stats[3];
		const uint32 TruncatedTiles = Stats[4];
		const uint32 MaxTileDrop = Stats[5];
		CandidateStatsReadback_RT->Unlock();
		const uint64 PrimitiveBytes = static_cast<uint64>(CandidateStatsNumGaussians_RT)
			* sizeof(GaussianVolumeGPU::FPackedPrimitive);
		const uint64 InstanceBytes = static_cast<uint64>(CandidateStatsInstanceBufferElements_RT)
			* sizeof(GaussianVolumeGPU::FPackedInstance);
		const uint64 CandidateBytes = static_cast<uint64>(Capacity) * sizeof(uint32);
		const uint64 NumTiles = static_cast<uint64>(
			FMath::DivideAndRoundUp(CandidateStatsResolution_RT.X, 32)
			* FMath::DivideAndRoundUp(CandidateStatsResolution_RT.Y, 32));
		const uint64 AuxiliaryBytes = NumTiles * 4 * sizeof(uint32)
			+ 6 * sizeof(uint32)
			+ InstanceBytes
			+ static_cast<uint64>(CandidateStatsLightTauElements_RT) * sizeof(float);
		UE_LOG(LogGaussianVolumeCandidates, Log,
			TEXT("CandidateStats resolution=%dx%d view=(%.1f,%.1f,%.1f) unique_gaussians=%d instances=%d virtual_gaussians=%d requested=%u granted=%u capacity=%u overflow=%u max_tile_requested=%u truncated_tiles=%u max_tile_drop=%u candidate_bytes=%llu primitive_bytes=%llu instance_bytes=%llu auxiliary_bytes=%llu logical_buffer_bytes=%llu"),
			CandidateStatsResolution_RT.X, CandidateStatsResolution_RT.Y,
			CandidateStatsViewOrigin_RT.X, CandidateStatsViewOrigin_RT.Y, CandidateStatsViewOrigin_RT.Z,
			CandidateStatsNumGaussians_RT, CandidateStatsNumInstances_RT,
			CandidateStatsVirtualGaussians_RT,
			Requested, Granted, Capacity, Requested >= Granted ? Requested - Granted : 0u,
			MaxTileRequested, TruncatedTiles, MaxTileDrop,
			CandidateBytes, PrimitiveBytes, InstanceBytes, AuxiliaryBytes,
			CandidateBytes + PrimitiveBytes + AuxiliaryBytes);
		bCandidateStatsReadbackPending_RT = false;
	}

	GaussianVolumeGPU::FScreenSizeLodBlend LodBlend;
	if (bEnableScreenSizeLod_RT && LodBoundsRadius_RT > 0.0f)
	{
		const float Distance = FVector::Distance(InView.ViewMatrices.GetViewOrigin(), LodBoundsCenter_RT);
		const float TanHalfFovX = FMath::Max(InView.ViewMatrices.GetTanHalfFov().X, UE_SMALL_NUMBER);
		const float ScreenRadius = Distance <= LodBoundsRadius_RT
			? TNumericLimits<float>::Max()
			: LodBoundsRadius_RT / (FMath::Sqrt(FMath::Max(
				Distance * Distance - LodBoundsRadius_RT * LodBoundsRadius_RT, UE_SMALL_NUMBER)) * TanHalfFovX);
		LodBlend = GaussianVolumeGPU::SelectScreenSizeLodBlend(
			ScreenRadius, HighLodMinScreenRadius_RT,
			MediumLodMinScreenRadius_RT, LodHysteresis_RT);
		if (bInPlaceComposite && LodBlend.LodA != LodBlend.LodB)
		{
			const int32 SelectedLod = LodBlend.Alpha < 0.5f ? LodBlend.LodA : LodBlend.LodB;
			LodBlend = {SelectedLod, SelectedLod, 0.0f};
		}
	}

	if (PackedGaussianData_RT[LodBlend.LodA].IsEmpty() && NanoVdbWords_RT.IsEmpty())
	{
		return SceneColor;  // nothing to draw
	}

	FRDGTextureRef SceneColorTex = SceneColor.Texture;
	const FIntRect ViewRect = SceneColor.ViewRect;          // actual sub-rect in the texture
	const FIntPoint ViewRectSize = ViewRect.Size();
	const FIntPoint FullExtent = SceneColorTex->Desc.Extent;

	const FRDGTextureDesc OutputDesc = FRDGTextureDesc::Create2D(
		FullExtent,
		SceneColorTex->Desc.Format,
		FClearValueBinding::Black,
		TexCreate_ShaderResource | TexCreate_UAV | TexCreate_RenderTargetable);
	constexpr uint32 TileSize = 32;
	const uint32 NumTilesX = FMath::DivideAndRoundUp(static_cast<uint32>(ViewRectSize.X), TileSize);
	const uint32 NumTilesY = FMath::DivideAndRoundUp(static_cast<uint32>(ViewRectSize.Y), TileSize);
	const uint32 NumTiles = NumTilesX * NumTilesY;

	// Camera basis
	const FVector ViewPos = InView.ViewMatrices.GetViewOrigin();
	const FVector CamForward = InView.GetViewDirection().GetSafeNormal();
	const FVector CamRight = InView.GetViewRight().GetSafeNormal();
	const FVector CamUp = InView.GetViewUp().GetSafeNormal();
	const FVector2f TanHalfFovXY = InView.ViewMatrices.GetTanHalfFov();
	const float TanHalfFovX = TanHalfFovXY.X;
	const float AspectWH = (float)ViewRectSize.X / (float)ViewRectSize.Y;  // width/height (~1.9 for widescreen)

	const FSceneTextureShaderParameters SceneTextures = GetSceneTextureShaderParameters(InView);

	// SceneDepth is rendered at the PRIMARY resolution = FViewInfo::ViewRect (scaled by
	// screen percentage / dynamic resolution). At this pre-bloom hook SceneColor has
	// ALREADY been upscaled by TSR to the OUTPUT resolution (UnscaledViewRect). Mapping
	// into the depth buffer with UnscaledViewRect therefore scales the UV wrong: the error
	// is ~0 at screen center but grows toward the corners, so a Gaussian pushed into a
	// corner samples a depth texel that belongs to a different object -> false occlusion.
	// Use the primary (scaled) ViewRect, which is what the depth buffer was rendered with.
	FIntRect DepthViewRect = InView.UnscaledViewRect;  // fallback if this isn't an FViewInfo
	if (InView.bIsViewInfo)
	{
		DepthViewRect = static_cast<const FViewInfo&>(InView).ViewRect;
	}
	FIntPoint DepthExtent = DepthViewRect.Max;
	if (const FRHITexture* DepthTex = GetSceneTextureExtracts().GetDepthTexture())
	{
		DepthExtent = DepthTex->GetDesc().Extent;
	}

	const FGlobalShaderMap* ShaderMap = GetGlobalShaderMap(InView.GetFeatureLevel());
	if (!NanoVdbWords_RT.IsEmpty())
	{
		RDG_EVENT_SCOPE_STAT(GraphBuilder, NanoVDBBaseline, "NanoVDBBaseline");
		TShaderMapRef<FNanoVdbRayMarchCS> NanoShader(ShaderMap);
		if (!NanoShader.IsValid())
		{
			UE_LOG(LogTemp, Error, TEXT("NanoVDB baseline: render shader missing from shader map"));
			return SceneColor;
		}

		FRDGTextureRef NanoOutput = GraphBuilder.CreateTexture(
			OutputDesc, TEXT("NanoVDB.Output"));
		FRDGBufferRef NanoGridBuffer = CreateStructuredBuffer(
			GraphBuilder, TEXT("NanoVDB.GridBuffer"), NanoVdbWords_RT);
		FNanoVdbRayMarchCS::FParameters* NanoParams =
			GraphBuilder.AllocParameters<FNanoVdbRayMarchCS::FParameters>();
		NanoParams->Resolution = FVector4f(
			static_cast<float>(ViewRectSize.X),
			static_cast<float>(ViewRectSize.Y),
			1.0f / static_cast<float>(ViewRectSize.X),
			1.0f / static_cast<float>(ViewRectSize.Y));
		NanoParams->ViewRectMin = FVector4f(
			static_cast<float>(ViewRect.Min.X),
			static_cast<float>(ViewRect.Min.Y), 0.0f, 0.0f);
		NanoParams->DepthViewRect = FVector4f(
			static_cast<float>(DepthViewRect.Min.X),
			static_cast<float>(DepthViewRect.Min.Y),
			static_cast<float>(DepthViewRect.Width()),
			static_cast<float>(DepthViewRect.Height()));
		NanoParams->DepthBufferInvSize = FVector4f(
			DepthExtent.X > 0 ? 1.0f / static_cast<float>(DepthExtent.X) : 0.0f,
			DepthExtent.Y > 0 ? 1.0f / static_cast<float>(DepthExtent.Y) : 0.0f,
			0.0f, 0.0f);
		NanoParams->ClipToWorld = FMatrix44f(InView.ViewMatrices.GetClipToWorld());
		NanoParams->WorldToNanoLocal = NanoWorldToLocal_RT;
		NanoParams->Albedo = NanoAlbedo_RT;
		NanoParams->DensityScale = NanoDensityScale_RT;
		NanoParams->StepSizeVoxels = NanoStepSizeVoxels_RT;
		NanoParams->MaxSteps = NanoMaxSteps_RT;
		NanoParams->bUseSceneDepth = bNanoUseSceneDepth_RT;
		NanoParams->NanoVdbBuffer =
			GraphBuilder.CreateSRV(FRDGBufferSRVDesc(NanoGridBuffer));
		NanoParams->SceneColorTexture =
			GraphBuilder.CreateSRV(FRDGTextureSRVDesc(SceneColorTex));
		NanoParams->SceneTextures = SceneTextures;
		NanoParams->OutputTexture =
			GraphBuilder.CreateUAV(FRDGTextureUAVDesc(NanoOutput));
		FComputeShaderUtils::AddPass(
			GraphBuilder,
			RDG_EVENT_NAME("NanoVDB HDDA Ray March %llu bytes",
				static_cast<uint64>(NanoVdbWords_RT.Num()) * sizeof(uint32)),
			NanoShader,
			NanoParams,
			FComputeShaderUtils::GetGroupCount(
				FIntVector(ViewRectSize.X, ViewRectSize.Y, 1), 8));
		FScreenPassTexture NanoResult = SceneColor;
		NanoResult.Texture = NanoOutput;
		return NanoResult;
	}

	RDG_EVENT_SCOPE_STAT(GraphBuilder, GaussianVolume, "GaussianVolume");
	TShaderMapRef<FGaussianVolumeRayTraceCS> ComputeShader(ShaderMap);
	TShaderMapRef<FGaussianVolumeCountTileCandidatesCS> CountTileShader(ShaderMap);
	TShaderMapRef<FGaussianVolumePrefixTileCandidatesCS> PrefixTileShader(ShaderMap);
	TShaderMapRef<FGaussianVolumeScatterTileCandidatesCS> ScatterTileShader(ShaderMap);
	if (!ComputeShader.IsValid() || !CountTileShader.IsValid()
		|| !PrefixTileShader.IsValid() || !ScatterTileShader.IsValid())
	{
		UE_LOG(LogTemp, Error, TEXT("GaussianVolume: render shader missing from shader map!"));
		return SceneColor;
	}

	const FVector4f Resolution(
		(float)ViewRectSize.X, (float)ViewRectSize.Y,
		1.0f / (float)ViewRectSize.X, 1.0f / (float)ViewRectSize.Y);
	const FVector4f ViewRectMin((float)ViewRect.Min.X, (float)ViewRect.Min.Y, 0.0f, 0.0f);
	const FIntVector DispatchCount = FComputeShaderUtils::GetGroupCount(FIntVector(ViewRectSize.X, ViewRectSize.Y, 1), 8);
	bool bCandidateStatsScheduled = false;

	auto RenderLod = [&](int32 LodIndex) -> FRDGTextureRef
	{
		const TArray<GaussianVolumeGPU::FPackedPrimitive>& PackedGaussianData = PackedGaussianData_RT[LodIndex];
		const TArray<GaussianVolumeGPU::FPackedInstance>& PackedInstanceData = PackedInstanceData_RT[LodIndex];
		const int32 NumGaussians = PackedGaussianData.Num();
		const int32 NumInstances = PackedInstanceData.Num();
		if (NumGaussians <= 0 || NumInstances <= 0)
		{
			return SceneColorTex;
		}
		if (NumGaussians >= (1 << 20) || NumInstances >= (1 << 12))
		{
			UE_LOG(LogTemp, Error,
				TEXT("GaussianVolume: compact candidate ID supports <1,048,576 unique primitives and <4,096 instances"));
			return SceneColorTex;
		}
		uint32 MaxPrimitivesPerInstance = 0;
		uint64 VirtualGaussianCount64 = 0;
		for (const GaussianVolumeGPU::FPackedInstance& Instance : PackedInstanceData)
		{
			MaxPrimitivesPerInstance = FMath::Max(MaxPrimitivesPerInstance, Instance.Data1.X);
			VirtualGaussianCount64 += Instance.Data1.X;
		}
		const uint32 VirtualGaussianCount = static_cast<uint32>(
			FMath::Min<uint64>(VirtualGaussianCount64, MAX_uint32));
		const bool bUseUniformFastPath = bUniformAppearance_RT[LodIndex];

		if (CVarGaussianVolumePoolFreeRaster.GetValueOnRenderThread() != 0
			&& bUniformAppearance_RT[LodIndex]
			&& NumInstances == 1)
		{
			RDG_EVENT_SCOPE_STAT(GraphBuilder, GaussianVolumePoolFree, "GaussianVolumePoolFree");
			TShaderMapRef<FGaussianVolumePoolFreeVS> VertexShader(ShaderMap);
			TShaderMapRef<FGaussianVolumePoolFreePS> PixelShader(ShaderMap);
			TShaderMapRef<FGaussianVolumePoolFreeCompositeCS> CompositeShader(ShaderMap);
			if (!VertexShader.IsValid() || !PixelShader.IsValid() || !CompositeShader.IsValid())
			{
				UE_LOG(LogTemp, Error, TEXT("GaussianVolume: pool-free raster shader missing from shader map"));
				return SceneColorTex;
			}

			const float ResolutionScale = FMath::Clamp(
				CVarGaussianVolumePoolFreeResolutionScale.GetValueOnRenderThread(), 0.25f, 1.0f);
			const FIntPoint RasterSize(
				FMath::Max(1, FMath::CeilToInt(ViewRectSize.X * ResolutionScale)),
				FMath::Max(1, FMath::CeilToInt(ViewRectSize.Y * ResolutionScale)));
			const FVector4f RasterResolution(
				static_cast<float>(RasterSize.X), static_cast<float>(RasterSize.Y),
				1.0f / static_cast<float>(RasterSize.X),
				1.0f / static_cast<float>(RasterSize.Y));
			const FRDGTextureDesc TauDesc = FRDGTextureDesc::Create2D(
				RasterSize, PF_R16F, FClearValueBinding::Black,
				TexCreate_ShaderResource | TexCreate_RenderTargetable);
			FRDGTextureRef PoolFreeTau = GraphBuilder.CreateTexture(
				TauDesc, TEXT("GaussianVolumePoolFree.Tau"));
			FRDGBufferRef PoolFreeGaussianBuffer = CreateStructuredBuffer(
				GraphBuilder, TEXT("GaussianVolumePoolFree.GaussianBuffer"), PackedGaussianData);
			FRDGBufferSRVRef PoolFreeGaussianSrv =
				GraphBuilder.CreateSRV(FRDGBufferSRVDesc(PoolFreeGaussianBuffer));
			FGaussianVolumePoolFreePassParameters* PassParameters =
				GraphBuilder.AllocParameters<FGaussianVolumePoolFreePassParameters>();
			PassParameters->VS.CameraPos = FVector4f(
				static_cast<float>(ViewPos.X), static_cast<float>(ViewPos.Y),
				static_cast<float>(ViewPos.Z), 0.0f);
			PassParameters->VS.CameraForward = FVector4f(
				static_cast<float>(CamForward.X), static_cast<float>(CamForward.Y),
				static_cast<float>(CamForward.Z), 0.0f);
			PassParameters->VS.CameraRight = FVector4f(
				static_cast<float>(CamRight.X), static_cast<float>(CamRight.Y),
				static_cast<float>(CamRight.Z), 0.0f);
			PassParameters->VS.CameraUp = FVector4f(
				static_cast<float>(CamUp.X), static_cast<float>(CamUp.Y),
				static_cast<float>(CamUp.Z), 0.0f);
			PassParameters->VS.CameraDirs = FVector4f(TanHalfFovX, AspectWH, 0.0f, 0.0f);
			PassParameters->VS.GaussianBuffer = PoolFreeGaussianSrv;
			PassParameters->PS.Resolution = RasterResolution;
			PassParameters->PS.ViewRectMin = FVector4f::Zero();
			PassParameters->PS.DepthViewRect = FVector4f(
				static_cast<float>(DepthViewRect.Min.X),
				static_cast<float>(DepthViewRect.Min.Y),
				static_cast<float>(DepthViewRect.Width()),
				static_cast<float>(DepthViewRect.Height()));
			PassParameters->PS.DepthBufferInvSize = FVector4f(
				DepthExtent.X > 0 ? 1.0f / static_cast<float>(DepthExtent.X) : 0.0f,
				DepthExtent.Y > 0 ? 1.0f / static_cast<float>(DepthExtent.Y) : 0.0f,
				0.0f, 0.0f);
			PassParameters->PS.ClipToWorld =
				FMatrix44f(InView.ViewMatrices.GetClipToWorld());
			PassParameters->PS.LightColor = LightColor_RT;
			PassParameters->PS.AmbientColor = AmbientColor_RT;
			PassParameters->PS.UniformAppearance = UniformAppearance_RT[LodIndex];
			PassParameters->PS.MaxRayDistance = MaxRayDistance_RT;
			PassParameters->PS.bUseSceneDepth = bUseSceneDepth_RT;
			PassParameters->PS.GaussianBuffer = PoolFreeGaussianSrv;
			PassParameters->PS.SceneTextures = SceneTextures;
			PassParameters->RenderTargets[0] =
				FRenderTargetBinding(PoolFreeTau, ERenderTargetLoadAction::EClear);

			GraphBuilder.AddPass(
				RDG_EVENT_NAME("GaussianVolume Pool-Free Tau %dx%d LOD%d %d",
					RasterSize.X, RasterSize.Y, LodIndex, NumGaussians),
				PassParameters,
				ERDGPassFlags::Raster,
				[PassParameters, VertexShader, PixelShader, RasterSize, NumGaussians](
					FRDGAsyncTask, FRHICommandList& RHICmdList)
				{
					FGraphicsPipelineStateInitializer GraphicsPSOInit;
					RHICmdList.ApplyCachedRenderTargets(GraphicsPSOInit);
					GraphicsPSOInit.BlendState =
						TStaticBlendState<
							CW_RED, BO_Add, BF_One, BF_One,
							BO_Add, BF_Zero, BF_One>::GetRHI();
					GraphicsPSOInit.RasterizerState =
						TStaticRasterizerState<FM_Solid, CM_None>::GetRHI();
					GraphicsPSOInit.DepthStencilState =
						TStaticDepthStencilState<false, CF_Always>::GetRHI();
					GraphicsPSOInit.BoundShaderState.VertexDeclarationRHI =
						GEmptyVertexDeclaration.VertexDeclarationRHI;
					GraphicsPSOInit.BoundShaderState.VertexShaderRHI =
						VertexShader.GetVertexShader();
					GraphicsPSOInit.BoundShaderState.PixelShaderRHI =
						PixelShader.GetPixelShader();
					GraphicsPSOInit.PrimitiveType = PT_TriangleList;
					SetGraphicsPipelineState(RHICmdList, GraphicsPSOInit, 0);
					RHICmdList.SetViewport(
						0, 0, 0.0f, RasterSize.X, RasterSize.Y, 1.0f);
					SetShaderParameters(
						RHICmdList, VertexShader, VertexShader.GetVertexShader(),
						PassParameters->VS);
					SetShaderParameters(
						RHICmdList, PixelShader, PixelShader.GetPixelShader(),
						PassParameters->PS);
					RHICmdList.SetStreamSource(0, nullptr, 0);
					RHICmdList.DrawPrimitive(0, 2, NumGaussians);
				});

			FRDGTextureRef PoolFreeOutput = SceneColorTex;
			if (!bInPlaceComposite)
			{
				PoolFreeOutput = GraphBuilder.CreateTexture(
					OutputDesc, TEXT("GaussianVolumePoolFree.Output"));
				AddCopyTexturePass(GraphBuilder, SceneColorTex, PoolFreeOutput);
			}
			FGaussianVolumePoolFreeCompositeCS::FParameters* CompositeParameters =
				GraphBuilder.AllocParameters<FGaussianVolumePoolFreeCompositeCS::FParameters>();
			CompositeParameters->Resolution = Resolution;
			CompositeParameters->ViewRectMin = ViewRectMin;
			CompositeParameters->LightColor = LightColor_RT;
			CompositeParameters->AmbientColor = AmbientColor_RT;
			CompositeParameters->UniformAppearance = UniformAppearance_RT[LodIndex];
			CompositeParameters->PowderFactor = PowderFactor_RT;
			CompositeParameters->bPoolFreeInPlaceComposite = bInPlaceComposite ? 1u : 0u;
			CompositeParameters->PoolFreeTauTexture =
				GraphBuilder.CreateSRV(FRDGTextureSRVDesc(PoolFreeTau));
			CompositeParameters->PoolFreeTauSampler =
				TStaticSamplerState<SF_Bilinear>::GetRHI();
			CompositeParameters->SceneColorTexture =
				GraphBuilder.CreateSRV(FRDGTextureSRVDesc(
					bInPlaceComposite ? GSystemTextures.GetBlackDummy(GraphBuilder) : SceneColorTex));
			CompositeParameters->OutputTexture =
				GraphBuilder.CreateUAV(FRDGTextureUAVDesc(PoolFreeOutput));
			FComputeShaderUtils::AddPass(
				GraphBuilder,
				RDG_EVENT_NAME("GaussianVolume Pool-Free Composite %.2fx", ResolutionScale),
				CompositeShader,
				CompositeParameters,
				DispatchCount);
			return PoolFreeOutput;
		}

		FRDGTextureRef OutputTexture = SceneColorTex;
		if (!bInPlaceComposite)
		{
			OutputTexture = GraphBuilder.CreateTexture(
				OutputDesc, TEXT("GaussianVolume.Output"));
			AddCopyTexturePass(GraphBuilder, SceneColorTex, OutputTexture);
		}
		FRDGBufferRef GaussianBuffer = CreateStructuredBuffer(
			GraphBuilder, TEXT("GaussianVolume.GaussianBuffer"), PackedGaussianData);
		FRDGBufferRef InstanceBuffer = GaussianBuffer;
		if (NumInstances > 1)
		{
			InstanceBuffer = CreateStructuredBuffer(
				GraphBuilder, TEXT("GaussianVolume.InstanceBuffer"), PackedInstanceData);
		}
		const GaussianVolumeGPU::FPackedInstance& SingleInstance = PackedInstanceData[0];
		const FVector4f SingleInstanceOffset(
			FMath::AsFloat(SingleInstance.Data0.X),
			FMath::AsFloat(SingleInstance.Data0.Y),
			FMath::AsFloat(SingleInstance.Data0.Z), 0.0f);
		const uint32 CandidatePoolCapacity = GaussianVolumeGPU::ResolveCandidatePoolCapacity(
			CVarGaussianVolumeCandidatePoolCapacity.GetValueOnRenderThread(),
			NumTiles, static_cast<int32>(FMath::Min<uint32>(VirtualGaussianCount, MAX_int32)));
		FRDGBufferRef TileCandidateRawCounts = GraphBuilder.CreateBuffer(
			FRDGBufferDesc::CreateStructuredDesc(sizeof(uint32), NumTiles),
			TEXT("GaussianVolume.TileCandidateRawCounts"));
		FRDGBufferRef TileCandidateCounts = GraphBuilder.CreateBuffer(
			FRDGBufferDesc::CreateStructuredDesc(sizeof(uint32), NumTiles),
			TEXT("GaussianVolume.TileCandidateCounts"));
		FRDGBufferRef TileCandidateOffsets = GraphBuilder.CreateBuffer(
			FRDGBufferDesc::CreateStructuredDesc(sizeof(uint32), NumTiles),
			TEXT("GaussianVolume.TileCandidateOffsets"));
		FRDGBufferRef TileWriteCursors = GraphBuilder.CreateBuffer(
			FRDGBufferDesc::CreateStructuredDesc(sizeof(uint32), NumTiles),
			TEXT("GaussianVolume.TileWriteCursors"));
		FRDGBufferRef TileCandidateIndices = GraphBuilder.CreateBuffer(
			FRDGBufferDesc::CreateStructuredDesc(sizeof(uint32), CandidatePoolCapacity),
			TEXT("GaussianVolume.TileCandidateIndices"));
		FRDGBufferRef CandidateStats = GraphBuilder.CreateBuffer(
			FRDGBufferDesc::CreateStructuredDesc(sizeof(uint32), 6),
			TEXT("GaussianVolume.CandidateStats"));
		AddClearUAVPass(GraphBuilder, GraphBuilder.CreateUAV(FRDGBufferUAVDesc(TileCandidateRawCounts)), 0u);
		AddClearUAVPass(GraphBuilder, GraphBuilder.CreateUAV(FRDGBufferUAVDesc(TileWriteCursors)), 0u);
		const bool bUseDirectionalLightTau =
			bUseUniformFastPath && bDirectionalLightTau_RT[LodIndex];
		// High-count clouds use the baked basis; exact pairwise light tau stays bounded to debug-sized sets.
		const bool bUseExactLightTau = !bUseDirectionalLightTau && NumGaussians <= 4096;
		const bool bRebuildLightTau =
			bUseExactLightTau && (bLightTauDirty_RT[LodIndex] || !LightTauPooled_RT[LodIndex]);
		FRDGBufferRef LightTauBuffer = bUseExactLightTau
			? (bRebuildLightTau ? GraphBuilder.CreateBuffer(
				FRDGBufferDesc::CreateStructuredDesc(sizeof(float), FMath::Max(NumGaussians, 1)),
				TEXT("GaussianVolume.LightTau"))
				: GraphBuilder.RegisterExternalBuffer(
					LightTauPooled_RT[LodIndex], TEXT("GaussianVolume.LightTau.Cached")))
			: GraphBuilder.CreateBuffer(
				FRDGBufferDesc::CreateStructuredDesc(sizeof(float), 1),
				TEXT("GaussianVolume.LightTau.Dummy"));
		if (!bUseExactLightTau)
		{
			AddClearUAVPass(
				GraphBuilder, GraphBuilder.CreateUAV(FRDGBufferUAVDesc(LightTauBuffer)),
				0x3F800000u);
		}

		FGaussianVolumeRayTraceCS::FParameters* CsParams = GraphBuilder.AllocParameters<FGaussianVolumeRayTraceCS::FParameters>();
		CsParams->Resolution = Resolution;
		CsParams->ViewRectMin = ViewRectMin;
		CsParams->DepthViewRect = FVector4f(
			(float)DepthViewRect.Min.X, (float)DepthViewRect.Min.Y,
			(float)DepthViewRect.Width(), (float)DepthViewRect.Height());
		CsParams->DepthBufferInvSize = FVector4f(
			DepthExtent.X > 0 ? 1.0f / (float)DepthExtent.X : 0.0f,
			DepthExtent.Y > 0 ? 1.0f / (float)DepthExtent.Y : 0.0f, 0.0f, 0.0f);
		CsParams->CameraPos = FVector4f((float)ViewPos.X, (float)ViewPos.Y, (float)ViewPos.Z, 0.0f);
		CsParams->CameraDirs = FVector4f(TanHalfFovX, AspectWH, 0.0f, 0.0f);
		CsParams->CameraForward = FVector4f((float)CamForward.X, (float)CamForward.Y, (float)CamForward.Z, 0.0f);
		CsParams->CameraRight = FVector4f((float)CamRight.X, (float)CamRight.Y, (float)CamRight.Z, 0.0f);
		CsParams->CameraUp = FVector4f((float)CamUp.X, (float)CamUp.Y, (float)CamUp.Z, 0.0f);
		CsParams->ClipToWorld = FMatrix44f(InView.ViewMatrices.GetClipToWorld());
		CsParams->LightDir = LightDir_RT;
		CsParams->LightColor = LightColor_RT;
		CsParams->AmbientColor = AmbientColor_RT;
		CsParams->PowderFactor = PowderFactor_RT;
		CsParams->MaxRayDistance = MaxRayDistance_RT;
		CsParams->bUseSceneDepth = bUseSceneDepth_RT;
		CsParams->DebugView = DebugView_RT;
		CsParams->NumGaussians = (uint32)NumGaussians;
		CsParams->NumInstances = static_cast<uint32>(NumInstances);
		CsParams->bSingleInstance = NumInstances == 1 ? 1u : 0u;
		CsParams->SinglePrimitiveOffset = SingleInstance.Data0.W;
		CsParams->SinglePrimitiveCount = SingleInstance.Data1.X;
		CsParams->SingleInstanceOffset = SingleInstanceOffset;
		CsParams->SingleLightBasisRotation = SingleInstance.Data1.Y;
		CsParams->NumTilesX = NumTilesX;
		CsParams->TileSize = TileSize;
		CsParams->bUseUniformFastPath = bUseUniformFastPath ? 1u : 0u;
		CsParams->bUseDirectionalLightTau = bUseDirectionalLightTau ? 1u : 0u;
		CsParams->UniformAppearance = UniformAppearance_RT[LodIndex];
		CsParams->GaussianBuffer = GraphBuilder.CreateSRV(FRDGBufferSRVDesc(GaussianBuffer));
		CsParams->InstanceBuffer = GraphBuilder.CreateSRV(FRDGBufferSRVDesc(InstanceBuffer));
		CsParams->TileCandidateRawCounts = GraphBuilder.CreateSRV(FRDGBufferSRVDesc(TileCandidateRawCounts));
		CsParams->TileCandidateCounts = GraphBuilder.CreateSRV(FRDGBufferSRVDesc(TileCandidateCounts));
		CsParams->TileCandidateOffsets = GraphBuilder.CreateSRV(FRDGBufferSRVDesc(TileCandidateOffsets));
		CsParams->TileCandidateIndices = GraphBuilder.CreateSRV(FRDGBufferSRVDesc(TileCandidateIndices));
		CsParams->LightTransmittance = GraphBuilder.CreateSRV(FRDGBufferSRVDesc(LightTauBuffer));
		CsParams->SceneTextures = SceneTextures;
		CsParams->OutputTexture = GraphBuilder.CreateUAV(FRDGTextureUAVDesc(OutputTexture));

		FGaussianVolumeCountTileCandidatesCS::FParameters* CountParams =
			GraphBuilder.AllocParameters<FGaussianVolumeCountTileCandidatesCS::FParameters>();
		CountParams->Resolution = CsParams->Resolution;
		CountParams->CameraPos = CsParams->CameraPos;
		CountParams->CameraForward = CsParams->CameraForward;
		CountParams->CameraRight = CsParams->CameraRight;
		CountParams->CameraUp = CsParams->CameraUp;
		CountParams->CameraDirs = CsParams->CameraDirs;
		CountParams->bUseTightPBF =
			CVarGaussianVolumeTightPBF.GetValueOnRenderThread() != 0 ? 1u : 0u;
		CountParams->NumGaussians = static_cast<uint32>(NumGaussians);
		CountParams->NumInstances = static_cast<uint32>(NumInstances);
		CountParams->bSingleInstance = CsParams->bSingleInstance;
		CountParams->SinglePrimitiveOffset = CsParams->SinglePrimitiveOffset;
		CountParams->SinglePrimitiveCount = CsParams->SinglePrimitiveCount;
		CountParams->SingleInstanceOffset = CsParams->SingleInstanceOffset;
		CountParams->NumTilesX = NumTilesX;
		CountParams->NumTilesY = NumTilesY;
		CountParams->TileSize = TileSize;
		CountParams->GaussianBuffer = CsParams->GaussianBuffer;
		CountParams->InstanceBuffer = CsParams->InstanceBuffer;
		CountParams->OutTileCandidateCounts = GraphBuilder.CreateUAV(FRDGBufferUAVDesc(TileCandidateRawCounts));
		FComputeShaderUtils::AddPass(
			GraphBuilder, RDG_EVENT_NAME("GaussianVolume Count Tile Candidates LOD%d", LodIndex),
			CountTileShader, CountParams,
			FComputeShaderUtils::GetGroupCount(
				FIntVector(MaxPrimitivesPerInstance, NumInstances, 1),
				FIntVector(64, 1, 1)));

		FGaussianVolumePrefixTileCandidatesCS::FParameters* PrefixParams =
			GraphBuilder.AllocParameters<FGaussianVolumePrefixTileCandidatesCS::FParameters>();
		PrefixParams->NumTiles = NumTiles;
		PrefixParams->CandidatePoolCapacity = CandidatePoolCapacity;
		PrefixParams->TileCandidateRawCounts = CsParams->TileCandidateRawCounts;
		PrefixParams->OutTileCandidateCounts = GraphBuilder.CreateUAV(FRDGBufferUAVDesc(TileCandidateCounts));
		PrefixParams->OutTileCandidateOffsets = GraphBuilder.CreateUAV(FRDGBufferUAVDesc(TileCandidateOffsets));
		PrefixParams->OutCandidateStats = GraphBuilder.CreateUAV(FRDGBufferUAVDesc(CandidateStats));
		FComputeShaderUtils::AddPass(
			GraphBuilder, RDG_EVENT_NAME("GaussianVolume Prefix Tile Candidates LOD%d", LodIndex),
			PrefixTileShader, PrefixParams, FIntVector(1, 1, 1));
		if (!bCandidateStatsScheduled
			&& !bCandidateStatsReadbackPending_RT
			&& !bCandidateStatsRequestConsumed_RT
			&& CandidateStatsDelayFrames_RT >= 8
			&& CVarGaussianVolumeLogCandidateStats.GetValueOnRenderThread() != 0)
		{
			if (!CandidateStatsReadback_RT)
			{
				CandidateStatsReadback_RT = MakeUnique<FRHIGPUBufferReadback>(
					TEXT("GaussianVolume.CandidateStatsReadback"));
			}
			AddEnqueueCopyPass(GraphBuilder, CandidateStatsReadback_RT.Get(), CandidateStats, 0u);
			bCandidateStatsReadbackPending_RT = true;
			bCandidateStatsRequestConsumed_RT = true;
			bCandidateStatsScheduled = true;
			CandidateStatsNumGaussians_RT = NumGaussians;
			CandidateStatsNumInstances_RT = NumInstances;
			CandidateStatsVirtualGaussians_RT = static_cast<int32>(
				FMath::Min<uint32>(VirtualGaussianCount, MAX_int32));
			CandidateStatsLightTauElements_RT = bUseExactLightTau ? NumGaussians : 1;
			CandidateStatsInstanceBufferElements_RT = NumInstances > 1 ? NumInstances : 0;
			CandidateStatsResolution_RT = ViewRectSize;
			CandidateStatsViewOrigin_RT = ViewPos;
		}

		FGaussianVolumeScatterTileCandidatesCS::FParameters* ScatterParams =
			GraphBuilder.AllocParameters<FGaussianVolumeScatterTileCandidatesCS::FParameters>();
		ScatterParams->Resolution = CountParams->Resolution;
		ScatterParams->CameraPos = CountParams->CameraPos;
		ScatterParams->CameraForward = CountParams->CameraForward;
		ScatterParams->CameraRight = CountParams->CameraRight;
		ScatterParams->CameraUp = CountParams->CameraUp;
		ScatterParams->CameraDirs = CountParams->CameraDirs;
		ScatterParams->bUseTightPBF = CountParams->bUseTightPBF;
		ScatterParams->NumGaussians = CountParams->NumGaussians;
		ScatterParams->NumInstances = CountParams->NumInstances;
		ScatterParams->bSingleInstance = CountParams->bSingleInstance;
		ScatterParams->SinglePrimitiveOffset = CountParams->SinglePrimitiveOffset;
		ScatterParams->SinglePrimitiveCount = CountParams->SinglePrimitiveCount;
		ScatterParams->SingleInstanceOffset = CountParams->SingleInstanceOffset;
		ScatterParams->NumTilesX = CountParams->NumTilesX;
		ScatterParams->NumTilesY = CountParams->NumTilesY;
		ScatterParams->TileSize = CountParams->TileSize;
		ScatterParams->GaussianBuffer = CountParams->GaussianBuffer;
		ScatterParams->InstanceBuffer = CountParams->InstanceBuffer;
		ScatterParams->TileCandidateCounts = CsParams->TileCandidateCounts;
		ScatterParams->TileCandidateOffsets = CsParams->TileCandidateOffsets;
		ScatterParams->TileWriteCursors = GraphBuilder.CreateUAV(FRDGBufferUAVDesc(TileWriteCursors));
		ScatterParams->OutTileCandidateIndices = GraphBuilder.CreateUAV(FRDGBufferUAVDesc(TileCandidateIndices));
		FComputeShaderUtils::AddPass(
			GraphBuilder, RDG_EVENT_NAME("GaussianVolume Scatter Tile Candidates LOD%d", LodIndex),
			ScatterTileShader, ScatterParams,
			FComputeShaderUtils::GetGroupCount(
				FIntVector(MaxPrimitivesPerInstance, NumInstances, 1),
				FIntVector(64, 1, 1)));

		if (bRebuildLightTau)
		{
			AddClearUAVPass(
				GraphBuilder, GraphBuilder.CreateUAV(FRDGBufferUAVDesc(LightTauBuffer)),
				0x3F800000u);
			TShaderMapRef<FGaussianVolumeLightTauCS> LightTauShader(ShaderMap);
			if (LightTauShader.IsValid())
			{
				FGaussianVolumeLightTauCS::FParameters* LtParams = GraphBuilder.AllocParameters<FGaussianVolumeLightTauCS::FParameters>();
				LtParams->LightDir = LightDir_RT;
				LtParams->MaxRayDistance = MaxRayDistance_RT;
				LtParams->NumGaussians = (uint32)NumGaussians;
				LtParams->GaussianBuffer = CsParams->GaussianBuffer;
				LtParams->OutLightTau = GraphBuilder.CreateUAV(FRDGBufferUAVDesc(LightTauBuffer));
				FComputeShaderUtils::AddPass(
					GraphBuilder, RDG_EVENT_NAME("GaussianVolume LightTau Rebuild LOD%d", LodIndex),
					LightTauShader, LtParams,
					FComputeShaderUtils::GetGroupCount(FIntVector(NumGaussians, 1, 1), FIntVector(64, 1, 1)));
			}
			GraphBuilder.QueueBufferExtraction(LightTauBuffer, &LightTauPooled_RT[LodIndex]);
			bLightTauDirty_RT[LodIndex] = false;
		}

		FComputeShaderUtils::AddPass(GraphBuilder,
			RDG_EVENT_NAME("GaussianVolume RayTrace CS LOD%d %d%s", LodIndex, NumGaussians, bUseUniformFastPath ? TEXT(" Uniform") : TEXT("")),
			ComputeShader, CsParams, DispatchCount);
		return OutputTexture;
	};

	FRDGTextureRef FinalTexture = RenderLod(LodBlend.LodA);
	if (LodBlend.LodB != LodBlend.LodA && LodBlend.Alpha > 0.0f)
	{
		FRDGTextureRef LodBTexture = RenderLod(LodBlend.LodB);
		TShaderMapRef<FGaussianVolumeLodBlendCS> BlendShader(ShaderMap);
		if (BlendShader.IsValid())
		{
			FRDGTextureRef BlendOutput = GraphBuilder.CreateTexture(OutputDesc, TEXT("GaussianVolume.LodBlend"));
			FGaussianVolumeLodBlendCS::FParameters* BlendParams =
				GraphBuilder.AllocParameters<FGaussianVolumeLodBlendCS::FParameters>();
			BlendParams->Resolution = Resolution;
			BlendParams->ViewRectMin = ViewRectMin;
			BlendParams->LodBlendAlpha = LodBlend.Alpha;
			BlendParams->LodATexture = GraphBuilder.CreateSRV(FRDGTextureSRVDesc(FinalTexture));
			BlendParams->LodBTexture = GraphBuilder.CreateSRV(FRDGTextureSRVDesc(LodBTexture));
			BlendParams->OutputTexture = GraphBuilder.CreateUAV(FRDGTextureUAVDesc(BlendOutput));
			FComputeShaderUtils::AddPass(
				GraphBuilder,
				RDG_EVENT_NAME("GaussianVolume LOD Blend %d->%d %.2f", LodBlend.LodA, LodBlend.LodB, LodBlend.Alpha),
				BlendShader, BlendParams, DispatchCount);
			FinalTexture = BlendOutput;
		}
	}

	FScreenPassTexture Result = SceneColor;
	Result.Texture = FinalTexture;
	return Result;
}

void FGaussianVolumeSceneViewExtension::SubscribeToPostProcessingPass(
	EPostProcessingPass Pass,
	const FSceneView& InView,
	FPostProcessingPassDelegateArray& InOutPassCallbacks,
	bool bIsPassEnabled)
{
	// Composite in HDR scene-linear BEFORE bloom & tonemap. The MotionBlur pass point maps to
	// BL_SceneColorBeforeBloom (see PostProcessing.cpp AddAfterPassForSceneColorSlice(EPass::
	// MotionBlur)), so our emissive arcs bloom and get tonemapper rolloff -> soft colored
	// highlights at crossings, instead of the hard white clamp from compositing post-tonemap.
	if (Pass == EPostProcessingPass::MotionBlur)
	{
		InOutPassCallbacks.Add(FPostProcessingPassDelegate::CreateRaw(
			this, &FGaussianVolumeSceneViewExtension::PostProcessCallback_RenderThread));
	}
}
