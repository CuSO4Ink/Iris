// Copyright 2026 Violina. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Math/Float16.h"

/**
 * GPU-packed layout for a single Gaussian volume primitive.
 * 3 x uint4 = 48 bytes per primitive:
 *   Data0.xyz : FP32 center
 *   Data0.w   : FP16 sigma_t, FP16 adaptive support sigma
 *   Data1.x   : FP16 scale.x, FP16 scale.y
 *   Data1.y   : FP16 scale.z, FP16 emission
 *   Data1.z   : SNORM8 quaternion xyzw
 *   Data1.w   : UNORM8 albedo rgb, high byte unused
 *   Data2.x   : FP32 Gabor angular frequency (0 = Gaussian)
 *   Data2.yzw : FP16 optical depth toward +/- X, +/- Y, +/- Z
 *
 * Kept as a free function (not a USTRUCT) since it is purely a GPU transport
 * format — CPU-side editable data lives in FGaussianVolumePrimitive.
 */
namespace GaussianVolumeGPU
{
	struct alignas(16) FPackedPrimitive
	{
		FUintVector4 Data0;
		FUintVector4 Data1;
		FUintVector4 Data2;
	};
	static_assert(sizeof(FPackedPrimitive) == 48, "Gaussian GPU primitive must remain 48 bytes");

	/**
	 * Translation-only instance of one contiguous primitive range.
	 * Keeping this separate from FPackedPrimitive lets 1/4/16 copies share the
	 * 32-byte cloud buffer; rotations/scales stay on the owning source Actor.
	 */
	struct alignas(16) FPackedInstance
	{
		FUintVector4 Data0;  // xyz: FP32 world offset, w: primitive offset
		FUintVector4 Data1;  // x: primitive count, yzw: reserved
	};
	static_assert(sizeof(FPackedInstance) == 32, "Gaussian GPU instance must remain 32 bytes");

	inline uint32 PackSnorm8x4(FQuat Quat);

	inline FPackedInstance PackInstance(
		const FVector& WorldOffset,
		uint32 PrimitiveOffset,
		uint32 PrimitiveCount,
		const FQuat& LightBasisRotation = FQuat::Identity)
	{
		FPackedInstance Instance;
		Instance.Data0 = FUintVector4(
			FMath::AsUInt(static_cast<float>(WorldOffset.X)),
			FMath::AsUInt(static_cast<float>(WorldOffset.Y)),
			FMath::AsUInt(static_cast<float>(WorldOffset.Z)),
			PrimitiveOffset);
		Instance.Data1 = FUintVector4(PrimitiveCount, PackSnorm8x4(LightBasisRotation), 0u, 0u);
		return Instance;
	}

	inline uint32 PackHalf2(float Low, float High)
	{
		FFloat16 LowHalf;
		FFloat16 HighHalf;
		LowHalf.SetClamped(Low);
		HighHalf.SetClamped(High);
		return static_cast<uint32>(LowHalf.Encoded) | (static_cast<uint32>(HighHalf.Encoded) << 16);
	}

	inline FVector2f UnpackHalf2(uint32 Packed)
	{
		FFloat16 Low;
		FFloat16 High;
		Low.Encoded = static_cast<uint16>(Packed);
		High.Encoded = static_cast<uint16>(Packed >> 16);
		return FVector2f(Low.GetFloat(), High.GetFloat());
	}

	inline uint32 PackSnorm8x4(FQuat Quat)
	{
		Quat.Normalize();
		if (Quat.W < 0.0)
		{
			Quat = FQuat(-Quat.X, -Quat.Y, -Quat.Z, -Quat.W);
		}
		auto Pack = [](double Value)
		{
			const int8 Quantized = static_cast<int8>(FMath::Clamp(
				FMath::RoundToInt(Value * 127.0), -127, 127));
			return static_cast<uint32>(static_cast<uint8>(Quantized));
		};
		return Pack(Quat.X) | (Pack(Quat.Y) << 8) | (Pack(Quat.Z) << 16) | (Pack(Quat.W) << 24);
	}

	inline FQuat UnpackSnorm8x4(uint32 Packed)
	{
		auto Unpack = [Packed](uint32 Shift)
		{
			return static_cast<double>(static_cast<int8>(
				static_cast<uint8>((Packed >> Shift) & 0xffu))) / 127.0;
		};
		FQuat Quat(Unpack(0), Unpack(8), Unpack(16), Unpack(24));
		Quat.Normalize();
		return Quat;
	}

