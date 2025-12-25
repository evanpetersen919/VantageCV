/******************************************************************************
 * VantageCV - Data Capture Implementation
 ******************************************************************************
 * File: DataCapture.cpp
 * Description: Implementation of image capture and annotation generation for
 *              synthetic computer vision datasets with ground truth extraction
 * Author: Evan Petersen
 * Date: December 2025
 *****************************************************************************/

#include "DataCapture.h"
#include "Components/SceneCaptureComponent2D.h"
#include "Engine/TextureRenderTarget2D.h"
#include "ImageUtils.h"
#include "IImageWrapper.h"
#include "IImageWrapperModule.h"
#include "Modules/ModuleManager.h"
#include "Camera/CameraComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "Kismet/GameplayStatics.h"
#include "EngineUtils.h"
#include "Engine/Engine.h"
#include "Async/Async.h"
#include "HAL/PlatformFileManager.h"
#include "Misc/FileHelper.h"
#include "Json.h"
#include "JsonUtilities.h"

DEFINE_LOG_CATEGORY_STATIC(LogDataCapture, Log, All);

ADataCapture::ADataCapture()
{
	PrimaryActorTick.bCanEverTick = true;

	// Create scene capture component
	CaptureComponent = CreateDefaultSubobject<USceneCaptureComponent2D>(TEXT("SceneCaptureComponent"));
	RootComponent = CaptureComponent;

	// Configure capture settings
	if (CaptureComponent)
	{
		CaptureComponent->CaptureSource = ESceneCaptureSource::SCS_FinalColorLDR;
		CaptureComponent->bCaptureEveryFrame = false;
		CaptureComponent->bCaptureOnMovement = false;
	}
}

void ADataCapture::BeginPlay()
{
	Super::BeginPlay();
	
	// Initialize default render targets
	SetResolution(1920, 1080);
	
	UE_LOG(LogDataCapture, Log, TEXT("DataCapture initialized with 1920x1080 resolution"));
}

void ADataCapture::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);
}

void ADataCapture::SetResolution(int32 Width, int32 Height)
{
	// Create RGB render target
	RenderTarget = NewObject<UTextureRenderTarget2D>();
	RenderTarget->InitAutoFormat(Width, Height);
	RenderTarget->UpdateResourceImmediate(true);

	// Create segmentation render target
	SegmentationTarget = NewObject<UTextureRenderTarget2D>();
	SegmentationTarget->InitAutoFormat(Width, Height);
	SegmentationTarget->UpdateResourceImmediate(true);

	if (CaptureComponent)
	{
		CaptureComponent->TextureTarget = RenderTarget;
	}

	UE_LOG(LogDataCapture, Log, TEXT("Set render resolution to %dx%d"), Width, Height);
}

bool ADataCapture::CaptureFrame(const FString& OutputPath, int32 Width, int32 Height)
{
	// Initialize components if not already done (for Editor mode)
	if (!CaptureComponent || !RenderTarget)
	{
		UE_LOG(LogDataCapture, Log, TEXT("Initializing components for Editor mode capture"));
		
		if (!CaptureComponent)
		{
			CaptureComponent = NewObject<USceneCaptureComponent2D>(this, TEXT("DataCaptureComponent"));
			CaptureComponent->RegisterComponent();
			CaptureComponent->bCaptureEveryFrame = false;
			CaptureComponent->bCaptureOnMovement = false;
			CaptureComponent->CaptureSource = ESceneCaptureSource::SCS_FinalColorLDR;
			
			// Attach to root
			if (GetRootComponent())
			{
				CaptureComponent->AttachToComponent(GetRootComponent(), FAttachmentTransformRules::SnapToTargetIncludingScale);
			}
		}
		
		if (!RenderTarget)
		{
			RenderTarget = NewObject<UTextureRenderTarget2D>();
			RenderTarget->InitAutoFormat(Width, Height);
			RenderTarget->UpdateResourceImmediate(true);
			
			if (CaptureComponent)
			{
				CaptureComponent->TextureTarget = RenderTarget;
			}
		}
		
		UE_LOG(LogDataCapture, Log, TEXT("Components initialized successfully"));
	}

	// Update resolution if needed
	if (RenderTarget->SizeX != Width || RenderTarget->SizeY != Height)
	{
		SetResolution(Width, Height);
	}

	// Capture scene
	CaptureComponent->CaptureScene();

	// Save to file
	bool bSuccess = SaveRenderTargetToFile(RenderTarget, OutputPath);
	
	if (bSuccess)
	{
		UE_LOG(LogDataCapture, Log, TEXT("Captured frame to: %s (%dx%d)"), *OutputPath, Width, Height);
	}
	else
	{
		UE_LOG(LogDataCapture, Error, TEXT("Failed to save frame to: %s"), *OutputPath);
	}

	return bSuccess;
}

