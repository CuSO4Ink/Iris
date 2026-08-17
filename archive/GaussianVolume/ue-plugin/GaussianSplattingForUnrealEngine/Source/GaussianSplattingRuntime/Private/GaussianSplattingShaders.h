#pragma once

#include "GlobalShader.h"
#include "RenderGraphResources.h"
#include "SceneView.h"
#include "ShaderParameterStruct.h"

class FGS7DSlicingCS final : public FGlobalShader
{
	DECLARE_GLOBAL_SHADER(FGS7DSlicingCS);
	SHADER_USE_PARAMETER_STRUCT(FGS7DSlicingCS, FGlobalShader);

	BEGIN_SHADER_PARAMETER_STRUCT(FParameters, )
		SHADER_PARAMETER_RDG_BUFFER_SRV(StructuredBuffer<float4>, GaussianData7D)
		SHADER_PARAMETER_RDG_BUFFER_UAV(RWStructuredBuffer<float4>, GaussianData3DEquiv)
		SHADER_PARAMETER(uint32, GS7D_NumGaussians)
		SHADER_PARAMETER(uint32, GS7D_InputStrideFloat4)
		SHADER_PARAMETER(float, GS7D_CurrentTime)
		SHADER_PARAMETER(FVector3f, GS7D_ViewDirection)
		SHADER_PARAMETER(FVector3f, GS7D_PreViewTranslation)
		SHADER_PARAMETER(FMatrix44f, GS7D_LocalToWorld)
		SHADER_PARAMETER(FVector3f, GS7D_LocalCenterOffset)
		SHADER_PARAMETER(uint32, GS7D_RelightEnable)
		SHADER_PARAMETER(FVector3f, GS7D_RelightLightDirWS)
		SHADER_PARAMETER(FVector3f, GS7D_RelightLightColor)
		SHADER_PARAMETER(uint32, GS7D_DualSHEnable)
		SHADER_PARAMETER(uint32, GS7D_TViewSHDegree)
		SHADER_PARAMETER(uint32, GS7D_DebugSHDegree)
	END_SHADER_PARAMETER_STRUCT()

	static bool ShouldCompilePermutation(const FGlobalShaderPermutationParameters& Parameters);
};

class FGSPreprocessCS final : public FGlobalShader
{
	DECLARE_GLOBAL_SHADER(FGSPreprocessCS);
	SHADER_USE_PARAMETER_STRUCT(FGSPreprocessCS, FGlobalShader);

	BEGIN_SHADER_PARAMETER_STRUCT(FParameters, )
		SHADER_PARAMETER_STRUCT_REF(FViewUniformShaderParameters, View)
		SHADER_PARAMETER_RDG_BUFFER_SRV(StructuredBuffer<float4>, GaussianDataBuffer)
		SHADER_PARAMETER_RDG_BUFFER_UAV(RWStructuredBuffer<float4>, VisiblePosOpacity)
		SHADER_PARAMETER_RDG_BUFFER_UAV(RWStructuredBuffer<float4>, VisibleConicColor)
		SHADER_PARAMETER_RDG_BUFFER_UAV(RWStructuredBuffer<float4>, VisibleColorExtra)
		SHADER_PARAMETER_RDG_BUFFER_UAV(RWStructuredBuffer<float4>, VisibleBasis)
		SHADER_PARAMETER_RDG_BUFFER_UAV(RWBuffer<float>, VisibleTView)
		SHADER_PARAMETER_RDG_BUFFER_UAV(RWBuffer<uint>, TilesTouched)
		SHADER_PARAMETER_RDG_BUFFER_UAV(RWBuffer<uint>, VisibleRectMin)
		SHADER_PARAMETER_RDG_BUFFER_UAV(RWBuffer<uint>, VisibleRectMax)
		SHADER_PARAMETER_RDG_BUFFER_UAV(RWBuffer<uint>, OutVisibleSortKey)
		SHADER_PARAMETER_RDG_BUFFER_UAV(RWBuffer<uint>, OutVisibleSortValue)
		SHADER_PARAMETER_RDG_BUFFER_UAV(RWBuffer<uint>, OutVisibleCount)
		SHADER_PARAMETER_RDG_BUFFER_UAV(RWBuffer<uint>, OutSourceScreenAABBMin)
		SHADER_PARAMETER_RDG_BUFFER_UAV(RWBuffer<uint>, OutSourceScreenAABBMax)
		SHADER_PARAMETER(FMatrix44f, GSViewMatrix)
		SHADER_PARAMETER(FMatrix44f, GSProjMatrix)
		SHADER_PARAMETER(FMatrix44f, GSViewProjMatrix)
		SHADER_PARAMETER(FVector2f, GSTanHalfFov)
		SHADER_PARAMETER(FUintVector2, GSScreenSize)
		SHADER_PARAMETER(uint32, GSNumGaussians)
		SHADER_PARAMETER(FVector3f, GSCameraPosition)
		SHADER_PARAMETER(uint32, GSFrustumCullMode)
		SHADER_PARAMETER(float, GSFrustumSlack)
		SHADER_PARAMETER(float, GSSubPixelLodRadius)
	END_SHADER_PARAMETER_STRUCT()

