#include "GaussianSplatting7DComponent.h"

#include "Components/DirectionalLightComponent.h"
#include "Components/SkyLightComponent.h"
#include "Containers/StringConv.h"
#include "Engine/DirectionalLight.h"
#include "Engine/SkyLight.h"
#include "GaussianSplatting7DSubsystem.h"
#include "GaussianSplatting7DTypes.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

DEFINE_LOG_CATEGORY_STATIC(LogGaussianSplatting7D, Log, All);

namespace
{
	constexpr float SH_C0 = 0.28209479177387814f;

	float Sigmoid(const float Value)
	{
		return Value >= 0.0f
			? 1.0f / (1.0f + FMath::Exp(-Value))
			: FMath::Exp(Value) / (1.0f + FMath::Exp(Value));
	}

	float Softplus(const float Value)
	{
		return Value > 20.0f ? Value : FMath::Loge(1.0f + FMath::Exp(Value));
	}

	struct FPlyHeader
	{
		int32 VertexCount = 0;
		int32 DataOffset = 0;
		TArray<FString> Properties;
	};

	bool ParseBinaryFloatPlyHeader(
		const TArray<uint8>& Bytes,
		FPlyHeader& OutHeader,
		FString& OutError)
	{
		static constexpr ANSICHAR EndMarker[] = "end_header";
		int32 MarkerOffset = INDEX_NONE;
		for (int32 Offset = 0; Offset + UE_ARRAY_COUNT(EndMarker) - 1 <= Bytes.Num(); ++Offset)
		{
			if (FMemory::Memcmp(Bytes.GetData() + Offset, EndMarker, UE_ARRAY_COUNT(EndMarker) - 1) == 0)
			{
				MarkerOffset = Offset;
				break;
			}
		}
		if (MarkerOffset == INDEX_NONE)
		{
			OutError = TEXT("PLY header has no end_header marker");
			return false;
		}

		int32 DataOffset = MarkerOffset + UE_ARRAY_COUNT(EndMarker) - 1;
		while (DataOffset < Bytes.Num() && (Bytes[DataOffset] == '\r' || Bytes[DataOffset] == '\n'))
		{
			++DataOffset;
		}

		const FUTF8ToTCHAR Converted(
			reinterpret_cast<const ANSICHAR*>(Bytes.GetData()),
			MarkerOffset);
		const FString HeaderText(Converted.Length(), Converted.Get());
		TArray<FString> Lines;
		HeaderText.ParseIntoArrayLines(Lines, true);

		bool bBinaryLittleEndian = false;
		bool bInVertex = false;
		for (FString Line : Lines)
		{
			Line.TrimStartAndEndInline();
			TArray<FString> Tokens;
			Line.ParseIntoArrayWS(Tokens);
			if (Tokens.Num() == 0)
			{
				continue;
			}
			if (Tokens[0] == TEXT("format") && Tokens.Num() >= 2)
			{
				bBinaryLittleEndian = Tokens[1] == TEXT("binary_little_endian");
			}
			else if (Tokens[0] == TEXT("element") && Tokens.Num() >= 3)
			{
				bInVertex = Tokens[1] == TEXT("vertex");
				if (bInVertex)
				{
					OutHeader.VertexCount = FCString::Atoi(*Tokens[2]);
				}
			}
			else if (bInVertex && Tokens[0] == TEXT("property"))
			{
				if (Tokens.Num() != 3
					|| (Tokens[1] != TEXT("float") && Tokens[1] != TEXT("float32")))
				{
					OutError = FString::Printf(
						TEXT("Only scalar float32 vertex properties are supported: %s"), *Line);
					return false;
				}
				OutHeader.Properties.Add(Tokens[2]);
			}
		}

		if (!bBinaryLittleEndian)
		{
			OutError = TEXT("Only binary_little_endian PLY is supported by the runtime reconstruction");
			return false;
		}
		if (OutHeader.VertexCount <= 0 || OutHeader.Properties.IsEmpty())
		{
			OutError = TEXT("PLY has no vertex records or properties");
			return false;
		}

		const int64 RequiredBytes =
			static_cast<int64>(DataOffset)
			+ static_cast<int64>(OutHeader.VertexCount)
			* OutHeader.Properties.Num() * sizeof(float);
		if (RequiredBytes > Bytes.Num())
		{
			OutError = FString::Printf(
				TEXT("PLY vertex payload is truncated: need %lld bytes, got %d"),
				RequiredBytes, Bytes.Num());
			return false;
		}

		OutHeader.DataOffset = DataOffset;
		return true;
	}

