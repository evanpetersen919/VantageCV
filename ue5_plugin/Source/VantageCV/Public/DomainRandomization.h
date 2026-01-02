/******************************************************************************
 * VantageCV - Domain Randomization Controller Header
 ******************************************************************************
 * File: DomainRandomization.h
 * Description: Structured Domain Randomization (SDR) system for sim-to-real
 *              transfer in computer vision research. Implements randomization
 *              of ground planes, sky colors, lighting, distractors, and 
 *              camera parameters to prevent background overfitting.
 * 
 * References:
 *   - Tobin et al. "Domain Randomization for Transferring Deep Neural 
 *     Networks from Simulation to the Real World" (2017)
 *   - Tremblay et al. "Training Deep Networks with Synthetic Data" (2018)
 * 
 * Author: Evan Petersen
 * Date: December 2025
 *****************************************************************************/

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Components/StaticMeshComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Engine/StaticMesh.h"
#include "DomainRandomization.generated.h"

/**
 * Configuration structure for ground plane randomization
 */
USTRUCT(BlueprintType)
struct FGroundRandomizationConfig
{
	GENERATED_BODY()

	/** Enable ground color randomization */
	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	bool bRandomizeColor = true;

	/** Enable ground roughness randomization */
	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	bool bRandomizeRoughness = true;

	/** Minimum ground color (RGB 0-1) */
	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	FLinearColor MinColor = FLinearColor(0.1f, 0.1f, 0.1f);

	/** Maximum ground color (RGB 0-1) */
	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	FLinearColor MaxColor = FLinearColor(0.6f, 0.6f, 0.6f);

	/** Roughness range */
	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	FVector2D RoughnessRange = FVector2D(0.3f, 0.9f);
};

/**
 * Configuration structure for sky/background randomization
 */
USTRUCT(BlueprintType)
struct FSkyRandomizationConfig
{
	GENERATED_BODY()

	/** Enable sky color randomization */
	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	bool bRandomizeColor = true;

	/** Enable horizon color randomization */
	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	bool bRandomizeHorizon = true;

	/** Sky color palette (randomly selects from these) */
	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	TArray<FLinearColor> SkyColorPalette;

	/** Horizon color palette */
	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	TArray<FLinearColor> HorizonColorPalette;
};

/**
 * Configuration structure for distractor object randomization
 */
USTRUCT(BlueprintType)
struct FDistractorConfig
{
	GENERATED_BODY()

	/** Enable distractor spawning */
	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	bool bEnabled = true;

	/** Number of distractors to spawn (min, max) */
	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	FIntPoint CountRange = FIntPoint(5, 15);

	/** Scale range for distractors */
	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	FVector2D ScaleRange = FVector2D(0.5f, 3.0f);

	/** Distance range from scene center */
	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	FVector2D DistanceRange = FVector2D(500.0f, 2000.0f);

	/** Height range above ground */
	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	FVector2D HeightRange = FVector2D(0.0f, 500.0f);

	/** Use random colors for distractors */
	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	bool bRandomColors = true;

	/** Use random shapes (cube, sphere, cylinder) */
	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	bool bRandomShapes = true;
};

/**
 * Configuration structure for vehicle randomization (Professional/Research-grade)
 */
USTRUCT(BlueprintType)
struct FVehicleRandomizationConfig
{
	GENERATED_BODY()

	/** Enable vehicle position randomization */
	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	bool bEnabled = true;

	/** Number of vehicles to place per scene (min, max) */
	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	FIntPoint CountRange = FIntPoint(2, 6);

	/** Spawn area size (X, Y in cm) centered on DomainRandomization actor */
	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	FVector2D SpawnAreaSize = FVector2D(3000.0f, 3000.0f);  // 30m x 30m

	/** Minimum spacing between vehicles (cm) */
	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	float MinSpacing = 400.0f;  // 4 meters

	/** Vehicle rotation range (yaw in degrees) */
	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	FVector2D RotationRange = FVector2D(0.0f, 360.0f);

	/** Height offset from ground (cm) */
	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	float GroundOffset = 0.0f;

	/** Randomize vehicle scale slightly for variety */
	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	bool bRandomizeScale = false;

