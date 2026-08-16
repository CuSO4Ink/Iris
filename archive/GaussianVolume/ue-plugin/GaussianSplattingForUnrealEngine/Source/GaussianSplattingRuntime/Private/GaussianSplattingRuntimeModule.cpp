#include "GaussianSplattingRuntimeModule.h"

#include "Interfaces/IPluginManager.h"
#include "ShaderCore.h"

DEFINE_LOG_CATEGORY_STATIC(LogGaussianSplattingRuntime, Log, All);

void FGaussianSplattingRuntimeModule::StartupModule()
{
	const TSharedPtr<IPlugin> Plugin =
		IPluginManager::Get().FindPlugin(TEXT("GaussianSplattingForUnrealEngine"));
	if (!Plugin.IsValid())
	{
		UE_LOG(LogGaussianSplattingRuntime, Error, TEXT("Plugin descriptor was not found"));
		return;
	}

	const FString ShaderDirectory = FPaths::Combine(Plugin->GetBaseDir(), TEXT("Shaders"));
	AddShaderSourceDirectoryMapping(TEXT("/GaussianSplatting"), ShaderDirectory);
	UE_LOG(LogGaussianSplattingRuntime, Display,
		TEXT("7DRGS reconstruction loaded; shaders=%s"), *ShaderDirectory);
}

void FGaussianSplattingRuntimeModule::ShutdownModule()
{
}

IMPLEMENT_MODULE(FGaussianSplattingRuntimeModule, GaussianSplattingRuntime)
