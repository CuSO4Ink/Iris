// Copyright 2026 Violina. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GlobalShader.h"
#include "RenderGraph.h"
#include "RenderGraphBuilder.h"
#include "ShaderParameterStruct.h"
#include "RHICommandList.h"
#include "SceneRenderTargetParameters.h"

/** Direct NanoVDB Fp8/FpN reference renderer used for the matched-memory baseline. */
class FNanoVdbRayMarchCS : public FGlobalShader
{
	DECLARE_GLOBAL_SHADER(FNanoVdbRayMarchCS);
	SHADER_USE_PARAMETER_STRUCT(FNanoVdbRayMarchCS, FGlobalShader);

	BEGIN_SHADER_PARAMETER_STRUCT(FParameters, )
		SHADER_PARAMETER(FVector4f, Resolution)
		SHADER_PARAMETER(FVector4f, ViewRectMin)
		SHADER_PARAMETER(FVector4f, DepthViewRect)
		SHADER_PARAMETER(FVector4f, DepthBufferInvSize)
		SHADER_PARAMETER(FMatrix44f, ClipToWorld)
		SHADER_PARAMETER(FMatrix44f, WorldToNanoLocal)
		SHADER_PARAMETER(FVector4f, Albedo)
		SHADER_PARAMETER(float, DensityScale)
		SHADER_PARAMETER(float, StepSizeVoxels)
		SHADER_PARAMETER(uint32, MaxSteps)
		SHADER_PARAMETER(uint32, bUseSceneDepth)
		SHADER_PARAMETER_RDG_BUFFER_SRV(StructuredBuffer<uint32>, NanoVdbBuffer)
		SHADER_PARAMETER_RDG_TEXTURE_SRV(Texture2D, SceneColorTexture)
		SHADER_PARAMETER_STRUCT_INCLUDE(FSceneTextureShaderParameters, SceneTextures)
		SHADER_PARAMETER_RDG_TEXTURE_UAV(RWTexture2D<float4>, OutputTexture)
	END_SHADER_PARAMETER_STRUCT()

public:
	static bool ShouldCompilePermutation(const FGlobalShaderPermutationParameters& Parameters)
	{
		return IsFeatureLevelSupported(Parameters.Platform, ERHIFeatureLevel::SM6);
	}

	static void ModifyCompilationEnvironment(
		const FGlobalShaderPermutationParameters& Parameters,
		FShaderCompilerEnvironment& OutEnvironment)
	{
		FGlobalShader::ModifyCompilationEnvironment(Parameters, OutEnvironment);
		OutEnvironment.SetDefine(TEXT("THREADGROUP_SIZE_X"), 8);
		OutEnvironment.SetDefine(TEXT("THREADGROUP_SIZE_Y"), 8);
	}
};

/**
 * Phase 3: Ray-tracing renderer compute shader.
 * Replaces the Phase 2 debug CS. Per-pixel: generates camera ray, loops over
 * all Gaussians (brute force), computes analytic transmittance via erf integral,
 * front-to-back compositing with single scattering + powder effect.
 *
 * Shader file: Shaders/Private/GaussianVolume.usf, entry point MainCS.
 */
class FGaussianVolumeRayTraceCS : public FGlobalShader
{
	DECLARE_GLOBAL_SHADER(FGaussianVolumeRayTraceCS);
	SHADER_USE_PARAMETER_STRUCT(FGaussianVolumeRayTraceCS, FGlobalShader);

