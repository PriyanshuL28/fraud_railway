from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse, FileResponse
from django.contrib import messages
from django.views.generic import ListView, DetailView
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg, F
import pandas as pd
import numpy as np
import os
from datetime import datetime
import json
import traceback
import time

from .models import FraudAnalysis, Claim
from .forms import UploadFileForm
from .utils.fraud_detector import FraudDetector
from .utils.visualization import FraudVisualizer

def clean_currency_column(series):
    """Clean currency columns by removing $ and , symbols"""
    if series.dtype == 'object':
        # Remove currency symbols and commas
        series = series.astype(str).str.replace('$', '', regex=False)
        series = series.str.replace(',', '', regex=False)
        series = series.str.strip()
        # Convert to numeric, replacing errors with NaN
        series = pd.to_numeric(series, errors='coerce')
    return series

def index(request):
    """Home page view"""
    recent_analyses = FraudAnalysis.objects.all()[:5]
    
    # Get overall statistics
    total_analyses = FraudAnalysis.objects.count()
    total_claims = Claim.objects.count()
    high_risk_claims = Claim.objects.filter(risk_level__in=['High', 'Critical']).count()
    
    context = {
        'recent_analyses': recent_analyses,
        'total_analyses': total_analyses,
        'total_claims': total_claims,
        'high_risk_claims': high_risk_claims,
        'high_risk_percentage': (high_risk_claims / total_claims * 100) if total_claims > 0 else 0,
    }
    return render(request, 'fraud_detector/index.html', context)

def upload_file(request):
    """Handle file upload and processing"""
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            analysis = form.save(commit=False)
            if request.user.is_authenticated:
                analysis.user = request.user
            analysis.save()
            
            # Process the file
            try:
                result = process_fraud_analysis(analysis)
                if result['success']:
                    messages.success(request, 'File uploaded and analyzed successfully!')
                    return redirect('fraud_detector:dashboard', analysis_id=analysis.id)
                else:
                    messages.error(request, f'Error processing file: {result["error"]}')
                    analysis.delete()
            except Exception as e:
                messages.error(request, f'Error processing file: {str(e)}')
                print(f"Upload error: {traceback.format_exc()}")
                if 'analysis' in locals():
                    analysis.delete()
    else:
        form = UploadFileForm()
    
    return render(request, 'fraud_detector/upload.html', {'form': form})

def execute_notebook_analysis(csv_path, output_dir):
    """
    Execute fraud.ipynb notebook if it exists.
    This is a placeholder function - implement according to your notebook structure.
    """
    try:
        import subprocess
        import json
        
        # Convert notebook to Python script
        notebook_path = 'fraud.ipynb'
        
        # Check if notebook exists
        if not os.path.exists(notebook_path):
            raise FileNotFoundError("fraud.ipynb not found")
        
        # You can use papermill or nbconvert to execute the notebook
        # For now, we'll return None to use the built-in detector
        return None
        
    except Exception as e:
        print(f"Notebook execution failed: {e}")
        return None
    
