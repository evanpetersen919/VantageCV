/******************************************************************************
 * VantageCV - Plugin Module Header
 ******************************************************************************
 * File: VantageCVModule.h
 * Description: Main module interface for VantageCV plugin, handles plugin
 *              initialization and shutdown in Unreal Engine
 * Author: Evan Petersen
 * Date: December 2025
 *****************************************************************************/

#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"

class FVantageCVModule : public IModuleInterface
{
public:

	/** IModuleInterface implementation */
	virtual void StartupModule() override;
	virtual void ShutdownModule() override;
};
