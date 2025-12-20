/******************************************************************************
 * VantageCV - Data Capture Header
 ******************************************************************************
 * File: DataCapture.h
 * Description: Handles image capture and annotation generation for computer
 *              vision tasks including bounding boxes and segmentation masks
 * Author: Evan Petersen
 * Date: December 2025
 *****************************************************************************/

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "DataCapture.generated.h"

/**
 * Captures rendered images and generates annotations for computer vision tasks
 */
UCLASS()
class VANTAGECV_API ADataCapture : public AActor
{
	GENERATED_BODY()
	
public:	
	ADataCapture();

	// Capture current frame to disk
	UFUNCTION(BlueprintCallable, Category = "VantageCV")
	bool CaptureFrame(const FString& OutputPath);

	// Generate bounding box annotations
	UFUNCTION(BlueprintCallable, Category = "VantageCV")
	TArray<FString> GenerateBoundingBoxes();

	// Generate segmentation mask
	UFUNCTION(BlueprintCallable, Category = "VantageCV")
	bool GenerateSegmentationMask(const FString& OutputPath);

protected:
	virtual void BeginPlay() override;

public:	
	virtual void Tick(float DeltaTime) override;

private:
	// Camera component for capturing
	UPROPERTY()
	class USceneCaptureComponent2D* CaptureComponent;
	
	// Helper function to save image data
	bool SaveImageToFile(const TArray<FColor>& ImageData, int32 Width, int32 Height, const FString& FilePath);
};
