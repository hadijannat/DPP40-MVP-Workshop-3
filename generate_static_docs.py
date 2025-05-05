#!/usr/bin/env python
"""
Generates static OpenAPI documentation (Swagger UI and ReDoc HTML files)
based on the FastAPI application's OpenAPI schema.

This script should be run after any changes to the API routes or schemas
to update the static documentation files.
"""

import json
import os
import sys
from pathlib import Path

# Ensure the src directory is in the Python path
project_root = Path(__file__).parent # Project root is the script's directory
sys.path.insert(0, str(project_root))

from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html

# --- Configuration ---
# Adjust these paths if your project structure is different
STATIC_DIR = project_root / "static" # Static dir relative to project root
OPENAPI_JSON_PATH = STATIC_DIR / "openapi.json"
SWAGGER_HTML_PATH = STATIC_DIR / "docs.html"
REDOC_HTML_PATH = STATIC_DIR / "redoc.html"

# URL path where the static openapi.json will be served
# Make sure this matches how you serve static files in your app
# (e.g., if static files are mounted at /static, this should be /static/openapi.json)
OPENAPI_URL = "/static/openapi.json" 

# --- Main Function ---
def generate_docs():
    """Generates the static documentation files."""
    print("Generating static API documentation...")

    # Ensure static directory exists
    STATIC_DIR.mkdir(exist_ok=True)

    try:
        # Import the FastAPI app instance
        # This assumes your app instance is named 'app' in 'src.main'
        from src.main import app
        print("Successfully imported FastAPI app instance.")

        # 1. Get the OpenAPI schema
        print(f"Generating OpenAPI schema...")
        openapi_schema = app.openapi()
        print("OpenAPI schema generated.")

        # 2. Save the schema to openapi.json
        print(f"Saving OpenAPI schema to {OPENAPI_JSON_PATH}...")
        with open(OPENAPI_JSON_PATH, "w") as f:
            json.dump(openapi_schema, f, indent=2)
        print("OpenAPI schema saved.")

        # 3. Generate Swagger UI HTML
        print(f"Generating Swagger UI HTML...")
        swagger_html = get_swagger_ui_html(
            openapi_url=OPENAPI_URL, 
            title=app.title + " - Swagger UI",
            # Optional: Add OAuth2 configuration if needed
            # oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
            # init_oauth=app.swagger_ui_init_oauth,
        )
        print("Swagger UI HTML generated.")

        # 4. Save Swagger UI HTML
        print(f"Saving Swagger UI HTML to {SWAGGER_HTML_PATH}...")
        with open(SWAGGER_HTML_PATH, "w", encoding="utf-8") as f:
            f.write(swagger_html.body.decode("utf-8")) # Extract body and decode
        print("Swagger UI HTML saved.")

        # 5. Generate ReDoc HTML
        print(f"Generating ReDoc HTML...")
        redoc_html = get_redoc_html(
            openapi_url=OPENAPI_URL, 
            title=app.title + " - ReDoc"
        )
        print("ReDoc HTML generated.")

        # 6. Save ReDoc HTML
        print(f"Saving ReDoc HTML to {REDOC_HTML_PATH}...")
        with open(REDOC_HTML_PATH, "w", encoding="utf-8") as f:
            f.write(redoc_html.body.decode("utf-8")) # Extract body and decode
        print("ReDoc HTML saved.")

        print("\nSuccessfully generated static API documentation files:")
        print(f"- Schema: {OPENAPI_JSON_PATH}")
        print(f"- Swagger UI: {SWAGGER_HTML_PATH}")
        print(f"- ReDoc: {REDOC_HTML_PATH}")
        print(f"\nEnsure these files are committed and that the web server serves them correctly.")
        print(f"Update frontend links to point to {SWAGGER_HTML_PATH.name} or {REDOC_HTML_PATH.name}.")

    except ImportError as e:
        print(f"Error: Could not import the FastAPI app. {e}")
        print("Please ensure the script is run from the project root or adjust the import path.")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    generate_docs()