	BEGIN_SHADER_PARAMETER_STRUCT(FParameters, )
		// Resolution: x=width, y=height, z=1/width, w=1/height
		SHADER_PARAMETER(FVector4f, Resolution)
		SHADER_PARAMETER(FVector4f, ViewRectMin)   // xy = viewport min offset in the full (SceneColor) texture
		// Depth-buffer mapping: SceneDepth lives at the PRIMARY render resolution, which
		// differs from the post-tonemap SceneColor extent (TSR/screen-percentage upscale).
		// xy = primary depth ViewRect min (texels), zw = primary depth ViewRect size (texels).
		SHADER_PARAMETER(FVector4f, DepthViewRect)
		// xy = 1 / SceneDepth buffer extent (for UV sampling).
		SHADER_PARAMETER(FVector4f, DepthBufferInvSize)
		SHADER_PARAMETER(FMatrix44f, ClipToWorld)  // inverse view-projection: NDC -> world
		// Camera: position + forward/right/up (each xyz, w unused)
		SHADER_PARAMETER(FVector4f, CameraPos)
		SHADER_PARAMETER(FVector4f, CameraDirs)   // x=tanHalfFov, y=aspect, zw unused
		SHADER_PARAMETER(FVector4f, CameraForward)
		SHADER_PARAMETER(FVector4f, CameraRight)
		SHADER_PARAMETER(FVector4f, CameraUp)
		// Lighting
		SHADER_PARAMETER(FVector4f, LightDir)
		SHADER_PARAMETER(FVector4f, LightColor)
		SHADER_PARAMETER(FVector4f, AmbientColor)
		SHADER_PARAMETER(float, PowderFactor)
		SHADER_PARAMETER(float, MaxRayDistance)
		SHADER_PARAMETER(uint32, bUseSceneDepth)
		SHADER_PARAMETER(uint32, DebugView)
		// Gaussian data
		SHADER_PARAMETER(uint32, NumGaussians)
		SHADER_PARAMETER(uint32, NumInstances)
		SHADER_PARAMETER(uint32, bSingleInstance)
		SHADER_PARAMETER(uint32, SinglePrimitiveOffset)
		SHADER_PARAMETER(uint32, SinglePrimitiveCount)
		SHADER_PARAMETER(FVector4f, SingleInstanceOffset)
		SHADER_PARAMETER(uint32, SingleLightBasisRotation)
		SHADER_PARAMETER(uint32, NumTilesX)
		SHADER_PARAMETER(uint32, TileSize)
		SHADER_PARAMETER(uint32, bUseUniformFastPath)
		SHADER_PARAMETER(uint32, bUseDirectionalLightTau)
		SHADER_PARAMETER(FVector4f, UniformAppearance)
		SHADER_PARAMETER_RDG_BUFFER_SRV(StructuredBuffer<FGaussianVolumePackedPrimitive>, GaussianBuffer)
		SHADER_PARAMETER_RDG_BUFFER_SRV(StructuredBuffer<FGaussianVolumePackedInstance>, InstanceBuffer)
		SHADER_PARAMETER_RDG_BUFFER_SRV(StructuredBuffer<uint>, TileCandidateRawCounts)
		SHADER_PARAMETER_RDG_BUFFER_SRV(StructuredBuffer<uint>, TileCandidateCounts)
		SHADER_PARAMETER_RDG_BUFFER_SRV(StructuredBuffer<uint>, TileCandidateOffsets)
		SHADER_PARAMETER_RDG_BUFFER_SRV(StructuredBuffer<uint>, TileCandidateIndices)
		// Per-primitive light transmittance from FGaussianVolumeLightTauCS prepass (global index).
		SHADER_PARAMETER_RDG_BUFFER_SRV(StructuredBuffer<float>, LightTransmittance)
		SHADER_PARAMETER_STRUCT_INCLUDE(FSceneTextureShaderParameters, SceneTextures)
		// Output
		SHADER_PARAMETER_RDG_TEXTURE_UAV(RWTexture2D<float4>, OutputTexture)
	END_SHADER_PARAMETER_STRUCT()

public:
	static bool ShouldCompilePermutation(const FGlobalShaderPermutationParameters& Parameters)
	{
		return IsFeatureLevelSupported(Parameters.Platform, ERHIFeatureLevel::SM6);
	}

	static void ModifyCompilationEnvironment(const FGlobalShaderPermutationParameters& Parameters, FShaderCompilerEnvironment& OutEnvironment)
	{
		FGlobalShader::ModifyCompilationEnvironment(Parameters, OutEnvironment);
		OutEnvironment.SetDefine(TEXT("THREADGROUP_SIZE_X"), 8);
		OutEnvironment.SetDefine(TEXT("THREADGROUP_SIZE_Y"), 8);
	}
};

