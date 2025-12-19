/******************************************************************************
 * VantageCV - TensorRT Inference Engine Header
 ******************************************************************************
 * File: tensorrt_engine.h
 * Description: TensorRT inference engine class definition for high-performance
 *              GPU inference on ONNX models
 * Author: Evan Petersen
 * Date: December 2025
 *****************************************************************************/

#ifndef TENSORRT_ENGINE_H
#define TENSORRT_ENGINE_H

#include <string>
#include <vector>
#include <memory>
#include <NvInfer.h>
#include <NvOnnxParser.h>

namespace vantagecv {

class TensorRTEngine {
public:
    TensorRTEngine();
    ~TensorRTEngine();

    // Load ONNX model and build TensorRT engine
    bool loadModel(const std::string& onnx_path);

    // Run inference on input data
    bool infer(const float* input, float* output, int batch_size);

    // Get input/output dimensions
    std::vector<int> getInputDims() const;
    std::vector<int> getOutputDims() const;

    // Performance metrics
    float getInferenceTime() const { return inference_time_ms_; }

private:
    // TensorRT objects
    nvinfer1::IRuntime* runtime_;
    nvinfer1::ICudaEngine* engine_;
    nvinfer1::IExecutionContext* context_;

    // CUDA stream
    void* cuda_stream_;

    // Model metadata
    std::vector<int> input_dims_;
    std::vector<int> output_dims_;
    
    // Performance tracking
    float inference_time_ms_;

    // Helper methods
    bool buildEngine(const std::string& onnx_path);
    bool allocateBuffers();
    void releaseBuffers();
};

} // namespace vantagecv

#endif // TENSORRT_ENGINE_H