FString ADataCapture::GenerateBoundingBoxes(const TArray<FString>& TargetTags)
{
	TArray<AActor*> Actors = GetAnnotatableActors(TargetTags);
	TArray<TSharedPtr<FJsonValue>> AnnotationsArray;

	for (AActor* Actor : Actors)
	{
		if (!Actor) continue;

		FVector2D BBoxMin, BBoxMax;
		if (CalculateBoundingBox(Actor, BBoxMin, BBoxMax))
		{
			TSharedPtr<FJsonObject> AnnotationObj = MakeShareable(new FJsonObject);
			
			AnnotationObj->SetStringField("class", Actor->GetClass()->GetName());
			AnnotationObj->SetNumberField("x_min", BBoxMin.X);
			AnnotationObj->SetNumberField("y_min", BBoxMin.Y);
			AnnotationObj->SetNumberField("x_max", BBoxMax.X);
			AnnotationObj->SetNumberField("y_max", BBoxMax.Y);
			AnnotationObj->SetNumberField("width", BBoxMax.X - BBoxMin.X);
			AnnotationObj->SetNumberField("height", BBoxMax.Y - BBoxMin.Y);

			AnnotationsArray.Add(MakeShareable(new FJsonValueObject(AnnotationObj)));
		}
	}

	// Convert to JSON string
	TSharedPtr<FJsonObject> RootObj = MakeShareable(new FJsonObject);
	RootObj->SetArrayField("annotations", AnnotationsArray);

	FString OutputString;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
	FJsonSerializer::Serialize(RootObj.ToSharedRef(), Writer);

	UE_LOG(LogDataCapture, Log, TEXT("Generated %d bounding box annotations"), AnnotationsArray.Num());
	return OutputString;
}

bool ADataCapture::GenerateSegmentationMask(const FString& OutputPath, int32 Width, int32 Height)
{
	if (!CaptureComponent || !SegmentationTarget)
	{
		UE_LOG(LogDataCapture, Error, TEXT("CaptureComponent or SegmentationTarget not initialized"));
		return false;
	}

	// Update resolution if needed
	if (SegmentationTarget->SizeX != Width || SegmentationTarget->SizeY != Height)
	{
		SegmentationTarget->InitAutoFormat(Width, Height);
		SegmentationTarget->UpdateResourceImmediate(true);
	}

	// Switch to segmentation rendering mode
	CaptureComponent->TextureTarget = SegmentationTarget;
	CaptureComponent->CaptureSource = ESceneCaptureSource::SCS_SceneColorHDR;
	CaptureComponent->ShowFlags.SetPostProcessing(false);
	CaptureComponent->CaptureScene();

	// Save segmentation mask
	bool bSuccess = SaveRenderTargetToFile(SegmentationTarget, OutputPath);

	// Restore normal rendering
	CaptureComponent->TextureTarget = RenderTarget;
	CaptureComponent->CaptureSource = ESceneCaptureSource::SCS_FinalColorLDR;
	CaptureComponent->ShowFlags.SetPostProcessing(true);

	if (bSuccess)
	{
		UE_LOG(LogDataCapture, Log, TEXT("Generated segmentation mask: %s"), *OutputPath);
	}
	else
	{
		UE_LOG(LogDataCapture, Error, TEXT("Failed to generate segmentation mask: %s"), *OutputPath);
	}

	return bSuccess;
}

FString ADataCapture::GeneratePoseAnnotations(const TArray<FString>& TargetTags)
{
	TArray<AActor*> Actors = GetAnnotatableActors(TargetTags);
	TArray<TSharedPtr<FJsonValue>> PosesArray;

	for (AActor* Actor : Actors)
	{
		if (!Actor) continue;

		FVector Location = Actor->GetActorLocation();
		FRotator Rotation = Actor->GetActorRotation();
		FVector Scale = Actor->GetActorScale3D();

		TSharedPtr<FJsonObject> PoseObj = MakeShareable(new FJsonObject);
		
		PoseObj->SetStringField("class", Actor->GetClass()->GetName());
		
		// Translation
		TArray<TSharedPtr<FJsonValue>> TranslationArray;
		TranslationArray.Add(MakeShareable(new FJsonValueNumber(Location.X)));
		TranslationArray.Add(MakeShareable(new FJsonValueNumber(Location.Y)));
		TranslationArray.Add(MakeShareable(new FJsonValueNumber(Location.Z)));
		PoseObj->SetArrayField("translation", TranslationArray);

		// Rotation (Euler angles)
		TArray<TSharedPtr<FJsonValue>> RotationArray;
		RotationArray.Add(MakeShareable(new FJsonValueNumber(Rotation.Roll)));
		RotationArray.Add(MakeShareable(new FJsonValueNumber(Rotation.Pitch)));
		RotationArray.Add(MakeShareable(new FJsonValueNumber(Rotation.Yaw)));
		PoseObj->SetArrayField("rotation", RotationArray);

		// Scale
		TArray<TSharedPtr<FJsonValue>> ScaleArray;
		ScaleArray.Add(MakeShareable(new FJsonValueNumber(Scale.X)));
		ScaleArray.Add(MakeShareable(new FJsonValueNumber(Scale.Y)));
		ScaleArray.Add(MakeShareable(new FJsonValueNumber(Scale.Z)));
		PoseObj->SetArrayField("scale", ScaleArray);

		PosesArray.Add(MakeShareable(new FJsonValueObject(PoseObj)));
	}

	// Convert to JSON string
	TSharedPtr<FJsonObject> RootObj = MakeShareable(new FJsonObject);
	RootObj->SetArrayField("poses", PosesArray);

	FString OutputString;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
	FJsonSerializer::Serialize(RootObj.ToSharedRef(), Writer);

	UE_LOG(LogDataCapture, Log, TEXT("Generated %d pose annotations"), PosesArray.Num());
	return OutputString;
}

