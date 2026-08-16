#include "GaussianSplattingShaders.h"

#include "DataDrivenShaderPlatformInfo.h"

namespace
{
	bool Supports7DRGS(const FGlobalShaderPermutationParameters& Parameters)
	{
		return IsFeatureLevelSupported(Parameters.Platform, ERHIFeatureLevel::SM6);
	}
}

bool FGS7DSlicingCS::ShouldCompilePermutation(const FGlobalShaderPermutationParameters& Parameters)
{
	return Supports7DRGS(Parameters);
}

bool FGSPreprocessCS::ShouldCompilePermutation(const FGlobalShaderPermutationParameters& Parameters)
{
	return Supports7DRGS(Parameters);
}

bool FGSBuildDrawArgsCS::ShouldCompilePermutation(const FGlobalShaderPermutationParameters& Parameters)
{
	return Supports7DRGS(Parameters);
}

bool FGSHWQuadVS::ShouldCompilePermutation(const FGlobalShaderPermutationParameters& Parameters)
{
	return Supports7DRGS(Parameters);
}

bool FGSHWQuadPS::ShouldCompilePermutation(const FGlobalShaderPermutationParameters& Parameters)
{
	return Supports7DRGS(Parameters);
}

bool FGSCompositeVS::ShouldCompilePermutation(const FGlobalShaderPermutationParameters& Parameters)
{
	return Supports7DRGS(Parameters);
}

bool FGSCompositePS::ShouldCompilePermutation(const FGlobalShaderPermutationParameters& Parameters)
{
	return Supports7DRGS(Parameters);
}

IMPLEMENT_GLOBAL_SHADER(
	FGS7DSlicingCS, "/GaussianSplatting/GaussianSplattingSlicing.usf", "MainCS", SF_Compute);
IMPLEMENT_GLOBAL_SHADER(
	FGSPreprocessCS, "/GaussianSplatting/GaussianSplattingPreprocess.usf", "MainCS", SF_Compute);
IMPLEMENT_GLOBAL_SHADER(
	FGSBuildDrawArgsCS, "/GaussianSplatting/GaussianSplattingSort.usf",
	"BuildDrawArgsFromCountCS", SF_Compute);
IMPLEMENT_GLOBAL_SHADER(
	FGSHWQuadVS, "/GaussianSplatting/GaussianSplattingHWRaster.usf", "MainVS", SF_Vertex);
IMPLEMENT_GLOBAL_SHADER(
	FGSHWQuadPS, "/GaussianSplatting/GaussianSplattingHWRaster.usf", "MainPS", SF_Pixel);
IMPLEMENT_GLOBAL_SHADER(
	FGSCompositeVS, "/GaussianSplatting/GaussianSplattingComposite.usf", "MainVS", SF_Vertex);
IMPLEMENT_GLOBAL_SHADER(
	FGSCompositePS, "/GaussianSplatting/GaussianSplattingComposite.usf", "MainPS", SF_Pixel);
