#include "GaussianSplattingSceneViewExtension.h"

#include "CommonRenderResources.h"
#include "GaussianSplattingShaders.h"
#include "GPUSort.h"
#include "HAL/IConsoleManager.h"
#include "PipelineStateCache.h"
#include "PostProcess/PostProcessMaterialInputs.h"
#include "ProfilingDebugging/RealtimeGPUProfiler.h"
#include "RenderGraphBuilder.h"
#include "RenderGraphUtils.h"
#include "RenderingThread.h"
#include "SceneTexturesConfig.h"
#include "ScreenPass.h"
#include "SceneRendering.h"
#include "SystemTextures.h"

DECLARE_GPU_STAT_NAMED(GaussianSplatting7DRGS, TEXT("GaussianSplatting7DRGS"));

namespace
{
	TAutoConsoleVariable<int32> CVarGSEnable(
		TEXT("r.GaussianSplatting.Enable"),
		1,
		TEXT("Render the reconstructed 7DRGS pipeline."),
		ECVF_RenderThreadSafe);

	TAutoConsoleVariable<int32> CVarGSFrustumCull(
		TEXT("r.GaussianSplatting.FrustumCull"),
		1,
		TEXT("Enable conservative center frustum culling before EWA projection."),
		ECVF_RenderThreadSafe);

	TAutoConsoleVariable<float> CVarGSFrustumSlack(
		TEXT("r.GaussianSplatting.FrustumSlack"),
		1.25f,
		TEXT("Conservative NDC slack for the early frustum test."),
		ECVF_RenderThreadSafe);

	TAutoConsoleVariable<float> CVarGSSubPixelRadius(
		TEXT("r.GaussianSplatting.SubPixelRadius"),
		0.0f,
		TEXT("Cull splats below this projected radius in pixels. Zero disables."),
		ECVF_RenderThreadSafe);

	TAutoConsoleVariable<int32> CVarGSSourceAABB(
		TEXT("r.GaussianSplatting.SourceAABB"),
		1,
		TEXT("Limit the final composite to the GPU-reduced source screen AABB."),
		ECVF_RenderThreadSafe);

	TAutoConsoleVariable<int32> CVarGSDebugSHDegree(
		TEXT("r.GaussianSplatting.DebugSHDegree"),
		0,
		TEXT("7DRGS T_view SH debug mode: 0 off, 1 delta, 2 selected, 3 split."),
		ECVF_RenderThreadSafe);

	FUintVector2 ToUint2(const FIntPoint Value)
	{
		return FUintVector2(
			static_cast<uint32>(FMath::Max(Value.X, 0)),
			static_cast<uint32>(FMath::Max(Value.Y, 0)));
	}
}

FGaussianSplattingSceneViewExtension::FGaussianSplattingSceneViewExtension(
	const FAutoRegister& AutoReg,
	UWorld* InWorld)
	: FWorldSceneViewExtension(AutoReg, InWorld)
{
}

void FGaussianSplattingSceneViewExtension::UpdateData_GameThread(
	TArray<FVector4f> RawData)
{
	ENQUEUE_RENDER_COMMAND(GaussianSplattingUpdateData)(
		[this, Data = MoveTemp(RawData)](FRHICommandListImmediate&) mutable
		{
			RawData_RT = MoveTemp(Data);
			PointCount_RT = static_cast<uint32>(
				RawData_RT.Num() / GaussianSplatting7DRGS::InputStrideFloat4);
			RawDataPooled_RT.SafeRelease();
		});
}

void FGaussianSplattingSceneViewExtension::UpdateParameters_GameThread(
	const GaussianSplatting7DRGS::FSourceParameters& Parameters)
{
	ENQUEUE_RENDER_COMMAND(GaussianSplattingUpdateParameters)(
		[this, Parameters](FRHICommandListImmediate&)
		{
			Parameters_RT = Parameters;
		});
}

