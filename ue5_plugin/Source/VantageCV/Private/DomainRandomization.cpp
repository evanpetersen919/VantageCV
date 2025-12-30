/******************************************************************************
 * VantageCV - Domain Randomization Controller Implementation
 ******************************************************************************
 * File: DomainRandomization.cpp
 * Description: Implementation of Structured Domain Randomization (SDR) for
 *              computer vision research. Provides research-grade randomization
 *              of visual elements to enable sim-to-real transfer learning.
 * 
 * Author: Evan Petersen
 * Date: December 2025
 *****************************************************************************/

#include "DomainRandomization.h"
#include "Engine/DirectionalLight.h"
#include "Components/DirectionalLightComponent.h"
#include "Engine/SkyLight.h"
#include "Components/SkyLightComponent.h"
#include "Kismet/GameplayStatics.h"
#include "EngineUtils.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Engine/StaticMeshActor.h"
#include "UObject/ConstructorHelpers.h"

// Forward declaration - ASkyAtmosphere not needed for this implementation
class ASkyAtmosphere;

DEFINE_LOG_CATEGORY_STATIC(LogDomainRandomization, Log, All);

ADomainRandomization::ADomainRandomization()
{
	PrimaryActorTick.bCanEverTick = false;

	// Create a simple scene component as root
	USceneComponent* SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SceneRoot"));
	RootComponent = SceneRoot;
}

void ADomainRandomization::BeginPlay()
{
	Super::BeginPlay();

	InitializeDefaultPalettes();

	UE_LOG(LogDomainRandomization, Log, 
		TEXT("Domain Randomization Controller initialized"));
}

void ADomainRandomization::InitializeDefaultPalettes()
{
	// Initialize sky color palette if empty
	if (Config.Sky.SkyColorPalette.Num() == 0)
	{
		Config.Sky.SkyColorPalette.Add(FLinearColor(0.4f, 0.6f, 1.0f));    // Clear blue
		Config.Sky.SkyColorPalette.Add(FLinearColor(0.6f, 0.65f, 0.7f));   // Overcast
		Config.Sky.SkyColorPalette.Add(FLinearColor(1.0f, 0.7f, 0.5f));    // Sunset
		Config.Sky.SkyColorPalette.Add(FLinearColor(0.15f, 0.15f, 0.25f)); // Dusk
		Config.Sky.SkyColorPalette.Add(FLinearColor(0.05f, 0.05f, 0.1f));  // Night
		Config.Sky.SkyColorPalette.Add(FLinearColor(0.8f, 0.85f, 0.9f));   // Bright overcast
		Config.Sky.SkyColorPalette.Add(FLinearColor(0.3f, 0.3f, 0.35f));   // Storm
		Config.Sky.SkyColorPalette.Add(FLinearColor(1.0f, 0.85f, 0.6f));   // Golden hour
	}

	// Initialize horizon color palette if empty
	if (Config.Sky.HorizonColorPalette.Num() == 0)
	{
		Config.Sky.HorizonColorPalette.Add(FLinearColor(0.8f, 0.9f, 1.0f));  // Light blue horizon
		Config.Sky.HorizonColorPalette.Add(FLinearColor(0.7f, 0.7f, 0.75f)); // Gray horizon
		Config.Sky.HorizonColorPalette.Add(FLinearColor(1.0f, 0.5f, 0.2f));  // Orange sunset
		Config.Sky.HorizonColorPalette.Add(FLinearColor(0.4f, 0.3f, 0.5f));  // Purple dusk
		Config.Sky.HorizonColorPalette.Add(FLinearColor(0.2f, 0.2f, 0.25f)); // Dark horizon
	}
}

void ADomainRandomization::SetConfiguration(const FDomainRandomizationConfig& NewConfig)
{
	Config = NewConfig;
	UE_LOG(LogDomainRandomization, Log, 
		TEXT("Configuration updated - Seed: %d, Distractors: %s"), 
		Config.RandomSeed,
		Config.Distractors.bEnabled ? TEXT("Enabled") : TEXT("Disabled"));
}

