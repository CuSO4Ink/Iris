// Copyright 2026 Violina. All Rights Reserved.

#include "NanoVdbVolumeComponent.h"
#include "GaussianVolumeSubsystem.h"
#include "Engine/World.h"
#include "Misc/Paths.h"

#if GAUSSIANVOLUME_WITH_NANOVDB
THIRD_PARTY_INCLUDES_START
UE_PUSH_MACRO("check")
#undef check
#if defined(_MSC_VER)
#pragma warning(push)
#pragma warning(disable : 4146)
#endif
#include <nanovdb/io/IO.h>
#if defined(_MSC_VER)
#pragma warning(pop)
#endif
UE_POP_MACRO("check")
THIRD_PARTY_INCLUDES_END
#endif

UNanoVdbVolumeComponent::UNanoVdbVolumeComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	bTickInEditor = true;
}

UGaussianVolumeWorldSubsystem* UNanoVdbVolumeComponent::GetGaussianSubsystem() const
{
	const UWorld* World = GetWorld();
	return World ? World->GetSubsystem<UGaussianVolumeWorldSubsystem>() : nullptr;
}

bool UNanoVdbVolumeComponent::ShouldRender() const
{
	const AActor* Owner = GetOwner();
	if (!bEnableRendering || GridWords.IsEmpty() || (Owner && Owner->IsHidden()))
	{
		return false;
	}
	if (Owner && Owner->GetRootComponent() && !Owner->GetRootComponent()->IsVisible())
	{
		return false;
	}
#if WITH_EDITOR
	return !Owner || !Owner->IsHiddenEd();
#else
	return true;
#endif
}

bool UNanoVdbVolumeComponent::ReloadNanoVdb()
{
#if GAUSSIANVOLUME_WITH_NANOVDB
	const FString Path = FPaths::ConvertRelativePathToFull(NanoVdbFile.FilePath);
	if (Path.IsEmpty() || !FPaths::FileExists(Path))
	{
		UE_LOG(LogTemp, Error, TEXT("NanoVDB baseline: file not found: %s"), *Path);
		GridWords.Reset();
		PushToRenderThread();
		return false;
	}

	try
	{
		nanovdb::GridHandle<nanovdb::HostBuffer> Handle =
			nanovdb::io::readGrid(TCHAR_TO_UTF8(*Path));
		if (!Handle || Handle.gridCount() != 1 || !Handle.gridData(0))
		{
			UE_LOG(LogTemp, Error, TEXT("NanoVDB baseline: expected one grid in %s"), *Path);
			return false;
		}
		const nanovdb::GridType GridType = Handle.gridType(0);
		if (GridType != nanovdb::GridType::Float
			&& GridType != nanovdb::GridType::Fp8
			&& GridType != nanovdb::GridType::FpN)
		{
			UE_LOG(LogTemp, Error, TEXT("NanoVDB baseline: unsupported grid type %d"), static_cast<int32>(GridType));
			return false;
		}

		const uint64 GridSize = Handle.gridSize(0);
		const int32 WordCount = FMath::DivideAndRoundUp(
			static_cast<int64>(GridSize), static_cast<int64>(sizeof(uint32)));
		GridWords.SetNumZeroed(WordCount);
		FMemory::Memcpy(GridWords.GetData(), Handle.gridData(0), GridSize);
		UE_LOG(LogTemp, Display,
			TEXT("NanoVDB baseline: loaded %s type=%d grid_bytes=%llu upload_bytes=%llu"),
			*Path,
			static_cast<int32>(GridType),
			GridSize,
			static_cast<uint64>(GridWords.Num()) * sizeof(uint32));
		PushToRenderThread();
		return true;
	}
	catch (const std::exception& Error)
	{
		UE_LOG(LogTemp, Error, TEXT("NanoVDB baseline: %s"), UTF8_TO_TCHAR(Error.what()));
		GridWords.Reset();
		PushToRenderThread();
		return false;
	}
#else
	return false;
#endif
}

void UNanoVdbVolumeComponent::PushToRenderThread()
{
	UGaussianVolumeWorldSubsystem* Subsystem = GetGaussianSubsystem();
	if (!Subsystem)
	{
		return;
	}
	bLastShouldRender = ShouldRender();
	if (!bLastShouldRender)
	{
		Subsystem->UnregisterNanoComponent(this);
		return;
	}
	Subsystem->RegisterNanoComponent(this);
	const FTransform OwnerTransform = GetOwner()
		? GetOwner()->GetActorTransform()
		: FTransform::Identity;
	Subsystem->UpdateNanoComponentData(
		this,
		TArray<uint32>(GridWords),
		FMatrix44f(OwnerTransform.ToMatrixWithScale().Inverse()),
		Albedo,
		FMath::Max(DensityScale, 0.0f),
		FMath::Clamp(StepSizeVoxels, 0.1f, 4.0f),
		static_cast<uint32>(FMath::Clamp(MaxSteps, 64, 4096)),
		bUseSceneDepth);
}

void UNanoVdbVolumeComponent::BeginPlay()
{
	Super::BeginPlay();
	if (GridWords.IsEmpty())
	{
		ReloadNanoVdb();
	}
	PushToRenderThread();
	LastOwnerTransform = GetOwner() ? GetOwner()->GetActorTransform() : FTransform::Identity;
}

void UNanoVdbVolumeComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (UGaussianVolumeWorldSubsystem* Subsystem = GetGaussianSubsystem())
	{
		Subsystem->UnregisterNanoComponent(this);
	}
	Super::EndPlay(EndPlayReason);
}

void UNanoVdbVolumeComponent::OnRegister()
{
	Super::OnRegister();
	if (GridWords.IsEmpty() && !NanoVdbFile.FilePath.IsEmpty())
	{
		ReloadNanoVdb();
	}
	PushToRenderThread();
	LastOwnerTransform = GetOwner() ? GetOwner()->GetActorTransform() : FTransform::Identity;
}

void UNanoVdbVolumeComponent::OnUnregister()
{
	if (UGaussianVolumeWorldSubsystem* Subsystem = GetGaussianSubsystem())
	{
		Subsystem->UnregisterNanoComponent(this);
	}
	Super::OnUnregister();
}

void UNanoVdbVolumeComponent::TickComponent(
	float DeltaTime,
	ELevelTick TickType,
	FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	const bool bShouldRender = ShouldRender();
	const FTransform OwnerTransform = GetOwner()
		? GetOwner()->GetActorTransform()
		: FTransform::Identity;
	if (bShouldRender != bLastShouldRender || !OwnerTransform.Equals(LastOwnerTransform))
	{
		LastOwnerTransform = OwnerTransform;
		PushToRenderThread();
	}
}

#if WITH_EDITOR
void UNanoVdbVolumeComponent::PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent)
{
	Super::PostEditChangeProperty(PropertyChangedEvent);
	const FName PropertyName = PropertyChangedEvent.GetPropertyName();
	if (PropertyName == GET_MEMBER_NAME_CHECKED(UNanoVdbVolumeComponent, NanoVdbFile))
	{
		ReloadNanoVdb();
	}
	else
	{
		PushToRenderThread();
	}
}
#endif
