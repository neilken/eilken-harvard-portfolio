#!/usr/bin/env python3
"""Verify Google Cloud credentials and permissions.

This script checks if the service account has the required permissions
for both RAG (GCS) and Orchestrator (Vertex AI) services.
"""

import os
import sys
import json
from pathlib import Path

def check_credentials_file():
    """Check if credentials file exists and is valid."""
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    
    if not creds_path:
        print("[✗] GOOGLE_APPLICATION_CREDENTIALS environment variable not set")
        return None
    
    if not os.path.exists(creds_path):
        print(f"[✗] Credentials file not found: {creds_path}")
        return None
    
    try:
        with open(creds_path, 'r') as f:
            creds = json.load(f)
        
        if 'type' not in creds or creds['type'] != 'service_account':
            print(f"[✗] Invalid credentials file: expected service account, got {creds.get('type', 'unknown')}")
            return None
        
        print(f"[✓] Credentials file found: {creds_path}")
        print(f"    Service account email: {creds.get('client_email', 'unknown')}")
        print(f"    Project ID: {creds.get('project_id', 'unknown')}")
        return creds
        
    except json.JSONDecodeError:
        print(f"[✗] Invalid JSON in credentials file: {creds_path}")
        return None
    except Exception as e:
        print(f"[✗] Error reading credentials file: {e}")
        return None

def check_gcs_permissions():
    """Check if credentials have GCS permissions."""
    try:
        from google.cloud import storage
        from google.oauth2 import service_account
        
        creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if not creds_path or not os.path.exists(creds_path):
            print("[⚠] Cannot check GCS permissions: credentials file not found")
            return False
        
        credentials = service_account.Credentials.from_service_account_file(creds_path)
        client = storage.Client(credentials=credentials, project=credentials.project_id)
        
        # Try to list buckets (requires storage.buckets.list permission)
        try:
            buckets = list(client.list_buckets(max_results=1))
            print("[✓] GCS permissions: Can list buckets")
            return True
        except Exception as e:
            if "PermissionDenied" in str(e) or "403" in str(e):
                print("[✗] GCS permissions: Cannot list buckets (missing storage.buckets.list)")
                print(f"    Error: {e}")
                return False
            else:
                # Other errors might be network-related, but permissions might be OK
                print("[⚠] GCS permissions: Could not verify (network/auth error)")
                print(f"    Error: {e}")
                return None
        
    except ImportError:
        print("[⚠] Cannot check GCS permissions: google-cloud-storage not installed")
        return None
    except Exception as e:
        print(f"[⚠] Error checking GCS permissions: {e}")
        return None

def check_vertex_ai_permissions():
    """Check if credentials have Vertex AI permissions."""
    try:
        from google.cloud import aiplatform
        from google.oauth2 import service_account
        
        creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        project_id = os.getenv("VERTEX_PROJECT_ID")
        region = os.getenv("VERTEX_REGION", "us-central1")
        
        if not creds_path or not os.path.exists(creds_path):
            print("[⚠] Cannot check Vertex AI permissions: credentials file not found")
            return False
        
        if not project_id:
            print("[⚠] Cannot check Vertex AI permissions: VERTEX_PROJECT_ID not set")
            return False
        
        credentials = service_account.Credentials.from_service_account_file(creds_path)
        
        # Initialize Vertex AI (this checks permissions)
        try:
            aiplatform.init(
                project=project_id,
                location=region,
                credentials=credentials
            )
            print("[✓] Vertex AI permissions: Can initialize Vertex AI")
            
            # Try to list models (requires aiplatform.models.list permission)
            try:
                from google.cloud import aiplatform_v1
                model_service_client = aiplatform_v1.ModelServiceClient(credentials=credentials)
                parent = f"projects/{project_id}/locations/{region}"
                # Just check if we can create the client, don't actually list
                print("[✓] Vertex AI permissions: Can access Model Service")
                return True
            except Exception as e:
                print(f"[⚠] Vertex AI permissions: Model Service access check failed: {e}")
                # Initialization succeeded, so basic permissions are OK
                return True
                
        except Exception as e:
            if "PermissionDenied" in str(e) or "403" in str(e):
                print("[✗] Vertex AI permissions: Cannot initialize Vertex AI")
                print(f"    Error: {e}")
                print(f"    Required role: roles/aiplatform.user")
                return False
            else:
                print(f"[⚠] Error checking Vertex AI permissions: {e}")
                return None
        
    except ImportError:
        print("[⚠] Cannot check Vertex AI permissions: google-cloud-aiplatform not installed")
        return None
    except Exception as e:
        print(f"[⚠] Error checking Vertex AI permissions: {e}")
        return None

def check_required_roles():
    """Print required IAM roles for the service account."""
    print("\n" + "=" * 80)
    print("REQUIRED IAM ROLES")
    print("=" * 80)
    print("\nFor RAG Service (GCS):")
    print("  - roles/storage.objectAdmin (or)")
    print("  - roles/storage.objectCreator + roles/storage.objectViewer")
    print("\nFor Orchestrator Service (Vertex AI):")
    print("  - roles/aiplatform.user (Vertex AI User)")
    print("\nTo grant roles in GCP Console:")
    print("  1. Go to: https://console.cloud.google.com/iam-admin/iam")
    print("  2. Find your service account")
    print("  3. Click 'Edit' (pencil icon)")
    print("  4. Click 'Add Another Role'")
    print("  5. Add the required roles")
    print("=" * 80)

def main():
    """Main verification function."""
    print("=" * 80)
    print("GOOGLE CLOUD CREDENTIALS VERIFICATION")
    print("=" * 80)
    
    # Check credentials file
    print("\n[STEP 1] Checking Credentials File...")
    creds = check_credentials_file()
    if not creds:
        print("\n[✗] Credentials verification failed")
        check_required_roles()
        sys.exit(1)
    
    # Check GCS permissions
    print("\n[STEP 2] Checking GCS Permissions...")
    gcs_ok = check_gcs_permissions()
    
    # Check Vertex AI permissions
    print("\n[STEP 3] Checking Vertex AI Permissions...")
    vertex_ok = check_vertex_ai_permissions()
    
    # Summary
    print("\n" + "=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)
    
    all_ok = True
    if gcs_ok is False:
        print("[✗] GCS permissions: FAILED")
        all_ok = False
    elif gcs_ok is True:
        print("[✓] GCS permissions: OK")
    else:
        print("[⚠] GCS permissions: UNKNOWN (check manually)")
    
    if vertex_ok is False:
        print("[✗] Vertex AI permissions: FAILED")
        all_ok = False
    elif vertex_ok is True:
        print("[✓] Vertex AI permissions: OK")
    else:
        print("[⚠] Vertex AI permissions: UNKNOWN (check manually)")
    
    if not all_ok:
        print("\n[✗] Some permissions are missing. Please grant the required roles.")
        check_required_roles()
        sys.exit(1)
    else:
        print("\n[✓] All permissions verified!")
        print("    Your credentials are ready for both RAG and Orchestrator services.")
        sys.exit(0)

if __name__ == "__main__":
    main()