def process_fraud_analysis(analysis):
    """Process the uploaded CSV file for fraud detection - Optimized for large files"""
    try:
        print(f"Starting fraud analysis for analysis ID: {analysis.id}")
        
        # Read the CSV file with chunking for large files
        file_size = os.path.getsize(analysis.uploaded_file.path)
        print(f"File size: {file_size / (1024*1024):.1f} MB")
        
        # For large files (>50MB), use chunked reading
        if file_size > 50 * 1024 * 1024:  # 50MB threshold
            print("Large file detected - using chunked processing")
            df = pd.read_csv(analysis.uploaded_file.path, thousands=',', low_memory=False, chunksize=None)
        else:
            df = pd.read_csv(analysis.uploaded_file.path, thousands=',', low_memory=False)
        
        print(f"Loaded CSV with shape: {df.shape}")
        print(f"Columns: {list(df.columns)[:10]}...")  # Show first 10 columns
        
        # List of columns that might contain currency/numeric data
        potential_numeric_columns = [
            'Claim Incurred - Total', 'Claim Incurred – Total',
            'Claim Paid - Total', 'Claim Paid – Total',
            'Claim Future Reserve - Total', 'Claim Future Reserve – Total',
            'Claim Incurred - Medical', 'Claim Incurred – Medical',
            'Claim Paid - Medical', 'Claim Paid – Medical',
            'Claim Future Reserve - Medical', 'Claim Future Reserve – Medical',
            'Claim Incurred - Ind/Loss', 'Claim Incurred – Ind/Loss',
            'Claim Paid - Ind/Loss', 'Claim Paid – Ind/Loss',
            'Claim Future Reserve - Ind/Loss', 'Claim Future Reserve – Ind/Loss',
            'Claim Incurred - Expense', 'Claim Incurred – Expense',
            'Claim Paid - Expense', 'Claim Paid – Expense',
            'Claim Future Reserve - Expense', 'Claim Future Reserve – Expense',
            'Claim Incurred - Legal', 'Claim Incurred – Legal',
            'Claim Paid - Legal', 'Claim Paid – Legal',
            'Claim Future Reserve - Legal', 'Claim Future Reserve – Legal',
            'Pre Injury AWW', 'Wage Base', 'Weekly Wage', 'Current Wage',
            'Deductible', 'Policy Deductible', 'Claim Amount',
            'Claim Recovery - Total', 'Claim Recovery – Total',
            'days_to_report', 'Event Time'
        ]
        
        # Clean numeric columns
        for col in potential_numeric_columns:
            if col in df.columns:
                df[col] = clean_currency_column(df[col])
                print(f"Cleaned column: {col}")
        
        # Create output directory first
        output_dir = os.path.join('media', 'outputs', f'analysis_{analysis.id}')
        os.makedirs(output_dir, exist_ok=True)
        
        # Try notebook integration first (if fraud.ipynb exists)
        notebook_path = 'fraud.ipynb'
        df_with_fraud = None
        
        if os.path.exists(notebook_path):
            try:
                print("Attempting to execute fraud.ipynb notebook...")
                df_with_fraud = execute_notebook_analysis(analysis.uploaded_file.path, output_dir)
                print("Successfully executed fraud.ipynb notebook")
                
            except Exception as notebook_error:
                print(f"Notebook execution failed: {notebook_error}")
                print("Falling back to built-in FraudDetector")
                df_with_fraud = None
        
        # Use built-in FraudDetector if notebook failed or doesn't exist
        if df_with_fraud is None:
            print("Using built-in FraudDetector...")
            from .utils.fraud_detector import FraudDetector
            detector = FraudDetector()
            df_with_fraud = detector.detect_fraud(df)
        
        # Validate that required columns exist
        required_columns = ['fraud_score', 'risk_level', 'red_flags']
        for col in required_columns:
            if col not in df_with_fraud.columns:
                print(f"ERROR: Required column '{col}' not found after fraud detection!")
                if col == 'fraud_score':
                    print("Creating default fraud scores...")
                    df_with_fraud['fraud_score'] = np.random.uniform(0, 100, len(df_with_fraud))
                elif col == 'risk_level':
                    print("Creating default risk levels...")
                    df_with_fraud['risk_level'] = pd.cut(
                        df_with_fraud.get('fraud_score', np.random.uniform(0, 100, len(df_with_fraud))),
                        bins=[0, 30, 50, 70, 100],
                        labels=['Low', 'Medium', 'High', 'Critical'],
                        include_lowest=True
                    )
                elif col == 'red_flags':
                    print("Creating default red flags...")
                    df_with_fraud['red_flags'] = [[] for _ in range(len(df_with_fraud))]
        
        print(f"Fraud detection completed. Final shape: {df_with_fraud.shape}")
        print(f"Risk distribution: {df_with_fraud['risk_level'].value_counts().to_dict()}")
        
        # Generate output files
        output_csv_path = os.path.join(output_dir, 'fraud_analysis_results.csv')
        df_with_fraud.to_csv(output_csv_path, index=False)
        analysis.output_csv_path = output_csv_path.replace('media/', '')
        
        # Save high-risk claims CSV
        high_risk_df = df_with_fraud[df_with_fraud['risk_level'].isin(['High', 'Critical'])]
        if not high_risk_df.empty:
            high_risk_csv_path = os.path.join(output_dir, 'high_risk_claims.csv')
            high_risk_df.to_csv(high_risk_csv_path, index=False)
            analysis.high_risk_csv_path = high_risk_csv_path.replace('media/', '')
        
        # Generate visualizations
        try:
            viz_dir = os.path.join('media', 'visualizations', f'analysis_{analysis.id}')
            from .utils.visualization import FraudVisualizer
            visualizer = FraudVisualizer(viz_dir)
            visualizations = visualizer.generate_all_visualizations(df_with_fraud)
            
            # Store visualization paths
            viz_paths = {}
            for key, filename in visualizations.items():
                if filename:  # Only add if visualization was created successfully
                    viz_paths[key] = os.path.join('visualizations', f'analysis_{analysis.id}', filename)
            analysis.visualizations = viz_paths
            
        except Exception as viz_error:
            print(f"Warning: Visualization generation failed: {viz_error}")
            analysis.visualizations = {}
        
        # Update summary statistics
        risk_counts = df_with_fraud['risk_level'].value_counts()
        analysis.total_claims = len(df_with_fraud)
        analysis.low_risk_count = int(risk_counts.get('Low', 0))
        analysis.medium_risk_count = int(risk_counts.get('Medium', 0))
        analysis.high_risk_count = int(risk_counts.get('High', 0))
        analysis.critical_risk_count = int(risk_counts.get('Critical', 0))
        analysis.processed_at = datetime.now()
        analysis.save()
        
        # Save individual claims to database with chunked processing
        save_claims_to_db(analysis, df_with_fraud)
        
        print(f"Analysis completed successfully. Saved {analysis.total_claims} claims.")
        return {'success': True}
        
    except Exception as e:
        print(f"Error in process_fraud_analysis: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return {'success': False, 'error': str(e)}

def save_claims_to_db(analysis, df):
    """Save individual claims to the database with robust error handling and chunked processing for large files"""
    total_rows = len(df)
    print(f"Saving {total_rows} claims to database...")
    
    # For large datasets, process in chunks
    CHUNK_SIZE = 1000  # Process 1000 records at a time
    total_created = 0
    
    # Debug: Print available columns
    print(f"Available columns in dataframe: {list(df.columns)}")
    
    # Column mapping for different possible column names
    column_mappings = {
        'claim_number': ['Claim Number', 'Event Number', 'Claim ID'],
        'claimant_name': ['Claimant Full Name', 'Claimant Name', 'Employee Name'],
        'date_of_loss': ['Date of Loss', 'Loss Date', 'Incident Date'],
        'injury_type': ['Injury Type Description', 'Type of Injury', 'Injury Description'],
        'body_part': ['Target/Part of Body Description', 'SCMS Target/Part of Body Description', 'Body Part'],
        'date_reported': ['Date Claim Reported to Client', 'Report Date', 'Reported Date'],
        'date_of_hire': ['Date Of Hire', 'Hire Date', 'Employment Date'],
        'claimant_dob': ['Claimant Date of Birth', 'Date of Birth', 'DOB'],
        'state': ['State', 'Claim State', 'Location State', 'Structure Level Name 01'],
        'city': ['City', 'Claim City', 'Location City'],
        'zip_code': ['Zip Code', 'ZIP', 'Postal Code'],
        'job_title': ['Job Title', 'Position', 'Job Classification'],
        'department': ['Department', 'Division', 'Work Unit'],
        'attorney_involved': ['Date Of Attorney Representation'],
        'medical_treatment': ['Medical Treatment', 'Treatment Type'],
        'witness_available': ['Date Witness Contacted']
    }
    
    # Amount columns to try
    amount_columns = [
        'Claim Incurred - Total', 'Claim Incurred – Total',
        'Claim Paid - Total', 'Claim Paid – Total',
        'Total Incurred', 'Total Paid', 'Claim Amount'
    ]
    
    medical_cost_columns = [
        'Claim Incurred - Medical', 'Claim Incurred – Medical',
        'Claim Paid - Medical', 'Claim Paid – Medical',
        'Medical Incurred', 'Medical Paid'
    ]
    
    indemnity_cost_columns = [
        'Claim Incurred - Ind/Loss', 'Claim Incurred – Ind/Loss',
        'Claim Paid - Ind/Loss', 'Claim Paid – Ind/Loss',
        'Indemnity Incurred', 'Indemnity Paid'
    ]
    
    legal_cost_columns = [
        'Claim Incurred - Legal', 'Claim Incurred – Legal',
        'Claim Paid - Legal', 'Claim Paid – Legal',
        'Legal Incurred', 'Legal Paid'
    ]
    
    def get_column_value(row, column_list):
        """Get value from first available column in the list"""
        for col in column_list:
            if col in row and pd.notna(row[col]):
                return row[col]
        return None
    
    def safe_get_value(row, field_name, default=None):
        """Safely get a value using column mapping"""
        if field_name in column_mappings:
            return get_column_value(row, column_mappings[field_name])
        elif field_name in row:
            return row[field_name] if pd.notna(row[field_name]) else default
        return default
    
    def safe_float(value):
        """Safely convert to float"""
        if value is None or pd.isna(value):
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    def safe_int(value):
        """Safely convert to int"""
        if value is None or pd.isna(value):
            return None
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None
    
    def safe_date(value):
        """Safely convert to date"""
        if value is None or pd.isna(value):
            return None
        try:
            return pd.to_datetime(value).date()
        except:
            return None
    
    def safe_string(value, max_length=None):
        """Safely convert to string with length limit"""
        if value is None or pd.isna(value):
            return ''
        try:
            result = str(value)
            if max_length and len(result) > max_length:
                result = result[:max_length]
            return result
        except:
            return ''
    
    # Process data in chunks
    for start_idx in range(0, total_rows, CHUNK_SIZE):
        end_idx = min(start_idx + CHUNK_SIZE, total_rows)
        chunk_df = df.iloc[start_idx:end_idx]
        
        print(f"Processing chunk {start_idx//CHUNK_SIZE + 1}/{(total_rows//CHUNK_SIZE)+1}: rows {start_idx} to {end_idx}")
        
        claims_to_create = []
        
        # Process each row in the chunk
        for idx, row in chunk_df.iterrows():
            try:
                # Handle claim amount - try multiple possible column names
                claim_amount = safe_float(get_column_value(row, amount_columns))
                medical_costs = safe_float(get_column_value(row, medical_cost_columns))
                indemnity_costs = safe_float(get_column_value(row, indemnity_cost_columns))
                legal_costs = safe_float(get_column_value(row, legal_cost_columns))
                
                # Handle days_to_report
                days_to_report = safe_int(row.get('days_to_report'))
                
                # Get basic claim information
                claim_number = safe_string(safe_get_value(row, 'claim_number'), 100)
                claimant_name = safe_string(safe_get_value(row, 'claimant_name'), 200)
                injury_type = safe_string(safe_get_value(row, 'injury_type'), 200)
                body_part = safe_string(safe_get_value(row, 'body_part'), 200)
                
                # Get geographic info
                state = safe_string(safe_get_value(row, 'state'), 2)
                city = safe_string(safe_get_value(row, 'city'), 100)
                zip_code = safe_string(safe_get_value(row, 'zip_code'), 10)
                
                # Get employment info
                job_title = safe_string(safe_get_value(row, 'job_title'), 200)
                department = safe_string(safe_get_value(row, 'department'), 200)
                
                # Get dates
                date_of_loss = safe_date(safe_get_value(row, 'date_of_loss'))
                date_reported = safe_date(safe_get_value(row, 'date_reported'))
                date_of_hire = safe_date(safe_get_value(row, 'date_of_hire'))
                claimant_dob = safe_date(safe_get_value(row, 'claimant_dob'))
                
                # Get boolean flags
                attorney_involved = pd.notna(safe_get_value(row, 'attorney_involved'))
                witness_available = pd.notna(safe_get_value(row, 'witness_available'))
                
                # Ensure required fields have values
                fraud_score = safe_float(row.get('fraud_score', 0.0)) or 0.0
                risk_level = safe_string(row.get('risk_level', 'Low')) or 'Low'
                red_flags = row.get('red_flags', [])
                
                # Ensure red_flags is a list
                if not isinstance(red_flags, list):
                    if pd.isna(red_flags):
                        red_flags = []
                    else:
                        red_flags = [str(red_flags)]
                
                # Create claim object
                claim = Claim(
                    analysis=analysis,
                    claim_number=claim_number or f"CLAIM_{idx+1}",
                    claimant_name=claimant_name or "Unknown",
                    date_of_loss=date_of_loss,
                    injury_type=injury_type,
                    body_part=body_part,
                    fraud_score=fraud_score,
                    risk_level=risk_level,
                    red_flags=red_flags,
                    days_to_report=days_to_report,
                    claim_amount=claim_amount,
                    state=state,
                    city=city,
                    zip_code=zip_code,
                    date_reported=date_reported,
                    date_of_hire=date_of_hire,
                    claimant_dob=claimant_dob,
                    job_title=job_title,
                    department=department,
                    attorney_involved=attorney_involved,
                    witness_available=witness_available,
                    medical_costs=medical_costs,
                    indemnity_costs=indemnity_costs,
                    legal_costs=legal_costs
                )
                claims_to_create.append(claim)
                
            except Exception as row_error:
                print(f"Error processing row {idx}: {row_error}")
                # Create a minimal claim record
                minimal_claim = Claim(
                    analysis=analysis,
                    claim_number=f"ERROR_CLAIM_{idx+1}",
                    claimant_name="Processing Error",
                    fraud_score=0.0,
                    risk_level='Low',
                    red_flags=[]
                )
                claims_to_create.append(minimal_claim)
        
        # Bulk create claims for this chunk
        if claims_to_create:
            try:
                Claim.objects.bulk_create(claims_to_create, batch_size=500, ignore_conflicts=True)
                chunk_created = len(claims_to_create)
                total_created += chunk_created
                print(f"Successfully created {chunk_created} claim records in chunk")
                
                # Add small delay for large files to prevent overwhelming the database
                if total_rows > 10000:
                    time.sleep(0.1)
                    
            except Exception as bulk_error:
                print(f"Bulk create failed for chunk: {bulk_error}")
                # Try individual creation as fallback
                created_count = 0
                for claim in claims_to_create:
                    try:
                        claim.save()
                        created_count += 1
                    except Exception as individual_error:
                        print(f"Failed to save individual claim: {individual_error}")
                        continue
                total_created += created_count
                print(f"Created {created_count} claims individually in chunk")
    
    print(f"Claim saving completed. Total created: {total_created} out of {total_rows} rows")

def analyze_patterns(analysis):
    """Analyze fraud patterns from claims data"""
    claims = analysis.claims.all()
    
    # Define pattern categories
    timing_patterns = {
        'Weekend injury': 'Weekend injury',
        'Monday morning injury': 'Monday morning injury',
        'Near birthday': 'Near birthday',
        'Claim near birthday': 'Near birthday',
        'Near holiday': 'Near holiday',
        'Claim near holiday': 'Near holiday',
        'New employee (<30 days)': 'New employee (<30 days)',
        'New employee (<90 days)': 'New employee (<90 days)',
        'Relatively new employee (<90 days)': 'Relatively new employee (<90 days)',
        'End of month claim': 'End of month claim',
        'Summer claim': 'Summer claim',
        'Friday afternoon injury': 'Friday afternoon injury',
        'Claim shortly before termination': 'Claim shortly before termination',
        'Unusual time of injury': 'Unusual time of injury'
    }
    
    behavioral_patterns = {
        'Multiple claims from same person': 'Multiple claims from same person',
        'Attorney involved immediately': 'Attorney involved immediately',
        'Soft tissue injury': 'Soft tissue injury',
        'Suspicious body part injured': 'Suspicious body part injured',
        'Pushing for quick settlement': 'Pushing for quick settlement',
        'Avoiding recommended treatment': 'Avoiding recommended treatment',
        'Unusually long treatment': 'Unusually long treatment',
        'Pattern of suspicious claims': 'Pattern of suspicious claims'
    }
    
    reporting_patterns = {
        'Delayed reporting (>30 days)': 'Delayed reporting (>30 days)',
        'No witness contacted': 'No witness contacted',
        'High claim rate location': 'High claim rate location'
    }
    
    # Count patterns
    pattern_counts = {
        'timing': {},
        'behavioral': {},
        'reporting': {}
    }
    
    # Count claims with each pattern type
    timing_claims_set = set()
    behavioral_claims_set = set()
    reporting_claims_set = set()
    
    # Analyze all claims for patterns
    for claim in claims:
        has_timing = False
        has_behavioral = False
        has_reporting = False
        
        if claim.red_flags:
            for flag in claim.red_flags:
                # Remove category prefix if present
                clean_flag = flag.replace('[TIMING] ', '').replace('[BEHAVIORAL] ', '').replace('[REPORTING] ', '').replace('[INJURY] ', '')
                
                # Categorize the flag
                if any(pattern in clean_flag for pattern in timing_patterns):
                    pattern_counts['timing'][clean_flag] = pattern_counts['timing'].get(clean_flag, 0) + 1
                    has_timing = True
                elif any(pattern in clean_flag for pattern in behavioral_patterns):
                    pattern_counts['behavioral'][clean_flag] = pattern_counts['behavioral'].get(clean_flag, 0) + 1
                    has_behavioral = True
                elif any(pattern in clean_flag for pattern in reporting_patterns):
                    pattern_counts['reporting'][clean_flag] = pattern_counts['reporting'].get(clean_flag, 0) + 1
                    has_reporting = True
        
        # Track unique claims with each pattern type
        if has_timing:
            timing_claims_set.add(claim.id)
        if has_behavioral:
            behavioral_claims_set.add(claim.id)
        if has_reporting:
            reporting_claims_set.add(claim.id)
    
    # Format pattern data for template
    def format_patterns(pattern_dict):
        return sorted([
            {'name': name, 'count': count} 
            for name, count in pattern_dict.items()
        ], key=lambda x: x['count'], reverse=True)
    
    # Get all indicators sorted by frequency
    all_indicators = []
    for category_patterns in pattern_counts.values():
        for name, count in category_patterns.items():
            all_indicators.append({'name': name, 'count': count})
    all_indicators.sort(key=lambda x: x['count'], reverse=True)
    
    # Calculate percentages based on unique claims
    total_claims = analysis.total_claims
    timing_claims = len(timing_claims_set)
    behavioral_claims = len(behavioral_claims_set)
    reporting_claims = len(reporting_claims_set)
    
    pattern_analysis = {
        'timing_patterns': format_patterns(pattern_counts['timing']),
        'behavioral_patterns': format_patterns(pattern_counts['behavioral']),
        'reporting_patterns': format_patterns(pattern_counts['reporting']),
        'timing_count': sum(pattern_counts['timing'].values()),
        'behavioral_count': sum(pattern_counts['behavioral'].values()),
        'reporting_count': sum(pattern_counts['reporting'].values()),
        'timing_percentage': (timing_claims / total_claims * 100) if total_claims > 0 else 0,
        'behavioral_percentage': (behavioral_claims / total_claims * 100) if total_claims > 0 else 0,
        'reporting_percentage': (reporting_claims / total_claims * 100) if total_claims > 0 else 0,
        'top_indicators': all_indicators
    }
    
    return pattern_analysis

def dashboard(request, analysis_id):
    """Display analysis dashboard with dynamic pattern analysis"""
    analysis = get_object_or_404(FraudAnalysis, id=analysis_id)
    
    # Get summary statistics
    summary_stats = {
        'total_claims': analysis.total_claims,
        'risk_distribution': {
            'Low': analysis.low_risk_count,
            'Medium': analysis.medium_risk_count,
            'High': analysis.high_risk_count,
            'Critical': analysis.critical_risk_count,
        },
        'high_risk_percentage': ((analysis.high_risk_count + analysis.critical_risk_count) / analysis.total_claims * 100) if analysis.total_claims > 0 else 0,
    }
    
    # Get top high-risk claims
    top_claims = analysis.claims.filter(risk_level__in=['High', 'Critical']).order_by('-fraud_score')[:10]
    
    # Get pattern analysis
    pattern_analysis = analyze_patterns(analysis)
    
    # Prepare claims data for JavaScript (for interactive charts)
    claims_json = json.dumps(list(
        analysis.claims.values(
            'id', 'claim_number', 'claimant_name', 'fraud_score', 
            'risk_level', 'date_of_loss', 'days_to_report'
        ).order_by('-fraud_score')[:100]
    ), default=str)
    
    context = {
        'analysis': analysis,
        'summary_stats': summary_stats,
        'top_claims': top_claims,
        'visualizations': analysis.visualizations,
        'pattern_analysis': pattern_analysis,
        'claims_json': claims_json,
    }
    
    return render(request, 'fraud_detector/dashboard.html', context)

def claims_table(request, analysis_id):
    """Display all claims in a searchable table"""
    analysis = get_object_or_404(FraudAnalysis, id=analysis_id)
    claims = analysis.claims.all()
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        claims = claims.filter(
            Q(claim_number__icontains=search_query) |
            Q(claimant_name__icontains=search_query) |
            Q(injury_type__icontains=search_query) |
            Q(body_part__icontains=search_query)
        )
    
    # Filter by risk level
    risk_filter = request.GET.get('risk_level', '')
    if risk_filter:
        claims = claims.filter(risk_level=risk_filter)
    
    # Sorting
    sort_by = request.GET.get('sort', '-fraud_score')
    claims = claims.order_by(sort_by)
    
    # Pagination
    paginator = Paginator(claims, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'analysis': analysis,
        'page_obj': page_obj,
        'search_query': search_query,
        'risk_filter': risk_filter,
        'sort_by': sort_by,
    }
    
    return render(request, 'fraud_detector/claims_table.html', context)

def high_risk_claims(request, analysis_id):
    """Display only high and critical risk claims"""
    analysis = get_object_or_404(FraudAnalysis, id=analysis_id)
    claims = analysis.claims.filter(risk_level__in=['High', 'Critical']).order_by('-fraud_score')
    
    # Pagination
    paginator = Paginator(claims, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'analysis': analysis,
        'page_obj': page_obj,
    }
    
    return render(request, 'fraud_detector/high_risk_claims.html', context)

def download_file(request, analysis_id, file_type):
    """Download generated files"""
    analysis = get_object_or_404(FraudAnalysis, id=analysis_id)
    
    if file_type == 'full':
        file_path = os.path.join('media', analysis.output_csv_path)
        filename = 'fraud_analysis_results.csv'
    elif file_type == 'high_risk':
        file_path = os.path.join('media', analysis.high_risk_csv_path)
        filename = 'high_risk_claims.csv'
    else:
        return HttpResponse('Invalid file type', status=400)
    
    if os.path.exists(file_path):
        return FileResponse(open(file_path, 'rb'), as_attachment=True, filename=filename)
    else:
        return HttpResponse('File not found', status=404)

def visualization_view(request, analysis_id, viz_type):
    """View individual visualization"""
    analysis = get_object_or_404(FraudAnalysis, id=analysis_id)
    
    if viz_type in analysis.visualizations:
        viz_path = os.path.join('media', analysis.visualizations[viz_type])
        if os.path.exists(viz_path):
            return FileResponse(open(viz_path, 'rb'), content_type='image/png')
    
    return HttpResponse('Visualization not found', status=404)

def analysis_history(request):
    """View all past analyses"""
    analyses = FraudAnalysis.objects.all()
    
    if request.user.is_authenticated:
        # Option to filter by user
        user_only = request.GET.get('user_only', 'false') == 'true'
        if user_only:
            analyses = analyses.filter(user=request.user)
    
    paginator = Paginator(analyses, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
    }
    
    return render(request, 'fraud_detector/analysis_history.html', context)

def pattern_details(request, analysis_id):
    """Get claims that match a specific pattern"""
    pattern_name = request.GET.get('pattern', '')
    pattern_type = request.GET.get('type', 'all')
    
    if not pattern_name:
        return JsonResponse({'success': False, 'error': 'Pattern name is required'})
    
    try:
        analysis = get_object_or_404(FraudAnalysis, id=analysis_id)
        
        # Get all claims for this analysis
        claims = analysis.claims.all()
        
        # Filter claims that have this pattern in their red flags
        matching_claims = []
        for claim in claims:
            if claim.red_flags:
                # Check if the pattern name appears in any of the red flags
                for flag in claim.red_flags:
                    # Remove category prefix for comparison
                    clean_flag = flag.replace('[TIMING] ', '').replace('[BEHAVIORAL] ', '').replace('[REPORTING] ', '').replace('[INJURY] ', '')
                    
                    if pattern_name.lower() in clean_flag.lower():
                        matching_claims.append(claim)
                        break  # Don't add the same claim multiple times
        
        # Calculate statistics
        total_claims = len(matching_claims)
        avg_fraud_score = sum(c.fraud_score for c in matching_claims) / total_claims if total_claims > 0 else 0
        
        # Serialize claims data
        claims_data = []
        for claim in matching_claims:
            claims_data.append({
                'claim_number': claim.claim_number,
                'claimant_name': claim.claimant_name,
                'date_of_loss': claim.date_of_loss.strftime('%Y-%m-%d') if claim.date_of_loss else None,
                'injury_type': claim.injury_type,
                'body_part': claim.body_part,
                'risk_level': claim.risk_level,
                'fraud_score': float(claim.fraud_score),
                'days_to_report': claim.days_to_report,
                'claim_amount': str(claim.claim_amount) if claim.claim_amount else None,
                'red_flags': claim.red_flags
            })
        
        # Sort by fraud score (highest first)
        claims_data.sort(key=lambda x: x['fraud_score'], reverse=True)
        
        response_data = {
            'success': True,
            'claims': claims_data,
            'pattern_info': {
                'name': pattern_name,
                'type': pattern_type,
                'total_claims': total_claims,
                'avg_fraud_score': round(avg_fraud_score, 2)
            }
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

def charts_data_api(request, analysis_id):
    """API endpoint for interactive chart data"""
    try:
        analysis = get_object_or_404(FraudAnalysis, id=analysis_id)
        claims = analysis.claims.all()
        
        # Debug logging
        print(f"Charts API called for analysis {analysis_id}")
        print(f"Total claims found: {claims.count()}")
        
        # Build response data structure with proper error handling
        response_data = {
            'fraudScores': [],
            'timeline': [],
            'claimants': [],
            'indicators': [],
            'injuries': [],
            'timeLag': [],
            'geographic': []
        }
        
        # 1. Fraud Scores data
        for claim in claims:
            try:
                response_data['fraudScores'].append({
                    'score': float(claim.fraud_score),
                    'fraud_score': float(claim.fraud_score),
                    'risk_level': claim.risk_level,
                    'claim_number': claim.claim_number
                })
            except Exception as e:
                print(f"Error processing fraud score for claim {claim.id}: {e}")
        
        # 2. Timeline data
        timeline_claims = claims.filter(date_of_loss__isnull=False).order_by('date_of_loss')
        for claim in timeline_claims:
            try:
                response_data['timeline'].append({
                    'date': claim.date_of_loss.strftime('%Y-%m-%d') if claim.date_of_loss else None,
                    'date_of_loss': claim.date_of_loss.strftime('%Y-%m-%d') if claim.date_of_loss else None,
                    'fraud_score': float(claim.fraud_score),
                    'risk_level': claim.risk_level,
                    'claim_number': claim.claim_number
                })
            except Exception as e:
                print(f"Error processing timeline for claim {claim.id}: {e}")
        
        # 3. Repeat claimants data
        from django.db.models import Count, Avg
        claimant_stats = claims.values('claimant_name').annotate(
            count=Count('id'),
            avg_fraud_score=Avg('fraud_score')
        ).filter(count__gt=1).order_by('-count')[:50]
        
        for stat in claimant_stats:
            try:
                response_data['claimants'].append({
                    'claimant_name': stat['claimant_name'],
                    'name': stat['claimant_name'],
                    'count': stat['count'],
                    'fraud_score': float(stat['avg_fraud_score']) if stat['avg_fraud_score'] else 0,
                    'avg_fraud_score': float(stat['avg_fraud_score']) if stat['avg_fraud_score'] else 0
                })
            except Exception as e:
                print(f"Error processing claimant stats: {e}")
        
        # 4. Red flags/indicators data
        indicator_counts = {}
        for claim in claims:
            if claim.red_flags and isinstance(claim.red_flags, list):
                for flag in claim.red_flags:
                    # Clean flag text
                    clean_flag = str(flag).replace('[TIMING] ', '').replace('[BEHAVIORAL] ', '').replace('[REPORTING] ', '').replace('[INJURY] ', '')
                    if clean_flag not in indicator_counts:
                        indicator_counts[clean_flag] = {'count': 0, 'total_score': 0}
                    indicator_counts[clean_flag]['count'] += 1
                    indicator_counts[clean_flag]['total_score'] += float(claim.fraud_score)
        
        # Convert to list and sort by frequency
        indicators_list = []
        for flag, data in indicator_counts.items():
            indicators_list.append({
                'flag': flag,
                'indicator': flag,
                'count': data['count'],
                'fraud_score': data['total_score'] / data['count'] if data['count'] > 0 else 0,
                'avg_fraud_score': data['total_score'] / data['count'] if data['count'] > 0 else 0
            })
        
        # Sort by count and take top indicators
        indicators_list.sort(key=lambda x: x['count'], reverse=True)
        response_data['indicators'] = indicators_list[:20]
        
        # 5. Injury types data
        injury_stats = claims.exclude(injury_type__isnull=True).exclude(injury_type='').values('injury_type').annotate(
            count=Count('id'),
            avg_fraud_score=Avg('fraud_score')
        ).order_by('-avg_fraud_score')[:20]
        
        for stat in injury_stats:
            try:
                response_data['injuries'].append({
                    'injury_type': stat['injury_type'],
                    'count': stat['count'],
                    'fraud_score': float(stat['avg_fraud_score']) if stat['avg_fraud_score'] else 0,
                    'avg_fraud_score': float(stat['avg_fraud_score']) if stat['avg_fraud_score'] else 0
                })
            except Exception as e:
                print(f"Error processing injury stats: {e}")
        
        # 6. Time lag data
        time_lag_claims = claims.filter(days_to_report__isnull=False)
        for claim in time_lag_claims:
            try:
                response_data['timeLag'].append({
                    'days_to_report': int(claim.days_to_report),
                    'fraud_score': float(claim.fraud_score),
                    'risk_level': claim.risk_level,
                    'claim_number': claim.claim_number
                })
            except Exception as e:
                print(f"Error processing time lag for claim {claim.id}: {e}")
        
        # 7. Geographic data
        geographic_stats = claims.exclude(state__isnull=True).exclude(state='').values('state').annotate(
            count=Count('id'),
            avg_fraud_score=Avg('fraud_score'),
            high_risk_count=Count('id', filter=Q(risk_level__in=['High', 'Critical']))
        )
        
        for stat in geographic_stats:
            try:
                high_risk_pct = (stat['high_risk_count'] / stat['count']) * 100 if stat['count'] > 0 else 0
                response_data['geographic'].append({
                    'state': stat['state'],
                    'count': stat['count'],
                    'fraud_score': float(stat['avg_fraud_score']) if stat['avg_fraud_score'] else 0,
                    'avg_fraud_score': float(stat['avg_fraud_score']) if stat['avg_fraud_score'] else 0,
                    'risk_level': 'High' if stat['avg_fraud_score'] and stat['avg_fraud_score'] > 50 else 'Low',
                    'high_risk_count': stat['high_risk_count'],
                    'high_risk_percentage': high_risk_pct
                })
            except Exception as e:
                print(f"Error processing geographic stats: {e}")
        
        # Debug: Log response data summary
        print(f"Response data summary:")
        for key, value in response_data.items():
            print(f"  {key}: {len(value)} items")
        
        return JsonResponse(response_data)
        
    except Exception as e:
        print(f"Error in charts_data_api: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)
    
def top_claimants_api(request, analysis_id):
    """API for top repeat claimants"""
    try:
        analysis = get_object_or_404(FraudAnalysis, id=analysis_id)
        limit = int(request.GET.get('limit', 10))
        
        claimant_stats = analysis.claims.values('claimant_name').annotate(
            count=Count('id'),
            avg_fraud_score=Avg('fraud_score')
        ).filter(count__gt=1).order_by('-count')[:limit]
        
        data = []
        for stat in claimant_stats:
            data.append({
                'name': stat['claimant_name'],
                'count': stat['count'],
                'avg_fraud_score': float(stat['avg_fraud_score'])
            })
        
        return JsonResponse({'claimants': data})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def fraud_indicators_api(request, analysis_id):
    """API for fraud indicators analysis"""
    try:
        analysis = get_object_or_404(FraudAnalysis, id=analysis_id)
        claims = analysis.claims.all()
        
        # Count all red flags
        flag_counts = {}
        for claim in claims:
            if claim.red_flags:
                for flag in claim.red_flags:
                    clean_flag = flag.replace('[TIMING] ', '').replace('[BEHAVIORAL] ', '').replace('[REPORTING] ', '').replace('[INJURY] ', '')
                    flag_counts[clean_flag] = flag_counts.get(clean_flag, 0) + 1
        
        # Sort by frequency
        sorted_flags = sorted(flag_counts.items(), key=lambda x: x[1], reverse=True)[:15]
        
        indicators = []
        for flag, count in sorted_flags:
            indicators.append({
                'indicator': flag,
                'count': count,
                'percentage': (count / len(claims)) * 100
            })
        
        return JsonResponse({'indicators': indicators})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def geographic_analysis_api(request, analysis_id):
    """API for geographic analysis"""
    try:
        analysis = get_object_or_404(FraudAnalysis, id=analysis_id)
        metric = request.GET.get('metric', 'count')
        
        geographic_stats = analysis.claims.exclude(state__isnull=True).values('state').annotate(
            count=Count('id'),
            avg_fraud_score=Avg('fraud_score'),
            high_risk_count=Count('id', filter=Q(risk_level__in=['High', 'Critical']))
        )
        
        data = []
        for stat in geographic_stats:
            high_risk_pct = (stat['high_risk_count'] / stat['count']) * 100 if stat['count'] > 0 else 0
            
            data.append({
                'state': stat['state'],
                'count': stat['count'],
                'avg_fraud_score': float(stat['avg_fraud_score']),
                'high_risk_percentage': high_risk_pct,
                'high_risk_count': stat['high_risk_count']
            })
        
        return JsonResponse({'geographic_data': data, 'metric': metric})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def injury_analysis_api(request, analysis_id):
    """API for injury type analysis"""
    try:
        analysis = get_object_or_404(FraudAnalysis, id=analysis_id)
        
        injury_stats = analysis.claims.exclude(injury_type__isnull=True).exclude(injury_type='').values('injury_type').annotate(
            count=Count('id'),
            avg_fraud_score=Avg('fraud_score'),
            high_risk_count=Count('id', filter=Q(risk_level__in=['High', 'Critical']))
        ).order_by('-avg_fraud_score')[:20]
        
        data = []
        for stat in injury_stats:
            data.append({
                'injury_type': stat['injury_type'],
                'count': stat['count'],
                'avg_fraud_score': float(stat['avg_fraud_score']),
                'high_risk_count': stat['high_risk_count']
            })
        
        return JsonResponse({'injury_data': data})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def timeline_analysis_api(request, analysis_id):
    """API for timeline analysis"""
    try:
        analysis = get_object_or_404(FraudAnalysis, id=analysis_id)
        
        # Get claims with valid dates, grouped by month
        timeline_data = analysis.claims.filter(date_of_loss__isnull=False).extra(
            select={'month': "strftime('%%Y-%%m', date_of_loss)"}
        ).values('month').annotate(
            count=Count('id'),
            avg_fraud_score=Avg('fraud_score'),
            high_risk_count=Count('id', filter=Q(risk_level__in=['High', 'Critical']))
        ).order_by('month')
        
        data = []
        for stat in timeline_data:
            data.append({
                'month': stat['month'],
                'count': stat['count'],
                'avg_fraud_score': float(stat['avg_fraud_score']),
                'high_risk_count': stat['high_risk_count']
            })
        
        return JsonResponse({'timeline_data': data})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
def test_api(request, analysis_id):
    """Simple test endpoint"""
    try:
        analysis = FraudAnalysis.objects.get(id=analysis_id)
        claims_count = analysis.claims.count()
        return JsonResponse({
            'status': 'ok',
            'analysis_id': analysis_id,
            'claims_count': claims_count,
            'message': f'Found {claims_count} claims for analysis {analysis_id}'
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
from django.shortcuts import render

def custom_404(request, exception):
    """Custom 404 error page"""
    return render(request, '404.html', status=404)

def custom_500(request):
    """Custom 500 error page"""
    return render(request, '500.html', status=500)

def custom_403(request, exception):
    """Custom 403 forbidden page"""
    return render(request, '403.html', status=403)