	bool Pack7DRGSPly(
		const TArray<uint8>& Bytes,
		const FPlyHeader& Header,
		TArray<FVector4f>& OutRawData,
		FString& OutError)
	{
		TMap<FString, int32> PropertyIndex;
		for (int32 Index = 0; Index < Header.Properties.Num(); ++Index)
		{
			PropertyIndex.Add(Header.Properties[Index], Index);
		}

		for (const TCHAR* Required : {
			TEXT("x"), TEXT("y"), TEXT("z"), TEXT("f_dc_j"), TEXT("opacity"),
			TEXT("mu_t"), TEXT("mu_d_0"), TEXT("mu_d_1"), TEXT("mu_d_2"),
			TEXT("lambda_t"), TEXT("lambda_d"), TEXT("f_dc_t")})
		{
			if (!PropertyIndex.Contains(Required))
			{
				OutError = FString::Printf(TEXT("PLY is missing required 7DRGS property '%s'"), Required);
				return false;
			}
		}
		for (int32 Index = 0; Index < 7; ++Index)
		{
			if (!PropertyIndex.Contains(FString::Printf(TEXT("chol_diag_%d"), Index)))
			{
				OutError = TEXT("PLY is missing one or more chol_diag_* properties");
				return false;
			}
		}
		for (int32 Index = 0; Index < 21; ++Index)
		{
			if (!PropertyIndex.Contains(FString::Printf(TEXT("chol_offdiag_%d"), Index)))
			{
				OutError = TEXT("PLY is missing one or more chol_offdiag_* properties");
				return false;
			}
		}

		const int32 PropertyCount = Header.Properties.Num();
		const uint8* Payload = Bytes.GetData() + Header.DataOffset;
		auto Read = [&](const int32 VertexIndex, const FString& Name, const float DefaultValue = 0.0f)
		{
			const int32* Index = PropertyIndex.Find(Name);
			if (!Index)
			{
				return DefaultValue;
			}
			float Value;
			FMemory::Memcpy(
				&Value,
				Payload + (static_cast<int64>(VertexIndex) * PropertyCount + *Index) * sizeof(float),
				sizeof(float));
			return FMath::IsFinite(Value) ? Value : DefaultValue;
		};

		OutRawData.SetNumZeroed(
			static_cast<int64>(Header.VertexCount)
			* GaussianSplatting7DRGS::InputStrideFloat4);

		for (int32 VertexIndex = 0; VertexIndex < Header.VertexCount; ++VertexIndex)
		{
			const int32 Base = VertexIndex * GaussianSplatting7DRGS::InputStrideFloat4;

			// Training/PLY uses GL metres. Runtime slicing keeps the covariance in
			// that frame, but stores the position in UE centimetres.
			const FVector3f PositionUE(
				Read(VertexIndex, TEXT("x")) * 100.0f,
				-Read(VertexIndex, TEXT("z")) * 100.0f,
				-Read(VertexIndex, TEXT("y")) * 100.0f);
			const FVector3f MuD = FVector3f(
				Read(VertexIndex, TEXT("mu_d_0")),
				Read(VertexIndex, TEXT("mu_d_1")),
				Read(VertexIndex, TEXT("mu_d_2"))).GetSafeNormal(
					UE_SMALL_NUMBER, FVector3f(0.0f, 0.0f, 1.0f));

			const float JDC = Read(VertexIndex, TEXT("f_dc_j"));
			const float JDisplay = FMath::Max(SH_C0 * JDC + 0.5f, 0.0f);
			const FVector3f Scale(
				FMath::Exp(Read(VertexIndex, TEXT("scale_0"))),
				FMath::Exp(Read(VertexIndex, TEXT("scale_1"))),
				FMath::Exp(Read(VertexIndex, TEXT("scale_2"))));
			FQuat4f Quat(
				Read(VertexIndex, TEXT("rot_0"), 1.0f),
				Read(VertexIndex, TEXT("rot_1")),
				Read(VertexIndex, TEXT("rot_2")),
				Read(VertexIndex, TEXT("rot_3")));
			Quat.Normalize();

			OutRawData[Base + 0] = FVector4f(PositionUE, Read(VertexIndex, TEXT("mu_t")));
			OutRawData[Base + 1] = FVector4f(
				MuD, Softplus(Read(VertexIndex, TEXT("lambda_t"))));
			OutRawData[Base + 2] = FVector4f(
				Softplus(Read(VertexIndex, TEXT("lambda_d"))),
				Sigmoid(Read(VertexIndex, TEXT("opacity"))),
				JDisplay, JDisplay);
			OutRawData[Base + 3] = FVector4f(JDisplay, Scale.X, Scale.Y, Scale.Z);
			OutRawData[Base + 4] = FVector4f(Quat.X, Quat.Y, Quat.Z, Quat.W);

			float Diag[7];
			float Offdiag[21];
			for (int32 Index = 0; Index < 7; ++Index)
			{
				Diag[Index] = FMath::Exp(
					Read(VertexIndex, FString::Printf(TEXT("chol_diag_%d"), Index)));
			}
			for (int32 Index = 0; Index < 21; ++Index)
			{
				Offdiag[Index] =
					Read(VertexIndex, FString::Printf(TEXT("chol_offdiag_%d"), Index));
			}
			OutRawData[Base + 5] = FVector4f(Diag[0], Diag[1], Diag[2], Diag[3]);
			OutRawData[Base + 6] = FVector4f(Diag[4], Diag[5], Diag[6], Offdiag[0]);
			for (int32 VectorIndex = 0; VectorIndex < 5; ++VectorIndex)
			{
				const int32 Start = 1 + VectorIndex * 4;
				OutRawData[Base + 7 + VectorIndex] = FVector4f(
					Offdiag[Start], Offdiag[Start + 1],
					Offdiag[Start + 2], Offdiag[Start + 3]);
			}

			float JRest[15] = {};
			float TViewRest[15] = {};
			for (int32 Index = 0; Index < 15; ++Index)
			{
				JRest[Index] = Read(
					VertexIndex, FString::Printf(TEXT("f_rest_j_%d"), Index));
				TViewRest[Index] = Read(
					VertexIndex, FString::Printf(TEXT("f_rest_t_%d"), Index));
			}
			OutRawData[Base + 12] = FVector4f(JRest[0], JRest[1], JRest[2], JRest[3]);
			OutRawData[Base + 13] = FVector4f(JRest[4], JRest[5], JRest[6], JRest[7]);
			OutRawData[Base + 14] = FVector4f(JRest[8], JRest[9], JRest[10], JRest[11]);
			OutRawData[Base + 15] = FVector4f(
				JRest[12], JRest[13], JRest[14], Read(VertexIndex, TEXT("f_dc_t")));
			OutRawData[Base + 16] = FVector4f(
				TViewRest[0], TViewRest[1], TViewRest[2], TViewRest[3]);
			OutRawData[Base + 17] = FVector4f(
				TViewRest[4], TViewRest[5], TViewRest[6], TViewRest[7]);
			OutRawData[Base + 18] = FVector4f(
				TViewRest[8], TViewRest[9], TViewRest[10], TViewRest[11]);
			OutRawData[Base + 19] = FVector4f(
				TViewRest[12], TViewRest[13], TViewRest[14], 0.0f);
		}
		return true;
	}
}