void ADomainRandomization::ApplyRandomization()
{
	// Initialize random stream
	if (Config.RandomSeed >= 0)
	{
		RandomStream.Initialize(Config.RandomSeed);
	}
	else
	{
		RandomStream.Initialize(FMath::Rand());
	}

	UE_LOG(LogDomainRandomization, Log, 
		TEXT("Applying domain randomization (Seed: %d)"), RandomStream.GetInitialSeed());

	// Clear previous state
	ClearDistractors();

	// Apply all randomization components
	RandomizeGround();
	RandomizeSky();
	RandomizeLighting();
	RandomizeVehicles();  // Professional training data: randomize vehicle positions
	SpawnDistractors();

	UE_LOG(LogDomainRandomization, Log, TEXT("Domain randomization complete"));
}

void ADomainRandomization::ApplyRandomizationWithSeed(int32 Seed)
{
	Config.RandomSeed = Seed;
	ApplyRandomization();
}

void ADomainRandomization::RandomizeGround()
{
	// Ground randomization disabled - no ground component
	// Use separate static mesh actors in your level for ground planes
	UE_LOG(LogDomainRandomization, Verbose, 
		TEXT("RandomizeGround() called but ground component removed - use level meshes"));
}

void ADomainRandomization::RandomizeSky()
{
	if (!Config.Sky.bRandomizeColor)
	{
		return;
	}

	// Find sky light in scene
	ASkyLight* SkyLight = nullptr;
	for (TActorIterator<ASkyLight> It(GetWorld()); It; ++It)
	{
		SkyLight = *It;
		break;
	}

	if (SkyLight && SkyLight->GetLightComponent())
	{
		// Select random color from palette
		if (Config.Sky.SkyColorPalette.Num() > 0)
		{
			int32 ColorIndex = RandomStream.RandRange(0, Config.Sky.SkyColorPalette.Num() - 1);
			FLinearColor SkyColor = Config.Sky.SkyColorPalette[ColorIndex];
			
			// Apply with slight randomization
			SkyColor.R += GetRandomFloat(-0.1f, 0.1f);
			SkyColor.G += GetRandomFloat(-0.1f, 0.1f);
			SkyColor.B += GetRandomFloat(-0.1f, 0.1f);
			SkyColor = SkyColor.GetClamped();

			SkyLight->GetLightComponent()->SetLightColor(SkyColor);

			UE_LOG(LogDomainRandomization, Verbose, 
				TEXT("Sky color set to palette index %d with variation"), ColorIndex);
		}

		// Randomize sky light intensity
		float SkyIntensity = GetRandomFloat(0.5f, 2.0f);
		SkyLight->GetLightComponent()->SetIntensity(SkyIntensity);
	}
	else
	{
		UE_LOG(LogDomainRandomization, Verbose, 
			TEXT("No SkyLight found in scene - sky randomization skipped"));
	}
}

