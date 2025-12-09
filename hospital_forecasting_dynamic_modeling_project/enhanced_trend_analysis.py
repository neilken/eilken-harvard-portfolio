"""
Enhanced trend analysis - deeper interpretation of plot patterns
"""

import json
from pathlib import Path

def analyze_trends_from_results(results_file='extracted_plots/analysis_results.json'):
    """Analyze trends and patterns from the analysis results"""
    
    with open(results_file, 'r') as f:
        results = json.load(f)
    
    notebook_data = results.get('notebook_data', {})
    analysis_results = results.get('analysis_results', {})
    
    print("=" * 70)
    print("ENHANCED TREND ANALYSIS & INTERPRETATION")
    print("=" * 70)
    
    # 1. Day of Week Pattern Analysis
    print("\n📅 DAY OF WEEK PATTERN ANALYSIS")
    print("-" * 70)
    
    if 'day_of_week_avg' in notebook_data and notebook_data['day_of_week_avg']:
        dow_avg = notebook_data['day_of_week_avg']
        
        # Calculate statistics
        weekend_days = ['Saturday', 'Sunday']
        weekdays = [k for k in dow_avg.keys() if k not in weekend_days]
        
        weekday_avg = sum(dow_avg[k] for k in weekdays) / len(weekdays) if weekdays else 0
        weekend_avg = sum(dow_avg[k] for k in weekend_days) / len(weekend_days) if weekend_days else 0
        
        print(f"Weekday average: {weekday_avg:.2f} admissions/day")
        print(f"Weekend average: {weekend_avg:.2f} admissions/day")
        print(f"Difference: {weekday_avg - weekend_avg:.2f} ({((weekday_avg - weekend_avg) / weekday_avg * 100):.1f}% lower on weekends)")
        
        # Interpretation
        if weekend_avg < weekday_avg:
            print("\n✓ INTERPRETATION: Weekend admissions are significantly lower")
            print("  → Expected pattern: Fewer elective procedures on weekends")
            print("  → Emergency admissions continue but at reduced volume")
            print("  → This pattern is consistent across most hospitals")
        else:
            print("\n⚠ INTERPRETATION: Unusual pattern - weekends higher than weekdays")
            print("  → May indicate data quality issue or special circumstances")
        
        # Find peak day
        peak_day = max(dow_avg.items(), key=lambda x: x[1])
        print(f"\nPeak day: {peak_day[0]} ({peak_day[1]:.2f} admissions)")
        print(f"Lowest day: {min(dow_avg.items(), key=lambda x: x[1])[0]} ({min(dow_avg.values()):.2f} admissions)")
    
    # 2. Monthly/Seasonal Pattern Analysis
    print("\n\n📊 MONTHLY/SEASONAL PATTERN ANALYSIS")
    print("-" * 70)
    
    if 'monthly_avg' in notebook_data and notebook_data['monthly_avg']:
        monthly_avg = notebook_data['monthly_avg']
        month_names = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
                      7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'}
        
        # Seasonal analysis
        winter_months = [11, 12, 1, 2]  # Nov, Dec, Jan, Feb
        spring_months = [3, 4, 5]       # Mar, Apr, May
        summer_months = [6, 7, 8]       # Jun, Jul, Aug
        fall_months = [9, 10]           # Sep, Oct
        
        seasons = {
            'Winter': [m for m in winter_months if m in monthly_avg],
            'Spring': [m for m in spring_months if m in monthly_avg],
            'Summer': [m for m in summer_months if m in monthly_avg],
            'Fall': [m for m in fall_months if m in monthly_avg]
        }
        
        season_avgs = {}
        for season, months in seasons.items():
            if months:
                season_avgs[season] = sum(monthly_avg[m] for m in months) / len(months)
                print(f"{season}: {season_avgs[season]:.2f} admissions/day")
        
        # Find peak and low months
        peak_month = max(monthly_avg.items(), key=lambda x: x[1])
        low_month = min(monthly_avg.items(), key=lambda x: x[1])
        
        print(f"\nPeak month: {month_names.get(peak_month[0], peak_month[0])} ({peak_month[1]:.2f} admissions/day)")
        print(f"Lowest month: {month_names.get(low_month[0], low_month[0])} ({low_month[1]:.2f} admissions/day)")
        print(f"Seasonal variation: {peak_month[1] - low_month[1]:.2f} ({((peak_month[1] - low_month[1]) / peak_month[1] * 100):.1f}% difference)")
        
        # Interpretation
        print("\n✓ INTERPRETATION:")
        if 'Winter' in season_avgs and 'Summer' in season_avgs:
            if season_avgs['Winter'] > season_avgs['Summer']:
                print("  → Winter admissions higher than summer (expected)")
                print("    - Flu season (Nov-Feb) typically increases hospitalizations")
                print("    - Respiratory illnesses more common in cold months")
                print("    - Summer often has lower baseline admissions")
            else:
                print("  → Unusual: Summer admissions higher than winter")
                print("    - May indicate data quality issue or regional patterns")
        
        # Check for flu season pattern
        if 11 in monthly_avg and 12 in monthly_avg and 1 in monthly_avg and 2 in monthly_avg:
            flu_season_avg = (monthly_avg[11] + monthly_avg[12] + monthly_avg[1] + monthly_avg[2]) / 4
            non_flu_avg = sum(v for k, v in monthly_avg.items() if k not in [11, 12, 1, 2]) / (len(monthly_avg) - 4)
            print(f"\nFlu season (Nov-Feb) average: {flu_season_avg:.2f}")
            print(f"Non-flu season average: {non_flu_avg:.2f}")
            print(f"Flu season increase: {flu_season_avg - non_flu_avg:.2f} ({((flu_season_avg - non_flu_avg) / non_flu_avg * 100):.1f}%)")
    
    # 3. Overall Statistics
    print("\n\n📈 OVERALL STATISTICS")
    print("-" * 70)
    
    if notebook_data.get('total_admissions') and notebook_data.get('avg_daily'):
        total = notebook_data['total_admissions']
        avg = notebook_data['avg_daily']
        
        print(f"Total admissions: {total:,}")
        print(f"Average daily: {avg:.2f}")
        date_range = notebook_data.get('date_range')
        if date_range and isinstance(date_range, (list, tuple)) and len(date_range) >= 2:
            print(f"Date range: {date_range[0]} to {date_range[1]}")
        else:
            print(f"Date range: Unknown")
        
        # Calculate variability
        if 'day_of_week_avg' in notebook_data and notebook_data['day_of_week_avg']:
            dow_values = list(notebook_data['day_of_week_avg'].values())
            import numpy as np
            cv = np.std(dow_values) / np.mean(dow_values) if np.mean(dow_values) > 0 else 0
            print(f"\nDay-of-week coefficient of variation: {cv:.3f}")
            if cv < 0.1:
                print("  → Low variability (consistent across days)")
            elif cv < 0.2:
                print("  → Moderate variability (some day-of-week effects)")
            else:
                print("  → High variability (strong day-of-week patterns)")
    
    # 4. Plot Quality Assessment
    print("\n\n🎨 PLOT QUALITY ASSESSMENT")
    print("-" * 70)
    
    for filename, analysis in analysis_results.items():
        print(f"\n{filename}:")
        
        ocr_data = analysis.get('ocr_data', {})
        text_count = ocr_data.get('text_count', 0)
        structure = analysis.get('structure_analysis', {})
        
        print(f"  Text regions detected: {text_count}")
        print(f"  Plot structure: {structure.get('dimensions', 'Unknown')} pixels")
        print(f"  Edge density: {structure.get('edge_density', 0)*100:.2f}% (indicates plot elements)")
        
        # Quality score
        quality_score = 0
        if text_count > 5:
            quality_score += 1
        if structure.get('edge_density', 0) > 0.005:
            quality_score += 1
        if analysis.get('title'):
            quality_score += 1
        
        quality_level = ['Poor', 'Fair', 'Good', 'Excellent'][quality_score]
        print(f"  Quality assessment: {quality_level} ({quality_score}/3)")
    
    # 5. Data Consistency Check
    print("\n\n✓ DATA CONSISTENCY CHECKS")
    print("-" * 70)
    
    checks = []
    
    # Check 1: Day of week pattern makes sense
    if 'day_of_week_avg' in notebook_data and notebook_data['day_of_week_avg']:
        dow_avg = notebook_data['day_of_week_avg']
        weekend_avg = sum(dow_avg.get(k, 0) for k in ['Saturday', 'Sunday']) / 2
        weekday_avg = sum(v for k, v in dow_avg.items() if k not in ['Saturday', 'Sunday']) / 5
        checks.append(("Weekend < Weekday pattern", weekend_avg < weekday_avg))
    
    # Check 2: Monthly values in reasonable range
    if 'monthly_avg' in notebook_data and notebook_data['monthly_avg']:
        monthly_values = list(notebook_data['monthly_avg'].values())
        if monthly_values:
            min_month = min(monthly_values)
            max_month = max(monthly_values)
            checks.append(("Monthly values reasonable", 20 < min_month < 60 and 20 < max_month < 60))
    
    # Check 3: Average daily aligns with totals
    if notebook_data.get('total_admissions') and notebook_data.get('avg_daily'):
        # Rough check: should be in reasonable range
        avg = notebook_data['avg_daily']
        checks.append(("Average daily reasonable", 30 < avg < 100))
    
    # Check 4: Date range consistency
    if notebook_data.get('date_range'):
        start_year = int(notebook_data['date_range'][0][:4])
        end_year = int(notebook_data['date_range'][1][:4])
        checks.append(("Date range valid", 2000 <= start_year < end_year <= 2025))
    
    for check_name, passed in checks:
        status = "✓" if passed else "✗"
        print(f"{status} {check_name}")
    
    passed_checks = sum(1 for _, p in checks if p)
    print(f"\nConsistency score: {passed_checks}/{len(checks)} checks passed")
    
    if passed_checks == len(checks):
        print("✓ All consistency checks passed - data appears valid!")
    elif passed_checks >= len(checks) * 0.75:
        print("⚠ Most checks passed - minor issues may exist")
    else:
        print("✗ Multiple consistency issues detected - review recommended")
    
    print("\n" + "=" * 70)
    print("END OF ENHANCED TREND ANALYSIS")
    print("=" * 70 + "\n")

if __name__ == '__main__':
    analyze_trends_from_results()