	/** Scale variation range (0.9 = 90% to 1.1 = 110%) */
	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	FVector2D ScaleRange = FVector2D(0.95f, 1.05f);
};

/**
 * Configuration structure for lighting randomization
 */
USTRUCT(BlueprintType)
struct FLightingRandomizationConfig
{
	GENERATED_BODY()

	/** Enable lighting randomization */
	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	bool bEnabled = true;

	/** Sun intensity range (lux) - MUST BE HIGH for proper capture exposure */
	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	FVector2D IntensityRange = FVector2D(50.0f, 100.0f);

	/** Sun elevation angle range (degrees) */
	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	FVector2D ElevationRange = FVector2D(15.0f, 75.0f);

	/** Sun azimuth angle range (degrees) */
	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	FVector2D AzimuthRange = FVector2D(0.0f, 360.0f);

	/** Color temperature range (Kelvin) */
	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	FVector2D TemperatureRange = FVector2D(4000.0f, 7500.0f);

	/** Enable shadow randomization */
	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	bool bRandomizeShadows = true;

	/** Shadow intensity range (0-1) */
	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	FVector2D ShadowIntensityRange = FVector2D(0.3f, 1.0f);
};

/**
 * Complete domain randomization configuration
 */
USTRUCT(BlueprintType)
struct FDomainRandomizationConfig
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	FGroundRandomizationConfig Ground;

	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	FSkyRandomizationConfig Sky;

	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	FDistractorConfig Distractors;

	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	FLightingRandomizationConfig Lighting;

	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	FVehicleRandomizationConfig Vehicles;

	/** Random seed for reproducibility (-1 for random) */
	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	int32 RandomSeed = -1;
};

/**
 * Domain Randomization Controller
 * 
 * Implements structured domain randomization for sim-to-real transfer.
 * Randomizes all non-essential visual elements to force the neural network
 * to learn object features rather than spurious background correlations.
 */
UCLASS(Blueprintable, ClassGroup=(VantageCV), meta=(BlueprintSpawnableComponent))
class VANTAGECV_API ADomainRandomization : public AActor
{
	GENERATED_BODY()

public:
	ADomainRandomization();

	/** Apply complete domain randomization with current config */
	UFUNCTION(BlueprintCallable, Category = "VantageCV|DomainRandomization")
	void ApplyRandomization();

	/** Apply randomization with explicit seed for reproducibility */
	UFUNCTION(BlueprintCallable, Category = "VantageCV|DomainRandomization")
	void ApplyRandomizationWithSeed(int32 Seed);

	/** Randomize ground plane appearance */
	UFUNCTION(BlueprintCallable, Category = "VantageCV|DomainRandomization")
	void RandomizeGround();

	/** Randomize sky/background colors */
	UFUNCTION(BlueprintCallable, Category = "VantageCV|DomainRandomization")
	void RandomizeSky();

	/** Spawn random distractor objects */
	UFUNCTION(BlueprintCallable, Category = "VantageCV|DomainRandomization")
	void SpawnDistractors();

	/** Clear all spawned distractors */
	UFUNCTION(BlueprintCallable, Category = "VantageCV|DomainRandomization")
	void ClearDistractors();

	/** Enable/disable distractor spawning */
	UFUNCTION(BlueprintCallable, Category = "VantageCV|DomainRandomization")
	void SetDistractorsEnabled(bool bEnabled);

	/** Randomize scene lighting */
	UFUNCTION(BlueprintCallable, Category = "VantageCV|DomainRandomization")
	void RandomizeLighting();

	/** Randomize vehicle positions for maximum training variety (Research-grade) */
	UFUNCTION(BlueprintCallable, Category = "VantageCV|DomainRandomization")
	void RandomizeVehicles();

	/** AUTHORITATIVE CLEANUP: Hide ALL vehicle-tagged actors (world sweep)
	 *  This is the ONLY cleanup method that guarantees zero vehicles remain visible.
	 *  Returns the number of vehicles hidden.
	 */
	UFUNCTION(BlueprintCallable, Category = "VantageCV|DomainRandomization")
	int32 HideAllVehicles();