	inline uint32 PackUnorm8Rgb(const FLinearColor& Color)
	{
		auto Pack = [](float Value)
		{
			return static_cast<uint32>(FMath::RoundToInt(FMath::Clamp(Value, 0.0f, 1.0f) * 255.0f));
		};
		return Pack(Color.R) | (Pack(Color.G) << 8) | (Pack(Color.B) << 16);
	}

	inline FVector4f GetAppearance(const FPackedPrimitive& Primitive)
	{
		const float Scale = 1.0f / 255.0f;
		const FVector2f ScaleZEmission = UnpackHalf2(Primitive.Data1.Y);
		return FVector4f(
			static_cast<float>(Primitive.Data1.W & 0xffu) * Scale,
			static_cast<float>((Primitive.Data1.W >> 8) & 0xffu) * Scale,
			static_cast<float>((Primitive.Data1.W >> 16) & 0xffu) * Scale,
			ScaleZEmission.Y);
	}

	struct FScreenSizeLodBlend
	{
		int32 LodA = 0;
		int32 LodB = 0;
		float Alpha = 0.0f;
	};

	/** Smoothly blends high/medium/low across the former hysteresis bands. Alpha weights LodB. */
	inline FScreenSizeLodBlend SelectScreenSizeLodBlend(
		float ScreenRadius,
		float HighMinScreenRadius,
		float MediumMinScreenRadius,
		float BlendBand)
	{
		const float HighThreshold = FMath::Max(HighMinScreenRadius, MediumMinScreenRadius);
		const float MediumThreshold = FMath::Min(HighMinScreenRadius, MediumMinScreenRadius);
		const float H = FMath::Clamp(BlendBand, 0.01f, 0.5f);

		const float HighBlendStart = HighThreshold * (1.0f + H);
		const float HighBlendEnd = HighThreshold * (1.0f - H);
		if (ScreenRadius >= HighBlendStart)
			return {0, 0, 0.0f};
		if (ScreenRadius > HighBlendEnd)
			return {0, 1, FMath::GetRangePct(HighBlendStart, HighBlendEnd, ScreenRadius)};

		const float MediumBlendStart = MediumThreshold * (1.0f + H);
		const float MediumBlendEnd = MediumThreshold * (1.0f - H);
		if (ScreenRadius >= MediumBlendStart)
			return {1, 1, 0.0f};
		if (ScreenRadius > MediumBlendEnd)
			return {1, 2, FMath::GetRangePct(MediumBlendStart, MediumBlendEnd, ScreenRadius)};
		return {2, 2, 0.0f};
	}

	inline bool HasUniformAppearance(TConstArrayView<FPackedPrimitive> PackedData)
	{
		if (PackedData.IsEmpty())
		{
			return false;
		}

		const uint32 Emission = PackedData[0].Data1.Y & 0xffff0000u;
		const uint32 Albedo = PackedData[0].Data1.W & 0x00ffffffu;
		for (int32 Index = 1; Index < PackedData.Num(); ++Index)
		{
			if ((PackedData[Index].Data1.Y & 0xffff0000u) != Emission
				|| (PackedData[Index].Data1.W & 0x00ffffffu) != Albedo)
			{
				return false;
			}
		}
		return true;
	}

	inline bool HasDirectionalLightTau(TConstArrayView<FPackedPrimitive> PackedData)
	{
		for (const FPackedPrimitive& Primitive : PackedData)
		{
			if (Primitive.Data2.Y != 0u || Primitive.Data2.Z != 0u || Primitive.Data2.W != 0u)
			{
				return true;
			}
		}
		return false;
	}

	inline uint32 ResolveCandidatePoolCapacity(int32 RequestedCapacity, uint32 NumTiles, int32 NumGaussians)
	{
		const uint64 ExactCapacity = FMath::Max<uint64>(
			static_cast<uint64>(NumTiles) * static_cast<uint64>(FMath::Max(NumGaussians, 1)), 1);
		const uint64 Capacity = RequestedCapacity <= 0
			? ExactCapacity
			: FMath::Min<uint64>(static_cast<uint32>(RequestedCapacity), ExactCapacity);
		return static_cast<uint32>(FMath::Min<uint64>(Capacity, MAX_uint32));
	}

