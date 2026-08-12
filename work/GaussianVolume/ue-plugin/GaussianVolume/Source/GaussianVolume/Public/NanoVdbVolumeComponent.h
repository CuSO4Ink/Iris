// Copyright 2026 Violina. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Engine/EngineTypes.h"
#include "NanoVdbVolumeComponent.generated.h"

class UGaussianVolumeWorldSubsystem;

/** Loads one uncompressed NanoVDB float/Fp8/FpN grid for the direct UE baseline. */
UCLASS(ClassGroup=(Rendering), meta=(BlueprintSpawnableComponent))
class GAUSSIANVOLUME_API UNanoVdbVolumeComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UNanoVdbVolumeComponent();

	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	virtual void OnRegister() override;
	virtual void OnUnregister() override;
	virtual void TickComponent(
		float DeltaTime,
		ELevelTick TickType,
		FActorComponentTickFunction* ThisTickFunction) override;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "NanoVDB", meta = (FilePathFilter = "nvdb"))
	FFilePath NanoVdbFile;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "NanoVDB|Rendering", meta = (ClampMin = "0.0"))
	float DensityScale = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "NanoVDB|Rendering")
	FLinearColor Albedo = FLinearColor(0.9f, 0.92f, 0.95f, 1.0f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "NanoVDB|Rendering", meta = (ClampMin = "0.1", ClampMax = "4.0"))
	float StepSizeVoxels = 0.75f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "NanoVDB|Rendering", meta = (ClampMin = "64", ClampMax = "4096"))
	int32 MaxSteps = 1024;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "NanoVDB|Rendering")
	bool bUseSceneDepth = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "NanoVDB|Rendering")
	bool bEnableRendering = true;

	UFUNCTION(BlueprintCallable, CallInEditor, Category = "NanoVDB")
	bool ReloadNanoVdb();

#if WITH_EDITOR
	virtual void PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent) override;
#endif

private:
	UGaussianVolumeWorldSubsystem* GetGaussianSubsystem() const;
	bool ShouldRender() const;
	void PushToRenderThread();

	TArray<uint32> GridWords;
	FTransform LastOwnerTransform;
	bool bLastShouldRender = true;
};
