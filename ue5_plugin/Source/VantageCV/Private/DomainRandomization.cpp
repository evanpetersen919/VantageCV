/******************************************************************************
 * VantageCV - Domain Randomization Controller Implementation
 ******************************************************************************
 * File: DomainRandomization.cpp
 * Description: Implementation of Structured Domain Randomization (SDR) for
 *              computer vision research. Provides research-grade randomization
 *              of visual elements to enable sim-to-real transfer learning.
 * 
 * Research References:
 * - Tobin et al. (2017) "Domain Randomization for Sim-to-Real Transfer"
 * - Tremblay et al. (2018) "Training Deep Networks with Synthetic Data"
 * - Kar et al. (2019) "Meta-Sim: Learning to Generate Synthetic Datasets"
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
#include "Camera/CameraComponent.h"
#include "Engine/LocalPlayer.h"
#include "GameFramework/PlayerController.h"

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

	// Suppress spammy Nanite material warnings
	UE_SET_LOG_VERBOSITY(LogStaticMesh, Error);

	InitializeDefaultPalettes();

	// CRITICAL: Discover and lock vehicle scales IMMEDIATELY at startup
	// This captures the correct editor-placed scales before anything can corrupt them
	InitializeVehicleSystem();

	UE_LOG(LogDomainRandomization, Log, 
		TEXT("Domain Randomization Controller initialized"));
}

void ADomainRandomization::InitializeVehicleSystem()
{
	RegisteredVehicles.Empty();
	OriginalVehicleTransforms.Empty();

	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}

	// Find all actors with "Vehicle" tag
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		AActor* Actor = *It;
		if (Actor && Actor->ActorHasTag(FName("Vehicle")))
		{
			// Store the EDITOR-PLACED transform - this is the correct scale
			FTransform OriginalTransform = Actor->GetTransform();
			RegisteredVehicles.Add(Actor);
			OriginalVehicleTransforms.Add(OriginalTransform);

			// IMMEDIATELY hide all vehicles - they start hidden
			Actor->SetActorHiddenInGame(true);
			
			FVector Scale = OriginalTransform.GetScale3D();
			UE_LOG(LogDomainRandomization, Log, 
				TEXT("  Vehicle locked: %s (Scale: %.2f, %.2f, %.2f) - HIDDEN"), 
				*Actor->GetName(), Scale.X, Scale.Y, Scale.Z);
		}
	}

	bVehiclesInitialized = true;
	UE_LOG(LogDomainRandomization, Log, 
		TEXT("Vehicle system initialized: %d vehicles locked and hidden"), 
		RegisteredVehicles.Num());
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

	// Randomize intensity - ENFORCE MINIMUM 50.0 for proper capture exposure
	float MinIntensity = FMath::Max(Config.Lighting.IntensityRange.X, 50.0f);
	float MaxIntensity = FMath::Max(Config.Lighting.IntensityRange.Y, 100.0f);
	float Intensity = GetRandomFloat(MinIntensity, MaxIntensity);
	LightComp->SetIntensity(Intensity);
	UE_LOG(LogDomainRandomization, Log, TEXT("Set DirectionalLight intensity to %.1f"), Intensity);

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

void ADomainRandomization::SetDistractorsEnabled(bool bEnabled)
{
	Config.Distractors.bEnabled = bEnabled;
	UE_LOG(LogDomainRandomization, Log, 
		TEXT("Distractors %s"), bEnabled ? TEXT("ENABLED") : TEXT("DISABLED"));
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
	// If already initialized at BeginPlay, don't re-discover (preserves locked scales)
	if (bVehiclesInitialized && RegisteredVehicles.Num() > 0)
	{
		UE_LOG(LogDomainRandomization, Verbose, 
			TEXT("Vehicles already initialized (%d), skipping re-discovery"), 
			RegisteredVehicles.Num());
		return;
	}

	// Fallback discovery if BeginPlay didn't run yet
	InitializeVehicleSystem();
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

// ============================================================================
// AUTHORITATIVE VEHICLE CLEANUP (MANDATORY)
// ============================================================================
// This is the ONLY function that guarantees all vehicles are hidden.
// It performs a WORLD SWEEP regardless of registration status.
// Python MUST call this after each capture.
// ============================================================================

int32 ADomainRandomization::HideAllVehicles()
{
	UE_LOG(LogDomainRandomization, Log, 
		TEXT("=== AUTHORITATIVE CLEANUP: HideAllVehicles ==="));

	int32 HiddenCount = 0;
	int32 FailedCount = 0;
	const float UndergroundZ = -100000.0f;  // 1km below ground

	UWorld* World = GetWorld();
	if (!World)
	{
		UE_LOG(LogDomainRandomization, Error, 
			TEXT("FATAL: HideAllVehicles - World is null"));
		return 0;
	}

	// WORLD SWEEP: Iterate ALL actors with "Vehicle" tag
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		AActor* Actor = *It;
		if (Actor && Actor->ActorHasTag(FName("Vehicle")))
		{
			// Perform HARD CLEANUP:
			// 1. Hide
			// 2. Disable collision
			// 3. Move underground
			Actor->SetActorHiddenInGame(true);
			Actor->SetActorEnableCollision(false);
			
			FVector CurrentLoc = Actor->GetActorLocation();
			Actor->SetActorLocation(FVector(CurrentLoc.X, CurrentLoc.Y, UndergroundZ));
			
			HiddenCount++;
			
			UE_LOG(LogDomainRandomization, Verbose, 
				TEXT("  Hidden: %s"), *Actor->GetName());
		}
	}

	// Also ensure RegisteredVehicles are all hidden (belt + suspenders)
	for (AActor* Vehicle : RegisteredVehicles)
	{
		if (Vehicle && Vehicle->IsValidLowLevel() && !Vehicle->IsHidden())
		{
			Vehicle->SetActorHiddenInGame(true);
			Vehicle->SetActorEnableCollision(false);
			
			FVector CurrentLoc = Vehicle->GetActorLocation();
			Vehicle->SetActorLocation(FVector(CurrentLoc.X, CurrentLoc.Y, UndergroundZ));
			
			FailedCount++;  // This means world sweep missed something!
			
			UE_LOG(LogDomainRandomization, Warning, 
				TEXT("  LEAKED from RegisteredVehicles: %s"), *Vehicle->GetName());
		}
	}

	// VERIFICATION
	int32 StillVisible = GetVisibleVehicleCountWorldSweep();
	if (StillVisible > 0)
	{
		UE_LOG(LogDomainRandomization, Error, 
			TEXT("FATAL: HideAllVehicles FAILED - %d vehicles still visible!"), StillVisible);
	}
	else
	{
		UE_LOG(LogDomainRandomization, Log, 
			TEXT("=== CLEANUP VERIFIED: %d vehicles hidden, 0 visible ==="), HiddenCount);
	}

	return HiddenCount;
}

int32 ADomainRandomization::GetVisibleVehicleCountWorldSweep() const
{
	int32 VisibleCount = 0;
	TArray<FString> VisibleActorNames;

	UWorld* World = GetWorld();
	if (!World)
	{
		return 0;
	}

	// WORLD SWEEP: Check ALL actors with "Vehicle" tag
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		AActor* Actor = *It;
		if (Actor && Actor->ActorHasTag(FName("Vehicle")))
		{
			if (!Actor->IsHidden())
			{
				VisibleCount++;
				VisibleActorNames.Add(Actor->GetName());
			}
		}
	}

	if (VisibleCount > 0)
	{
		FString ActorList = FString::Join(VisibleActorNames, TEXT(", "));
		UE_LOG(LogDomainRandomization, Error, 
			TEXT("VEHICLE LEAK DETECTED: %d visible [%s]"), VisibleCount, *ActorList);
	}

	return VisibleCount;
}

// ============================================================================
// RESEARCH-GRADE VISIBILITY VALIDATION
// ============================================================================
// Implements frustum culling and visibility percentage calculation
// Vehicles with <50% visibility are hidden to ensure clean training data
// Based on: Tremblay et al. "Training Deep Networks with Synthetic Data"
// ============================================================================

float ADomainRandomization::CalculateVisibilityPercentage(AActor* Vehicle, const FVector& CameraLocation, const FRotator& CameraRotation, float FOV) const
{
	if (!Vehicle)
	{
		return 0.0f;
	}

	// Get vehicle bounding box corners
	FVector Origin, Extent;
	Vehicle->GetActorBounds(false, Origin, Extent);
	
	// Calculate 8 corners of bounding box
	TArray<FVector> Corners;
	Corners.Add(Origin + FVector(-Extent.X, -Extent.Y, -Extent.Z));
	Corners.Add(Origin + FVector(-Extent.X, -Extent.Y,  Extent.Z));
	Corners.Add(Origin + FVector(-Extent.X,  Extent.Y, -Extent.Z));
	Corners.Add(Origin + FVector(-Extent.X,  Extent.Y,  Extent.Z));
	Corners.Add(Origin + FVector( Extent.X, -Extent.Y, -Extent.Z));
	Corners.Add(Origin + FVector( Extent.X, -Extent.Y,  Extent.Z));
	Corners.Add(Origin + FVector( Extent.X,  Extent.Y, -Extent.Z));
	Corners.Add(Origin + FVector( Extent.X,  Extent.Y,  Extent.Z));
	
	// Count corners within camera frustum
	int32 VisibleCorners = 0;
	float HalfFOVRad = FMath::DegreesToRadians(FOV / 2.0f);
	
	// Calculate camera forward and right vectors
	FVector CameraForward = CameraRotation.Vector();
	FVector CameraRight = FRotationMatrix(CameraRotation).GetUnitAxis(EAxis::Y);
	FVector CameraUp = FRotationMatrix(CameraRotation).GetUnitAxis(EAxis::Z);
	
	for (const FVector& Corner : Corners)
	{
		FVector ToCorner = (Corner - CameraLocation).GetSafeNormal();
		
		// Check if corner is in front of camera
		float ForwardDot = FVector::DotProduct(ToCorner, CameraForward);
		if (ForwardDot < 0.0f)
		{
			continue;  // Behind camera
		}
		
		// Check horizontal angle (use slightly wider margin - 60% of FOV as border)
		float HorizontalAngle = FMath::Acos(FMath::Abs(FVector::DotProduct(ToCorner, CameraRight)));
		float EffectiveFOV = HalfFOVRad * 0.8f;  // 80% of half-FOV = 40% border on each side
		
		if (FMath::Abs(FMath::Acos(ForwardDot)) < EffectiveFOV)
		{
			VisibleCorners++;
		}
	}
	
	// Return percentage of visible corners
	return (float)VisibleCorners / 8.0f * 100.0f;
}

bool ADomainRandomization::IsVehicleInSpawnBounds(const FVector& Position, const FVector& SpawnCenter, float HalfWidth, float HalfLength, float Margin) const
{
	// Check if vehicle position is within spawn bounds with margin
	// Margin ensures vehicle bounding box doesn't extend outside spawn area
	float EffectiveHalfWidth = HalfWidth - Margin;
	float EffectiveHalfLength = HalfLength - Margin;
	
	float DeltaX = FMath::Abs(Position.X - SpawnCenter.X);
	float DeltaY = FMath::Abs(Position.Y - SpawnCenter.Y);
	
	return (DeltaX < EffectiveHalfWidth) && (DeltaY < EffectiveHalfLength);
}

// Structure to track placed vehicles with their bounding boxes
struct FPlacedVehicle
{
	FVector Position;
	FBox BoundingBox;
	float Radius;  // Simplified collision radius
};

bool ADomainRandomization::IsPositionValidForVehicle(AActor* Vehicle, const FVector& Position, 
	const TArray<FPlacedVehicle>& PlacedVehicles) const
{
	if (!Vehicle)
	{
		return false;
	}

	// Get this vehicle's bounding box
	FVector Origin, Extent;
	Vehicle->GetActorBounds(false, Origin, Extent);
	
	// Calculate collision radius (use largest XY extent + safety margin)
	float ThisRadius = FMath::Max(Extent.X, Extent.Y) + 200.0f;  // 2m safety margin
	
	// Check against all placed vehicles
	for (const FPlacedVehicle& Placed : PlacedVehicles)
	{
		float Distance = FVector::Dist2D(Position, Placed.Position);
		float MinRequired = ThisRadius + Placed.Radius;
		
		if (Distance < MinRequired)
		{
			return false;
		}
	}
	
	// Also check minimum spacing from config as fallback
	float ConfigSpacing = Config.Vehicles.MinSpacing;
	for (const FPlacedVehicle& Placed : PlacedVehicles)
	{
		float Distance = FVector::Dist2D(Position, Placed.Position);
		if (Distance < ConfigSpacing)
		{
			return false;
		}
	}
	
	return true;
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

	// FORCE initialization if not done yet (BeginPlay might run too early)
	if (!bVehiclesInitialized || RegisteredVehicles.Num() == 0)
	{
		UE_LOG(LogDomainRandomization, Warning, 
			TEXT("Vehicles not initialized, forcing initialization now..."));
		InitializeVehicleSystem();
	}

	if (RegisteredVehicles.Num() == 0)
	{
		UE_LOG(LogDomainRandomization, Error, 
			TEXT("No vehicles found with 'Vehicle' tag - cannot randomize"));
		return;
	}

	UE_LOG(LogDomainRandomization, Log, 
		TEXT("=== Starting Vehicle Randomization (Total: %d) ==="), 
		RegisteredVehicles.Num());

	// =========================================================================
	// STEP 1: MOVE ALL VEHICLES UNDERGROUND (instead of just hiding)
	// This ensures camera never picks them up even if visibility fails
	// =========================================================================
	const float UndergroundZ = -10000.0f;  // 100 meters underground
	int32 HiddenCount = 0;
	
	for (int32 i = 0; i < RegisteredVehicles.Num(); ++i)
	{
		AActor* Vehicle = RegisteredVehicles[i];
		if (!Vehicle || !Vehicle->IsValidLowLevel())
		{
			continue;
		}
		
		// CRITICAL: Restore LOCKED scale from BeginPlay/initialization
		if (OriginalVehicleTransforms.IsValidIndex(i))
		{
			FVector LockedScale = OriginalVehicleTransforms[i].GetScale3D();
			FVector CurrentScale = Vehicle->GetActorScale3D();
			
			// Log if scale has been corrupted
			if (!CurrentScale.Equals(LockedScale, 0.01f))
			{
				UE_LOG(LogDomainRandomization, Warning, 
					TEXT("  %s scale corrupted! Current:(%.2f,%.2f,%.2f) -> Restoring:(%.2f,%.2f,%.2f)"), 
					*Vehicle->GetName(),
					CurrentScale.X, CurrentScale.Y, CurrentScale.Z,
					LockedScale.X, LockedScale.Y, LockedScale.Z);
			}
			
			Vehicle->SetActorScale3D(LockedScale);
		}
		
		// Move vehicle UNDERGROUND - completely out of camera view
		FVector CurrentLoc = Vehicle->GetActorLocation();
		Vehicle->SetActorLocation(FVector(CurrentLoc.X, CurrentLoc.Y, UndergroundZ));
		Vehicle->SetActorHiddenInGame(true);
		Vehicle->SetActorEnableCollision(false);
		HiddenCount++;
	}

	UE_LOG(LogDomainRandomization, Log, 
		TEXT("  Step 1: All %d vehicles moved underground (Z=%.0f) and scales restored"), 
		HiddenCount, UndergroundZ);

	// =========================================================================
	// STEP 2: Calculate spawn parameters - use EXACT ground Z from spawn center
	// =========================================================================
	FVector SpawnCenter = GetActorLocation();
	float GroundZ = SpawnCenter.Z + Config.Vehicles.GroundOffset;  // Exact Z for ALL vehicles
	float HalfWidth = Config.Vehicles.SpawnAreaSize.X / 2.0f;
	float HalfLength = Config.Vehicles.SpawnAreaSize.Y / 2.0f;

	UE_LOG(LogDomainRandomization, Log, 
		TEXT("  Step 2: Ground Z = %.1f (SpawnCenter.Z=%.1f + Offset=%.1f)"), 
		GroundZ, SpawnCenter.Z, Config.Vehicles.GroundOffset);

	TArray<FVector> OccupiedPositions;
	int32 RandomizedCount = 0;

	// Determine how many vehicles to show this frame
	int32 VehiclesToShow = RandomStream.RandRange(
		Config.Vehicles.CountRange.X,
		FMath::Min(Config.Vehicles.CountRange.Y, RegisteredVehicles.Num()));

	// =========================================================================
	// STEP 3: Shuffle vehicle indices for random selection
	// =========================================================================
	TArray<int32> VehicleIndices;
	for (int32 i = 0; i < RegisteredVehicles.Num(); ++i)
	{
		VehicleIndices.Add(i);
	}
	
	// Fisher-Yates shuffle for unbiased randomization
	for (int32 i = VehicleIndices.Num() - 1; i > 0; --i)
	{
		int32 j = RandomStream.RandRange(0, i);
		VehicleIndices.Swap(i, j);
	}

	// =========================================================================
	// STEP 4: GRID-BASED PLACEMENT - CENTER SLOTS with adaptive camera zoom
	// =========================================================================
	// Use center grid slots - camera zoom adapts to vehicle count
	// 1 vehicle = close zoom, 5 vehicles = wide zoom to capture all
	// =========================================================================
	
	const float GRID_SPACING = 3000.0f;  // 30 meters between grid slots (tighter for better framing)
	
	// Create ONLY CENTER 5 slots (cross pattern)
	TArray<FVector> GridSlots;
	GridSlots.Add(SpawnCenter + FVector(0.0f, -GRID_SPACING, 0.0f));      // North
	GridSlots.Add(SpawnCenter + FVector(-GRID_SPACING, 0.0f, 0.0f));      // West
	GridSlots.Add(SpawnCenter + FVector(0.0f, 0.0f, 0.0f));               // CENTER
	GridSlots.Add(SpawnCenter + FVector(GRID_SPACING, 0.0f, 0.0f));       // East
	GridSlots.Add(SpawnCenter + FVector(0.0f, GRID_SPACING, 0.0f));       // South
	
	// Shuffle center slots for variety
	for (int32 i = GridSlots.Num() - 1; i > 0; --i)
	{
		int32 j = RandomStream.RandRange(0, i);
		GridSlots.Swap(i, j);
	}
	
	// Cap vehicles to 5 max (one per center slot)
	VehiclesToShow = FMath::Min(VehiclesToShow, GridSlots.Num());
	
	UE_LOG(LogDomainRandomization, Log, 
		TEXT("  Step 4: Placing %d vehicles in CENTER grid (30m spacing, camera will adapt)"), VehiclesToShow);
	
	// Place vehicles in center grid slots
	int32 SlotIndex = 0;
	for (int32 i = 0; i < VehiclesToShow && i < VehicleIndices.Num() && SlotIndex < GridSlots.Num(); ++i)
	{
		int32 VehicleIndex = VehicleIndices[i];
		AActor* Vehicle = RegisteredVehicles[VehicleIndex];
		if (!Vehicle || !Vehicle->IsValidLowLevel())
		{
			continue;
		}

		// Get the next available center grid slot
		FVector SlotPosition = GridSlots[SlotIndex];
		SlotPosition.Z = GroundZ;
		SlotIndex++;
		
		// Small random offset (max 5m) for variety
		float OffsetX = GetRandomFloat(-500.0f, 500.0f);
		float OffsetY = GetRandomFloat(-500.0f, 500.0f);
		FVector FinalPosition = SlotPosition + FVector(OffsetX, OffsetY, 0.0f);
		
		// Get locked scale
		FVector LockedScale = OriginalVehicleTransforms[VehicleIndex].GetScale3D();
		
		// Set position
		Vehicle->SetActorLocation(FinalPosition);

		// Random rotation
		float NewYaw = GetRandomFloat(
			Config.Vehicles.RotationRange.X,
			Config.Vehicles.RotationRange.Y);
		Vehicle->SetActorRotation(FRotator(0.0f, NewYaw, 0.0f));

		// Show vehicle
		Vehicle->SetActorHiddenInGame(false);
		Vehicle->SetActorEnableCollision(true);
		RandomizedCount++;
		
		UE_LOG(LogDomainRandomization, Log, 
			TEXT("  Slot %d: %s at (%.0f,%.0f)"), 
			SlotIndex, *Vehicle->GetName(), FinalPosition.X, FinalPosition.Y);
	}

	UE_LOG(LogDomainRandomization, Log, 
		TEXT("=== %d vehicles placed - Python will adapt camera zoom ==="),
		RandomizedCount);
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

int32 ADomainRandomization::GetVisibleVehicleCount()
{
	int32 VisibleCount = 0;
	
	for (AActor* Vehicle : RegisteredVehicles)
	{
		if (Vehicle && Vehicle->IsValidLowLevel() && !Vehicle->IsHidden())
		{
			VisibleCount++;
		}
	}
	
	UE_LOG(LogDomainRandomization, Log, TEXT("GetVisibleVehicleCount called: %d vehicles visible"), VisibleCount);
	return VisibleCount;
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