	/** Returns a sigma multiple in [0, 3] whose boundary-ray optical depth falls below TauMin. */
	inline float ResolveSupportSigma(float SigmaT, float MaxScale, float TauMin)
	{
		if (TauMin <= 0.0f)
		{
			return 3.0f;
		}
		const float PeakRayTau = FMath::Abs(SigmaT) * FMath::Sqrt(2.0f * UE_PI) * FMath::Max(MaxScale, 0.0f);
		return PeakRayTau <= TauMin
			? 0.0f
			: FMath::Min(3.0f, FMath::Sqrt(2.0f * FMath::Loge(PeakRayTau / TauMin)));
	}

	/** Exact perspective slope bounds for one axis of a projected ellipsoid. */
	inline bool ProjectEllipsoidAxisBounds(
		float CenterAxis,
		float Depth,
		float CovAxisAxis,
		float CovAxisDepth,
		float CovDepthDepth,
		float SupportSigma,
		float& OutMinSlope,
		float& OutMaxSlope)
	{
		const float K2 = FMath::Square(FMath::Max(SupportSigma, 0.0f));
		const float A = FMath::Square(Depth) - K2 * CovDepthDepth;
		if (A <= UE_SMALL_NUMBER)
		{
			OutMinSlope = -TNumericLimits<float>::Max();
			OutMaxSlope = TNumericLimits<float>::Max();
			return true;
		}
		const float B = -2.0f * CenterAxis * Depth + 2.0f * K2 * CovAxisDepth;
		const float C = FMath::Square(CenterAxis) - K2 * CovAxisAxis;
		const float Discriminant = B * B - 4.0f * A * C;
		if (Discriminant < 0.0f)
		{
			return false;
		}
		const float Root = FMath::Sqrt(FMath::Max(Discriminant, 0.0f));
		const float R0 = (-B - Root) / (2.0f * A);
		const float R1 = (-B + Root) / (2.0f * A);
		OutMinSlope = FMath::Min(R0, R1);
		OutMaxSlope = FMath::Max(R0, R1);
		return true;
	}

	inline float PackPrimitive(
		const FVector& Center,
		const FVector& Scale,
		const FQuat& Quat,
		float SigmaT,
		float Omega,
		const FLinearColor& Albedo,
		float Emission,
		TArray<FPackedPrimitive>& OutPacked,
		float SupportTauMin = 0.0f,
		const FVector3f& PositiveLightTau = FVector3f::ZeroVector,
		const FVector3f& NegativeLightTau = FVector3f::ZeroVector)
	{
		const float MaxScale = static_cast<float>(Scale.GetMax());
		const float SupportSigma = ResolveSupportSigma(SigmaT, MaxScale, SupportTauMin);
		const float BoundRadius = SupportSigma * MaxScale;
		if (BoundRadius <= 0.0f)
		{
			return 0.0f;
		}

		FPackedPrimitive Primitive;
		Primitive.Data0 = FUintVector4(
			FMath::AsUInt(static_cast<float>(Center.X)),
			FMath::AsUInt(static_cast<float>(Center.Y)),
			FMath::AsUInt(static_cast<float>(Center.Z)),
			PackHalf2(SigmaT, SupportSigma));
		Primitive.Data1 = FUintVector4(
			PackHalf2(static_cast<float>(Scale.X), static_cast<float>(Scale.Y)),
			PackHalf2(static_cast<float>(Scale.Z), Emission),
			PackSnorm8x4(Quat),
			PackUnorm8Rgb(Albedo));
		Primitive.Data2 = FUintVector4(
			FMath::AsUInt(Omega),
			PackHalf2(FMath::Max(PositiveLightTau.X, 0.0f), FMath::Max(NegativeLightTau.X, 0.0f)),
			PackHalf2(FMath::Max(PositiveLightTau.Y, 0.0f), FMath::Max(NegativeLightTau.Y, 0.0f)),
			PackHalf2(FMath::Max(PositiveLightTau.Z, 0.0f), FMath::Max(NegativeLightTau.Z, 0.0f)));
		OutPacked.Add(Primitive);
		return BoundRadius;
	}
}
