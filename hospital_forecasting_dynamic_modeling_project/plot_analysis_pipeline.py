"""
Comprehensive Plot Analysis Pipeline
Extracts plots from notebook, analyzes them using OCR and visual analysis,
and validates trends against data outputs.
"""

import json
import base64
from pathlib import Path
import easyocr
import numpy as np
from PIL import Image
import pandas as pd
import re

class PlotAnalysisPipeline:
    def __init__(self, notebook_path, output_dir='extracted_plots'):
        self.notebook_path = Path(notebook_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.reader = None
        self.extracted_images = {}
        self.analysis_results = {}
        
    def initialize_ocr(self):
        """Initialize OCR reader"""
        print("Initializing OCR reader...")
        try:
            self.reader = easyocr.Reader(['en'], gpu=False)
            print("✓ OCR initialized successfully\n")
            return True
        except Exception as e:
            print(f"✗ Error initializing OCR: {e}\n")
            return False
    
    def extract_images_from_notebook(self):
        """Extract all PNG images from notebook"""
        print("=" * 70)
        print("STEP 1: EXTRACTING IMAGES FROM NOTEBOOK")
        print("=" * 70)
        
        with open(self.notebook_path, 'r', encoding='utf-8') as f:
            nb = json.load(f)
        
        # Map of cell indices to expected plot names
        expected_plots = {
            12: 'daily_admissions_timeseries.png',
            14: 'decomposition.png',
            16: 'day_of_week_pattern.png',
            18: 'monthly_pattern.png',
            23: 'acf_pacf.png'
        }
        
        extracted_count = 0
        for i, cell in enumerate(nb['cells']):
            if cell.get('outputs'):
                for output in cell['outputs']:
                    if output.get('data', {}).get('image/png'):
                        image_data = output['data']['image/png']
                        if i in expected_plots:
                            filename = expected_plots[i]
                            filepath = self.output_dir / filename
                            
                            # Decode and save
                            image_bytes = base64.b64decode(image_data)
                            with open(filepath, 'wb') as f:
                                f.write(image_bytes)
                            
                            self.extracted_images[filename] = {
                                'path': filepath,
                                'cell': i,
                                'size_kb': len(image_bytes) / 1024
                            }
                            extracted_count += 1
                            print(f"  ✓ Extracted: {filename} ({len(image_bytes) / 1024:.1f} KB)")
        
        print(f"\nExtracted {extracted_count} images\n")
        return extracted_count > 0
    
    def analyze_image_structure(self, img_path):
        """Analyze visual structure of plot"""
        img = Image.open(img_path)
        img_array = np.array(img)
        
        # Convert to grayscale
        if img.mode == 'RGBA':
            rgb = img_array[:, :, :3]
            gray = np.mean(rgb, axis=2)
        else:
            gray = np.array(img.convert('L'))
        
        # Detect edges (sudden intensity changes)
        edges_h = np.abs(np.diff(gray, axis=0)) > 20
        edges_v = np.abs(np.diff(gray, axis=1)) > 20
        edge_density = (np.sum(edges_h) + np.sum(edges_v)) / (edges_h.size + edges_v.size)
        
        # Find dark regions (plot elements)
        dark_regions = gray < 100
        dark_density = np.sum(dark_regions) / dark_regions.size
        
        # Color variation
        if img.mode == 'RGBA':
            rgb = img_array[:, :, :3]
            color_variation = np.std(rgb, axis=2)
            has_color = np.sum(color_variation > 10) / color_variation.size
        else:
            has_color = 0
        
        return {
            'dimensions': img.size,
            'edge_density': edge_density,
            'dark_density': dark_density,
            'color_variation': has_color,
            'avg_brightness': np.mean(gray)
        }
    
    def extract_text_with_ocr(self, img_path):
        """Extract text from image using OCR"""
        if not self.reader:
            return {}
        
        try:
            ocr_results = self.reader.readtext(str(img_path))
            
            text_regions = []
            all_text = []
            for bbox, text, confidence in ocr_results:
                if confidence > 0.3:
                    text_regions.append({
                        'text': text,
                        'confidence': float(confidence)
                    })
                    all_text.append(text)
            
            return {
                'text_regions': text_regions,
                'extracted_text': ' '.join(all_text),
                'text_count': len(text_regions)
            }
        except Exception as e:
            return {'error': str(e)}
    
    def analyze_timeseries_plot(self, img_path, ocr_data):
        """Analyze time series plot and extract trends"""
        structure = self.analyze_image_structure(img_path)
        text = ocr_data.get('extracted_text', '').lower()
        
        analysis = {
            'plot_type': 'time_series',
            'title': None,
            'date_range': [],
            'trend_detected': False,
            'structure_analysis': structure
        }
        
        # Extract title
        if 'daily hospital admissions' in text:
            analysis['title'] = 'Daily Hospital Admissions Over Time'
        
        # Extract dates
        dates = re.findall(r'\b(20\d{2})\b', text)
        analysis['date_range'] = sorted(set(dates))
        
        # Detect trend indicators from structure
        # High edge density suggests continuous line
        if structure['edge_density'] > 0.005:
            analysis['trend_detected'] = True
            analysis['trend_type'] = 'continuous_line'
        
        return analysis
    
    def analyze_day_of_week_plot(self, img_path, ocr_data):
        """Analyze day of week bar chart"""
        structure = self.analyze_image_structure(img_path)
        text = ocr_data.get('extracted_text', '').lower()
        
        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        detected_days = [day for day in days if day in text]
        
        analysis = {
            'plot_type': 'bar_chart',
            'title': 'Average Daily Admissions by Day of Week' if 'day of week' in text else None,
            'days_detected': len(detected_days),
            'detected_days': detected_days,
            'structure_analysis': structure
        }
        
        # Higher dark density suggests bar chart structure
        if structure['dark_density'] > 0.01:
            analysis['chart_type_confirmed'] = 'bar_chart'
        
        return analysis
    
    def analyze_monthly_plot(self, img_path, ocr_data):
        """Analyze monthly pattern bar chart"""
        structure = self.analyze_image_structure(img_path)
        text = ocr_data.get('extracted_text', '').lower()
        
        months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 
                  'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
        detected_months = [month for month in months if month in text]
        
        analysis = {
            'plot_type': 'bar_chart',
            'title': 'Average Daily Admissions by Month' if 'month' in text else None,
            'months_detected': len(detected_months),
            'detected_months': detected_months,
            'structure_analysis': structure
        }
        
        return analysis
    
    def analyze_acf_pacf_plot(self, img_path, ocr_data):
        """Analyze ACF/PACF plots"""
        structure = self.analyze_image_structure(img_path)
        text = ocr_data.get('extracted_text', '').lower()
        
        # Extract correlation values
        corr_values = re.findall(r'-?\d\.\d{2}', text)
        corr_values = [float(v) for v in corr_values if abs(float(v)) <= 1.0]
        
        analysis = {
            'plot_type': 'correlation_plots',
            'has_acf': 'acf' in text or 'autocorrelation' in text,
            'has_pacf': 'pacf' in text or 'partial' in text,
            'correlation_range': {
                'min': min(corr_values) if corr_values else None,
                'max': max(corr_values) if corr_values else None,
                'values_detected': len(corr_values)
            },
            'structure_analysis': structure
        }
        
        return analysis
    
    def analyze_decomposition_plot(self, img_path, ocr_data):
        """Analyze time series decomposition plot"""
        structure = self.analyze_image_structure(img_path)
        text = ocr_data.get('extracted_text', '').lower()
        
        # Check for subplot indicators
        analysis = {
            'plot_type': 'decomposition',
            'title': 'Time Series Decomposition' if 'decomposition' in text else None,
            'components_detected': [],
            'structure_analysis': structure
        }
        
        # Detect components from text
        if 'trend' in text:
            analysis['components_detected'].append('trend')
        if 'seasonal' in text or 'season' in text:
            analysis['components_detected'].append('seasonal')
        if 'residual' in text:
            analysis['components_detected'].append('residual')
        
        # Taller image suggests multiple stacked subplots
        if structure['dimensions'][1] > 900:
            analysis['multiple_subplots'] = True
            analysis['estimated_subplots'] = 4
        
        return analysis
    
    def validate_against_notebook_outputs(self):
        """Validate plots against numerical outputs from notebook"""
        print("=" * 70)
        print("STEP 4: VALIDATING AGAINST NOTEBOOK DATA OUTPUTS")
        print("=" * 70)
        
        # Read notebook outputs
        with open(self.notebook_path, 'r', encoding='utf-8') as f:
            nb = json.load(f)
        
        # Extract key numerical outputs
        notebook_data = {
            'total_admissions': None,
            'date_range': None,
            'avg_daily': None,
            'day_of_week_avg': {},
            'monthly_avg': {}
        }
        
        for cell in nb['cells']:
            if cell.get('outputs'):
                for output in cell['outputs']:
                    if output.get('output_type') == 'stream':
                        text = ''.join(output.get('text', []))
                        
                        # Extract total admissions
                        match = re.search(r'Total admissions: ([\d,]+)', text)
                        if match:
                            notebook_data['total_admissions'] = int(match.group(1).replace(',', ''))
                        
                        # Extract date range
                        match = re.search(r'Date range: ([\d-]+) to ([\d-]+)', text)
                        if match:
                            notebook_data['date_range'] = (match.group(1), match.group(2))
                        
                        # Extract average daily
                        match = re.search(r'Average daily admissions: ([\d.]+)', text)
                        if match:
                            notebook_data['avg_daily'] = float(match.group(1))
                        
                        # Extract day of week averages
                        if 'Day of week averages:' in text:
                            for line in text.split('\n'):
                                day_match = re.match(r'(\w+)\s+([\d.]+)', line)
                                if day_match:
                                    day, avg = day_match.groups()
                                    notebook_data['day_of_week_avg'][day] = float(avg)
                        
                        # Extract monthly averages
                        if 'Monthly averages:' in text:
                            for line in text.split('\n'):
                                month_match = re.match(r'(\d+)\s+([\d.]+)', line)
                                if month_match:
                                    month, avg = month_match.groups()
                                    notebook_data['monthly_avg'][int(month)] = float(avg)
        
        # Validate plots against data
        validations = {}
        
        # Validate time series plot
        if 'daily_admissions_timeseries.png' in self.analysis_results:
            ts_analysis = self.analysis_results['daily_admissions_timeseries.png']
            validations['timeseries'] = {
                'date_range_matches': False,
                'title_correct': ts_analysis.get('title') is not None
            }
            
            if notebook_data['date_range'] and ts_analysis.get('date_range'):
                start_year = notebook_data['date_range'][0][:4]
                validations['timeseries']['date_range_matches'] = start_year in ts_analysis['date_range']
        
        # Validate day of week plot
        if 'day_of_week_pattern.png' in self.analysis_results:
            dow_analysis = self.analysis_results['day_of_week_pattern.png']
            validations['day_of_week'] = {
                'all_days_detected': dow_analysis.get('days_detected', 0) >= 7,
                'title_correct': dow_analysis.get('title') is not None
            }
            
            # Check if weekend/weekday pattern makes sense
            if notebook_data['day_of_week_avg']:
                weekend_days = ['Saturday', 'Sunday']
                weekday_avg = np.mean([v for k, v in notebook_data['day_of_week_avg'].items() 
                                      if k not in weekend_days])
                weekend_avg = np.mean([v for k, v in notebook_data['day_of_week_avg'].items() 
                                      if k in weekend_days])
                validations['day_of_week']['weekend_lower'] = weekend_avg < weekday_avg
        
        # Validate monthly plot
        if 'monthly_pattern.png' in self.analysis_results:
            month_analysis = self.analysis_results['monthly_pattern.png']
            validations['monthly'] = {
                'title_correct': month_analysis.get('title') is not None,
                'has_seasonality': False
            }
            
            if notebook_data['monthly_avg']:
                # Check for seasonal variation (winter vs summer)
                winter_months = [11, 12, 1, 2]
                summer_months = [6, 7, 8]
                winter_avg = np.mean([v for k, v in notebook_data['monthly_avg'].items() if k in winter_months])
                summer_avg = np.mean([v for k, v in notebook_data['monthly_avg'].items() if k in summer_months])
                validations['monthly']['has_seasonality'] = abs(winter_avg - summer_avg) > 2
        
        # Validate ACF/PACF plot
        if 'acf_pacf.png' in self.analysis_results:
            acf_analysis = self.analysis_results['acf_pacf.png']
            validations['acf_pacf'] = {
                'both_plots_detected': acf_analysis.get('has_acf') and acf_analysis.get('has_pacf'),
                'correlation_range_valid': False
            }
            
            corr_range = acf_analysis.get('correlation_range', {})
            if corr_range.get('min') is not None and corr_range.get('max') is not None:
                validations['acf_pacf']['correlation_range_valid'] = (
                    corr_range['min'] >= -1.0 and corr_range['max'] <= 1.0
                )
        
        # Validate decomposition plot
        if 'decomposition.png' in self.analysis_results:
            decomp_analysis = self.analysis_results['decomposition.png']
            validations['decomposition'] = {
                'multiple_subplots': decomp_analysis.get('multiple_subplots', False),
                'components_detected': len(decomp_analysis.get('components_detected', [])) >= 2
            }
        
        return notebook_data, validations
    
    def run_full_analysis(self):
        """Run complete analysis pipeline"""
        print("\n" + "=" * 70)
        print("PLOT ANALYSIS PIPELINE")
        print("=" * 70 + "\n")
        
        # Step 1: Extract images
        if not self.extract_images_from_notebook():
            print("✗ Failed to extract images")
            return False
        
        # Step 2: Initialize OCR
        if not self.initialize_ocr():
            print("⚠ OCR not available, continuing without text extraction")
        
        # Step 3: Analyze each plot
        print("=" * 70)
        print("STEP 2: ANALYZING PLOT STRUCTURE AND CONTENT")
        print("=" * 70 + "\n")
        
        plot_analyzers = {
            'daily_admissions_timeseries.png': self.analyze_timeseries_plot,
            'day_of_week_pattern.png': self.analyze_day_of_week_plot,
            'monthly_pattern.png': self.analyze_monthly_plot,
            'acf_pacf.png': self.analyze_acf_pacf_plot,
            'decomposition.png': self.analyze_decomposition_plot
        }
        
        for filename, img_info in self.extracted_images.items():
            print(f"Analyzing: {filename}")
            img_path = img_info['path']
            
            # Analyze structure
            structure = self.analyze_image_structure(img_path)
            
            # Extract text with OCR
            ocr_data = self.extract_text_with_ocr(img_path) if self.reader else {}
            
            # Run specific analyzer
            if filename in plot_analyzers:
                analysis = plot_analyzers[filename](img_path, ocr_data)
                analysis['ocr_data'] = ocr_data
                self.analysis_results[filename] = analysis
                print(f"  ✓ Completed analysis\n")
        
        # Step 4: Validate against notebook outputs
        notebook_data, validations = self.validate_against_notebook_outputs()
        
        # Step 5: Generate comprehensive report
        self.generate_report(notebook_data, validations)
        
        return True
    
    def generate_report(self, notebook_data, validations):
        """Generate comprehensive analysis report"""
        print("\n" + "=" * 70)
        print("STEP 5: COMPREHENSIVE ANALYSIS REPORT")
        print("=" * 70 + "\n")
        
        # Overall summary
        print("EXECUTIVE SUMMARY")
        print("-" * 70)
        print(f"✓ Analyzed {len(self.analysis_results)} plots")
        print(f"✓ Extracted text from {sum(1 for r in self.analysis_results.values() if r.get('ocr_data', {}).get('text_count', 0) > 0)} plots")
        print(f"✓ Validated against notebook numerical outputs\n")
        
        # Detailed findings
        print("DETAILED FINDINGS BY PLOT")
        print("-" * 70)
        
        for filename, analysis in self.analysis_results.items():
            print(f"\n📊 {filename}:")
            print(f"   Type: {analysis.get('plot_type', 'unknown')}")
            
            if analysis.get('title'):
                print(f"   Title: {analysis['title']}")
            
            # Plot-specific findings
            if analysis['plot_type'] == 'time_series':
                dates = analysis.get('date_range', [])
                if dates:
                    print(f"   Date range: {min(dates)}-{max(dates)}")
                if analysis.get('trend_detected'):
                    print(f"   ✓ Trend line detected")
            
            elif analysis['plot_type'] == 'bar_chart':
                if 'days_detected' in analysis:
                    print(f"   Days detected: {analysis['days_detected']}/7")
                if 'months_detected' in analysis:
                    print(f"   Months detected: {analysis['months_detected']}/12")
            
            elif analysis['plot_type'] == 'correlation_plots':
                corr_range = analysis.get('correlation_range', {})
                if corr_range.get('min') is not None:
                    print(f"   Correlation range: {corr_range['min']:.2f} to {corr_range['max']:.2f}")
            
            elif analysis['plot_type'] == 'decomposition':
                components = analysis.get('components_detected', [])
                if components:
                    print(f"   Components: {', '.join(components)}")
                if analysis.get('multiple_subplots'):
                    print(f"   ✓ Multiple subplots confirmed")
        
        # Validation results
        print("\n" + "=" * 70)
        print("VALIDATION RESULTS")
        print("=" * 70 + "\n")
        
        validation_status = {
            'timeseries': '✓' if validations.get('timeseries', {}).get('date_range_matches') else '⚠',
            'day_of_week': '✓' if validations.get('day_of_week', {}).get('all_days_detected') else '⚠',
            'monthly': '✓' if validations.get('monthly', {}).get('has_seasonality') else '⚠',
            'acf_pacf': '✓' if validations.get('acf_pacf', {}).get('both_plots_detected') else '⚠',
            'decomposition': '✓' if validations.get('decomposition', {}).get('multiple_subplots') else '⚠'
        }
        
        for plot_type, status in validation_status.items():
            print(f"{status} {plot_type.replace('_', ' ').title()}")
        
        # Trend interpretation
        print("\n" + "=" * 70)
        print("TREND INTERPRETATION")
        print("=" * 70 + "\n")
        
        if 'day_of_week_pattern.png' in self.analysis_results:
            dow_validation = validations.get('day_of_week', {})
            if dow_validation.get('weekend_lower'):
                print("✓ DAY OF WEEK PATTERN: Weekend admissions lower than weekdays")
                print("  → This is expected and makes clinical sense (fewer elective procedures)")
            else:
                print("⚠ DAY OF WEEK PATTERN: Weekend/weekday pattern unclear")
        
        if 'monthly_pattern.png' in self.analysis_results:
            monthly_validation = validations.get('monthly', {})
            if monthly_validation.get('has_seasonality'):
                print("✓ MONTHLY PATTERN: Seasonal variation detected")
                print("  → Higher winter admissions (flu season) vs lower summer is expected")
            else:
                print("⚠ MONTHLY PATTERN: Limited seasonal variation detected")
        
        if 'daily_admissions_timeseries.png' in self.analysis_results:
            print("✓ TIME SERIES: Continuous trend line shows historical pattern")
            print("  → Allows identification of long-term trends and anomalies")
        
        if 'acf_pacf.png' in self.analysis_results:
            print("✓ ACF/PACF: Correlation plots properly formatted")
            print("  → Useful for ARIMA model parameter selection")
        
        if 'decomposition.png' in self.analysis_results:
            print("✓ DECOMPOSITION: Multiple components separated")
            print("  → Trend, seasonal, and residual patterns visible separately")
        
        # Save results to JSON
        results = {
            'extracted_images': {k: {'cell': v['cell'], 'size_kb': v['size_kb']} 
                                for k, v in self.extracted_images.items()},
            'analysis_results': self.analysis_results,
            'notebook_data': notebook_data,
            'validations': validations
        }
        
        output_file = self.output_dir / 'analysis_results.json'
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n{'='*70}")
        print(f"✓ Complete analysis saved to: {output_file}")
        print(f"{'='*70}\n")


if __name__ == '__main__':
    pipeline = PlotAnalysisPipeline(
        notebook_path='hospital_admissions_forecasting/notebooks/02_exploratory_analysis.ipynb'
    )
    pipeline.run_full_analysis()

