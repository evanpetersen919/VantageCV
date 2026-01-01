/******************************************************************************
 * VantageCV - Scene Controller Header
 ******************************************************************************
 * File: SceneController.h
 * Description: Controls scene randomization for synthetic data generation
 *              including lighting, materials, camera, and object placement
 * Author: Evan Petersen
 * Date: December 2025
 *****************************************************************************/

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "SceneController.generated.h"

/**
 * Controls scene randomization for synthetic data generation
 * Exposed via Remote Control API for Python-driven dataset generation
 */
UCLASS()
class VANTAGECV_API ASceneController : public AActor
{
	GENERATED_BODY()
	
public:	
	ASceneController();

	/** Randomize scene lighting (intensity, color, direction) */
	UFUNCTION(BlueprintCallable, Category = "VantageCV")
	void RandomizeLighting(float MinIntensity, float MaxIntensity, float MinTemperature, float MaxTemperature);

	/** Randomize object materials with parameter variations */
	UFUNCTION(BlueprintCallable, Category = "VantageCV")
	void RandomizeMaterials(const TArray<FString>& TargetTags);

	/** Randomize camera position and orientation */
	UFUNCTION(BlueprintCallable, Category = "VantageCV")
	void RandomizeCamera(float MinDistance, float MaxDistance, float MinFOV, float MaxFOV);

	/** Spawn objects in scene with random placement */
	UFUNCTION(BlueprintCallable, Category = "VantageCV")
	void SpawnRandomObjects(int32 NumObjects, const TArray<FString>& ObjectClasses);

	/** Clear all spawned objects from scene */
	UFUNCTION(BlueprintCallable, Category = "VantageCV")
	void ClearSpawnedObjects();

	/** Set specific lighting preset (industrial LED, outdoor sun, etc.) */
	UFUNCTION(BlueprintCallable, Category = "VantageCV")
	void SetLightingPreset(const FString& PresetName);

	/** Setup perfect lighting for vehicle capture (bright, uniform, no shadows) */
	UFUNCTION(BlueprintCallable, Category = "VantageCV")
	void SetupPerfectLighting();

protected:
	virtual void BeginPlay() override;

public:	
	virtual void Tick(float DeltaTime) override;

private:
	/** Track spawned actors for cleanup */
	UPROPERTY()
	TArray<AActor*> SpawnedActors;

	/** Find all lights in scene */
	TArray<class ALight*> GetSceneLights() const;
	
	/** Find all actors with specified tags */
	TArray<AActor*> GetActorsByTags(const TArray<FString>& Tags) const;
	
	/** Get random rotation in range */
	FRotator GetRandomRotation() const;
	
	/** Get random location within bounds */
	FVector GetRandomLocation(const FVector& Center, float Radius) const;
};
