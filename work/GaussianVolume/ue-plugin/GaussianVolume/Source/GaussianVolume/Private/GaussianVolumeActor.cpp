// Copyright 2026 Violina. All Rights Reserved.

#include "GaussianVolumeActor.h"
#include "GaussianVolumeComponent.h"
#include "Components/SplineComponent.h"
#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

#if GAUSSIANVOLUME_WITH_OPENVDB
THIRD_PARTY_INCLUDES_START
UE_PUSH_MACRO("check")
#undef check
#define BOOST_ALLOW_DEPRECATED_HEADERS
#include <openvdb/openvdb.h>
#include <openvdb/io/File.h>
UE_POP_MACRO("check")
THIRD_PARTY_INCLUDES_END
#endif

namespace
{
#if GAUSSIANVOLUME_WITH_OPENVDB
bool WriteGaussianJson(const FString& Path, const FString& Source, const TArray<FGaussianVolumePrimitive>& Gaussians)
{
	TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetStringField(TEXT("schema"), TEXT("GaussianVolume.Primitives.v1"));
	Root->SetStringField(TEXT("source"), Source);
	Root->SetNumberField(TEXT("primitive_count"), Gaussians.Num());

	TArray<TSharedPtr<FJsonValue>> Values;
	Values.Reserve(Gaussians.Num());
	auto VectorValue = [](double X, double Y, double Z)
	{
		TArray<TSharedPtr<FJsonValue>> Array;
		Array.Add(MakeShared<FJsonValueNumber>(X));
		Array.Add(MakeShared<FJsonValueNumber>(Y));
		Array.Add(MakeShared<FJsonValueNumber>(Z));
		return Array;
	};

	for (const FGaussianVolumePrimitive& Primitive : Gaussians)
	{
		TSharedRef<FJsonObject> Object = MakeShared<FJsonObject>();
		Object->SetArrayField(TEXT("center"), VectorValue(Primitive.Center.X, Primitive.Center.Y, Primitive.Center.Z));
		Object->SetArrayField(TEXT("scale"), VectorValue(Primitive.Scale.X, Primitive.Scale.Y, Primitive.Scale.Z));
		const FQuat Quat(Primitive.Rotation);
		TArray<TSharedPtr<FJsonValue>> Rotation;
		Rotation.Add(MakeShared<FJsonValueNumber>(Quat.X));
		Rotation.Add(MakeShared<FJsonValueNumber>(Quat.Y));
		Rotation.Add(MakeShared<FJsonValueNumber>(Quat.Z));
		Rotation.Add(MakeShared<FJsonValueNumber>(Quat.W));
		Object->SetArrayField(TEXT("rotation"), MoveTemp(Rotation));
		Object->SetNumberField(TEXT("sigma_t"), Primitive.SigmaT);
		Object->SetNumberField(TEXT("omega"), Primitive.Omega);
		Object->SetArrayField(TEXT("albedo"), VectorValue(Primitive.Albedo.R, Primitive.Albedo.G, Primitive.Albedo.B));
		Object->SetNumberField(TEXT("emission"), Primitive.Emission);
		if (!Primitive.PositiveLightTau.IsNearlyZero() || !Primitive.NegativeLightTau.IsNearlyZero())
		{
			TArray<TSharedPtr<FJsonValue>> LightTau;
			LightTau.Add(MakeShared<FJsonValueNumber>(Primitive.PositiveLightTau.X));
			LightTau.Add(MakeShared<FJsonValueNumber>(Primitive.NegativeLightTau.X));
			LightTau.Add(MakeShared<FJsonValueNumber>(Primitive.PositiveLightTau.Y));
			LightTau.Add(MakeShared<FJsonValueNumber>(Primitive.NegativeLightTau.Y));
			LightTau.Add(MakeShared<FJsonValueNumber>(Primitive.PositiveLightTau.Z));
			LightTau.Add(MakeShared<FJsonValueNumber>(Primitive.NegativeLightTau.Z));
			Object->SetArrayField(TEXT("light_tau_axes"), MoveTemp(LightTau));
		}
		Values.Add(MakeShared<FJsonValueObject>(Object));
	}
	Root->SetArrayField(TEXT("gaussians"), MoveTemp(Values));

	FString Text;
	const TSharedRef<TJsonWriter<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>> Writer =
		TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&Text);
	if (!FJsonSerializer::Serialize(Root, Writer))
	{
		return false;
	}
	IFileManager::Get().MakeDirectory(*FPaths::GetPath(Path), true);
	return FFileHelper::SaveStringToFile(Text, *Path, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
}
#endif
}

