/******************************************************************************
 * VantageCV - Data Capture Header
 ******************************************************************************
 * File: DataCapture.h
 * Description: Handles high-resolution image capture and ground truth annotation
 *              generation (bounding boxes, segmentation masks, 6D poses)
 * Author: Evan Petersen
 * Date: December 2025
 *****************************************************************************/

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Engine/TextureRenderTarget2D.h"
#include "DataCapture.generated.h"

/**
 * Annotation data structure for single object
 */
USTRUCT(BlueprintType)
struct FObjectAnnotation
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadWrite)
	FString ClassName;

	UPROPERTY(BlueprintReadWrite)
	FVector2D BBoxMin;

	UPROPERTY(BlueprintReadWrite)
	FVector2D BBoxMax;

	UPROPERTY(BlueprintReadWrite)
	FVector Location;

	UPROPERTY(BlueprintReadWrite)
	FRotator Rotation;

	UPROPERTY(BlueprintReadWrite)
	int32 InstanceID;
};

/**
 * Captures rendered images and generates annotations for computer vision tasks
 * Exposed via Remote Control API for Python-driven dataset generation
 */
UCLASS()
class VANTAGECV_API ADataCapture : public AActor
{
	GENERATED_BODY()
	
public:	
	ADataCapture();

	/** Capture current frame to disk as PNG */
	UFUNCTION(BlueprintCallable, Category = "VantageCV")
	bool CaptureFrame(const FString& OutputPath, int32 Width, int32 Height);

	/** Generate bounding box annotations in JSON format */
	UFUNCTION(BlueprintCallable, Category = "VantageCV")
	FString GenerateBoundingBoxes(const TArray<FString>& TargetTags);

	/** Generate segmentation mask and save to disk */
	UFUNCTION(BlueprintCallable, Category = "VantageCV")
	bool GenerateSegmentationMask(const FString& OutputPath, int32 Width, int32 Height);

	/** Generate 6D pose annotations for all objects */
	UFUNCTION(BlueprintCallable, Category = "VantageCV")
	FString GeneratePoseAnnotations(const TArray<FString>& TargetTags);

	/** Set render target resolution */
	UFUNCTION(BlueprintCallable, Category = "VantageCV")
	void SetResolution(int32 Width, int32 Height);

	/** Match viewport camera position and FOV */
	UFUNCTION(BlueprintCallable, Category = "VantageCV")
	void MatchViewportCamera();

	/** Randomize camera position around target with spherical coordinates */
	UFUNCTION(BlueprintCallable, Category = "VantageCV")
	void RandomizeCamera(float MinDistance, float MaxDistance, float MinFOV, float MaxFOV);

protected:
	virtual void BeginPlay() override;

public:	
	virtual void Tick(float DeltaTime) override;

private:
	/** Scene capture component for rendering */
	UPROPERTY()
	class USceneCaptureComponent2D* CaptureComponent;

	/** Render target for capturing images */
	UPROPERTY()
	UTextureRenderTarget2D* RenderTarget;

	/** Render target for segmentation masks */
	UPROPERTY()
	UTextureRenderTarget2D* SegmentationTarget;

	/** Find all actors matching tags */
	TArray<AActor*> GetAnnotatableActors(const TArray<FString>& Tags) const;

	/** Calculate 2D bounding box from 3D actor bounds */
	bool CalculateBoundingBox(AActor* Actor, FVector2D& OutMin, FVector2D& OutMax) const;

	/** Project 3D point to 2D screen space */
	FVector2D ProjectWorldToScreen(const FVector& WorldLocation) const;

	/** Save texture render target to file */
	bool SaveRenderTargetToFile(UTextureRenderTarget2D* RenderTarget, const FString& FilePath);

	/** Read pixel data from render target */
	bool ReadRenderTargetPixels(UTextureRenderTarget2D* RenderTarget, TArray<FColor>& OutPixels);
};