UGaussianSplatting7DComponent::UGaussianSplatting7DComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.bStartWithTickEnabled = true;
	bTickInEditor = true;
#if WITH_EDITORONLY_DATA
	bVisualizeComponent = true;
#endif
}

void UGaussianSplatting7DComponent::OnRegister()
{
	Super::OnRegister();
	RefreshRenderRegistration();
}

void UGaussianSplatting7DComponent::OnUnregister()
{
	bLastShouldRender = false;
	if (UGaussianSplatting7DWorldSubsystem* Subsystem =
		GetWorld() ? GetWorld()->GetSubsystem<UGaussianSplatting7DWorldSubsystem>() : nullptr)
	{
		Subsystem->UnregisterComponent(this);
	}
	Super::OnUnregister();
}

void UGaussianSplatting7DComponent::TickComponent(
	float DeltaTime,
	ELevelTick TickType,
	FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	const bool bShouldRender = ShouldRender();
	if (bShouldRender != bLastShouldRender)
	{
		RefreshRenderRegistration();
		return;
	}
	if (bShouldRender)
	{
		PushParameters();
	}
}

bool UGaussianSplatting7DComponent::LoadFromFile(const FString& InFilePath)
{
	FString AbsolutePath = InFilePath;
	if (FPaths::IsRelative(AbsolutePath))
	{
		AbsolutePath = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir(), AbsolutePath);
	}

	TArray<uint8> Bytes;
	if (!FFileHelper::LoadFileToArray(Bytes, *AbsolutePath))
	{
		UE_LOG(LogGaussianSplatting7D, Error, TEXT("Could not read PLY: %s"), *AbsolutePath);
		return false;
	}

	FPlyHeader Header;
	FString Error;
	if (!ParseBinaryFloatPlyHeader(Bytes, Header, Error)
		|| !Pack7DRGSPly(Bytes, Header, RawData, Error))
	{
		UE_LOG(LogGaussianSplatting7D, Error, TEXT("7DRGS PLY rejected: %s (%s)"),
			*AbsolutePath, *Error);
		RawData.Reset();
		return false;
	}

	PlyFile.FilePath = InFilePath;
	UE_LOG(LogGaussianSplatting7D, Display, TEXT("Loaded %d 7DRGS gaussians from %s"),
		GetPointCount(), *AbsolutePath);
	PushData();
	return true;
}