FScreenPassTexture FGaussianSplattingSceneViewExtension::PostProcessCallback_RenderThread(
	FRDGBuilder& GraphBuilder,
	const FSceneView& InView,
	const FPostProcessMaterialInputs& Inputs)
{
	const FScreenPassTexture SceneColor = FScreenPassTexture::CopyFromSlice(
		GraphBuilder, Inputs.GetInput(EPostProcessMaterialInput::SceneColor));
	if (!SceneColor.IsValid()
		|| CVarGSEnable.GetValueOnRenderThread() == 0
		|| PointCount_RT == 0
		|| RawData_RT.Num()
			!= static_cast<int64>(PointCount_RT)
				* GaussianSplatting7DRGS::InputStrideFloat4)
	{
		return SceneColor;
	}

	RDG_EVENT_SCOPE_STAT(
		GraphBuilder, GaussianSplatting7DRGS,
		"GaussianSplatting 7DRGS %u", PointCount_RT);

	const FIntPoint Extent = SceneColor.Texture->Desc.Extent;
	const FIntRect OutputViewRect = SceneColor.ViewRect;
	const FUintVector2 ScreenSize = ToUint2(Extent);
	const ERHIFeatureLevel::Type FeatureLevel = InView.GetFeatureLevel();
	FGlobalShaderMap* ShaderMap = GetGlobalShaderMap(FeatureLevel);

	FRDGBufferRef RawBuffer = nullptr;
	if (RawDataPooled_RT.IsValid())
	{
		RawBuffer = GraphBuilder.RegisterExternalBuffer(RawDataPooled_RT);
	}
	else
	{
		RawBuffer = CreateStructuredBuffer(
			GraphBuilder, TEXT("GS7DRGS.Raw"), RawData_RT);
		GraphBuilder.QueueBufferExtraction(RawBuffer, &RawDataPooled_RT);
	}

	const FRDGBufferDesc Float4Desc = FRDGBufferDesc::CreateStructuredDesc(
		sizeof(FVector4f), PointCount_RT);
	const FRDGBufferDesc UintDesc =
		FRDGBufferDesc::CreateBufferDesc(sizeof(uint32), PointCount_RT);
	const FRDGBufferDesc FloatDesc =
		FRDGBufferDesc::CreateBufferDesc(sizeof(float), PointCount_RT);

	FRDGBufferRef Sliced = GraphBuilder.CreateBuffer(
		FRDGBufferDesc::CreateStructuredDesc(
			sizeof(FVector4f),
			PointCount_RT * GaussianSplatting7DRGS::SlicedStrideFloat4),
		TEXT("GS7DRGS.Sliced"));
	FRDGBufferRef VisiblePosOpacity =
		GraphBuilder.CreateBuffer(Float4Desc, TEXT("GS7DRGS.VisiblePosOpacity"));
	FRDGBufferRef VisibleConicColor =
		GraphBuilder.CreateBuffer(Float4Desc, TEXT("GS7DRGS.VisibleConicColor"));
	FRDGBufferRef VisibleColorExtra =
		GraphBuilder.CreateBuffer(Float4Desc, TEXT("GS7DRGS.VisibleColorExtra"));
	FRDGBufferRef VisibleBasis =
		GraphBuilder.CreateBuffer(Float4Desc, TEXT("GS7DRGS.VisibleBasis"));
	FRDGBufferRef VisibleTView =
		GraphBuilder.CreateBuffer(FloatDesc, TEXT("GS7DRGS.VisibleTView"));
	FRDGBufferRef TilesTouched =
		GraphBuilder.CreateBuffer(UintDesc, TEXT("GS7DRGS.TilesTouched"));
	FRDGBufferRef VisibleRectMin =
		GraphBuilder.CreateBuffer(UintDesc, TEXT("GS7DRGS.VisibleRectMin"));
	FRDGBufferRef VisibleRectMax =
		GraphBuilder.CreateBuffer(UintDesc, TEXT("GS7DRGS.VisibleRectMax"));
	FRDGBufferRef SortKeys[2] = {
		GraphBuilder.CreateBuffer(UintDesc, TEXT("GS7DRGS.SortKeys0")),
		GraphBuilder.CreateBuffer(UintDesc, TEXT("GS7DRGS.SortKeys1"))};
	FRDGBufferRef SortValues[2] = {
		GraphBuilder.CreateBuffer(UintDesc, TEXT("GS7DRGS.SortValues0")),
		GraphBuilder.CreateBuffer(UintDesc, TEXT("GS7DRGS.SortValues1"))};
	FRDGBufferRef VisibleCount = GraphBuilder.CreateBuffer(
		FRDGBufferDesc::CreateBufferDesc(sizeof(uint32), 1),
		TEXT("GS7DRGS.VisibleCount"));
	FRDGBufferRef SourceAABBMin = GraphBuilder.CreateBuffer(
		FRDGBufferDesc::CreateBufferDesc(sizeof(uint32), 2),
		TEXT("GS7DRGS.SourceAABBMin"));
	FRDGBufferRef SourceAABBMax = GraphBuilder.CreateBuffer(
		FRDGBufferDesc::CreateBufferDesc(sizeof(uint32), 2),
		TEXT("GS7DRGS.SourceAABBMax"));
	FRDGBufferRef DrawArgs = GraphBuilder.CreateBuffer(
		FRDGBufferDesc::CreateIndirectDesc<FRHIDrawIndirectParameters>(),
		TEXT("GS7DRGS.DrawArgs"));

	AddClearUAVPass(
		GraphBuilder, GraphBuilder.CreateUAV(SortKeys[0], PF_R32_UINT), 0xffffffffu);
	AddClearUAVPass(
		GraphBuilder, GraphBuilder.CreateUAV(SortKeys[1], PF_R32_UINT), 0xffffffffu);
	AddClearUAVPass(
		GraphBuilder, GraphBuilder.CreateUAV(SortValues[0], PF_R32_UINT), 0u);
	AddClearUAVPass(
		GraphBuilder, GraphBuilder.CreateUAV(SortValues[1], PF_R32_UINT), 0u);
	AddClearUAVPass(
		GraphBuilder, GraphBuilder.CreateUAV(VisibleCount, PF_R32_UINT), 0u);
	AddClearUAVPass(
		GraphBuilder, GraphBuilder.CreateUAV(SourceAABBMin, PF_R32_UINT), 0xffffffffu);
	AddClearUAVPass(
		GraphBuilder, GraphBuilder.CreateUAV(SourceAABBMax, PF_R32_UINT), 0u);

	{
		TShaderMapRef<FGS7DSlicingCS> Shader(ShaderMap);
		FGS7DSlicingCS::FParameters* Pass =
			GraphBuilder.AllocParameters<FGS7DSlicingCS::FParameters>();
		Pass->GaussianData7D = GraphBuilder.CreateSRV(RawBuffer);
		Pass->GaussianData3DEquiv = GraphBuilder.CreateUAV(Sliced);
		Pass->GS7D_NumGaussians = PointCount_RT;
		Pass->GS7D_InputStrideFloat4 = GaussianSplatting7DRGS::InputStrideFloat4;
		Pass->GS7D_CurrentTime = Parameters_RT.CurrentTime;
		Pass->GS7D_ViewDirection = Parameters_RT.ConditionDirection;
		Pass->GS7D_PreViewTranslation =
			FVector3f(InView.ViewMatrices.GetPreViewTranslation());
		Pass->GS7D_LocalToWorld = Parameters_RT.LocalToWorld;
		Pass->GS7D_LocalCenterOffset = Parameters_RT.LocalCenterOffset;
		Pass->GS7D_RelightEnable = 1u;
		Pass->GS7D_RelightLightDirWS = Parameters_RT.LightDirectionWS;
		Pass->GS7D_RelightLightColor = Parameters_RT.LightColor;
		Pass->GS7D_DualSHEnable = Parameters_RT.bDualSH;
		Pass->GS7D_TViewSHDegree = Parameters_RT.TViewSHDegree;
		Pass->GS7D_DebugSHDegree = static_cast<uint32>(
			FMath::Clamp(CVarGSDebugSHDegree.GetValueOnRenderThread(), 0, 3));
		FComputeShaderUtils::AddPass(
			GraphBuilder,
			RDG_EVENT_NAME("GS7DRGS Slice"),
			Shader,
			Pass,
			FComputeShaderUtils::GetGroupCountWrapped(PointCount_RT, 64));
	}

	{
		const FMatrix Projection = InView.ViewMatrices.GetViewToClip();
		FGSPreprocessCS::FParameters* Pass =
			GraphBuilder.AllocParameters<FGSPreprocessCS::FParameters>();
		Pass->View = GetShaderBinding(InView.ViewUniformBuffer);
		Pass->GaussianDataBuffer = GraphBuilder.CreateSRV(Sliced);
		Pass->VisiblePosOpacity = GraphBuilder.CreateUAV(VisiblePosOpacity);
		Pass->VisibleConicColor = GraphBuilder.CreateUAV(VisibleConicColor);
		Pass->VisibleColorExtra = GraphBuilder.CreateUAV(VisibleColorExtra);
		Pass->VisibleBasis = GraphBuilder.CreateUAV(VisibleBasis);
		Pass->VisibleTView = GraphBuilder.CreateUAV(VisibleTView, PF_R32_FLOAT);
		Pass->TilesTouched = GraphBuilder.CreateUAV(TilesTouched, PF_R32_UINT);
		Pass->VisibleRectMin = GraphBuilder.CreateUAV(VisibleRectMin, PF_R32_UINT);
		Pass->VisibleRectMax = GraphBuilder.CreateUAV(VisibleRectMax, PF_R32_UINT);
		Pass->OutVisibleSortKey = GraphBuilder.CreateUAV(SortKeys[0], PF_R32_UINT);
		Pass->OutVisibleSortValue = GraphBuilder.CreateUAV(SortValues[0], PF_R32_UINT);
		Pass->OutVisibleCount = GraphBuilder.CreateUAV(VisibleCount, PF_R32_UINT);
		Pass->OutSourceScreenAABBMin =
			GraphBuilder.CreateUAV(SourceAABBMin, PF_R32_UINT);
		Pass->OutSourceScreenAABBMax =
			GraphBuilder.CreateUAV(SourceAABBMax, PF_R32_UINT);
		Pass->GSViewMatrix =
			FMatrix44f(InView.ViewMatrices.GetTranslatedViewMatrix());
		Pass->GSProjMatrix = FMatrix44f(Projection);
		Pass->GSViewProjMatrix =
			FMatrix44f(InView.ViewMatrices.GetTranslatedWorldToClip());
		Pass->GSTanHalfFov = FVector2f(
			1.0f / FMath::Max(static_cast<float>(Projection.M[0][0]), UE_SMALL_NUMBER),
			1.0f / FMath::Max(static_cast<float>(Projection.M[1][1]), UE_SMALL_NUMBER));
		Pass->GSScreenSize = ScreenSize;
		Pass->GSNumGaussians = PointCount_RT;
		// These legacy cull slots are unused by the shader. Reuse them to pass
		// the exact post-process output rect without changing shader metadata.
		Pass->GSCameraPosition = FVector3f(
			static_cast<float>(OutputViewRect.Min.X),
			static_cast<float>(OutputViewRect.Min.Y),
			static_cast<float>(OutputViewRect.Width()));
		Pass->GSFrustumCullMode =
			CVarGSFrustumCull.GetValueOnRenderThread() != 0 ? 1u : 0u;
		Pass->GSFrustumSlack = static_cast<float>(OutputViewRect.Height());
		Pass->GSSubPixelLodRadius =
			FMath::Max(CVarGSSubPixelRadius.GetValueOnRenderThread(), 0.0f);

		TShaderMapRef<FGSPreprocessCS> Shader(ShaderMap);
		FComputeShaderUtils::AddPass(
			GraphBuilder,
			RDG_EVENT_NAME("GS7DRGS Preprocess"),
			Shader,
			Pass,
			FComputeShaderUtils::GetGroupCountWrapped(PointCount_RT, 256));
	}

	{
		FGSSortPassParameters* Pass =
			GraphBuilder.AllocParameters<FGSSortPassParameters>();
		Pass->KeySRV0 = GraphBuilder.CreateSRV(SortKeys[0], PF_R32_UINT);
		Pass->KeySRV1 = GraphBuilder.CreateSRV(SortKeys[1], PF_R32_UINT);
		Pass->KeyUAV0 = GraphBuilder.CreateUAV(SortKeys[0], PF_R32_UINT);
		Pass->KeyUAV1 = GraphBuilder.CreateUAV(SortKeys[1], PF_R32_UINT);
		Pass->ValueSRV0 = GraphBuilder.CreateSRV(SortValues[0], PF_R32_UINT);
		Pass->ValueSRV1 = GraphBuilder.CreateSRV(SortValues[1], PF_R32_UINT);
		Pass->ValueUAV0 = GraphBuilder.CreateUAV(SortValues[0], PF_R32_UINT);
		Pass->ValueUAV1 = GraphBuilder.CreateUAV(SortValues[1], PF_R32_UINT);
		GraphBuilder.AddPass(
			RDG_EVENT_NAME("GS7DRGS Sort BackToFront"),
			Pass,
			ERDGPassFlags::Compute,
			[Pass, PointCount = PointCount_RT, FeatureLevel](FRHICommandList& RHICmdList)
			{
				FGPUSortBuffers Buffers;
				Buffers.RemoteKeySRVs[0] = Pass->KeySRV0->GetRHI();
				Buffers.RemoteKeySRVs[1] = Pass->KeySRV1->GetRHI();
				Buffers.RemoteKeyUAVs[0] = Pass->KeyUAV0->GetRHI();
				Buffers.RemoteKeyUAVs[1] = Pass->KeyUAV1->GetRHI();
				Buffers.RemoteValueSRVs[0] = Pass->ValueSRV0->GetRHI();
				Buffers.RemoteValueSRVs[1] = Pass->ValueSRV1->GetRHI();
				Buffers.RemoteValueUAVs[0] = Pass->ValueUAV0->GetRHI();
				Buffers.RemoteValueUAVs[1] = Pass->ValueUAV1->GetRHI();
				const int32 Result = SortGPUBuffers(
					RHICmdList, Buffers, 0, 0xffffffffu,
					static_cast<int32>(PointCount), FeatureLevel);
				check(Result == 0);
			});
	}

	{
		TShaderMapRef<FGSBuildDrawArgsCS> Shader(ShaderMap);
		FGSBuildDrawArgsCS::FParameters* Pass =
			GraphBuilder.AllocParameters<FGSBuildDrawArgsCS::FParameters>();
		Pass->InVisibleCount = GraphBuilder.CreateSRV(VisibleCount, PF_R32_UINT);
		Pass->OutDrawArgs = GraphBuilder.CreateUAV(DrawArgs, PF_R32_UINT);
		Pass->GSMaxInstanceCap = PointCount_RT;
		FComputeShaderUtils::AddPass(
			GraphBuilder,
			RDG_EVENT_NAME("GS7DRGS Build Draw Args"),
			Shader,
			Pass,
			FIntVector(1, 1, 1));
	}

	FRDGTextureRef GSColor = GraphBuilder.CreateTexture(
		FRDGTextureDesc::Create2D(
			Extent,
			PF_FloatRGBA,
			FClearValueBinding(FLinearColor(0.0f, 0.0f, 0.0f, 1.0f)),
			TexCreate_ShaderResource | TexCreate_RenderTargetable),
		TEXT("GS7DRGS.Color"));

	const FSceneTextureUniformParameters* SceneTextureContents =
		Inputs.SceneTextures.SceneTextures
			? Inputs.SceneTextures.SceneTextures->GetContents()
			: nullptr;
	FRDGTextureRef SceneDepth =
		SceneTextureContents && SceneTextureContents->SceneDepthTexture
			? SceneTextureContents->SceneDepthTexture
			: GSystemTextures.GetDepthDummy(GraphBuilder);

	{
		TShaderMapRef<FGSHWQuadVS> VertexShader(ShaderMap);
		TShaderMapRef<FGSHWQuadPS> PixelShader(ShaderMap);
		FGSHWRasterPassParameters* Pass =
			GraphBuilder.AllocParameters<FGSHWRasterPassParameters>();
		Pass->VS.VisiblePosOpacity = GraphBuilder.CreateSRV(VisiblePosOpacity);
		Pass->VS.VisibleConicColor = GraphBuilder.CreateSRV(VisibleConicColor);
		Pass->VS.VisibleColorExtra = GraphBuilder.CreateSRV(VisibleColorExtra);
		Pass->VS.VisibleBasis = GraphBuilder.CreateSRV(VisibleBasis);
		Pass->VS.SortedGaussianIDs =
			GraphBuilder.CreateSRV(SortValues[0], PF_R32_UINT);
		Pass->VS.VisibleTView =
			GraphBuilder.CreateSRV(VisibleTView, PF_R32_FLOAT);
		Pass->VS.GSScreenSize = ScreenSize;
		Pass->VS.GSDualSHEnable = Parameters_RT.bDualSH;
		Pass->PS.View = GetShaderBinding(InView.ViewUniformBuffer);
		Pass->PS.GSScreenSize = ScreenSize;
		Pass->PS.GSOpacityMultiplier = Parameters_RT.OpacityMultiplier;
		Pass->PS.GSOpacityPower = Parameters_RT.OpacityPower;
		Pass->PS.SceneDepthTexture = SceneDepth;
		Pass->PS.SceneDepthSampler =
			TStaticSamplerState<SF_Point, AM_Clamp, AM_Clamp, AM_Clamp>::GetRHI();
		Pass->PS.GSDepthTestMode = Parameters_RT.DepthTestMode;
		Pass->PS.GSDepthSoftFadeUU = Parameters_RT.DepthSoftFadeUU;
		Pass->PS.GSDualSHEnable = Parameters_RT.bDualSH;
		Pass->DrawIndirectArgs = DrawArgs;
		Pass->RenderTargets[0] =
			FRenderTargetBinding(GSColor, ERenderTargetLoadAction::EClear);
		ClearUnusedGraphResources(VertexShader, &Pass->VS);
		ClearUnusedGraphResources(PixelShader, &Pass->PS);

		GraphBuilder.AddPass(
			RDG_EVENT_NAME("GS7DRGS HW Raster"),
			Pass,
			ERDGPassFlags::Raster,
			[Pass, VertexShader, PixelShader, Extent](
				FRDGAsyncTask, FRHICommandList& RHICmdList)
			{
				RHICmdList.SetViewport(
					0.0f, 0.0f, 0.0f,
					static_cast<float>(Extent.X), static_cast<float>(Extent.Y), 1.0f);
				FGraphicsPipelineStateInitializer PSO;
				RHICmdList.ApplyCachedRenderTargets(PSO);
				PSO.RasterizerState =
					TStaticRasterizerState<FM_Solid, CM_None>::GetRHI();
				PSO.DepthStencilState =
					TStaticDepthStencilState<false, CF_Always>::GetRHI();
				PSO.BlendState =
					TStaticBlendState<
						CW_RGBA,
						BO_Add, BF_One, BF_SourceAlpha,
						BO_Add, BF_Zero, BF_SourceAlpha>::GetRHI();
				PSO.PrimitiveType = PT_TriangleStrip;
				PSO.BoundShaderState.VertexDeclarationRHI =
					GEmptyVertexDeclaration.VertexDeclarationRHI;
				PSO.BoundShaderState.VertexShaderRHI = VertexShader.GetVertexShader();
				PSO.BoundShaderState.PixelShaderRHI = PixelShader.GetPixelShader();
				SetGraphicsPipelineState(RHICmdList, PSO, 0);
				SetShaderParameters(
					RHICmdList, VertexShader, VertexShader.GetVertexShader(), Pass->VS);
				SetShaderParameters(
					RHICmdList, PixelShader, PixelShader.GetPixelShader(), Pass->PS);
				RHICmdList.SetStreamSource(0, nullptr, 0);
				RHICmdList.DrawPrimitiveIndirect(
					Pass->DrawIndirectArgs->GetIndirectRHICallBuffer(), 0);
			});
	}

	{
		TShaderMapRef<FGSCompositeVS> VertexShader(ShaderMap);
		TShaderMapRef<FGSCompositePS> PixelShader(ShaderMap);
		FGSCompositePassParameters* Pass =
			GraphBuilder.AllocParameters<FGSCompositePassParameters>();
		const FRDGBufferSRVRef AABBMinSRV =
			GraphBuilder.CreateSRV(SourceAABBMin, PF_R32_UINT);
		const FRDGBufferSRVRef AABBMaxSRV =
			GraphBuilder.CreateSRV(SourceAABBMax, PF_R32_UINT);
		const uint32 bUseAABB =
			CVarGSSourceAABB.GetValueOnRenderThread() != 0 ? 1u : 0u;
		Pass->VS.GSSourceScreenAABBMin = AABBMinSRV;
		Pass->VS.GSSourceScreenAABBMax = AABBMaxSRV;
		Pass->VS.GSCompositeSize = ScreenSize;
		Pass->VS.GSUseSourceAABB = bUseAABB;
		Pass->PS.View = GetShaderBinding(InView.ViewUniformBuffer);
		Pass->PS.GSColorTexture = GSColor;
		Pass->PS.GSColorSampler =
			TStaticSamplerState<SF_Point, AM_Clamp, AM_Clamp, AM_Clamp>::GetRHI();
		Pass->PS.GSRelightLightColor = Parameters_RT.LightColor;
		Pass->PS.GSRelightAmbientColor = Parameters_RT.AmbientLightColor;
		Pass->PS.GSRelightLightDirWS = Parameters_RT.LightDirectionWS;
		Pass->PS.GSUseTViewMatte = Parameters_RT.bDualSH;
		Pass->PS.GSApplyAtmosphereScale = 1u;
		Pass->PS.GSDebugOverlay = 0u;
		Pass->PS.GSCompositeSize = ScreenSize;
		Pass->PS.GSSourceScreenAABBMin = AABBMinSRV;
		Pass->PS.GSSourceScreenAABBMax = AABBMaxSRV;
		Pass->PS.GSUseSourceAABB = bUseAABB;
		Pass->PS.GSPhaseMode = Parameters_RT.PhaseMode;
		Pass->PS.GSPhaseG = Parameters_RT.PhaseG;
		Pass->PS.GSPhaseG2 = Parameters_RT.PhaseG2;
		Pass->PS.GSPhaseBlend = Parameters_RT.PhaseBlend;
		Pass->PS.GSNubisEccentricity = Parameters_RT.NubisEccentricity;
		Pass->PS.GSNubisSilverIntensity = Parameters_RT.NubisSilverIntensity;
		Pass->PS.GSNubisSilverSpread = Parameters_RT.NubisSilverSpread;
		Pass->PS.GSPhaseIntensity = Parameters_RT.PhaseIntensity;
		const FLumenTranslucencyGIVolume& LumenGI =
			const_cast<FViewInfo&>(static_cast<const FViewInfo&>(InView))
				.GetOwnLumenTranslucencyGIVolume();
		const FRDGTextureRef LumenAmbient =
			LumenGI.HistoryTexture0 ? LumenGI.HistoryTexture0 : LumenGI.Texture0;
		Pass->PS.GSTranslucencyGIVolumeHistory0 =
			LumenAmbient
				? LumenAmbient
				: GSystemTextures.GetVolumetricBlackDummy(GraphBuilder);
		Pass->PS.GSTranslucencyGIVolumeSampler =
			TStaticSamplerState<SF_Trilinear, AM_Clamp, AM_Clamp, AM_Clamp>::GetRHI();
		Pass->PS.GSTranslucencyGIGridZParams =
			LumenAmbient ? FVector3f(LumenGI.GridZParams) : FVector3f::ZeroVector;
		Pass->PS.GSTranslucencyGIGridSize =
			LumenAmbient ? LumenGI.GridSize : FIntVector::ZeroValue;
		Pass->PS.GSTranslucencyGIScreenToResourceUV =
			LumenAmbient ? LumenGI.ScreenToResourceUV : FVector2f(1.0f, 1.0f);
		Pass->PS.GSTranslucencyGIScreenToResourceMaxUV =
			LumenAmbient ? LumenGI.ScreenToResourceMaxUV : FVector2f(1.0f, 1.0f);
		Pass->PS.GSSourceWorldPos = Parameters_RT.SourceWorldPosition;
		Pass->PS.GSIndirectLightEnable =
			LumenAmbient && LumenGI.GridSize.Z > 0 ? 1u : 0u;
		Pass->PS.GSIndirectLightIntensity = 1.0f;
		Pass->RenderTargets[0] =
			FRenderTargetBinding(SceneColor.Texture, ERenderTargetLoadAction::ELoad);
		ClearUnusedGraphResources(VertexShader, &Pass->VS);
		ClearUnusedGraphResources(PixelShader, &Pass->PS);

		GraphBuilder.AddPass(
			RDG_EVENT_NAME("GS7DRGS Composite"),
			Pass,
			ERDGPassFlags::Raster,
			[Pass, VertexShader, PixelShader, Extent](
				FRDGAsyncTask, FRHICommandList& RHICmdList)
			{
				RHICmdList.SetViewport(
					0.0f, 0.0f, 0.0f,
					static_cast<float>(Extent.X), static_cast<float>(Extent.Y), 1.0f);
				FGraphicsPipelineStateInitializer PSO;
				RHICmdList.ApplyCachedRenderTargets(PSO);
				PSO.RasterizerState =
					TStaticRasterizerState<FM_Solid, CM_None>::GetRHI();
				PSO.DepthStencilState =
					TStaticDepthStencilState<false, CF_Always>::GetRHI();
				PSO.BlendState =
					TStaticBlendState<
						CW_RGBA,
						BO_Add, BF_One, BF_SourceAlpha,
						BO_Add, BF_Zero, BF_SourceAlpha>::GetRHI();
				PSO.PrimitiveType = PT_TriangleStrip;
				PSO.BoundShaderState.VertexDeclarationRHI =
					GEmptyVertexDeclaration.VertexDeclarationRHI;
				PSO.BoundShaderState.VertexShaderRHI = VertexShader.GetVertexShader();
				PSO.BoundShaderState.PixelShaderRHI = PixelShader.GetPixelShader();
				SetGraphicsPipelineState(RHICmdList, PSO, 0);
				SetShaderParameters(
					RHICmdList, VertexShader, VertexShader.GetVertexShader(), Pass->VS);
				SetShaderParameters(
					RHICmdList, PixelShader, PixelShader.GetPixelShader(), Pass->PS);
				RHICmdList.SetStreamSource(0, nullptr, 0);
				RHICmdList.DrawPrimitive(0, 2, 1);
			});
	}

	return SceneColor;
}

void FGaussianSplattingSceneViewExtension::SubscribeToPostProcessingPass(
	EPostProcessingPass Pass,
	const FSceneView& InView,
	FPostProcessingPassDelegateArray& InOutPassCallbacks,
	bool bIsPassEnabled)
{
	if (Pass == EPostProcessingPass::MotionBlur)
	{
		InOutPassCallbacks.Add(FPostProcessingPassDelegate::CreateRaw(
			this,
			&FGaussianSplattingSceneViewExtension::PostProcessCallback_RenderThread));
	}
}
