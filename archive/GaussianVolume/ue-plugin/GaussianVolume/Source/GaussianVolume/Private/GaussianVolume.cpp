// Copyright 2026 Violina. All Rights Reserved.

#include "GaussianVolume.h"
#include "Containers/Ticker.h"
#include "Engine/Engine.h"
#include "HAL/IConsoleManager.h"
#include "Modules/ModuleManager.h"
#include "ShaderCore.h"
#include "Interfaces/IPluginManager.h"

DEFINE_LOG_CATEGORY_STATIC(LogGaussianVolume, Log, All);

#define LOCTEXT_NAMESPACE "FGaussianVolumeModule"

namespace
{
	int32 GMemoryDumpFramesRemaining = -1;
	FTSTicker::FDelegateHandle GMemoryDumpTickerHandle;

	FAutoConsoleCommand GScheduleMemoryDumpCommand(
		TEXT("GaussianVolume.ScheduleMemoryDump"),
		TEXT("Schedule RHI and SVT memory logs after N game ticks (default 300)."),
		FConsoleCommandWithArgsDelegate::CreateLambda([](const TArray<FString>& Args)
		{
			GMemoryDumpFramesRemaining = Args.IsEmpty()
				? 300
				: FMath::Max(FCString::Atoi(*Args[0]), 1);
			UE_LOG(LogGaussianVolume, Log,
				TEXT("Scheduled memory dump in %d game ticks"), GMemoryDumpFramesRemaining);
		}));

	bool TickScheduledMemoryDump(float)
	{
		if (GMemoryDumpFramesRemaining >= 0 && --GMemoryDumpFramesRemaining <= 0)
		{
			GMemoryDumpFramesRemaining = -1;
			UE_LOG(LogGaussianVolume, Display, TEXT("GAUSSIAN_VOLUME_MEMORY_DUMP_BEGIN"));
			if (GEngine)
			{
				GEngine->Exec(nullptr, TEXT("rhi.DumpMemory"));
				GEngine->Exec(nullptr,
					TEXT("rhi.DumpResourceMemory all Name=GaussianVolume Transient=all"));
				GEngine->Exec(nullptr,
					TEXT("rhi.DumpResourceMemory all Name=NanoVDB Transient=all"));
				GEngine->Exec(nullptr, TEXT("stat dumpnonframe SparseVolumeTextureMemory"));
			}
			UE_LOG(LogGaussianVolume, Display, TEXT("GAUSSIAN_VOLUME_MEMORY_DUMP_END"));
		}

		return true;
	}
}

void FGaussianVolumeModule::StartupModule()
{
	// Register shader source directory mapping:
	//   "/GaussianVolume" → <Plugin>/Shaders
	const TSharedPtr<IPlugin> Plugin = IPluginManager::Get().FindPlugin(TEXT("GaussianVolume"));
	if (Plugin.IsValid())
	{
		const FString ShaderDirectory = FPaths::Combine(Plugin->GetBaseDir(), TEXT("Shaders"));
		AddShaderSourceDirectoryMapping(TEXT("/GaussianVolume"), ShaderDirectory);
		UE_LOG(LogGaussianVolume, Log, TEXT("GaussianVolume module started. Shader dir: %s"), *ShaderDirectory);
	}
	else
	{
		UE_LOG(LogGaussianVolume, Warning, TEXT("GaussianVolume plugin not found in IPluginManager — shaders will not be registered!"));
	}
	GMemoryDumpTickerHandle = FTSTicker::GetCoreTicker().AddTicker(
		FTickerDelegate::CreateStatic(&TickScheduledMemoryDump));
}

void FGaussianVolumeModule::ShutdownModule()
{
	if (GMemoryDumpTickerHandle.IsValid())
	{
		FTSTicker::GetCoreTicker().RemoveTicker(GMemoryDumpTickerHandle);
		GMemoryDumpTickerHandle.Reset();
	}
	UE_LOG(LogGaussianVolume, Log, TEXT("GaussianVolume module shutting down"));
}

#undef LOCTEXT_NAMESPACE

IMPLEMENT_MODULE(FGaussianVolumeModule, GaussianVolume)