/** Cross-fades complete LOD renders so different fitted density fields do not hard-pop. */
class FGaussianVolumeLodBlendCS : public FGlobalShader
{
	DECLARE_GLOBAL_SHADER(FGaussianVolumeLodBlendCS);
	SHADER_USE_PARAMETER_STRUCT(FGaussianVolumeLodBlendCS, FGlobalShader);

	BEGIN_SHADER_PARAMETER_STRUCT(FParameters, )
		SHADER_PARAMETER(FVector4f, Resolution)
		SHADER_PARAMETER(FVector4f, ViewRectMin)
		SHADER_PARAMETER(float, LodBlendAlpha)
		SHADER_PARAMETER_RDG_TEXTURE_SRV(Texture2D, LodATexture)
		SHADER_PARAMETER_RDG_TEXTURE_SRV(Texture2D, LodBTexture)
		SHADER_PARAMETER_RDG_TEXTURE_UAV(RWTexture2D<float4>, OutputTexture)
	END_SHADER_PARAMETER_STRUCT()

public:
	static bool ShouldCompilePermutation(const FGlobalShaderPermutationParameters& Parameters)
	{
		return IsFeatureLevelSupported(Parameters.Platform, ERHIFeatureLevel::SM6);
	}

	static void ModifyCompilationEnvironment(const FGlobalShaderPermutationParameters& Parameters, FShaderCompilerEnvironment& OutEnvironment)
	{
		FGlobalShader::ModifyCompilationEnvironment(Parameters, OutEnvironment);
		OutEnvironment.SetDefine(TEXT("THREADGROUP_SIZE_X"), 8);
		OutEnvironment.SetDefine(TEXT("THREADGROUP_SIZE_Y"), 8);
	}
};

/** Instanced tight proxies for the order-independent uniform-extinction A/B. */
class FGaussianVolumePoolFreeVS : public FGlobalShader
{
	DECLARE_GLOBAL_SHADER(FGaussianVolumePoolFreeVS);
	SHADER_USE_PARAMETER_STRUCT(FGaussianVolumePoolFreeVS, FGlobalShader);

	BEGIN_SHADER_PARAMETER_STRUCT(FParameters, )
		SHADER_PARAMETER(FVector4f, CameraPos)
		SHADER_PARAMETER(FVector4f, CameraForward)
		SHADER_PARAMETER(FVector4f, CameraRight)
		SHADER_PARAMETER(FVector4f, CameraUp)
		SHADER_PARAMETER(FVector4f, CameraDirs)
		SHADER_PARAMETER_RDG_BUFFER_SRV(StructuredBuffer<FGaussianVolumePackedPrimitive>, GaussianBuffer)
	END_SHADER_PARAMETER_STRUCT()

public:
	static bool ShouldCompilePermutation(const FGlobalShaderPermutationParameters& Parameters)
	{
		return IsFeatureLevelSupported(Parameters.Platform, ERHIFeatureLevel::SM6);
	}
};

/** Analytic per-proxy optical depth, composited with premultiplied alpha. */
class FGaussianVolumePoolFreePS : public FGlobalShader
{
	DECLARE_GLOBAL_SHADER(FGaussianVolumePoolFreePS);
	SHADER_USE_PARAMETER_STRUCT(FGaussianVolumePoolFreePS, FGlobalShader);

	BEGIN_SHADER_PARAMETER_STRUCT(FParameters, )
		SHADER_PARAMETER(FVector4f, Resolution)
		SHADER_PARAMETER(FVector4f, ViewRectMin)
		SHADER_PARAMETER(FVector4f, DepthViewRect)
		SHADER_PARAMETER(FVector4f, DepthBufferInvSize)
		SHADER_PARAMETER(FMatrix44f, ClipToWorld)
		SHADER_PARAMETER(FVector4f, LightColor)
		SHADER_PARAMETER(FVector4f, AmbientColor)
		SHADER_PARAMETER(FVector4f, UniformAppearance)
		SHADER_PARAMETER(float, MaxRayDistance)
		SHADER_PARAMETER(uint32, bUseSceneDepth)
		SHADER_PARAMETER_RDG_BUFFER_SRV(StructuredBuffer<FGaussianVolumePackedPrimitive>, GaussianBuffer)
		SHADER_PARAMETER_STRUCT_INCLUDE(FSceneTextureShaderParameters, SceneTextures)
	END_SHADER_PARAMETER_STRUCT()

public:
	static bool ShouldCompilePermutation(const FGlobalShaderPermutationParameters& Parameters)
	{
		return IsFeatureLevelSupported(Parameters.Platform, ERHIFeatureLevel::SM6);
	}
};

