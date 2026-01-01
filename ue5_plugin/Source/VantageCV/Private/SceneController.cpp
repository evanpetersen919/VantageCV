/******************************************************************************
 * VantageCV - Scene Controller Implementation
 ******************************************************************************
 * File: SceneController.cpp
 * Description: Implementation of scene randomization for synthetic data
 *              generation with lighting, materials, camera, and object control
 * Author: Evan Petersen
 * Date: December 2025
 *****************************************************************************/

#include "SceneController.h"
#include "Engine/DirectionalLight.h"
#include "Engine/PointLight.h"
#include "Engine/SpotLight.h"
#include "Engine/SkyLight.h"
#include "Engine/StaticMeshActor.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/SpotLightComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Kismet/GameplayStatics.h"
#include "EngineUtils.h"

DEFINE_LOG_CATEGORY_STATIC(LogSceneController, Log, All);

ASceneController::ASceneController()
{
	PrimaryActorTick.bCanEverTick = true;
}

void ASceneController::BeginPlay()
{
	Super::BeginPlay();
	UE_LOG(LogSceneController, Log, TEXT("SceneController initialized"));
}

void ASceneController::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);
}

void ASceneController::RandomizeLighting(float MinIntensity, float MaxIntensity, 
	float MinTemperature, float MaxTemperature)
{
	TArray<ALight*> Lights = GetSceneLights();
	
	for (ALight* Light : Lights)
	{
		if (!Light) continue;

		// Randomize intensity
		float RandomIntensity = FMath::RandRange(MinIntensity, MaxIntensity);
		
		// Randomize color temperature
		float RandomTemp = FMath::RandRange(MinTemperature, MaxTemperature);
		FLinearColor LightColor = FLinearColor::MakeFromColorTemperature(RandomTemp);

		if (ADirectionalLight* DirLight = Cast<ADirectionalLight>(Light))
		{
			UDirectionalLightComponent* LightComp = DirLight->GetComponent();
			if (LightComp)
			{
				LightComp->SetIntensity(RandomIntensity);
				LightComp->SetLightColor(LightColor);
				
				// Constrained sun rotation for DAYTIME ONLY
				// Pitch: -70 to -30 = sun 30-70 degrees above horizon (midday to afternoon)
				// Yaw: 0-360 = sun can be anywhere around the scene
				// Roll: 0 = no tilt
				float SunPitch = FMath::RandRange(-70.0f, -30.0f);  // Negative = sun above horizon
				float SunYaw = FMath::RandRange(0.0f, 360.0f);
				FRotator SunRotation = FRotator(SunPitch, SunYaw, 0.0f);
				DirLight->SetActorRotation(SunRotation);
				
				UE_LOG(LogSceneController, Verbose, TEXT("Sun rotation: Pitch=%.1f Yaw=%.1f"), SunPitch, SunYaw);
			}
		}
		else if (APointLight* PtLight = Cast<APointLight>(Light))
		{
			UPointLightComponent* LightComp = Cast<UPointLightComponent>(PtLight->GetLightComponent());
			if (LightComp)
			{
				LightComp->SetIntensity(RandomIntensity);
				LightComp->SetLightColor(LightColor);
			}
		}
		else if (ASpotLight* SpLight = Cast<ASpotLight>(Light))
		{
			USpotLightComponent* LightComp = Cast<USpotLightComponent>(SpLight->GetLightComponent());
			if (LightComp)
			{
				LightComp->SetIntensity(RandomIntensity);
				LightComp->SetLightColor(LightColor);
			}
		}
	}
	
	UE_LOG(LogSceneController, Log, TEXT("Randomized %d lights (Intensity: %.2f-%.2f, Temp: %.0fK-%.0fK)"), 
		Lights.Num(), MinIntensity, MaxIntensity, MinTemperature, MaxTemperature);
}

