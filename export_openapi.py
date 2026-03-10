import json
import os
import sys

# Add the current directory to sys.path so we can import app
sys.path.append(os.getcwd())

try:
    from app.main import app
    from fastapi.openapi.utils import get_openapi
    
    # Generate OpenAPI schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
    )
    
    # Save to file
    with open("openapi.json", "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2, ensure_ascii=False)
        
    print("Successfully exported openapi.json")
    
except Exception as e:
    print(f"Error exporting OpenAPI: {e}")
    import traceback
    traceback.print_exc()