TArray<AActor*> ADataCapture::GetAnnotatableActors(const TArray<FString>& FilterTags) const
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

bool ADataCapture::CalculateBoundingBox(AActor* Actor, FVector2D& OutMin, FVector2D& OutMax) const
{
	if (!Actor) return false;

	FVector Origin, BoxExtent;
	Actor->GetActorBounds(false, Origin, BoxExtent);

	// Get 8 corners of bounding box
	TArray<FVector> Corners;
	Corners.Add(Origin + FVector(BoxExtent.X, BoxExtent.Y, BoxExtent.Z));
	Corners.Add(Origin + FVector(BoxExtent.X, BoxExtent.Y, -BoxExtent.Z));
	Corners.Add(Origin + FVector(BoxExtent.X, -BoxExtent.Y, BoxExtent.Z));
	Corners.Add(Origin + FVector(BoxExtent.X, -BoxExtent.Y, -BoxExtent.Z));
	Corners.Add(Origin + FVector(-BoxExtent.X, BoxExtent.Y, BoxExtent.Z));
	Corners.Add(Origin + FVector(-BoxExtent.X, BoxExtent.Y, -BoxExtent.Z));
	Corners.Add(Origin + FVector(-BoxExtent.X, -BoxExtent.Y, BoxExtent.Z));
	Corners.Add(Origin + FVector(-BoxExtent.X, -BoxExtent.Y, -BoxExtent.Z));

	// Project to screen space
	float MinX = FLT_MAX, MinY = FLT_MAX;
	float MaxX = -FLT_MAX, MaxY = -FLT_MAX;

	for (const FVector& Corner : Corners)
	{
		FVector2D ScreenPos = ProjectWorldToScreen(Corner);
		MinX = FMath::Min(MinX, ScreenPos.X);
		MinY = FMath::Min(MinY, ScreenPos.Y);
		MaxX = FMath::Max(MaxX, ScreenPos.X);
		MaxY = FMath::Max(MaxY, ScreenPos.Y);
	}

	OutMin = FVector2D(MinX, MinY);
	OutMax = FVector2D(MaxX, MaxY);

	return true;
}

FVector2D ADataCapture::ProjectWorldToScreen(const FVector& WorldLocation) const
{
	UWorld* World = GetWorld();
	if (!World) return FVector2D::ZeroVector;

	APlayerController* PC = UGameplayStatics::GetPlayerController(World, 0);
	if (!PC) return FVector2D::ZeroVector;

	FVector2D ScreenLocation;
	PC->ProjectWorldLocationToScreen(WorldLocation, ScreenLocation);

	return ScreenLocation;
}

bool ADataCapture::SaveRenderTargetToFile(UTextureRenderTarget2D* InRenderTarget, const FString& FilePath)
{
	if (!InRenderTarget) return false;

	TArray<FColor> Pixels;
	if (!ReadRenderTargetPixels(InRenderTarget, Pixels))
	{
		return false;
	}

	// Use FImageUtils for high-quality PNG export (research-grade quality)
	// Save asynchronously to avoid blocking game thread
	AsyncTask(ENamedThreads::AnyBackgroundThreadNormalTask, [Pixels, FilePath, Width = InRenderTarget->SizeX, Height = InRenderTarget->SizeY]()
	{
		IImageWrapperModule& ImageWrapperModule = FModuleManager::LoadModuleChecked<IImageWrapperModule>(FName("ImageWrapper"));
		TSharedPtr<IImageWrapper> ImageWrapper = ImageWrapperModule.CreateImageWrapper(EImageFormat::PNG);
		
		if (ImageWrapper.IsValid() && ImageWrapper->SetRaw(Pixels.GetData(), Pixels.Num() * sizeof(FColor), Width, Height, ERGBFormat::BGRA, 8))
		{
			const TArray64<uint8>& CompressedData = ImageWrapper->GetCompressed(100);
			FFileHelper::SaveArrayToFile(CompressedData, *FilePath);
		}
	});

	return true;
}

bool ADataCapture::ReadRenderTargetPixels(UTextureRenderTarget2D* InRenderTarget, TArray<FColor>& OutPixels)
{
	if (!InRenderTarget) return false;

	FTextureRenderTargetResource* RTResource = InRenderTarget->GameThread_GetRenderTargetResource();
	if (!RTResource) return false;

	OutPixels.SetNum(InRenderTarget->SizeX * InRenderTarget->SizeY);
	
	FReadSurfaceDataFlags ReadPixelFlags(RCM_UNorm);
	ReadPixelFlags.SetLinearToGamma(false);

	return RTResource->ReadPixels(OutPixels, ReadPixelFlags);
}