void ASceneController::RandomizeMaterials(const TArray<FString>& TargetTags)
{
	// Search by actor NAME instead of tags (more reliable with World Partition)
	TArray<AActor*> TargetActors;
	UWorld* World = GetWorld();
	
	if (World)
	{
		for (TActorIterator<AStaticMeshActor> It(World); It; ++It)
		{
			AStaticMeshActor* Actor = *It;
			FString ActorName = Actor->GetName();
			
			// Check if actor name contains any of the search patterns
			for (const FString& Pattern : TargetTags)
			{
				if (ActorName.Contains(Pattern))
				{
					TargetActors.Add(Actor);
					break;
				}
			}
		}
	}
	
	int32 ModifiedCount = 0;

	for (AActor* Actor : TargetActors)
	{
		if (!Actor) continue;

		TArray<UStaticMeshComponent*> MeshComponents;
		Actor->GetComponents<UStaticMeshComponent>(MeshComponents);

		for (UStaticMeshComponent* MeshComp : MeshComponents)
		{
			if (!MeshComp) continue;

			// Create dynamic material instance for randomization
			for (int32 i = 0; i < MeshComp->GetNumMaterials(); ++i)
			{
				UMaterialInterface* Material = MeshComp->GetMaterial(i);
				if (!Material) continue;

				UMaterialInstanceDynamic* DynMaterial = MeshComp->CreateAndSetMaterialInstanceDynamic(i);
				if (DynMaterial)
				{
					// Randomize material parameters for PCB-like surfaces (non-metallic, slightly rough)
					DynMaterial->SetScalarParameterValue(FName("Metallic"), FMath::RandRange(0.0f, 0.2f));  // PCBs are not metallic
					DynMaterial->SetScalarParameterValue(FName("Roughness"), FMath::RandRange(0.4f, 0.8f));  // Slightly rough fiberglass
					DynMaterial->SetScalarParameterValue(FName("Specular"), FMath::RandRange(0.3f, 0.6f));  // Moderate specular
					
					// Randomize base color tint (subtle variation)
					FLinearColor RandomTint = FLinearColor(
						FMath::RandRange(0.9f, 1.1f),
						FMath::RandRange(0.9f, 1.1f),
						FMath::RandRange(0.9f, 1.1f)
					);
					DynMaterial->SetVectorParameterValue(FName("BaseColorTint"), RandomTint);
					
					ModifiedCount++;
				}
			}
		}
	}
	
	UE_LOG(LogSceneController, Log, TEXT("Randomized materials on %d actors (%d materials modified)"), 
		TargetActors.Num(), ModifiedCount);
}

void ASceneController::RandomizeCamera(float MinDistance, float MaxDistance, float MinFOV, float MaxFOV)
{
	UWorld* World = GetWorld();
	if (!World) return;

	// Find player camera or spawn one
	APlayerCameraManager* CameraManager = UGameplayStatics::GetPlayerCameraManager(World, 0);
	if (!CameraManager) return;

	// Random spherical coordinates for camera placement
	float Distance = FMath::RandRange(MinDistance, MaxDistance);
	float Theta = FMath::RandRange(0.0f, 360.0f);
	float Phi = FMath::RandRange(-45.0f, 45.0f);

	FVector CameraLocation = FVector(
		Distance * FMath::Cos(FMath::DegreesToRadians(Theta)) * FMath::Cos(FMath::DegreesToRadians(Phi)),
		Distance * FMath::Sin(FMath::DegreesToRadians(Theta)) * FMath::Cos(FMath::DegreesToRadians(Phi)),
		Distance * FMath::Sin(FMath::DegreesToRadians(Phi))
	);

	// Look at origin (or target object)
	FRotator CameraRotation = (FVector::ZeroVector - CameraLocation).Rotation();
	
	CameraManager->SetActorLocationAndRotation(CameraLocation, CameraRotation);

	// Randomize FOV
	float RandomFOV = FMath::RandRange(MinFOV, MaxFOV);
	CameraManager->SetFOV(RandomFOV);
	
	UE_LOG(LogSceneController, Log, TEXT("Randomized camera (Dist: %.2f, FOV: %.2f, Rot: %s)"), 
		Distance, RandomFOV, *CameraRotation.ToString());
}

