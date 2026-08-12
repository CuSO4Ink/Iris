#pragma once

#include "Components/SceneComponent.h"
#include "Engine/EngineTypes.h"
#include "GaussianSplatting7DComponent.generated.h"

class ADirectionalLight;
class ASkyLight;

UCLASS(ClassGroup=(Rendering), meta=(BlueprintSpawnableComponent))
class GAUSSIANSPLATTINGRUNTIME_API UGaussianSplatting7DComponent final : public USceneComponent
{
	GENERATED_BODY()

public:
	UGaussianSplatting7DComponent();

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="7DRGS|Source")
	FFilePath PlyFile;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="7DRGS|Source")
	bool bUseSyntheticCloudWhenPlyMissing = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="7DRGS|Source", meta=(ClampMin="1", ClampMax="1000000"))
	int32 SyntheticPointCount = 8192;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="7DRGS|Source", meta=(ClampMin="1.0"))
	float SyntheticCloudRadiusUU = 220.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="7DRGS|Playback")
	float CurrentTime = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="7DRGS|Relight")
	TObjectPtr<ADirectionalLight> DirectionalLight;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="7DRGS|Relight")
	bool bUseManualLightDirection = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="7DRGS|Relight")
	FVector ManualLightDirection = FVector(0.0, 0.0, 1.0);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="7DRGS|Relight")
	FLinearColor ManualLightColor = FLinearColor(8.0f, 8.0f, 8.0f, 1.0f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="7DRGS|Relight", meta=(ClampMin="0.0"))
	float RelightIntensityScale = 0.0795774715f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="7DRGS|Relight", meta=(HideAlphaChannel))
	FLinearColor RelightColorTint = FLinearColor::White;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="7DRGS|Relight")
	TObjectPtr<ASkyLight> SkyLight;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="7DRGS|Relight", meta=(ClampMin="0.0"))
	float AmbientLightIntensityScale = 0.1f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="7DRGS|Relight")
	bool bDualSH = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="7DRGS|Relight", meta=(ClampMin="0", ClampMax="3"))
	int32 TViewSHDegree = 3;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="7DRGS|Appearance", meta=(ClampMin="0.0"))
	float OpacityMultiplier = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="7DRGS|Appearance", meta=(ClampMin="0.01"))
	float OpacityPower = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="7DRGS|Phase", meta=(ClampMin="0", ClampMax="2"))
	int32 PhaseMode = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="7DRGS|Phase", meta=(ClampMin="-0.99", ClampMax="0.99"))
	float PhaseG = 0.6f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="7DRGS|Phase", meta=(ClampMin="-0.99", ClampMax="0.99"))
	float PhaseG2 = -0.2f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="7DRGS|Phase", meta=(ClampMin="0.0", ClampMax="1.0"))
	float PhaseBlend = 0.2f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="7DRGS|Phase", meta=(ClampMin="0.0", ClampMax="1.0"))
	float PhaseIntensity = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="7DRGS|Depth", meta=(ClampMin="0", ClampMax="2"))
	int32 DepthTestMode = 2;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="7DRGS|Depth", meta=(ClampMin="0.01"))
	float DepthSoftFadeUU = 10.0f;

	UFUNCTION(BlueprintCallable, Category="7DRGS")
	bool LoadFromFile(const FString& InFilePath);

	UFUNCTION(BlueprintCallable, Category="7DRGS")
	bool ReloadPointCloud();

	UFUNCTION(BlueprintCallable, Category="7DRGS")
	void GenerateSyntheticCloud();

	UFUNCTION(BlueprintCallable, Category="7DRGS")
	void RefreshRenderingParameters();

	UFUNCTION(BlueprintPure, Category="7DRGS")
	int32 GetPointCount() const { return RawData.Num() / 20; }

protected:
	virtual void OnRegister() override;
	virtual void OnUnregister() override;
	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

#if WITH_EDITOR
	virtual void PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent) override;
#endif

private:
	void PushData();
	void PushParameters();

	TArray<FVector4f> RawData;
};
