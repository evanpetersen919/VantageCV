/******************************************************************************
 * VantageCV - Scene Controller Header
 ******************************************************************************
 * File: SceneController.h
 * Description: Controls scene randomization and object spawning for synthetic
 *              data generation. Handles lighting, materials, and object placement.
 * Author: Evan Petersen
 * Date: December 2025
 *****************************************************************************/

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "SceneController.generated.h"

/**
 * Controls scene randomization and object spawning for synthetic data generation
 */
UCLASS()
class VANTAGECV_API ASceneController : public AActor
{
	GENERATED_BODY()
	
public:	
	ASceneController();

	// Randomize scene lighting
	UFUNCTION(BlueprintCallable, Category = "VantageCV")
	void RandomizeLighting();

	// Randomize object materials
	UFUNCTION(BlueprintCallable, Category = "VantageCV")
	void RandomizeMaterials();

	// Spawn objects in scene
	UFUNCTION(BlueprintCallable, Category = "VantageCV")
	void SpawnRandomObjects(int32 NumObjects);

protected:
	virtual void BeginPlay() override;

public:	
	virtual void Tick(float DeltaTime) override;

private:
	// Internal helper functions
	void SetupDefaultLighting();
};