void ASceneController::SpawnRandomObjects(int32 NumObjects, const TArray<FString>& ObjectClasses)
{
	UWorld* World = GetWorld();
	if (!World || ObjectClasses.Num() == 0)
	{
		UE_LOG(LogSceneController, Warning, TEXT("Cannot spawn objects: Invalid world or empty ObjectClasses"));
		return;
	}

	FVector SpawnCenter = GetActorLocation();
	float SpawnRadius = 500.0f;

	for (int32 i = 0; i < NumObjects; ++i)
	{
		// Random object class from provided list
		const FString& ClassName = ObjectClasses[FMath::RandRange(0, ObjectClasses.Num() - 1)];
		
		// Random spawn location
		FVector SpawnLocation = GetRandomLocation(SpawnCenter, SpawnRadius);
		FRotator SpawnRotation = GetRandomRotation();

		// Spawn parameters
		FActorSpawnParameters SpawnParams;
		SpawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButAlwaysSpawn;

		// Note: In production, load actual asset classes from content browser
		// For now, spawn simple static mesh actors as placeholders
		AActor* SpawnedActor = World->SpawnActor<AActor>(AActor::StaticClass(), SpawnLocation, SpawnRotation, SpawnParams);
		
		if (SpawnedActor)
		{
			SpawnedActors.Add(SpawnedActor);
		}
	}
	
	UE_LOG(LogSceneController, Log, TEXT("Spawned %d objects from %d classes"), 
		NumObjects, ObjectClasses.Num());
}

void ASceneController::ClearSpawnedObjects()
{
	for (AActor* Actor : SpawnedActors)
	{
		if (Actor && Actor->IsValidLowLevel())
		{
			Actor->Destroy();
		}
	}
	
	int32 ClearedCount = SpawnedActors.Num();
	SpawnedActors.Empty();
	
	UE_LOG(LogSceneController, Log, TEXT("Cleared %d spawned objects"), ClearedCount);
}

void ASceneController::SetLightingPreset(const FString& PresetName)
{
	if (PresetName == TEXT("IndustrialLED"))
	{
		RandomizeLighting(50000.0f, 100000.0f, 5000.0f, 6500.0f);
	}
	else if (PresetName == TEXT("OutdoorSun"))
	{
		RandomizeLighting(80000.0f, 120000.0f, 5500.0f, 6500.0f);
	}
	else if (PresetName == TEXT("StudioSoft"))
	{
		RandomizeLighting(20000.0f, 40000.0f, 3200.0f, 4500.0f);
	}
	else
	{
		UE_LOG(LogSceneController, Warning, TEXT("Unknown lighting preset: %s"), *PresetName);
	}
}

TArray<ALight*> ASceneController::GetSceneLights() const
{
	TArray<ALight*> Lights;
	UWorld* World = GetWorld();
	if (!World) return Lights;

	// Find all light types (Point, Spot, Directional)
	for (TActorIterator<APointLight> It(World); It; ++It)
	{
		Lights.Add(*It);
	}
	
	for (TActorIterator<ASpotLight> It(World); It; ++It)
	{
		Lights.Add(*It);
	}
	
	for (TActorIterator<ADirectionalLight> It(World); It; ++It)
	{
		Lights.Add(*It);
	}

	return Lights;
}

TArray<AActor*> ASceneController::GetActorsByTags(const TArray<FString>& FilterTags) const
{
	TArray<AActor*> FoundActors;
	UWorld* World = GetWorld();
	if (!World) return FoundActors;

	for (TActorIterator<AActor> It(World); It; ++It)
	{
		AActor* Actor = *It;
		for (const FString& Tag : FilterTags)
		{
			if (Actor->ActorHasTag(FName(*Tag)))
			{
				FoundActors.Add(Actor);
				break;
			}
		}
	}

	return FoundActors;
}