AGaussianVolumeActor::AGaussianVolumeActor()
{
	PrimaryActorTick.bCanEverTick = false;

	SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SceneRoot"));
	RootComponent = SceneRoot;

	// UGaussianVolumeComponent derives from UActorComponent (not USceneComponent):
	// it has no transform of its own, so it does not attach to RootComponent —
	// it just needs to exist on this Actor. Its Gaussians use world-space Center
	// values (see UGaussianVolumeComponent::BeginPlay default primitive).
	GaussianVolumeComponent = CreateDefaultSubobject<UGaussianVolumeComponent>(TEXT("GaussianVolumeComponent"));
	SplineComponent = CreateDefaultSubobject<USplineComponent>(TEXT("FieldSpline"));
	SplineComponent->SetupAttachment(SceneRoot);
	SplineComponent->ClearSplinePoints(false);
	SplineComponent->AddSplinePoint(FVector(-600.0, 0.0, 0.0), ESplineCoordinateSpace::Local, false);
	SplineComponent->AddSplinePoint(FVector(-250.0, 0.0, 500.0), ESplineCoordinateSpace::Local, false);
	SplineComponent->AddSplinePoint(FVector(250.0, 0.0, 500.0), ESplineCoordinateSpace::Local, false);
	SplineComponent->AddSplinePoint(FVector(600.0, 0.0, 0.0), ESplineCoordinateSpace::Local, true);
}

void AGaussianVolumeActor::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	if (bAutoConvertOpenVdb)
	{
		bAutoConvertOpenVdb = false;
		ConvertOpenVdbToGaussianJson();
	}
	if (GaussianVolumeComponent && GaussianVolumeComponent->bUseDebugDefaultGaussianIfEmpty
		&& !GaussianJsonFile.FilePath.IsEmpty())
	{
		ImportGaussianJson();
	}
	if (bGenerateFromSpline)
	{
		RebuildFromSpline();
	}
}

void AGaussianVolumeActor::RebuildFromSpline()
{
	if (!GaussianVolumeComponent)
	{
		return;
	}

	// Gather ALL spline components on this Actor (the constructor's "FieldSpline" plus
	// any extra USplineComponent the user added in the editor). Every spline's primitives
	// are appended into ONE Gaussians array = one SVE = one composite pass, so crossing
	// arcs occlude each other correctly (per-ray t_star ordering in the shader handles it).
	// Two separate GaussianVolume Actors CANNOT occlude each other: each owns its own SVE
	// pass and the later-registered one always draws on top.
	TArray<USplineComponent*> Splines;
	GetComponents<USplineComponent>(Splines);
	if (Splines.Num() == 0)
	{
		return;
	}

	TArray<FGaussianVolumePrimitive>& Out = GaussianVolumeComponent->Gaussians;
	Out.Reset();

	int32 ArcIndex = 0;
	for (const USplineComponent* Spline : Splines)
	{
		if (Spline)
		{
			AppendArcFromSpline(*Spline, ArcIndex++, Out);
		}
	}

	GaussianVolumeComponent->bUseDebugDefaultGaussianIfEmpty = false;
	GaussianVolumeComponent->PushGaussianDataToRenderThread();
}