	/** VERIFICATION: Get count of ALL visible vehicle-tagged actors
	 *  Returns 0 if cleanup was successful.
	 *  If > 0, vehicles have leaked and system is BROKEN.
	 */
	UFUNCTION(BlueprintCallable, Category = "VantageCV|DomainRandomization")
	int32 GetVisibleVehicleCountWorldSweep() const;

	/** Register a vehicle actor for randomization */
	UFUNCTION(BlueprintCallable, Category = "VantageCV|DomainRandomization")
	void RegisterVehicle(AActor* Vehicle);

	/** Unregister a vehicle actor */
	UFUNCTION(BlueprintCallable, Category = "VantageCV|DomainRandomization")
	void UnregisterVehicle(AActor* Vehicle);

	/** Get count of currently visible vehicles (for adaptive camera zoom) */
	UFUNCTION(BlueprintCallable, Category = "VantageCV|DomainRandomization")
	int32 GetVisibleVehicleCount();

	/** Get randomly selected target point for camera focus */
	UFUNCTION(BlueprintCallable, Category = "VantageCV|DomainRandomization")
	FVector GetRandomVehicleLocation() const;

	/** Set configuration from Python/Blueprint */
	UFUNCTION(BlueprintCallable, Category = "VantageCV|DomainRandomization")
	void SetConfiguration(const FDomainRandomizationConfig& NewConfig);

	/** Get current configuration */
	UFUNCTION(BlueprintCallable, Category = "VantageCV|DomainRandomization")
	FDomainRandomizationConfig GetConfiguration() const { return Config; }

	/** Reset scene to clean state */
	UFUNCTION(BlueprintCallable, Category = "VantageCV|DomainRandomization")
	void ResetScene();

	/** Reset vehicles to original positions */
	UFUNCTION(BlueprintCallable, Category = "VantageCV|DomainRandomization")
	void ResetVehicles();

protected:
	virtual void BeginPlay() override;

public:
	/** Current randomization configuration */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "VantageCV|Configuration")
	FDomainRandomizationConfig Config;

private:
	/** Track spawned distractor actors for cleanup */
	UPROPERTY()
	TArray<AActor*> SpawnedDistractors;

	/** Track registered vehicle actors for randomization */
	UPROPERTY()
	TArray<AActor*> RegisteredVehicles;

	/** Store original vehicle positions for reset */
	TArray<FTransform> OriginalVehicleTransforms;

	/** Flag to track if vehicles have been initialized */
	bool bVehiclesInitialized = false;

	/** Random stream for reproducible randomization */
	FRandomStream RandomStream;

	/** Initialize vehicle system - discover, lock scales, hide all */
	void InitializeVehicleSystem();

	/** Initialize default sky color palettes */
	void InitializeDefaultPalettes();

	/** Get random float in range using current stream */
	float GetRandomFloat(float Min, float Max);

	/** Get random color in range using current stream */
	FLinearColor GetRandomColor(const FLinearColor& Min, const FLinearColor& Max);

	/** Get random vector in range */
	FVector GetRandomVector(const FVector& Min, const FVector& Max);

	/** Spawn single distractor with random properties */
	AActor* SpawnSingleDistractor();

	/** Find directional light in scene */
	class ADirectionalLight* FindDirectionalLight() const;

	/** Check if position is valid (not colliding with other vehicles) */
	bool IsPositionValid(const FVector& Position, float MinSpacing, const TArray<FVector>& OccupiedPositions) const;

	/** Check if position is valid using bounding box collision detection */
	bool IsPositionValidForVehicle(AActor* Vehicle, const FVector& Position, const TArray<struct FPlacedVehicle>& PlacedVehicles) const;

	/** Calculate what percentage of vehicle is visible in camera frustum (0-100%) */
	float CalculateVisibilityPercentage(AActor* Vehicle, const FVector& CameraLocation, const FRotator& CameraRotation, float FOV) const;

	/** Check if vehicle position is within spawn bounds with margin */
	bool IsVehicleInSpawnBounds(const FVector& Position, const FVector& SpawnCenter, float HalfWidth, float HalfLength, float Margin) const;

	/** Auto-discover vehicles in scene by tag */
	void AutoDiscoverVehicles();
};
