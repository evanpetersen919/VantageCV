/******************************************************************************
 * VantageCV - Plugin Module Implementation
 ******************************************************************************
 * File: VantageCVModule.cpp
 * Description: Implementation of VantageCV plugin module initialization and
 *              shutdown logic
 * Author: Evan Petersen
 * Date: December 2025
 *****************************************************************************/

#include "VantageCVModule.h"

#define LOCTEXT_NAMESPACE "FVantageCVModule"

void FVantageCVModule::StartupModule()
{
	// This code executes after the module is loaded into memory
	UE_LOG(LogTemp, Log, TEXT("VantageCV Module Started"));
}

void FVantageCVModule::ShutdownModule()
{
	// This function is called during shutdown to clean up the module
	UE_LOG(LogTemp, Log, TEXT("VantageCV Module Shutdown"));
}

#undef LOCTEXT_NAMESPACE
	
IMPLEMENT_MODULE(FVantageCVModule, VantageCV)
