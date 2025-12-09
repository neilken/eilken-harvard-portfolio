"""
Script to run all notebooks sequentially and display outputs.
"""
import sys
import os
import json
from pathlib import Path

def run_notebook(notebook_path):
    """Run a notebook and return outputs."""
    print(f"\n{'='*80}")
    print(f"Running: {notebook_path}")
    print(f"{'='*80}\n")
    
    try:
        # Try using nbconvert if available
        import subprocess
        result = subprocess.run(
            ['jupyter', 'nbconvert', '--to', 'notebook', '--execute', '--inplace', str(notebook_path)],
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout per notebook
        )
        
        if result.returncode == 0:
            print(f"✓ Notebook executed successfully: {notebook_path}")
            return True
        else:
            print(f"✗ Error executing notebook: {notebook_path}")
            print(f"Error output: {result.stderr}")
            return False
            
    except FileNotFoundError:
        print("jupyter command not found. Trying alternative method...")
        # Alternative: use papermill or nbformat
        try:
            import nbformat
            from nbconvert.preprocessors import ExecutePreprocessor
            
            with open(notebook_path, 'r', encoding='utf-8') as f:
                nb = nbformat.read(f, as_version=4)
            
            ep = ExecutePreprocessor(timeout=600, kernel_name='python3')
            ep.preprocess(nb, {'metadata': {'path': str(notebook_path.parent)}})
            
            with open(notebook_path, 'w', encoding='utf-8') as f:
                nbformat.write(nb, f)
            
            print(f"✓ Notebook executed successfully: {notebook_path}")
            return True
            
        except ImportError:
            print("nbformat/nbconvert not available. Cannot execute notebooks programmatically.")
            print("Please run notebooks manually in Jupyter or install: pip install nbconvert")
            return False
        except Exception as e:
            print(f"✗ Error executing notebook: {e}")
            return False
    except subprocess.TimeoutExpired:
        print(f"✗ Notebook execution timed out: {notebook_path}")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def main():
    """Run all notebooks in sequence."""
    notebooks_dir = Path(__file__).parent / 'notebooks'
    
    # List of notebooks in order
    notebook_files = [
        '00_generate_mock_data.ipynb',
        '01_data_extraction.ipynb',
        '02_exploratory_analysis.ipynb',
        '03_feature_engineering.ipynb',
        '04_model_development.ipynb',
        '05_model_evaluation.ipynb',
        '06_forecasting.ipynb'
    ]
    
    results = {}
    
    for notebook_file in notebook_files:
        notebook_path = notebooks_dir / notebook_file
        if notebook_path.exists():
            success = run_notebook(notebook_path)
            results[notebook_file] = success
        else:
            print(f"✗ Notebook not found: {notebook_path}")
            results[notebook_file] = False
    
    # Summary
    print(f"\n{'='*80}")
    print("EXECUTION SUMMARY")
    print(f"{'='*80}")
    for notebook, success in results.items():
        status = "✓" if success else "✗"
        print(f"{status} {notebook}")
    
    successful = sum(1 for s in results.values() if s)
    print(f"\nSuccessful: {successful}/{len(results)}")

if __name__ == '__main__':
    main()



