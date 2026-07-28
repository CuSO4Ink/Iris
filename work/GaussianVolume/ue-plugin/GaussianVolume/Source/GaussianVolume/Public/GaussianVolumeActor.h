// Copyright 2026 Violina. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Engine/EngineTypes.h"
#include "GaussianVolumeActor.generated.h"

class UGaussianVolumeComponent;
class USplineComponent;

/**
 * Convenience Actor that comes with a UGaussianVolumeComponent already
 * attached, so it can be dragged straight into a level or placed from the
 * Place Actors panel / Class Viewer without manually adding the component.
 */
UCLASS(ClassGroup=(Rendering), meta=(DisplayName="Gaussian Volume"))
class GAUSSIANVOLUME_API AGaussianVolumeActor : public AActor
{
	GENERATED_BODY()

public:
	AGaussianVolumeActor();
	virtual void OnConstruction(const FTransform& Transform) override;

	/** The Gaussian volume rendering component. Edit its Gaussians array in the Details panel. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "GaussianVolume")
	TObjectPtr<UGaussianVolumeComponent> GaussianVolumeComponent;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "GaussianVolume")
	TObjectPtr<USplineComponent> SplineComponent;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "GaussianVolume|Authoring")
	bool bGenerateFromSpline = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "GaussianVolume|Authoring", meta = (ClampMin = "1", ClampMax = "128"))
	int32 PrimitiveCount = 64;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "GaussianVolume|Authoring", meta = (ClampMin = "0.01"))
	float Thickness = 100.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "GaussianVolume|Authoring", meta = (ClampMin = "0.0"))
	float Density = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "GaussianVolume|Authoring", meta = (ClampMin = "0.0"))
	float Emission = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "GaussianVolume|Authoring")
	float TwistDegrees = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "GaussianVolume|Authoring", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float Breakup = 0.15f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "GaussianVolume|Authoring")
	int32 Seed = 7;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "GaussianVolume|Authoring")
	FLinearColor FieldColor = FLinearColor(0.1f, 0.8f, 1.0f, 1.0f);

	UFUNCTION(BlueprintCallable, CallInEditor, Category = "GaussianVolume|Authoring")
	void RebuildFromSpline();

	/** Portable JSON exported from a volumetric-primitives PLY file. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "GaussianVolume|Import", meta = (FilePathFilter = "json"))
	FFilePath GaussianJsonFile;

	/** Replace the current primitive array with GaussianJsonFile. */
	UFUNCTION(BlueprintCallable, CallInEditor, Category = "GaussianVolume|Import")
	bool ImportGaussianJson();

	/** Source OpenVDB. The editor converter selects a scalar float grid named density. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "GaussianVolume|VDB", meta = (FilePathFilter = "vdb"))
	FFilePath OpenVdbFile;

	/** Portable JSON written by ConvertOpenVdbToGaussianJson. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "GaussianVolume|VDB", meta = (FilePathFilter = "json"))
	FFilePath OpenVdbOutputJsonFile;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "GaussianVolume|VDB", meta = (ClampMin = "128", ClampMax = "65536"))
	int32 OpenVdbTargetPrimitiveCount = 2048;

	/** Normalize the longest active VDB dimension to this size in UE centimeters. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "GaussianVolume|VDB", meta = (ClampMin = "1.0"))
	float OpenVdbTargetWorldSizeCm = 1000.0f;

	/** Peak extinction coefficient after density normalization. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "GaussianVolume|VDB", meta = (ClampMin = "0.000001"))
	float OpenVdbPeakSigmaT = 0.04f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "GaussianVolume|VDB", meta = (ClampMin = "0.0"))
	float OpenVdbMinimumDensity = 0.001f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "GaussianVolume|VDB")
	FLinearColor OpenVdbAlbedo = FLinearColor(0.8f, 0.82f, 0.85f, 1.0f);

	/** One-shot automation trigger. Resets to false after conversion. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "GaussianVolume|VDB")
	bool bAutoConvertOpenVdb = false;

	/** Spatially aggregate a density VDB, write portable JSON, and import it. Editor only. */
	UFUNCTION(BlueprintCallable, CallInEditor, Category = "GaussianVolume|VDB")
	bool ConvertOpenVdbToGaussianJson();

#if WITH_EDITOR
	virtual void PostEditMove(bool bFinished) override;
#endif

private:
	/** Generate Count primitives along one spline and APPEND them into Out.
	 *  ArcIndex offsets the RNG so each arc gets a distinct breakup pattern. */
	void AppendArcFromSpline(const USplineComponent& Spline, int32 ArcIndex, TArray<struct FGaussianVolumePrimitive>& Out) const;

	UPROPERTY(VisibleAnywhere, Category = "GaussianVolume")
	TObjectPtr<USceneComponent> SceneRoot;
};