	static bool ShouldCompilePermutation(const FGlobalShaderPermutationParameters& Parameters);
};

class FGSBuildDrawArgsCS final : public FGlobalShader
{
	DECLARE_GLOBAL_SHADER(FGSBuildDrawArgsCS);
	SHADER_USE_PARAMETER_STRUCT(FGSBuildDrawArgsCS, FGlobalShader);

	BEGIN_SHADER_PARAMETER_STRUCT(FParameters, )
		SHADER_PARAMETER_RDG_BUFFER_SRV(Buffer<uint>, InVisibleCount)
		SHADER_PARAMETER_RDG_BUFFER_UAV(RWBuffer<uint>, OutDrawArgs)
		SHADER_PARAMETER(uint32, GSMaxInstanceCap)
	END_SHADER_PARAMETER_STRUCT()

	static bool ShouldCompilePermutation(const FGlobalShaderPermutationParameters& Parameters);
};

class FGSHWQuadVS final : public FGlobalShader
{
	DECLARE_GLOBAL_SHADER(FGSHWQuadVS);
	SHADER_USE_PARAMETER_STRUCT(FGSHWQuadVS, FGlobalShader);

	BEGIN_SHADER_PARAMETER_STRUCT(FParameters, )
		SHADER_PARAMETER_RDG_BUFFER_SRV(StructuredBuffer<float4>, VisiblePosOpacity)
		SHADER_PARAMETER_RDG_BUFFER_SRV(StructuredBuffer<float4>, VisibleConicColor)
		SHADER_PARAMETER_RDG_BUFFER_SRV(StructuredBuffer<float4>, VisibleColorExtra)
		SHADER_PARAMETER_RDG_BUFFER_SRV(StructuredBuffer<float4>, VisibleBasis)
		SHADER_PARAMETER_RDG_BUFFER_SRV(Buffer<uint>, SortedGaussianIDs)
		SHADER_PARAMETER_RDG_BUFFER_SRV(Buffer<float>, VisibleTView)
		SHADER_PARAMETER(FUintVector2, GSScreenSize)
		SHADER_PARAMETER(uint32, GSDualSHEnable)
	END_SHADER_PARAMETER_STRUCT()

	static bool ShouldCompilePermutation(const FGlobalShaderPermutationParameters& Parameters);
};

class FGSHWQuadPS final : public FGlobalShader
{
	DECLARE_GLOBAL_SHADER(FGSHWQuadPS);
	SHADER_USE_PARAMETER_STRUCT(FGSHWQuadPS, FGlobalShader);

	BEGIN_SHADER_PARAMETER_STRUCT(FParameters, )
		SHADER_PARAMETER_STRUCT_REF(FViewUniformShaderParameters, View)
		SHADER_PARAMETER(FUintVector2, GSScreenSize)
		SHADER_PARAMETER(float, GSOpacityMultiplier)
		SHADER_PARAMETER(float, GSOpacityPower)
		SHADER_PARAMETER_RDG_TEXTURE(Texture2D, SceneDepthTexture)
		SHADER_PARAMETER_SAMPLER(SamplerState, SceneDepthSampler)
		SHADER_PARAMETER(uint32, GSDepthTestMode)
		SHADER_PARAMETER(float, GSDepthSoftFadeUU)
		SHADER_PARAMETER(uint32, GSDualSHEnable)
	END_SHADER_PARAMETER_STRUCT()

	static bool ShouldCompilePermutation(const FGlobalShaderPermutationParameters& Parameters);
};

class FGSCompositeVS final : public FGlobalShader
{
	DECLARE_GLOBAL_SHADER(FGSCompositeVS);
	SHADER_USE_PARAMETER_STRUCT(FGSCompositeVS, FGlobalShader);

	BEGIN_SHADER_PARAMETER_STRUCT(FParameters, )
		SHADER_PARAMETER_RDG_BUFFER_SRV(Buffer<uint>, GSSourceScreenAABBMin)
		SHADER_PARAMETER_RDG_BUFFER_SRV(Buffer<uint>, GSSourceScreenAABBMax)
		SHADER_PARAMETER(FUintVector2, GSCompositeSize)
		SHADER_PARAMETER(uint32, GSUseSourceAABB)
	END_SHADER_PARAMETER_STRUCT()

	static bool ShouldCompilePermutation(const FGlobalShaderPermutationParameters& Parameters);
};

class FGSCompositePS final : public FGlobalShader
{
	DECLARE_GLOBAL_SHADER(FGSCompositePS);
	SHADER_USE_PARAMETER_STRUCT(FGSCompositePS, FGlobalShader);