/** Upsamples accumulated optical depth and composites the uniform medium once. */
class FGaussianVolumePoolFreeCompositeCS : public FGlobalShader
{
	DECLARE_GLOBAL_SHADER(FGaussianVolumePoolFreeCompositeCS);
	SHADER_USE_PARAMETER_STRUCT(FGaussianVolumePoolFreeCompositeCS, FGlobalShader);

	BEGIN_SHADER_PARAMETER_STRUCT(FParameters, )
		SHADER_PARAMETER(FVector4f, Resolution)
		SHADER_PARAMETER(FVector4f, ViewRectMin)
		SHADER_PARAMETER(FVector4f, LightColor)
		SHADER_PARAMETER(FVector4f, AmbientColor)
		SHADER_PARAMETER(FVector4f, UniformAppearance)
		SHADER_PARAMETER(float, PowderFactor)
		SHADER_PARAMETER(uint32, bPoolFreeInPlaceComposite)
		SHADER_PARAMETER_RDG_TEXTURE_SRV(Texture2D<float>, PoolFreeTauTexture)
		SHADER_PARAMETER_SAMPLER(SamplerState, PoolFreeTauSampler)
		SHADER_PARAMETER_RDG_TEXTURE_SRV(Texture2D, SceneColorTexture)
		SHADER_PARAMETER_RDG_TEXTURE_UAV(RWTexture2D<float4>, OutputTexture)
	END_SHADER_PARAMETER_STRUCT()

public:
	static bool ShouldCompilePermutation(const FGlobalShaderPermutationParameters& Parameters)
	{
		return IsFeatureLevelSupported(Parameters.Platform, ERHIFeatureLevel::SM6);
	}

	static void ModifyCompilationEnvironment(
		const FGlobalShaderPermutationParameters& Parameters,
		FShaderCompilerEnvironment& OutEnvironment)
	{
		FGlobalShader::ModifyCompilationEnvironment(Parameters, OutEnvironment);
		OutEnvironment.SetDefine(TEXT("THREADGROUP_SIZE_X"), 8);
		OutEnvironment.SetDefine(TEXT("THREADGROUP_SIZE_Y"), 8);
	}
};

BEGIN_SHADER_PARAMETER_STRUCT(FGaussianVolumePoolFreePassParameters, )
	SHADER_PARAMETER_STRUCT_INCLUDE(FGaussianVolumePoolFreeVS::FParameters, VS)
	SHADER_PARAMETER_STRUCT_INCLUDE(FGaussianVolumePoolFreePS::FParameters, PS)
	RENDER_TARGET_BINDING_SLOTS()
END_SHADER_PARAMETER_STRUCT()

/** Counts conservative Gaussian support overlaps per screen tile. */
class FGaussianVolumeCountTileCandidatesCS : public FGlobalShader
{
	DECLARE_GLOBAL_SHADER(FGaussianVolumeCountTileCandidatesCS);
	SHADER_USE_PARAMETER_STRUCT(FGaussianVolumeCountTileCandidatesCS, FGlobalShader);

