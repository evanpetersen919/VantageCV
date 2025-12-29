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
 * Configuration structure for lighting randomization
 */
USTRUCT(BlueprintType)
struct FLightingRandomizationConfig
{
	GENERATED_BODY()

	/** Enable lighting randomization */
	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	bool bEnabled = true;

	/** Sun intensity range (lux) */
	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	FVector2D IntensityRange = FVector2D(1.0f, 15.0f);

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

	/** Randomize scene lighting */
	UFUNCTION(BlueprintCallable, Category = "VantageCV|DomainRandomization")
	void RandomizeLighting();

	/** Set configuration from Python/Blueprint */
	UFUNCTION(BlueprintCallable, Category = "VantageCV|DomainRandomization")
	void SetConfiguration(const FDomainRandomizationConfig& NewConfig);

	/** Get current configuration */
	UFUNCTION(BlueprintCallable, Category = "VantageCV|DomainRandomization")
	FDomainRandomizationConfig GetConfiguration() const { return Config; }

	/** Reset scene to clean state */
	UFUNCTION(BlueprintCallable, Category = "VantageCV|DomainRandomization")
	void ResetScene();

protected:
	virtual void BeginPlay() override;

public:
	/** Current randomization configuration */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "VantageCV|Configuration")
	FDomainRandomizationConfig Config;

	/** Ground plane mesh component */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "VantageCV|Components")
	UStaticMeshComponent* GroundPlane;

private:
	/** Track spawned distractor actors for cleanup */
	UPROPERTY()
	TArray<AActor*> SpawnedDistractors;

	/** Dynamic material for ground randomization */
	UPROPERTY()
	UMaterialInstanceDynamic* GroundMaterial;

	/** Random stream for reproducible randomization */
	FRandomStream RandomStream;

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

	/** Find sky atmosphere in scene */
	class ASkyAtmosphere* FindSkyAtmosphere() const;
};
