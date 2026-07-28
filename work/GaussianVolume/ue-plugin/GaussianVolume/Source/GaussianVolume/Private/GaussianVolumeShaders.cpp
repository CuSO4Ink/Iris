// Copyright 2026 Violina. All Rights Reserved.

#include "GaussianVolumeShaders.h"
#include "RenderCore.h"

IMPLEMENT_GLOBAL_SHADER(FNanoVdbRayMarchCS, "/GaussianVolume/Private/NanoVdbVolume.usf", "MainCS", SF_Compute);
IMPLEMENT_GLOBAL_SHADER(FGaussianVolumeRayTraceCS, "/GaussianVolume/Private/GaussianVolume.usf", "MainCS", SF_Compute);
IMPLEMENT_GLOBAL_SHADER(FGaussianVolumeLodBlendCS, "/GaussianVolume/Private/GaussianVolume.usf", "BlendLodsCS", SF_Compute);
IMPLEMENT_GLOBAL_SHADER(FGaussianVolumePoolFreeVS, "/GaussianVolume/Private/GaussianVolume.usf", "PoolFreeVS", SF_Vertex);
IMPLEMENT_GLOBAL_SHADER(FGaussianVolumePoolFreePS, "/GaussianVolume/Private/GaussianVolume.usf", "PoolFreePS", SF_Pixel);
IMPLEMENT_GLOBAL_SHADER(FGaussianVolumePoolFreeCompositeCS, "/GaussianVolume/Private/GaussianVolume.usf", "PoolFreeCompositeCS", SF_Compute);
IMPLEMENT_GLOBAL_SHADER(FGaussianVolumeCountTileCandidatesCS, "/GaussianVolume/Private/GaussianVolume.usf", "CountTileCandidatesCS", SF_Compute);
IMPLEMENT_GLOBAL_SHADER(FGaussianVolumePrefixTileCandidatesCS, "/GaussianVolume/Private/GaussianVolume.usf", "PrefixTileCandidatesCS", SF_Compute);
IMPLEMENT_GLOBAL_SHADER(FGaussianVolumeScatterTileCandidatesCS, "/GaussianVolume/Private/GaussianVolume.usf", "ScatterTileCandidatesCS", SF_Compute);
IMPLEMENT_GLOBAL_SHADER(FGaussianVolumeLightTauCS, "/GaussianVolume/Private/GaussianVolume.usf", "LightTauCS", SF_Compute);