	BEGIN_SHADER_PARAMETER_STRUCT(FParameters, )
		SHADER_PARAMETER(FVector4f, Resolution)
		SHADER_PARAMETER(FVector4f, CameraPos)
		SHADER_PARAMETER(FVector4f, CameraForward)
		SHADER_PARAMETER(FVector4f, CameraRight)
		SHADER_PARAMETER(FVector4f, CameraUp)
		SHADER_PARAMETER(FVector4f, CameraDirs)
		SHADER_PARAMETER(uint32, bUseTightPBF)
		SHADER_PARAMETER(uint32, NumGaussians)
		SHADER_PARAMETER(uint32, NumInstances)
		SHADER_PARAMETER(uint32, bSingleInstance)
		SHADER_PARAMETER(uint32, SinglePrimitiveOffset)
		SHADER_PARAMETER(uint32, SinglePrimitiveCount)
		SHADER_PARAMETER(FVector4f, SingleInstanceOffset)
		SHADER_PARAMETER(uint32, NumTilesX)
		SHADER_PARAMETER(uint32, NumTilesY)
		SHADER_PARAMETER(uint32, TileSize)
		SHADER_PARAMETER_RDG_BUFFER_SRV(StructuredBuffer<FGaussianVolumePackedPrimitive>, GaussianBuffer)
		SHADER_PARAMETER_RDG_BUFFER_SRV(StructuredBuffer<FGaussianVolumePackedInstance>, InstanceBuffer)
		SHADER_PARAMETER_RDG_BUFFER_UAV(RWStructuredBuffer<uint>, OutTileCandidateCounts)
	END_SHADER_PARAMETER_STRUCT()

public:
	static bool ShouldCompilePermutation(const FGlobalShaderPermutationParameters& Parameters)
	{
		return IsFeatureLevelSupported(Parameters.Platform, ERHIFeatureLevel::SM6);
	}

	static void ModifyCompilationEnvironment(const FGlobalShaderPermutationParameters& Parameters, FShaderCompilerEnvironment& OutEnvironment)
	{
		FGlobalShader::ModifyCompilationEnvironment(Parameters, OutEnvironment);
		OutEnvironment.SetDefine(TEXT("THREADGROUP_SIZE_X"), 64);
	}
};

/** Serial GPU prefix scan; tile count is small (about 2K at 1080p/32px). */
class FGaussianVolumePrefixTileCandidatesCS : public FGlobalShader
{
	DECLARE_GLOBAL_SHADER(FGaussianVolumePrefixTileCandidatesCS);
	SHADER_USE_PARAMETER_STRUCT(FGaussianVolumePrefixTileCandidatesCS, FGlobalShader);

	BEGIN_SHADER_PARAMETER_STRUCT(FParameters, )
		SHADER_PARAMETER(uint32, NumTiles)
		SHADER_PARAMETER(uint32, CandidatePoolCapacity)
		SHADER_PARAMETER_RDG_BUFFER_SRV(StructuredBuffer<uint>, TileCandidateRawCounts)
		SHADER_PARAMETER_RDG_BUFFER_UAV(RWStructuredBuffer<uint>, OutTileCandidateCounts)
		SHADER_PARAMETER_RDG_BUFFER_UAV(RWStructuredBuffer<uint>, OutTileCandidateOffsets)
		SHADER_PARAMETER_RDG_BUFFER_UAV(RWStructuredBuffer<uint>, OutCandidateStats)
	END_SHADER_PARAMETER_STRUCT()

public:
	static bool ShouldCompilePermutation(const FGlobalShaderPermutationParameters& Parameters)
	{
		return IsFeatureLevelSupported(Parameters.Platform, ERHIFeatureLevel::SM6);
	}
};

/** Reprojects supports and scatters IDs into the compact global candidate pool. */
class FGaussianVolumeScatterTileCandidatesCS : public FGlobalShader
{
	DECLARE_GLOBAL_SHADER(FGaussianVolumeScatterTileCandidatesCS);
	SHADER_USE_PARAMETER_STRUCT(FGaussianVolumeScatterTileCandidatesCS, FGlobalShader);