bool AGaussianVolumeActor::ImportGaussianJson()
{
	if (!GaussianVolumeComponent || GaussianJsonFile.FilePath.IsEmpty())
	{
		UE_LOG(LogTemp, Error, TEXT("GaussianVolume: choose a JSON file before importing"));
		return false;
	}

	FString Path = GaussianJsonFile.FilePath;
	if (FPaths::IsRelative(Path))
	{
		Path = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir(), Path);
	}

	FString Text;
	if (!FFileHelper::LoadFileToString(Text, *Path))
	{
		UE_LOG(LogTemp, Error, TEXT("GaussianVolume: failed to read %s"), *Path);
		return false;
	}

	TSharedPtr<FJsonObject> Root;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid()
		|| Root->GetStringField(TEXT("schema")) != TEXT("GaussianVolume.Primitives.v1"))
	{
		UE_LOG(LogTemp, Error, TEXT("GaussianVolume: invalid JSON schema in %s"), *Path);
		return false;
	}

	const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
	if (!Root->TryGetArrayField(TEXT("gaussians"), Values) || !Values)
	{
		UE_LOG(LogTemp, Error, TEXT("GaussianVolume: missing gaussians array in %s"), *Path);
		return false;
	}

	auto ReadNumbers = [](const TSharedPtr<FJsonObject>& Object, const TCHAR* Name, int32 Count, TArray<double>& Out)
	{
		const TArray<TSharedPtr<FJsonValue>>* Array = nullptr;
		if (!Object.IsValid() || !Object->TryGetArrayField(Name, Array) || !Array || Array->Num() != Count)
		{
			return false;
		}
		Out.Reset(Count);
		for (const TSharedPtr<FJsonValue>& Value : *Array)
		{
			double Number = 0.0;
			if (!Value.IsValid() || !Value->TryGetNumber(Number) || !FMath::IsFinite(Number))
			{
				return false;
			}
			Out.Add(Number);
		}
		return true;
	};

	TArray<FGaussianVolumePrimitive> Imported;
	Imported.Reserve(Values->Num());
	for (const TSharedPtr<FJsonValue>& Value : *Values)
	{
		const TSharedPtr<FJsonObject> Object = Value.IsValid() ? Value->AsObject() : nullptr;
		TArray<double> Center, Scale, Rotation, Albedo, LightTau;
		double SigmaT = 0.0;
		double Omega = 0.0;
		double EmissionValue = 0.0;
		const bool bHasLightTau = Object.IsValid() && Object->HasField(TEXT("light_tau_axes"));
		if (Object.IsValid() && Object->HasField(TEXT("omega"))
			&& (!Object->TryGetNumberField(TEXT("omega"), Omega) || !FMath::IsFinite(Omega) || Omega < 0.0))
		{
			UE_LOG(LogTemp, Error, TEXT("GaussianVolume: malformed omega in primitive %d in %s"), Imported.Num(), *Path);
			return false;
		}
		if ((bHasLightTau && !ReadNumbers(Object, TEXT("light_tau_axes"), 6, LightTau))
			|| !ReadNumbers(Object, TEXT("center"), 3, Center)
			|| !ReadNumbers(Object, TEXT("scale"), 3, Scale)
			|| !ReadNumbers(Object, TEXT("rotation"), 4, Rotation)
			|| !ReadNumbers(Object, TEXT("albedo"), 3, Albedo)
			|| !Object->TryGetNumberField(TEXT("sigma_t"), SigmaT)
			|| !Object->TryGetNumberField(TEXT("emission"), EmissionValue)
			|| !FMath::IsFinite(SigmaT) || !FMath::IsFinite(EmissionValue)
			|| (SigmaT < 0.0 && Omega <= 0.0))
		{
			UE_LOG(LogTemp, Error, TEXT("GaussianVolume: malformed primitive %d in %s"), Imported.Num(), *Path);
			return false;
		}

		const FQuat Quat(Rotation[0], Rotation[1], Rotation[2], Rotation[3]);
		FGaussianVolumePrimitive& Primitive = Imported.AddDefaulted_GetRef();
		Primitive.Center = FVector(Center[0], Center[1], Center[2]);
		Primitive.Scale = FVector(Scale[0], Scale[1], Scale[2]).GetAbs().ComponentMax(FVector(0.01));
		Primitive.Rotation = Quat.GetNormalized().Rotator();
		Primitive.SigmaT = static_cast<float>(SigmaT);
		Primitive.Omega = static_cast<float>(Omega);
		Primitive.Albedo = FLinearColor(Albedo[0], Albedo[1], Albedo[2], 1.0);
		Primitive.Emission = FMath::Max(static_cast<float>(EmissionValue), 0.0f);
		if (bHasLightTau)
		{
			for (double Tau : LightTau)
			{
				if (Tau < 0.0)
				{
					UE_LOG(LogTemp, Error, TEXT("GaussianVolume: negative light_tau_axes in primitive %d in %s"), Imported.Num() - 1, *Path);
					return false;
				}
			}
			Primitive.PositiveLightTau = FVector3f(
				static_cast<float>(LightTau[0]), static_cast<float>(LightTau[2]), static_cast<float>(LightTau[4]));
			Primitive.NegativeLightTau = FVector3f(
				static_cast<float>(LightTau[1]), static_cast<float>(LightTau[3]), static_cast<float>(LightTau[5]));
		}
	}

	GaussianVolumeComponent->Gaussians = MoveTemp(Imported);
	GaussianVolumeComponent->bUseDebugDefaultGaussianIfEmpty = false;
	bGenerateFromSpline = false;
	GaussianVolumeComponent->PushGaussianDataToRenderThread();