	BEGIN_SHADER_PARAMETER_STRUCT(FParameters, )
		SHADER_PARAMETER_STRUCT_REF(FViewUniformShaderParameters, View)
		SHADER_PARAMETER_RDG_TEXTURE(Texture2D, GSColorTexture)
		SHADER_PARAMETER_SAMPLER(SamplerState, GSColorSampler)
		SHADER_PARAMETER(FVector3f, GSRelightLightColor)
		SHADER_PARAMETER(FVector3f, GSRelightAmbientColor)
		SHADER_PARAMETER(FVector3f, GSRelightLightDirWS)
		SHADER_PARAMETER(uint32, GSUseTViewMatte)
		SHADER_PARAMETER(uint32, GSApplyAtmosphereScale)
		SHADER_PARAMETER(uint32, GSDebugOverlay)
		SHADER_PARAMETER(FUintVector2, GSCompositeSize)
		SHADER_PARAMETER_RDG_BUFFER_SRV(Buffer<uint>, GSSourceScreenAABBMin)
		SHADER_PARAMETER_RDG_BUFFER_SRV(Buffer<uint>, GSSourceScreenAABBMax)
		SHADER_PARAMETER(uint32, GSUseSourceAABB)
		SHADER_PARAMETER(uint32, GSPhaseMode)
		SHADER_PARAMETER(float, GSPhaseG)
		SHADER_PARAMETER(float, GSPhaseG2)
		SHADER_PARAMETER(float, GSPhaseBlend)
		SHADER_PARAMETER(float, GSNubisEccentricity)
		SHADER_PARAMETER(float, GSNubisSilverIntensity)
		SHADER_PARAMETER(float, GSNubisSilverSpread)
		SHADER_PARAMETER(float, GSPhaseIntensity)
		SHADER_PARAMETER_RDG_TEXTURE(Texture3D, GSTranslucencyGIVolumeHistory0)
		SHADER_PARAMETER_SAMPLER(SamplerState, GSTranslucencyGIVolumeSampler)
		SHADER_PARAMETER(FVector3f, GSTranslucencyGIGridZParams)
		SHADER_PARAMETER(FIntVector, GSTranslucencyGIGridSize)
		SHADER_PARAMETER(FVector2f, GSTranslucencyGIScreenToResourceUV)
		SHADER_PARAMETER(FVector2f, GSTranslucencyGIScreenToResourceMaxUV)
		SHADER_PARAMETER(FVector3f, GSSourceWorldPos)
		SHADER_PARAMETER(uint32, GSIndirectLightEnable)
		SHADER_PARAMETER(float, GSIndirectLightIntensity)
	END_SHADER_PARAMETER_STRUCT()

	static bool ShouldCompilePermutation(const FGlobalShaderPermutationParameters& Parameters);
};

BEGIN_SHADER_PARAMETER_STRUCT(FGSSortPassParameters, )
	SHADER_PARAMETER_RDG_BUFFER_SRV(Buffer<uint>, KeySRV0)
	SHADER_PARAMETER_RDG_BUFFER_SRV(Buffer<uint>, KeySRV1)
	SHADER_PARAMETER_RDG_BUFFER_UAV(RWBuffer<uint>, KeyUAV0)
	SHADER_PARAMETER_RDG_BUFFER_UAV(RWBuffer<uint>, KeyUAV1)
	SHADER_PARAMETER_RDG_BUFFER_SRV(Buffer<uint>, ValueSRV0)
	SHADER_PARAMETER_RDG_BUFFER_SRV(Buffer<uint>, ValueSRV1)
	SHADER_PARAMETER_RDG_BUFFER_UAV(RWBuffer<uint>, ValueUAV0)
	SHADER_PARAMETER_RDG_BUFFER_UAV(RWBuffer<uint>, ValueUAV1)
END_SHADER_PARAMETER_STRUCT()

BEGIN_SHADER_PARAMETER_STRUCT(FGSHWRasterPassParameters, )
	SHADER_PARAMETER_STRUCT_INCLUDE(FGSHWQuadVS::FParameters, VS)
	SHADER_PARAMETER_STRUCT_INCLUDE(FGSHWQuadPS::FParameters, PS)
	RDG_BUFFER_ACCESS(DrawIndirectArgs, ERHIAccess::IndirectArgs)
	RENDER_TARGET_BINDING_SLOTS()
END_SHADER_PARAMETER_STRUCT()

BEGIN_SHADER_PARAMETER_STRUCT(FGSCompositePassParameters, )
	SHADER_PARAMETER_STRUCT_INCLUDE(FGSCompositeVS::FParameters, VS)
	SHADER_PARAMETER_STRUCT_INCLUDE(FGSCompositePS::FParameters, PS)
	RENDER_TARGET_BINDING_SLOTS()
END_SHADER_PARAMETER_STRUCT()
