# Updated import test
try:
    print("Testing websockets import...")
    import websockets
    print(f"websockets package exists: {websockets}")
    print(f"websockets dir: {dir(websockets)}")
    
    print("\nTesting specific websockets imports...")
    try:
        from websockets import datastructures
        print("websockets.datastructures import successful")
    except ImportError as e:
        print(f"datastructures import failed: {e}")
    
    print("\nTesting uvicorn import...")
    import uvicorn
    print(f"uvicorn package exists: {uvicorn}")
    
    print("\nChecking pip installation...")
    import subprocess
    result = subprocess.run(['pip', 'list'], capture_output=True, text=True)
    print(result.stdout)
    
except Exception as e:
    print(f"Error: {e}")