#if WITH_EDITOR
	Modify();
	MarkPackageDirty();
#endif
	UE_LOG(LogTemp, Display, TEXT("GaussianVolume: imported %d primitives from %s"), GaussianVolumeComponent->Gaussians.Num(), *Path);
	return true;
}

bool AGaussianVolumeActor::ConvertOpenVdbToGaussianJson()
{
#if GAUSSIANVOLUME_WITH_OPENVDB
	if (!GaussianVolumeComponent || OpenVdbFile.FilePath.IsEmpty() || OpenVdbOutputJsonFile.FilePath.IsEmpty())
	{
		UE_LOG(LogTemp, Error, TEXT("GaussianVolume: choose VDB source and JSON output before converting"));
		return false;
	}

	FString SourcePath = OpenVdbFile.FilePath;
	FString OutputPath = OpenVdbOutputJsonFile.FilePath;
	if (FPaths::IsRelative(SourcePath))
	{
		SourcePath = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir(), SourcePath);
	}
	if (FPaths::IsRelative(OutputPath))
	{
		OutputPath = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir(), OutputPath);
	}
	if (!FPaths::FileExists(SourcePath))
	{
		UE_LOG(LogTemp, Error, TEXT("GaussianVolume: VDB file not found: %s"), *SourcePath);
		return false;
	}

	struct FVoxel
	{
		FIntVector Coord;
		FVector WorldPosition;
		float Density = 0.0f;
		float Gradient = 0.0f;
	};
	struct FBin
	{
		FVector WeightedPosition = FVector::ZeroVector;
		double DensitySum = 0.0;
		double GradientSum = 0.0;
		float DensityMin = TNumericLimits<float>::Max();
		float DensityMax = 0.0f;
		int32 VoxelCount = 0;
	};

	try
	{
		openvdb::initialize();
		openvdb::io::File File(TCHAR_TO_UTF8(*SourcePath));
		File.open(false);
		openvdb::GridPtrVecPtr Grids = File.getGrids();
		openvdb::FloatGrid::Ptr DensityGrid;
		for (const openvdb::GridBase::Ptr& Grid : *Grids)
		{
			if (Grid && Grid->isType<openvdb::FloatGrid>() && Grid->getName() == "density")
			{
				DensityGrid = openvdb::gridPtrCast<openvdb::FloatGrid>(Grid);
				break;
			}
		}
		if (!DensityGrid)
		{
			for (const openvdb::GridBase::Ptr& Grid : *Grids)
			{
				if (Grid && Grid->isType<openvdb::FloatGrid>())
				{
					DensityGrid = openvdb::gridPtrCast<openvdb::FloatGrid>(Grid);
					break;
				}
			}
		}
		if (!DensityGrid)
		{
			UE_LOG(LogTemp, Error, TEXT("GaussianVolume: VDB has no scalar float density grid: %s"), *SourcePath);
			return false;
		}

		const openvdb::CoordBBox ActiveBounds = DensityGrid->evalActiveVoxelBoundingBox();
		const openvdb::Coord MinCoord = ActiveBounds.min();
		const openvdb::Coord ActiveDim = ActiveBounds.dim();
		TArray<FVoxel> Voxels;
		Voxels.Reserve(static_cast<int32>(FMath::Min<int64>(DensityGrid->activeVoxelCount(), MAX_int32)));
		FVector WorldMin(TNumericLimits<double>::Max());
		FVector WorldMax(-TNumericLimits<double>::Max());
		float DensityMax = 0.0f;
		auto DensityAccessor = DensityGrid->getConstAccessor();
		for (auto It = DensityGrid->cbeginValueOn(); It; ++It)
		{
			if (!It.isVoxelValue())
			{
				continue;
			}
			const float DensityValue = *It;
			if (!FMath::IsFinite(DensityValue) || DensityValue <= OpenVdbMinimumDensity)
			{
				continue;
			}
			const openvdb::Coord Coord = It.getCoord();
			const openvdb::Vec3d Position = DensityGrid->transform().indexToWorld(openvdb::Vec3d(Coord.x(), Coord.y(), Coord.z()));
			FVoxel& Voxel = Voxels.AddDefaulted_GetRef();
			Voxel.Coord = FIntVector(Coord.x(), Coord.y(), Coord.z());
			Voxel.WorldPosition = FVector(Position.x(), Position.y(), Position.z());
			Voxel.Density = DensityValue;
			const float Dx = DensityAccessor.getValue(Coord + openvdb::Coord(1, 0, 0)) - DensityAccessor.getValue(Coord - openvdb::Coord(1, 0, 0));
			const float Dy = DensityAccessor.getValue(Coord + openvdb::Coord(0, 1, 0)) - DensityAccessor.getValue(Coord - openvdb::Coord(0, 1, 0));
			const float Dz = DensityAccessor.getValue(Coord + openvdb::Coord(0, 0, 1)) - DensityAccessor.getValue(Coord - openvdb::Coord(0, 0, 1));
			Voxel.Gradient = 0.5f * FMath::Sqrt(Dx * Dx + Dy * Dy + Dz * Dz);
			WorldMin = WorldMin.ComponentMin(Voxel.WorldPosition);
			WorldMax = WorldMax.ComponentMax(Voxel.WorldPosition);
			DensityMax = FMath::Max(DensityMax, DensityValue);
		}
		File.close();
		if (Voxels.IsEmpty() || DensityMax <= 0.0f)
		{
			UE_LOG(LogTemp, Error, TEXT("GaussianVolume: VDB has no density voxels above %g"), OpenVdbMinimumDensity);
			return false;
		}

		const int32 Target = FMath::Clamp(OpenVdbTargetPrimitiveCount, 128, 65536);
		auto BinKey = [MinCoord](const FIntVector& Coord, int32 CellSize)
		{
			return FIntVector(
				(Coord.X - MinCoord.x()) / CellSize,
				(Coord.Y - MinCoord.y()) / CellSize,
				(Coord.Z - MinCoord.z()) / CellSize);
		};
		auto CountBins = [&Voxels, &BinKey](int32 CellSize)
		{
			TSet<FIntVector> Keys;
			for (const FVoxel& Voxel : Voxels)
			{
				Keys.Add(BinKey(Voxel.Coord, CellSize));
			}
			return Keys.Num();
		};

		int32 Low = 1;
		int32 High = FMath::Max3(ActiveDim.x(), ActiveDim.y(), ActiveDim.z());
		while (Low < High)
		{
			const int32 Mid = Low + (High - Low) / 2;
			if (CountBins(Mid) <= Target)
			{
				High = Mid;
			}
			else
			{
				Low = Mid + 1;
			}
		}
		// Start one level finer than the uniform budget, then selectively split only
		// high-detail parents until the requested count is reached.
		const int32 FineCellSize = FMath::Max(Low - 1, 1);
		const int32 BaseCellSize = FineCellSize * 2;
		TMap<FIntVector, FBin> FineBins;
		TMap<FIntVector, FBin> BaseBins;
		auto Accumulate = [](FBin& Bin, const FVoxel& Voxel)
		{
			Bin.WeightedPosition += Voxel.WorldPosition * Voxel.Density;
			Bin.DensitySum += Voxel.Density;
			Bin.GradientSum += Voxel.Gradient;
			Bin.DensityMin = FMath::Min(Bin.DensityMin, Voxel.Density);
			Bin.DensityMax = FMath::Max(Bin.DensityMax, Voxel.Density);
			++Bin.VoxelCount;
		};
		for (const FVoxel& Voxel : Voxels)
		{
			Accumulate(FineBins.FindOrAdd(BinKey(Voxel.Coord, FineCellSize)), Voxel);
			Accumulate(BaseBins.FindOrAdd(BinKey(Voxel.Coord, BaseCellSize)), Voxel);
		}

		TMap<FIntVector, TArray<FIntVector>> FineChildren;
		for (const TPair<FIntVector, FBin>& Pair : FineBins)
		{
			const FIntVector& FineKey = Pair.Key;
			FineChildren.FindOrAdd(FIntVector(FineKey.X / 2, FineKey.Y / 2, FineKey.Z / 2)).Add(FineKey);
		}
		TArray<FIntVector> DetailOrder;
		BaseBins.GetKeys(DetailOrder);
		DetailOrder.Sort([&BaseBins, DensityMax](const FIntVector& A, const FIntVector& B)
		{
			auto Score = [DensityMax](const FBin& Bin)
			{
				const double Range = (Bin.DensityMax - Bin.DensityMin) / DensityMax;
				const double Gradient = Bin.VoxelCount > 0 ? (Bin.GradientSum / Bin.VoxelCount) / DensityMax : 0.0;
				return Range + 2.0 * Gradient;
			};
			const double ScoreA = Score(BaseBins.FindChecked(A));
			const double ScoreB = Score(BaseBins.FindChecked(B));
			if (!FMath::IsNearlyEqual(ScoreA, ScoreB))
			{
				return ScoreA > ScoreB;
			}
			return A.X != B.X ? A.X < B.X : (A.Y != B.Y ? A.Y < B.Y : A.Z < B.Z);
		});
		TSet<FIntVector> SplitBins;
		int32 OutputCount = BaseBins.Num();
		for (const FIntVector& Key : DetailOrder)
		{
			const TArray<FIntVector>* ChildKeys = FineChildren.Find(Key);
			if (!ChildKeys || ChildKeys->Num() <= 1)
			{
				continue;
			}
			const int32 SplitCount = OutputCount - 1 + ChildKeys->Num();
			if (SplitCount <= Target)
			{
				SplitBins.Add(Key);
				OutputCount = SplitCount;
			}
			if (OutputCount == Target)
			{
				break;
			}
		}

		struct FOutputBin
		{
			FBin Bin;
			int32 CellSize = 1;
		};
		TArray<FIntVector> SortedBaseKeys;
		BaseBins.GetKeys(SortedBaseKeys);
		SortedBaseKeys.Sort([](const FIntVector& A, const FIntVector& B)
		{
			return A.X != B.X ? A.X < B.X : (A.Y != B.Y ? A.Y < B.Y : A.Z < B.Z);
		});
		TArray<FOutputBin> OutputBins;
		OutputBins.Reserve(OutputCount);
		for (const FIntVector& BaseKey : SortedBaseKeys)
		{
			if (!SplitBins.Contains(BaseKey))
			{
				OutputBins.Add({BaseBins.FindChecked(BaseKey), BaseCellSize});
				continue;
			}
			TArray<FIntVector> ChildKeys = FineChildren.FindChecked(BaseKey);
			ChildKeys.Sort([](const FIntVector& A, const FIntVector& B)
			{
				return A.X != B.X ? A.X < B.X : (A.Y != B.Y ? A.Y < B.Y : A.Z < B.Z);
			});
			for (const FIntVector& FineKey : ChildKeys)
			{
				OutputBins.Add({FineBins.FindChecked(FineKey), FineCellSize});
			}
		}

		double AggregatedDensityMax = 0.0;
		for (const FOutputBin& Output : OutputBins)
		{
			const FBin& Bin = Output.Bin;
			if (Bin.VoxelCount > 0)
			{
				AggregatedDensityMax = FMath::Max(AggregatedDensityMax, Bin.DensitySum / Bin.VoxelCount);
			}
		}

		const FVector SourceExtent = WorldMax - WorldMin;
		const double LongestExtent = SourceExtent.GetMax();
		if (LongestExtent <= UE_DOUBLE_SMALL_NUMBER)
		{
			UE_LOG(LogTemp, Error, TEXT("GaussianVolume: VDB active bounds are degenerate"));
			return false;
		}
		const double WorldScale = FMath::Max(OpenVdbTargetWorldSizeCm, 1.0f) / LongestExtent;
		const FVector SourceCenter = (WorldMin + WorldMax) * 0.5;
		const openvdb::Vec3d Origin = DensityGrid->transform().indexToWorld(openvdb::Vec3d(0.0));
		auto CellScale = [&DensityGrid, &Origin, WorldScale](int32 CellSize)
		{
			const openvdb::Vec3d StepX = DensityGrid->transform().indexToWorld(openvdb::Vec3d(CellSize, 0.0, 0.0));
			const openvdb::Vec3d StepY = DensityGrid->transform().indexToWorld(openvdb::Vec3d(0.0, CellSize, 0.0));
			const openvdb::Vec3d StepZ = DensityGrid->transform().indexToWorld(openvdb::Vec3d(0.0, 0.0, CellSize));
			return FVector(
				(StepX - Origin).length() * WorldScale * 0.6,
				(StepY - Origin).length() * WorldScale * 0.6,
				(StepZ - Origin).length() * WorldScale * 0.6);
		};
		const FVector FineScale = CellScale(FineCellSize);
		const FVector BaseScale = CellScale(BaseCellSize);

		TArray<FGaussianVolumePrimitive> Converted;
		Converted.Reserve(OutputBins.Num());
		for (const FOutputBin& Output : OutputBins)
		{
			const FBin& Bin = Output.Bin;
			if (Bin.DensitySum <= 0.0 || Bin.VoxelCount <= 0)
			{
				continue;
			}
			FGaussianVolumePrimitive& Primitive = Converted.AddDefaulted_GetRef();
			Primitive.Center = (Bin.WeightedPosition / Bin.DensitySum - SourceCenter) * WorldScale;
			Primitive.Scale = (Output.CellSize == FineCellSize ? FineScale : BaseScale).ComponentMax(FVector(0.01));
			Primitive.SigmaT = static_cast<float>((Bin.DensitySum / Bin.VoxelCount) / AggregatedDensityMax) * OpenVdbPeakSigmaT;
			Primitive.Albedo = OpenVdbAlbedo;
			Primitive.Emission = 0.0f;
		}

		if (!WriteGaussianJson(OutputPath, SourcePath, Converted))
		{
			UE_LOG(LogTemp, Error, TEXT("GaussianVolume: failed to write %s"), *OutputPath);
			return false;
		}
		GaussianJsonFile.FilePath = OutputPath;
		UE_LOG(LogTemp, Display, TEXT("GaussianVolume: converted VDB grid '%s': %d voxels -> %d adaptive primitives (base=%d fine=%d split=%d), output=%s"),
			UTF8_TO_TCHAR(DensityGrid->getName().c_str()), Voxels.Num(), Converted.Num(), BaseCellSize, FineCellSize, SplitBins.Num(), *OutputPath);
		return ImportGaussianJson();
	}
	catch (const openvdb::Exception& Error)
	{
		UE_LOG(LogTemp, Error, TEXT("GaussianVolume: OpenVDB error: %s"), UTF8_TO_TCHAR(Error.what()));
		return false;
	}