	BEGIN_SHADER_PARAMETER_STRUCT(FParameters, )
		SHADER_PARAMETER(FVector4f, Resolution)
		SHADER_PARAMETER(FVector4f, CameraPos)
		SHADER_PARAMETER(FVector4f, CameraForward)
		SHADER_PARAMETER(FVector4f, CameraRight)
		SHADER_PARAMETER(FVector4f, CameraUp)
		SHADER_PARAMETER(FVector4f, CameraDirs)
		SHADER_PARAMETER(uint32, bUseTightPBF)
		SHADER_PARAMETER(uint32, NumGaussians)
		SHADER_PARAMETER(uint32, NumInstances)
		SHADER_PARAMETER(uint32, bSingleInstance)
		SHADER_PARAMETER(uint32, SinglePrimitiveOffset)
		SHADER_PARAMETER(uint32, SinglePrimitiveCount)
		SHADER_PARAMETER(FVector4f, SingleInstanceOffset)
		SHADER_PARAMETER(uint32, NumTilesX)
		SHADER_PARAMETER(uint32, NumTilesY)
		SHADER_PARAMETER(uint32, TileSize)
		SHADER_PARAMETER_RDG_BUFFER_SRV(StructuredBuffer<FGaussianVolumePackedPrimitive>, GaussianBuffer)
		SHADER_PARAMETER_RDG_BUFFER_SRV(StructuredBuffer<FGaussianVolumePackedInstance>, InstanceBuffer)
		SHADER_PARAMETER_RDG_BUFFER_SRV(StructuredBuffer<uint>, TileCandidateCounts)
		SHADER_PARAMETER_RDG_BUFFER_SRV(StructuredBuffer<uint>, TileCandidateOffsets)
		SHADER_PARAMETER_RDG_BUFFER_UAV(RWStructuredBuffer<uint>, TileWriteCursors)
		SHADER_PARAMETER_RDG_BUFFER_UAV(RWStructuredBuffer<uint>, OutTileCandidateIndices)
	END_SHADER_PARAMETER_STRUCT()

public:
	static bool ShouldCompilePermutation(const FGlobalShaderPermutationParameters& Parameters)
	{
		return IsFeatureLevelSupported(Parameters.Platform, ERHIFeatureLevel::SM6);
	}

	static void ModifyCompilationEnvironment(const FGlobalShaderPermutationParameters& Parameters, FShaderCompilerEnvironment& OutEnvironment)
	{
		FGlobalShader::ModifyCompilationEnvironment(Parameters, OutEnvironment);
		OutEnvironment.SetDefine(TEXT("THREADGROUP_SIZE_X"), 64);
	}
};

/**
 * SPEC §10 cross-primitive light transmittance prepass.
 * One thread per primitive: marches from the primitive center toward the light through ALL
 * primitives, accumulates optical depth, and writes exp(-tau) to OutLightTau[i]. O(N^2) compute,
 * O(N) storage. The main ray-trace CS then does an O(1) lookup, so one arc can shadow another
 * and lighting responds to the light DIRECTION (the old self-only shadow could not).
 * Shader file: Shaders/Private/GaussianVolume.usf, entry point LightTauCS.
 */
class FGaussianVolumeLightTauCS : public FGlobalShader
{
	DECLARE_GLOBAL_SHADER(FGaussianVolumeLightTauCS);
	SHADER_USE_PARAMETER_STRUCT(FGaussianVolumeLightTauCS, FGlobalShader);

	BEGIN_SHADER_PARAMETER_STRUCT(FParameters, )
		SHADER_PARAMETER(FVector4f, LightDir)
		SHADER_PARAMETER(float, MaxRayDistance)
		SHADER_PARAMETER(uint32, NumGaussians)
		SHADER_PARAMETER_RDG_BUFFER_SRV(StructuredBuffer<FGaussianVolumePackedPrimitive>, GaussianBuffer)
		SHADER_PARAMETER_RDG_BUFFER_UAV(RWStructuredBuffer<float>, OutLightTau)
	END_SHADER_PARAMETER_STRUCT()

public:
	static bool ShouldCompilePermutation(const FGlobalShaderPermutationParameters& Parameters)
	{
		return IsFeatureLevelSupported(Parameters.Platform, ERHIFeatureLevel::SM6);
	}

	static void ModifyCompilationEnvironment(const FGlobalShaderPermutationParameters& Parameters, FShaderCompilerEnvironment& OutEnvironment)
	{
		FGlobalShader::ModifyCompilationEnvironment(Parameters, OutEnvironment);
		OutEnvironment.SetDefine(TEXT("THREADGROUP_SIZE_X"), 64);
	}
};