void ADomainRandomization::RandomizeLighting()
{
	if (!Config.Lighting.bEnabled)
	{
		return;
	}

	ADirectionalLight* Sun = FindDirectionalLight();
	if (!Sun || !Sun->GetComponent())
	{
		UE_LOG(LogDomainRandomization, Warning, 
			TEXT("No DirectionalLight found in scene"));
		return;
	}

	UDirectionalLightComponent* LightComp = Sun->GetComponent();

	// Randomize intensity
	float Intensity = GetRandomFloat(
		Config.Lighting.IntensityRange.X,
		Config.Lighting.IntensityRange.Y);
	LightComp->SetIntensity(Intensity);

	// Randomize sun angle (elevation and azimuth)
	float Elevation = GetRandomFloat(
		Config.Lighting.ElevationRange.X,
		Config.Lighting.ElevationRange.Y);
	float Azimuth = GetRandomFloat(
		Config.Lighting.AzimuthRange.X,
		Config.Lighting.AzimuthRange.Y);
	
	// Convert to rotation (pitch = elevation, yaw = azimuth)
	FRotator SunRotation(-Elevation, Azimuth, 0.0f);
	Sun->SetActorRotation(SunRotation);

	// Randomize color temperature
	float Temperature = GetRandomFloat(
		Config.Lighting.TemperatureRange.X,
		Config.Lighting.TemperatureRange.Y);
	FLinearColor LightColor = FLinearColor::MakeFromColorTemperature(Temperature);
	LightComp->SetLightColor(LightColor);

	// Randomize shadow intensity if enabled
	if (Config.Lighting.bRandomizeShadows)
	{
		float ShadowIntensity = GetRandomFloat(
			Config.Lighting.ShadowIntensityRange.X,
			Config.Lighting.ShadowIntensityRange.Y);
		LightComp->SetShadowAmount(ShadowIntensity);
	}

	UE_LOG(LogDomainRandomization, Log, 
		TEXT("Lighting: Intensity=%.2f, Elevation=%.1f, Azimuth=%.1f, Temp=%.0fK"),
		Intensity, Elevation, Azimuth, Temperature);
}

void ADomainRandomization::SpawnDistractors()
{
	if (!Config.Distractors.bEnabled)
	{
		return;
	}

	int32 NumDistractors = RandomStream.RandRange(
		Config.Distractors.CountRange.X,
		Config.Distractors.CountRange.Y);

	for (int32 i = 0; i < NumDistractors; ++i)
	{
		AActor* Distractor = SpawnSingleDistractor();
		if (Distractor)
		{
			SpawnedDistractors.Add(Distractor);
		}
	}

	UE_LOG(LogDomainRandomization, Log, 
		TEXT("Spawned %d distractor objects"), SpawnedDistractors.Num());
}

AActor* ADomainRandomization::SpawnSingleDistractor()
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return nullptr;
	}

	// Select random shape mesh
	FString MeshPath;
	if (Config.Distractors.bRandomShapes)
	{
		int32 ShapeIndex = RandomStream.RandRange(0, 2);
		switch (ShapeIndex)
		{
			case 0: MeshPath = TEXT("/Engine/BasicShapes/Cube.Cube"); break;
			case 1: MeshPath = TEXT("/Engine/BasicShapes/Sphere.Sphere"); break;
			case 2: MeshPath = TEXT("/Engine/BasicShapes/Cylinder.Cylinder"); break;
		}
	}
	else
	{
		MeshPath = TEXT("/Engine/BasicShapes/Cube.Cube");
	}

	UStaticMesh* Mesh = Cast<UStaticMesh>(
		StaticLoadObject(UStaticMesh::StaticClass(), nullptr, *MeshPath));
	if (!Mesh)
	{
		return nullptr;
	}

	// Calculate random position
	float Distance = GetRandomFloat(
		Config.Distractors.DistanceRange.X,
		Config.Distractors.DistanceRange.Y);
	float Angle = GetRandomFloat(0.0f, 360.0f);
	float Height = GetRandomFloat(
		Config.Distractors.HeightRange.X,
		Config.Distractors.HeightRange.Y);

	FVector Location = GetActorLocation() + FVector(
		Distance * FMath::Cos(FMath::DegreesToRadians(Angle)),
		Distance * FMath::Sin(FMath::DegreesToRadians(Angle)),
		Height);

	// Random rotation
	FRotator Rotation(
		GetRandomFloat(0.0f, 360.0f),
		GetRandomFloat(0.0f, 360.0f),
		GetRandomFloat(0.0f, 360.0f));

	// Random scale
	float Scale = GetRandomFloat(
		Config.Distractors.ScaleRange.X,
		Config.Distractors.ScaleRange.Y);

	// Spawn static mesh actor
	FActorSpawnParameters SpawnParams;
	SpawnParams.SpawnCollisionHandlingOverride = 
		ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButAlwaysSpawn;

	AStaticMeshActor* DistractorActor = World->SpawnActor<AStaticMeshActor>(
		AStaticMeshActor::StaticClass(), Location, Rotation, SpawnParams);

	if (DistractorActor)
	{
		UStaticMeshComponent* MeshComp = DistractorActor->GetStaticMeshComponent();
		MeshComp->SetStaticMesh(Mesh);
		MeshComp->SetWorldScale3D(FVector(Scale));

		// Random color if enabled
		if (Config.Distractors.bRandomColors)
		{
			UMaterialInstanceDynamic* DynMat = MeshComp->CreateAndSetMaterialInstanceDynamic(0);
			if (DynMat)
			{
				FLinearColor RandomColor(
					GetRandomFloat(0.0f, 1.0f),
					GetRandomFloat(0.0f, 1.0f),
					GetRandomFloat(0.0f, 1.0f));
				DynMat->SetVectorParameterValue(FName("BaseColor"), RandomColor);
			}
		}

		// Tag as distractor for annotation exclusion
		DistractorActor->Tags.Add(FName("Distractor"));
	}

	return DistractorActor;
}