#else
	UE_LOG(LogTemp, Error, TEXT("GaussianVolume: OpenVDB conversion is only available in Windows/Linux editor builds"));
	return false;
#endif
}

void AGaussianVolumeActor::AppendArcFromSpline(const USplineComponent& Spline, int32 ArcIndex, TArray<FGaussianVolumePrimitive>& Out) const
{
	const int32 Count = FMath::Clamp(PrimitiveCount, 1, 128);
	const float Length = Spline.GetSplineLength();
	const float Spacing = Count > 1 ? Length / static_cast<float>(Count - 1) : FMath::Max(Length, Thickness);
	FRandomStream Random(Seed + ArcIndex * 101);  // distinct breakup per arc

	Out.Reserve(Out.Num() + Count);
	for (int32 Index = 0; Index < Count; ++Index)
	{
		const float U = Count > 1 ? static_cast<float>(Index) / static_cast<float>(Count - 1) : 0.5f;
		const float Distance = U * Length;
		const float Noise = Random.FRandRange(-1.0f, 1.0f);
		const float RadiusNoise = 1.0f + Noise * Breakup * 0.35f;

		FGaussianVolumePrimitive& Primitive = Out.AddDefaulted_GetRef();
		Primitive.Center = Spline.GetLocationAtDistanceAlongSpline(Distance, ESplineCoordinateSpace::Local);
		const FVector Right = Spline.GetRightVectorAtDistanceAlongSpline(Distance, ESplineCoordinateSpace::Local);
		const FVector Up = Spline.GetUpVectorAtDistanceAlongSpline(Distance, ESplineCoordinateSpace::Local);
		Primitive.Center += (Right * Random.FRandRange(-1.0f, 1.0f) + Up * Random.FRandRange(-1.0f, 1.0f)) * Thickness * Breakup * 0.25f;
		Primitive.Rotation = Spline.GetRotationAtDistanceAlongSpline(Distance, ESplineCoordinateSpace::Local);
		Primitive.Rotation.Roll += TwistDegrees * U;
		Primitive.Scale = FVector(FMath::Max(Spacing * 0.65f, 1.0f), Thickness * RadiusNoise, Thickness * RadiusNoise * 0.65f);
		Primitive.SigmaT = FMath::Max(Density * (1.0f + Noise * Breakup * 0.5f), 0.0f);
		Primitive.Albedo = FieldColor;
		Primitive.Emission = Emission;
	}
}


#if WITH_EDITOR
void AGaussianVolumeActor::PostEditMove(bool bFinished)
{
	Super::PostEditMove(bFinished);

	if (bFinished && GaussianVolumeComponent)
	{
		GaussianVolumeComponent->PushGaussianDataToRenderThread();
	}
}
#endif