bool UGaussianSplatting7DComponent::ReloadPointCloud()
{
	if (!PlyFile.FilePath.IsEmpty() && LoadFromFile(PlyFile.FilePath))
	{
		return true;
	}
	if (bUseSyntheticCloudWhenPlyMissing)
	{
		GenerateSyntheticCloud();
		return true;
	}

	RawData.Reset();
	PushData();
	return false;
}

void UGaussianSplatting7DComponent::GenerateSyntheticCloud()
{
	const int32 Count = FMath::Clamp(SyntheticPointCount, 1, 1000000);
	RawData.SetNumZeroed(
		static_cast<int64>(Count)
		* GaussianSplatting7DRGS::InputStrideFloat4);

	constexpr float GoldenAngle = 2.39996322972865332f;
	constexpr float SpatialSigmaMetres = 0.085f;
	constexpr float JValue = 0.05f;
	constexpr float TViewValue = 0.62f;
	const float TViewDC = (TViewValue - 0.5f) / SH_C0;

	for (int32 Index = 0; Index < Count; ++Index)
	{
		const float U = (Index + 0.5f) / Count;
		const float Z = 2.0f * U - 1.0f;
		const float Ring = FMath::Sqrt(FMath::Max(1.0f - Z * Z, 0.0f));
		const float Phi = GoldenAngle * Index;
		const float Radial = FMath::Pow(
			FMath::Frac(Index * 0.61803398875f + 0.37f), 1.0f / 3.0f);
		const FVector3f Position(
			FMath::Cos(Phi) * Ring * Radial * SyntheticCloudRadiusUU,
			FMath::Sin(Phi) * Ring * Radial * SyntheticCloudRadiusUU,
			Z * Radial * SyntheticCloudRadiusUU * 0.55f);

		const int32 Base = Index * GaussianSplatting7DRGS::InputStrideFloat4;
		RawData[Base + 0] = FVector4f(Position, 0.0f);
		// UE +Z toward-light maps to training/GL (x,-z,-y) = (0,-1,0).
		RawData[Base + 1] = FVector4f(0.0f, -1.0f, 0.0f, 0.35f);
		RawData[Base + 2] = FVector4f(0.08f, 0.18f, JValue, JValue);
		RawData[Base + 3] = FVector4f(JValue, 1.0f, 1.0f, 1.0f);
		RawData[Base + 4] = FVector4f(0.0f, 0.0f, 0.0f, 1.0f);
		RawData[Base + 5] = FVector4f(
			SpatialSigmaMetres, SpatialSigmaMetres, SpatialSigmaMetres, 0.35f);
		RawData[Base + 6] = FVector4f(2.0f, 2.0f, 2.0f, 0.0f);
		RawData[Base + 15].W = TViewDC;
	}

	UE_LOG(LogGaussianSplatting7D, Display,
		TEXT("Generated %d deterministic synthetic 7DRGS gaussians"), Count);
	PushData();
}