void ADomainRandomization::ClearDistractors()
{
	for (AActor* Distractor : SpawnedDistractors)
	{
		if (Distractor && Distractor->IsValidLowLevel())
		{
			Distractor->Destroy();
		}
	}

	int32 ClearedCount = SpawnedDistractors.Num();
	SpawnedDistractors.Empty();

	if (ClearedCount > 0)
	{
		UE_LOG(LogDomainRandomization, Verbose, 
			TEXT("Cleared %d distractor objects"), ClearedCount);
	}
}

void ADomainRandomization::ResetScene()
{
	ClearDistractors();

	UE_LOG(LogDomainRandomization, Log, TEXT("Scene reset to default state"));
}

ADirectionalLight* ADomainRandomization::FindDirectionalLight() const
{
	for (TActorIterator<ADirectionalLight> It(GetWorld()); It; ++It)
	{
		return *It;
	}
	return nullptr;
}

float ADomainRandomization::GetRandomFloat(float Min, float Max)
{
	return RandomStream.FRandRange(Min, Max);
}

FLinearColor ADomainRandomization::GetRandomColor(const FLinearColor& Min, const FLinearColor& Max)
{
	return FLinearColor(
		GetRandomFloat(Min.R, Max.R),
		GetRandomFloat(Min.G, Max.G),
		GetRandomFloat(Min.B, Max.B),
		1.0f);
}

FVector ADomainRandomization::GetRandomVector(const FVector& Min, const FVector& Max)
{
	return FVector(
		GetRandomFloat(Min.X, Max.X),
		GetRandomFloat(Min.Y, Max.Y),
		GetRandomFloat(Min.Z, Max.Z));
}

// ============================================================================
// Vehicle Randomization System - Professional Training Data Generation
// ============================================================================

void ADomainRandomization::AutoDiscoverVehicles()
{
	RegisteredVehicles.Empty();
	OriginalVehicleTransforms.Empty();

	// Find all actors with "Vehicle" tag in scene
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}

	for (TActorIterator<AActor> It(World); It; ++It)
	{
		AActor* Actor = *It;
		if (Actor && Actor->ActorHasTag(FName("Vehicle")))
		{
			RegisteredVehicles.Add(Actor);
			OriginalVehicleTransforms.Add(Actor->GetTransform());
		}
	}

	UE_LOG(LogDomainRandomization, Log, 
		TEXT("Auto-discovered %d vehicles with 'Vehicle' tag"), RegisteredVehicles.Num());
}

