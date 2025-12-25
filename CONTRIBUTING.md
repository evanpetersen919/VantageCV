# Contributing to VantageCV

## Development Setup

### Prerequisites
- Python 3.11+
- Unreal Engine 5.7+
- Visual Studio 2022+ with C++ workload
- CUDA 11.8+ and TensorRT 8.6+ (for inference)
- Git

### Setting Up Development Environment

1. **Clone the repository**
   ```bash
   git clone https://github.com/evanpetersen919/VantageCV.git
   cd VantageCV
   ```

2. **Create Python virtual environment**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   pip install -r requirements.txt
   ```

3. **Build C++ TensorRT engine**
   ```bash
   cd cpp/inference_engine
   mkdir build && cd build
   cmake ..
   cmake --build . --config Release
   ```

4. **Build UE5 plugin**
   - Copy `ue5_plugin` to your UE5 project's `Plugins` directory
   - Open project in UE5 - it will prompt to build
   - Or manually build: `UnrealBuildTool.exe VantageCV Win64 Development`

## Code Standards

### Python
- Follow PEP 8 style guide
- Use type hints for all function signatures
- Docstrings for all public methods (Google style)
- Maximum line length: 100 characters

### C++
- Follow Unreal Engine coding standards
- Use `UE_LOG` for logging (not `printf` or `std::cout`)
- RAII for resource management
- Smart pointers (`TSharedPtr`, `TUniquePtr`) over raw pointers

### Git Workflow
- Branch naming: `feature/description`, `fix/description`, `refactor/description`
- Commit messages: Present tense, descriptive ("Add feature" not "Added feature")
- Keep commits atomic and focused
- Squash before merging to main

## Testing

### Running Tests
```bash
# Python unit tests
pytest tests/unit/

# Integration tests (requires UE5 running)
python tests/integration/test_ue5_connection.py
python tests/integration/proof_of_concept_capture.py
```

### Writing Tests
- Unit tests for all Python modules in `vantagecv/`
- Integration tests for UE5 communication
- Performance benchmarks for TensorRT inference

## Documentation

- Update README.md for user-facing features
- Add docstrings for all public APIs
- Include code examples for complex features
- Update architecture diagrams in `docs/` when changing system design

## Research Standards

This project targets research-paper quality implementation:
- **No simplified shortcuts** - use production-grade approaches
- **Cite related work** in code comments where applicable
- **Benchmark performance** against published baselines
- **Document design decisions** with rationale

## Getting Help

- Open an issue for bugs or feature requests
- Tag with appropriate labels: `bug`, `enhancement`, `question`
- Provide minimal reproducible examples
- Include system specs (GPU, OS, UE5 version)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
