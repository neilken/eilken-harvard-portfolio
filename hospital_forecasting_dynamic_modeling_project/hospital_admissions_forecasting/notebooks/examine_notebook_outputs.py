#!/usr/bin/env python3
"""
Examine outputs from Jupyter notebook cells.

Usage:
    python examine_notebook_outputs.py <notebook_path> [options]

Examples:
    # Show all outputs from all cells
    python examine_notebook_outputs.py 03_feature_engineering.ipynb

    # Show outputs from specific cell
    python examine_notebook_outputs.py 03_feature_engineering.ipynb --cell 19

    # Show outputs from multiple cells
    python examine_notebook_outputs.py 03_feature_engineering.ipynb --cell 19 --cell 20

    # Search for specific text in outputs
    python examine_notebook_outputs.py 03_feature_engineering.ipynb --search "VIF"

    # Show only cells with outputs
    python examine_notebook_outputs.py 03_feature_engineering.ipynb --only-with-outputs

    # Show last N cells
    python examine_notebook_outputs.py 03_feature_engineering.ipynb --last 5
"""

import json
import sys
import argparse
from pathlib import Path
from typing import List, Optional, Set


def extract_output_text(output: dict) -> str:
    """Extract text from a notebook output."""
    if 'text' in output:
        text = output['text']
        if isinstance(text, list):
            return ''.join(text)
        return str(text)
    elif 'data' in output and 'text/plain' in output['data']:
        text = output['data']['text/plain']
        if isinstance(text, list):
            return ''.join(text)
        return str(text)
    return ''


def get_cell_outputs(notebook_path: Path, cell_indices: Optional[List[int]] = None) -> dict:
    """Extract outputs from notebook cells."""
    try:
        with open(notebook_path, 'r', encoding='utf-8') as f:
            nb = json.load(f)
    except FileNotFoundError:
        print(f"Error: Notebook '{notebook_path}' not found.", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in notebook '{notebook_path}': {e}", file=sys.stderr)
        sys.exit(1)

    cells = nb.get('cells', [])
    results = {}

    # Determine which cells to examine
    if cell_indices is None:
        cell_indices = list(range(len(cells)))
    else:
        # Validate cell indices
        valid_indices = [i for i in cell_indices if 0 <= i < len(cells)]
        if len(valid_indices) != len(cell_indices):
            invalid = [i for i in cell_indices if i not in valid_indices]
            print(f"Warning: Invalid cell indices: {invalid}", file=sys.stderr)
        cell_indices = valid_indices

    for cell_idx in cell_indices:
        cell = cells[cell_idx]
        outputs = cell.get('outputs', [])
        
        if not outputs:
            continue

        # Extract all output text
        output_texts = []
        for output in outputs:
            text = extract_output_text(output)
            if text:
                output_texts.append(text)

        if output_texts:
            results[cell_idx] = {
                'cell_type': cell.get('cell_type', 'unknown'),
                'source_preview': ''.join(cell.get('source', []))[:100].replace('\n', ' '),
                'outputs': output_texts,
                'output_count': len(outputs)
            }

    return results


def print_outputs(results: dict, search_term: Optional[str] = None, max_length: Optional[int] = None):
    """Print cell outputs with formatting."""
    if not results:
        print("No outputs found.")
        return

    for cell_idx in sorted(results.keys()):
        cell_info = results[cell_idx]
        
        # Filter by search term if provided
        all_output_text = '\n'.join(cell_info['outputs'])
        if search_term and search_term.lower() not in all_output_text.lower():
            continue

        print(f"\n{'='*80}")
        print(f"Cell {cell_idx} ({cell_info['cell_type']})")
        print(f"{'='*80}")
        print(f"Source preview: {cell_info['source_preview']}...")
        print(f"Output count: {cell_info['output_count']}")
        print(f"{'-'*80}")

        for i, output_text in enumerate(cell_info['outputs'], 1):
            if max_length and len(output_text) > max_length:
                print(f"\n[Output {i} - Truncated to {max_length} chars]")
                print(output_text[:max_length])
                print(f"\n... ({len(output_text) - max_length} more characters)")
            else:
                print(f"\n[Output {i}]")
                print(output_text)


def main():
    parser = argparse.ArgumentParser(
        description='Examine outputs from Jupyter notebook cells',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        'notebook',
        type=str,
        help='Path to the notebook file'
    )
    
    parser.add_argument(
        '--cell', '-c',
        type=int,
        action='append',
        dest='cells',
        help='Cell index to examine (can be used multiple times)'
    )
    
    parser.add_argument(
        '--search', '-s',
        type=str,
        help='Search for specific text in outputs'
    )
    
    parser.add_argument(
        '--only-with-outputs',
        action='store_true',
        help='Show only cells that have outputs'
    )
    
    parser.add_argument(
        '--last', '-l',
        type=int,
        help='Show outputs from last N cells'
    )
    
    parser.add_argument(
        '--max-length',
        type=int,
        default=None,
        help='Maximum length of output to display (truncate if longer)'
    )
    
    parser.add_argument(
        '--list-cells',
        action='store_true',
        help='List all cells with their indices and types'
    )

    args = parser.parse_args()

    notebook_path = Path(args.notebook)
    if not notebook_path.exists():
        print(f"Error: Notebook '{notebook_path}' not found.", file=sys.stderr)
        sys.exit(1)

    # Load notebook to get cell count
    try:
        with open(notebook_path, 'r', encoding='utf-8') as f:
            nb = json.load(f)
        total_cells = len(nb.get('cells', []))
    except Exception as e:
        print(f"Error reading notebook: {e}", file=sys.stderr)
        sys.exit(1)

    # List cells if requested
    if args.list_cells:
        print(f"Notebook: {notebook_path}")
        print(f"Total cells: {total_cells}\n")
        print(f"{'Index':<8} {'Type':<12} {'Has Outputs':<15} {'Source Preview'}")
        print("-" * 80)
        
        for i, cell in enumerate(nb.get('cells', [])):
            has_outputs = 'Yes' if cell.get('outputs') else 'No'
            source_preview = ''.join(cell.get('source', []))[:50].replace('\n', ' ')
            cell_type = cell.get('cell_type', 'unknown')
            print(f"{i:<8} {cell_type:<12} {has_outputs:<15} {source_preview}")
        return

    # Determine cell indices
    cell_indices = args.cells
    
    if args.last:
        # Show last N cells
        cell_indices = list(range(max(0, total_cells - args.last), total_cells))
    
    # Get outputs
    results = get_cell_outputs(notebook_path, cell_indices)
    
    # Filter by only-with-outputs (already handled in get_cell_outputs)
    if args.only_with_outputs and not args.cells and not args.last:
        # If no specific cells requested, show all cells with outputs
        results = get_cell_outputs(notebook_path, None)
    
    # Print results
    if results:
        print(f"Examining outputs from notebook: {notebook_path}")
        if args.cells:
            print(f"Cells: {args.cells}")
        elif args.last:
            print(f"Last {args.last} cells")
        else:
            print("All cells")
        if args.search:
            print(f"Search term: '{args.search}'")
        print()
    
    print_outputs(results, args.search, args.max_length)


if __name__ == '__main__':
    main()

