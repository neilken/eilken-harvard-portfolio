"""Check feature engineering notebook outputs for correctness"""
import json
import re

# Read notebook
with open('03_feature_engineering.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

print("="*60)
print("FEATURE ENGINEERING OUTPUT ANALYSIS")
print("="*60)

# Find cells with outputs
for i, cell in enumerate(nb['cells']):
    if 'outputs' in cell and len(cell.get('outputs', [])) > 0:
        # Get output text
        output_text = ''
        for output in cell['outputs']:
            if 'text' in output:
                if isinstance(output['text'], list):
                    output_text += ''.join(output['text'])
                else:
                    output_text += str(output['text'])
        
        # Check for key outputs
        if 'Loaded' in output_text and 'days' in output_text:
            print(f"\nCell {i}: Data Loading")
            if '39,884' in output_text:
                print("  ✓ Correct: 39,884 days loaded")
            if '2105-10-04' in output_text:
                print("  ✓ Correct: Date range starts Oct 4, 2105")
        
        if 'Holiday features created' in output_text:
            print(f"\nCell {i}: Holiday Features")
            match = re.search(r'Total holidays: (\d+)', output_text)
            if match:
                holidays = int(match.group(1))
                if 1000 <= holidays <= 1500:
                    print(f"  ✓ Reasonable: {holidays} holidays over ~109 years (~{holidays/109:.1f}/year)")
                else:
                    print(f"  ⚠️  Unexpected: {holidays} holidays")
        
        if 'Removed.*rows with NaN' in output_text or 'Removed' in output_text and 'rows' in output_text:
            print(f"\nCell {i}: Data Cleaning")
            match = re.search(r'Removed (\d+) rows', output_text)
            if match:
                removed = int(match.group(1))
                if removed == 365:
                    print(f"  ✓ Correct: Removed 365 rows (from lag_365)")
                else:
                    print(f"  ⚠️  Unexpected: Removed {removed} rows")
        
        if 'highly correlated feature pairs' in output_text:
            print(f"\nCell {i}: Multicollinearity Check")
            match = re.search(r'Found (\d+) highly correlated', output_text)
            if match:
                pairs = int(match.group(1))
                if pairs > 50:
                    print(f"  ⚠️  HIGH: {pairs} highly correlated pairs (consider removing redundant features)")
                else:
                    print(f"  ✓ Acceptable: {pairs} highly correlated pairs")
        
        if 'Days near capacity (max):' in output_text:
            print(f"\nCell {i}: Capacity Features")
            match = re.search(r'Days near capacity \(max\): (\d+)', output_text)
            if match:
                max_days = int(match.group(1))
                if max_days > 1000:
                    print(f"  ⚠️  UNUSUAL: {max_days} consecutive days near capacity ({max_days/365:.1f} years)")
                    print("     This seems unrealistic - check data quality or calculation")
                else:
                    print(f"  ✓ Reasonable: {max_days} consecutive days near capacity")

print("\n" + "="*60)
print("Analysis complete!")
print("="*60)