FRotator ASceneController::GetRandomRotation() const
{
	return FRotator(
		FMath::RandRange(-180.0f, 180.0f),
		FMath::RandRange(-180.0f, 180.0f),
		FMath::RandRange(-180.0f, 180.0f)
	);
}

FVector ASceneController::GetRandomLocation(const FVector& Center, float Radius) const
{
	float RandomAngle = FMath::RandRange(0.0f, 360.0f);
	float RandomDistance = FMath::RandRange(0.0f, Radius);
	
	return Center + FVector(
		RandomDistance * FMath::Cos(FMath::DegreesToRadians(RandomAngle)),
		RandomDistance * FMath::Sin(FMath::DegreesToRadians(RandomAngle)),
		0.0f
	);
}
void ASceneController::SetupPerfectLighting()
{
	UWorld* World = GetWorld();
	if (!World)
	{
		UE_LOG(LogSceneController, Error, TEXT("SetupPerfectLighting: World is null"));
		return;
	}

	// Find or create main directional light (sun)
	ADirectionalLight* SunLight = nullptr;
	for (TActorIterator<ADirectionalLight> It(World); It; ++It)
	{
		SunLight = *It;
		break;  // Use first directional light found
	}

	if (!SunLight)
	{
		// Create new directional light if none exists
		FActorSpawnParameters SpawnParams;
		SpawnParams.Name = FName(TEXT("VantageCV_Sun"));
		SunLight = World->SpawnActor<ADirectionalLight>(FVector::ZeroVector, FRotator::ZeroRotator, SpawnParams);
		UE_LOG(LogSceneController, Log, TEXT("Created new directional light: VantageCV_Sun"));
	}

	if (SunLight)
	{
		UDirectionalLightComponent* LightComp = SunLight->GetComponent();
		if (LightComp)
		{
			// PERFECT LIGHTING SETTINGS - EXTREMELY BRIGHT for captures
			LightComp->SetIntensity(50.0f);  // MAXIMUM brightness for dark captures
			LightComp->SetLightColor(FLinearColor::White);  // Pure white
			LightComp->SetTemperature(6500.0f);  // Daylight
			
			// Optimal sun angle: 45 degrees elevation, front lighting
			SunLight->SetActorRotation(FRotator(-45.0f, 0.0f, 0.0f));
			
			// Soft shadows for realism
			LightComp->SetCastShadows(true);
			LightComp->DynamicShadowDistanceMovableLight = 20000.0f;
			LightComp->CascadeDistributionExponent = 2.0f;
			
			UE_LOG(LogSceneController, Log, TEXT("Configured sun: Intensity=10.0, Angle=45deg, White 6500K"));
		}
	}

	// Find or create sky light for ambient fill
	ASkyLight* SkyLight = nullptr;
	for (TActorIterator<ASkyLight> It(World); It; ++It)
	{
		SkyLight = *It;
		break;
	}

	if (!SkyLight)
	{
		// Create sky light if missing
		FActorSpawnParameters SpawnParams;
		SpawnParams.Name = FName(TEXT("VantageCV_SkyLight"));
		SkyLight = World->SpawnActor<ASkyLight>(FVector::ZeroVector, FRotator::ZeroRotator, SpawnParams);
		UE_LOG(LogSceneController, Log, TEXT("Created new sky light: VantageCV_SkyLight"));
	}

	if (SkyLight)
	{
		USkyLightComponent* SkyComp = SkyLight->GetLightComponent();
		if (SkyComp)
		{
			// Bright ambient lighting to eliminate dark shadows
			SkyComp->SetIntensity(2.0f);  // Strong ambient
			SkyComp->SetLightColor(FLinearColor(0.9f, 0.95f, 1.0f));  // Slightly blue sky
			SkyComp->RecaptureSky();
			
			UE_LOG(LogSceneController, Log, TEXT("Configured sky light: Intensity=2.0, Blue tint"));
		}
	}

	UE_LOG(LogSceneController, Log, TEXT("Perfect lighting setup complete - bright uniform illumination"));
}