void UGaussianSplatting7DComponent::RefreshRenderingParameters()
{
	PushParameters();
}

void UGaussianSplatting7DComponent::RefreshRenderRegistration()
{
	bLastShouldRender = ShouldRender();
	if (!bLastShouldRender)
	{
		if (UGaussianSplatting7DWorldSubsystem* Subsystem =
			GetWorld() ? GetWorld()->GetSubsystem<UGaussianSplatting7DWorldSubsystem>() : nullptr)
		{
			Subsystem->UnregisterComponent(this);
		}
		return;
	}

	if (RawData.IsEmpty())
	{
		ReloadPointCloud();
	}
	else
	{
		PushData();
	}
	PushParameters();
}

void UGaussianSplatting7DComponent::PushData()
{
	if (!ShouldRender())
	{
		return;
	}
	if (UGaussianSplatting7DWorldSubsystem* Subsystem =
		GetWorld() ? GetWorld()->GetSubsystem<UGaussianSplatting7DWorldSubsystem>() : nullptr)
	{
		Subsystem->UpdateData(this, TArray<FVector4f>(RawData));
	}
}

void UGaussianSplatting7DComponent::PushParameters()
{
	UGaussianSplatting7DWorldSubsystem* Subsystem =
		GetWorld() ? GetWorld()->GetSubsystem<UGaussianSplatting7DWorldSubsystem>() : nullptr;
	if (!Subsystem)
	{
		return;
	}
	if (!ShouldRender())
	{
		Subsystem->UnregisterComponent(this);
		return;
	}

	FVector TowardLightWS = ManualLightDirection.GetSafeNormal(
		UE_SMALL_NUMBER, FVector::UpVector);
	FLinearColor LightEnergy = ManualLightColor * RelightColorTint;
	FLinearColor AmbientLightEnergy = FLinearColor::Black;
	if (!bUseManualLightDirection && DirectionalLight)
	{
		TowardLightWS = (-DirectionalLight->GetActorForwardVector()).GetSafeNormal(
			UE_SMALL_NUMBER, FVector::UpVector);
		if (const UDirectionalLightComponent* LightComponent =
			Cast<UDirectionalLightComponent>(DirectionalLight->GetLightComponent()))
		{
			LightEnergy = LightComponent->GetLightColor()
				* RelightColorTint
				* LightComponent->Intensity * RelightIntensityScale;
		}
	}
	if (SkyLight)
	{
		if (const USkyLightComponent* SkyLightComponent =
			Cast<USkyLightComponent>(SkyLight->GetLightComponent()))
		{
			AmbientLightEnergy = SkyLightComponent->GetLightColor()
				* RelightColorTint
				* SkyLightComponent->Intensity
				* FMath::Max(AmbientLightIntensityScale, 0.0f);
		}
	}

	const FVector LocalDirectionUE =
		GetComponentTransform().InverseTransformVectorNoScale(TowardLightWS)
		.GetSafeNormal(UE_SMALL_NUMBER, FVector::UpVector);

	GaussianSplatting7DRGS::FSourceParameters Parameters;
	Parameters.LocalToWorld = FMatrix44f(GetComponentTransform().ToMatrixWithScale());
	Parameters.ConditionDirection = FVector3f(
		static_cast<float>(LocalDirectionUE.X),
		static_cast<float>(-LocalDirectionUE.Z),
		static_cast<float>(-LocalDirectionUE.Y)).GetSafeNormal(
			UE_SMALL_NUMBER, FVector3f(0.0f, 0.0f, 1.0f));
	Parameters.LightDirectionWS = FVector3f(TowardLightWS);
	Parameters.LightColor = FVector3f(LightEnergy.R, LightEnergy.G, LightEnergy.B);
	Parameters.AmbientLightColor = FVector3f(
		AmbientLightEnergy.R, AmbientLightEnergy.G, AmbientLightEnergy.B);
	Parameters.SourceWorldPosition = FVector3f(GetComponentLocation());
	Parameters.CurrentTime = CurrentTime;
	Parameters.OpacityMultiplier = FMath::Max(OpacityMultiplier, 0.0f);
	Parameters.OpacityPower = FMath::Max(OpacityPower, 0.01f);
	Parameters.PhaseMode = static_cast<uint32>(FMath::Clamp(PhaseMode, 0, 2));
	Parameters.PhaseG = FMath::Clamp(PhaseG, -0.99f, 0.99f);
	Parameters.PhaseG2 = FMath::Clamp(PhaseG2, -0.99f, 0.99f);
	Parameters.PhaseBlend = FMath::Clamp(PhaseBlend, 0.0f, 1.0f);
	Parameters.PhaseIntensity = FMath::Clamp(PhaseIntensity, 0.0f, 1.0f);
	Parameters.DepthTestMode = static_cast<uint32>(FMath::Clamp(DepthTestMode, 0, 2));
	Parameters.DepthSoftFadeUU = FMath::Max(DepthSoftFadeUU, 0.01f);
	Parameters.TViewSHDegree = static_cast<uint32>(FMath::Clamp(TViewSHDegree, 0, 3));
	Parameters.bDualSH = bDualSH ? 1u : 0u;
	Subsystem->UpdateParameters(this, Parameters);
}

#if WITH_EDITOR
void UGaussianSplatting7DComponent::PostEditChangeProperty(
	FPropertyChangedEvent& PropertyChangedEvent)
{
	Super::PostEditChangeProperty(PropertyChangedEvent);
	const FName PropertyName = PropertyChangedEvent.GetMemberPropertyName();
	if (PropertyName == TEXT("bVisible"))
	{
		RefreshRenderRegistration();
	}
	else if (PropertyName == GET_MEMBER_NAME_CHECKED(UGaussianSplatting7DComponent, PlyFile)
		|| PropertyName == GET_MEMBER_NAME_CHECKED(UGaussianSplatting7DComponent, SyntheticPointCount)
		|| PropertyName == GET_MEMBER_NAME_CHECKED(UGaussianSplatting7DComponent, SyntheticCloudRadiusUU))
	{
		ReloadPointCloud();
	}
	else
	{
		PushParameters();
	}
}
#endif
