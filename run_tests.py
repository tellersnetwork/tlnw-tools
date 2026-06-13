import os
import sys
import traceback

def run_test_module(module_name, module_path):
    # Dynamically load the module
    import importlib.util
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    
    # Find all test functions
    test_functions = [getattr(module, name) for name in dir(module) if name.startswith("test_")]
    
    passed = 0
    failed = 0
    for func in test_functions:
        print(f"Running {module_name}.{func.__name__}... ", end="")
        try:
            func()
            print("PASSED")
            passed += 1
        except Exception as e:
            print("FAILED")
            traceback.print_exc()
            failed += 1
            
    return passed, failed

def main():
    # Setup python paths
    root_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, root_dir)
    sys.path.insert(0, os.path.join(root_dir, "generate-image"))
    
    test_files = [
        ("tests.test_loader", os.path.join(root_dir, "tests", "test_loader.py")),
        ("tests.test_generate_image", os.path.join(root_dir, "generate-image", "tests", "test_generate_image.py")),
    ]
    
    total_passed = 0
    total_failed = 0
    
    print("==================================================")
    print("TLNW-TOOLS ZERO-DEPENDENCY TEST RUNNER")
    print("==================================================")
    
    for module_name, path in test_files:
        if os.path.exists(path):
            print(f"\n--- Testing Module: {module_name} ---")
            p, f = run_test_module(module_name, path)
            total_passed += p
            total_failed += f
        else:
            print(f"\nWarning: Test file not found: {path}")
            
    print("\n==================================================")
    print(f"Test Summary: {total_passed} PASSED, {total_failed} FAILED")
    print("==================================================")
    
    if total_failed > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
