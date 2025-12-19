#==============================================================================
# VantageCV - C++ TensorRT Inference Build Configuration
#==============================================================================
# File: CMakeLists.txt
# Description: CMake build configuration for TensorRT inference engine
# Author: Evan Petersen
# Date: December 2025
#==============================================================================

cmake_minimum_required(VERSION 3.18)
project(VantageCV_Inference LANGUAGES CXX CUDA)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CUDA_STANDARD 17)

# Find required packages
find_package(CUDA REQUIRED)
find_package(TensorRT REQUIRED)

# Include directories
include_directories(
    ${CUDA_INCLUDE_DIRS}
    ${TensorRT_INCLUDE_DIRS}
    inference
)

# Source files
set(SOURCES
    inference/tensorrt_engine.cpp
    inference/cuda_kernels.cu
)

# Create shared library
add_library(vantagecv_inference SHARED ${SOURCES})

# Link libraries
target_link_libraries(vantagecv_inference
    ${CUDA_LIBRARIES}
    ${TensorRT_LIBRARIES}
    nvinfer
    nvonnxparser
)

# Set output directory
set_target_properties(vantagecv_inference PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/lib
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/bin
)

# Installation
install(TARGETS vantagecv_inference
    LIBRARY DESTINATION lib
    RUNTIME DESTINATION bin
)