void ADomainRandomization::RegisterVehicle(AActor* Vehicle)
{
	if (!Vehicle)
	{
		return;
	}

	if (!RegisteredVehicles.Contains(Vehicle))
	{
		RegisteredVehicles.Add(Vehicle);
		OriginalVehicleTransforms.Add(Vehicle->GetTransform());
		
		// Ensure vehicle has tag for annotation
		if (!Vehicle->ActorHasTag(FName("Vehicle")))
		{
			Vehicle->Tags.Add(FName("Vehicle"));
		}

		UE_LOG(LogDomainRandomization, Log, 
			TEXT("Registered vehicle: %s (Total: %d)"), 
			*Vehicle->GetName(), RegisteredVehicles.Num());
	}
}

void ADomainRandomization::UnregisterVehicle(AActor* Vehicle)
{
	if (!Vehicle)
	{
		return;
	}

	int32 Index = RegisteredVehicles.IndexOfByKey(Vehicle);
	if (Index != INDEX_NONE)
	{
		RegisteredVehicles.RemoveAt(Index);
		if (OriginalVehicleTransforms.IsValidIndex(Index))
		{
			OriginalVehicleTransforms.RemoveAt(Index);
		}

		UE_LOG(LogDomainRandomization, Log, 
			TEXT("Unregistered vehicle: %s"), *Vehicle->GetName());
	}
}

bool ADomainRandomization::IsPositionValid(const FVector& Position, float MinSpacing, 
	const TArray<FVector>& OccupiedPositions) const
{
	for (const FVector& Occupied : OccupiedPositions)
	{
		float Distance = FVector::Dist2D(Position, Occupied);
		if (Distance < MinSpacing)
		{
			return false;
		}
	}
	return true;
}

void ADomainRandomization::RandomizeVehicles()
{
	if (!Config.Vehicles.bEnabled)
	{
		UE_LOG(LogDomainRandomization, Verbose, 
			TEXT("Vehicle randomization disabled"));
		return;
	}

	// Auto-discover vehicles if none registered
	if (RegisteredVehicles.Num() == 0)
	{
		AutoDiscoverVehicles();
	}

	if (RegisteredVehicles.Num() == 0)
	{
		UE_LOG(LogDomainRandomization, Warning, 
			TEXT("No vehicles registered for randomization"));
		return;
	}

	// Calculate spawn area bounds
	FVector SpawnCenter = GetActorLocation();
	float HalfWidth = Config.Vehicles.SpawnAreaSize.X / 2.0f;
	float HalfLength = Config.Vehicles.SpawnAreaSize.Y / 2.0f;

	TArray<FVector> OccupiedPositions;
	int32 RandomizedCount = 0;
	int32 HiddenCount = 0;

	// Determine how many vehicles to show this frame
	int32 VehiclesToShow = RandomStream.RandRange(
		Config.Vehicles.CountRange.X,
		FMath::Min(Config.Vehicles.CountRange.Y, RegisteredVehicles.Num()));

	// Shuffle vehicle indices for random selection
	TArray<int32> VehicleIndices;
	for (int32 i = 0; i < RegisteredVehicles.Num(); ++i)
	{
		VehicleIndices.Add(i);
	}
	
	// Fisher-Yates shuffle
	for (int32 i = VehicleIndices.Num() - 1; i > 0; --i)
	{
		int32 j = RandomStream.RandRange(0, i);
		VehicleIndices.Swap(i, j);
	}

	for (int32 i = 0; i < RegisteredVehicles.Num(); ++i)
	{
		AActor* Vehicle = RegisteredVehicles[VehicleIndices[i]];
		if (!Vehicle || !Vehicle->IsValidLowLevel())
		{
			continue;
		}

		// Hide vehicles beyond the count limit
		if (i >= VehiclesToShow)
		{
			Vehicle->SetActorHiddenInGame(true);
			HiddenCount++;
			continue;
		}

		// Show and randomize this vehicle
		Vehicle->SetActorHiddenInGame(false);

		// Try to find valid position (avoid overlaps)
		FVector NewPosition;
		bool bFoundValid = false;
		int32 MaxAttempts = 50;

		for (int32 Attempt = 0; Attempt < MaxAttempts && !bFoundValid; ++Attempt)
		{
			NewPosition = SpawnCenter + FVector(
				GetRandomFloat(-HalfWidth, HalfWidth),
				GetRandomFloat(-HalfLength, HalfLength),
				Config.Vehicles.GroundOffset);

			bFoundValid = IsPositionValid(NewPosition, Config.Vehicles.MinSpacing, OccupiedPositions);
		}

		if (bFoundValid)
		{
			OccupiedPositions.Add(NewPosition);
			Vehicle->SetActorLocation(NewPosition);

			// Random rotation (typically just yaw for vehicles)
			float NewYaw = GetRandomFloat(
				Config.Vehicles.RotationRange.X,
				Config.Vehicles.RotationRange.Y);
			FRotator NewRotation(0.0f, NewYaw, 0.0f);
			Vehicle->SetActorRotation(NewRotation);

			// Random scale variation if enabled
			if (Config.Vehicles.ScaleRange.X != Config.Vehicles.ScaleRange.Y)
			{
				float ScaleFactor = GetRandomFloat(
					Config.Vehicles.ScaleRange.X,
					Config.Vehicles.ScaleRange.Y);
				Vehicle->SetActorScale3D(FVector(ScaleFactor));
			}

			RandomizedCount++;
		}
		else
		{
			// Could not find valid position - hide this vehicle
			Vehicle->SetActorHiddenInGame(true);
			HiddenCount++;
		}
	}

	UE_LOG(LogDomainRandomization, Log, 
		TEXT("Vehicle randomization: %d positioned, %d hidden (area: %.0fx%.0f cm)"),
		RandomizedCount, HiddenCount, 
		Config.Vehicles.SpawnAreaSize.X, Config.Vehicles.SpawnAreaSize.Y);
}

FVector ADomainRandomization::GetRandomVehicleLocation() const
{
	// Return location of a random visible vehicle (for camera targeting)
	TArray<AActor*> VisibleVehicles;

	for (AActor* Vehicle : RegisteredVehicles)
	{
		if (Vehicle && Vehicle->IsValidLowLevel() && !Vehicle->IsHidden())
		{
			VisibleVehicles.Add(Vehicle);
		}
	}

	if (VisibleVehicles.Num() > 0)
	{
		int32 RandomIndex = FMath::RandRange(0, VisibleVehicles.Num() - 1);
		FVector VehicleLocation = VisibleVehicles[RandomIndex]->GetActorLocation();
		
		// Offset to look at center of vehicle (approximate)
		VehicleLocation.Z += 100.0f;

		UE_LOG(LogDomainRandomization, Verbose, 
			TEXT("Random vehicle target: %s at (%s)"), 
			*VisibleVehicles[RandomIndex]->GetName(),
			*VehicleLocation.ToString());

		return VehicleLocation;
	}

	// Fallback to scene center
	return GetActorLocation();
}

void ADomainRandomization::ResetVehicles()
{
	if (RegisteredVehicles.Num() != OriginalVehicleTransforms.Num())
	{
		UE_LOG(LogDomainRandomization, Warning, 
			TEXT("Vehicle/transform count mismatch - cannot reset"));
		return;
	}

	for (int32 i = 0; i < RegisteredVehicles.Num(); ++i)
	{
		AActor* Vehicle = RegisteredVehicles[i];
		if (Vehicle && Vehicle->IsValidLowLevel())
		{
			Vehicle->SetActorTransform(OriginalVehicleTransforms[i]);
			Vehicle->SetActorHiddenInGame(false);
		}
	}

	UE_LOG(LogDomainRandomization, Log, 
		TEXT("Reset %d vehicles to original positions"), RegisteredVehicles.Num());
}

