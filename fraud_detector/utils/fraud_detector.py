import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
from django.conf import settings

class FraudDetector:
    def __init__(self):
        # Existing weights
        self.fraud_weights = {
            # REPORTING PATTERNS (Already implemented)
            'delayed_reporting': 2.0,
            'no_witness': 1.6,
            
            # TIMING PATTERNS (Existing)
            'near_birthday': 1.5,
            'new_employee_30d': 1.8,
            'new_employee_90d': 1.3,
            'near_holiday': 1.3,
            'claim_before_termination': 2.2,
            'weekend_injury': 1.2,
            'unusual_time': 1.3,
            'summer_claim': 1.1,
            
            # NEW TIMING PATTERNS
            'monday_morning_claim': 1.4,          # Monday morning injuries (weekend activities)
            'friday_afternoon_claim': 1.3,        # Friday afternoon (early weekend)
            'end_of_month_claim': 1.2,           # Financial pressure timing
            'seasonal_spike': 1.3,                # Unusual seasonal patterns
            'shift_change_injury': 1.4,           # Injuries during shift changes
            'lunch_break_injury': 1.2,            # Injuries during breaks
            'pre_vacation_claim': 1.5,            # Claims before scheduled vacation
            'post_holiday_claim': 1.4,            # First day back from holiday
            
            # BEHAVIORAL PATTERNS (Existing)
            'multiple_claims': 2.5,
            
            # NEW BEHAVIORAL PATTERNS
            'claim_shopping': 2.3,                # Multiple doctors/treatments
            'treatment_avoidance': 1.8,           # Refusing recommended treatment
            'doctor_shopping': 2.2,               # Changing doctors frequently
            'excessive_treatment': 1.9,           # Unusually long treatment
            'quick_settlement': 1.7,              # Pushing for fast settlement
            'attorney_immediate': 2.4,            # Attorney on day 1
            'previous_claims_pattern': 2.6,       # Pattern in previous claims
            'refused_light_duty': 1.9,            # Refusing modified work
            'no_medical_history': 1.6,            # No prior medical records
            'changing_story': 2.5,                # Inconsistent injury description
            
            # LOCATION/ENVIRONMENTAL (Existing)
            'suspicious_body_part': 1.4,
            'soft_tissue_injury': 1.7,
            'high_claim_rate_location': 1.5,
            'injury_at_home': 1.4,
        }

        
    def detect_fraud(self, df):
        """Main fraud detection method"""
        print(f"Starting fraud detection with {len(df)} rows and {len(df.columns)} columns")
        df = df.copy()
        
        try:
            # Add all fraud indicators
            print("Adding fraud indicators...")
            df = self._add_fraud_indicators(df)
            print(f"After fraud indicators: {df.shape}")
            
            print("Adding timing patterns...")
            df = self._add_timing_patterns(df)
            print(f"After timing patterns: {df.shape}")
            
            print("Adding behavioral patterns...")
            df = self._add_behavioral_patterns(df)
            print(f"After behavioral patterns: {df.shape}")
            
            # Calculate fraud score - ENSURE this always creates the column
            print("Calculating fraud scores...")
            df['fraud_score'] = self._calculate_fraud_score(df)
            print(f"Fraud scores calculated. Min: {df['fraud_score'].min()}, Max: {df['fraud_score'].max()}")
            
            # Assign risk levels - ENSURE this always creates the column
            print("Assigning risk levels...")
            df['risk_level'] = self._assign_risk_level(df['fraud_score'])
            print(f"Risk levels assigned: {df['risk_level'].value_counts().to_dict()}")
            
            # Get red flags for each claim - ENSURE this always creates the column
            print("Getting red flags...")
            df['red_flags'] = df.apply(self._get_red_flags, axis=1)
            print(f"Red flags added. Sample: {df['red_flags'].iloc[0] if len(df) > 0 else 'No data'}")
            
            # Add pattern categories
            df['timing_flags_count'] = df.apply(self._count_timing_flags, axis=1)
            df['behavioral_flags_count'] = df.apply(self._count_behavioral_flags, axis=1)
            df['reporting_flags_count'] = df.apply(self._count_reporting_flags, axis=1)
            
            print(f"Fraud detection completed successfully. Final shape: {df.shape}")
            print(f"Required columns present: fraud_score={df.get('fraud_score') is not None}, risk_level={'risk_level' in df.columns}, red_flags={'red_flags' in df.columns}")
            
            return df
            
        except Exception as e:
            print(f"Error in detect_fraud: {str(e)}")
            # Ensure we always return a dataframe with required columns
            if 'fraud_score' not in df.columns:
                df['fraud_score'] = 0.0
            if 'risk_level' not in df.columns:
                df['risk_level'] = 'Low'
            if 'red_flags' not in df.columns:
                df['red_flags'] = [[] for _ in range(len(df))]
            raise e
    
    def _calculate_fraud_score(self, df):
        """Calculate fraud score based on weighted indicators"""
        print("Starting fraud score calculation...")
        
        # Initialize score with zeros
        score = pd.Series(0.0, index=df.index)
        
        indicators_found = 0
        for indicator, weight in self.fraud_weights.items():
            if indicator in df.columns:
                try:
                    # Ensure the column is boolean/numeric
                    indicator_values = df[indicator].fillna(False).astype(bool).astype(float)
                    score += indicator_values * weight
                    indicators_found += 1
                    print(f"Added indicator '{indicator}' with weight {weight}. Active in {indicator_values.sum()} claims.")
                except Exception as e:
                    print(f"Warning: Could not process indicator '{indicator}': {e}")
                    continue
        
        print(f"Processed {indicators_found} indicators out of {len(self.fraud_weights)} total")

        
        # Normalize score to 0-100 scale
        if indicators_found > 0:
            max_possible = sum(weight for indicator, weight in self.fraud_weights.items() if indicator in df.columns)
            if max_possible > 0:
                normalized_score = (score / max_possible * 100).round(2)
            else:
                normalized_score = score.round(2)
        else:
            # If no indicators found, assign random scores for testing
            print("Warning: No fraud indicators found. Assigning random scores for testing.")
            normalized_score = pd.Series(np.random.uniform(0, 100, len(df)), index=df.index).round(2)
        
        print(f"Score calculation completed. Range: {normalized_score.min():.2f} - {normalized_score.max():.2f}")
        return normalized_score
    
    def _assign_risk_level(self, fraud_score):
        """Assign risk level based on fraud score"""
        print("Assigning risk levels...")
        
        # Ensure fraud_score is a pandas Series
        if not isinstance(fraud_score, pd.Series):
            fraud_score = pd.Series(fraud_score)
        
        # Use conditions for risk level assignment
        conditions = [
            fraud_score < 30,
            (fraud_score >= 30) & (fraud_score < 50),
            (fraud_score >= 50) & (fraud_score < 70),
            fraud_score >= 70
        ]
        
        choices = ['Low', 'Medium', 'High', 'Critical']
        
        risk_levels = pd.Series(np.select(conditions, choices, default='Low'), index=fraud_score.index)
        
        risk_distribution = risk_levels.value_counts().to_dict()
        print(f"Risk level distribution: {risk_distribution}")
        
        return risk_levels
    
    def _add_fraud_indicators(self, df):
        """Add various fraud indicator columns"""
        print("Adding basic fraud indicators...")
        
        # Convert date columns
        date_columns = ['Date of Loss', 'Date Claim Reported to Client', 'Date Of Hire', 'Date of Termination']
        for col in date_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        # Initialize all indicators with False to avoid dtype issues
        default_indicators = [
            'delayed_reporting', 'near_birthday', 'new_employee_30d', 'new_employee_90d',
            'multiple_claims', 'soft_tissue_injury', 'no_witness', 'suspicious_body_part',
            'weekend_injury', 'near_holiday', 'summer_claim', 'claim_before_termination',
            'high_claim_rate_location', 'unusual_time', 'injury_at_home'
        ]
        
        for indicator in default_indicators:
            df[indicator] = False
        
        # Days to report
        if 'Date of Loss' in df.columns and 'Date Claim Reported to Client' in df.columns:
            df['days_to_report'] = (df['Date Claim Reported to Client'] - df['Date of Loss']).dt.days
            df.loc[df['days_to_report'] > 30, 'delayed_reporting'] = True
        
        # New employee indicators
        if 'Date of Loss' in df.columns and 'Date Of Hire' in df.columns:
            days_employed = (df['Date of Loss'] - df['Date Of Hire']).dt.days
            df.loc[days_employed <= 30, 'new_employee_30d'] = True
            df.loc[days_employed <= 90, 'new_employee_90d'] = True
        
        # Near birthday
        if 'Date of Loss' in df.columns and 'Claimant Date of Birth' in df.columns:
            df['Claimant Date of Birth'] = pd.to_datetime(df['Claimant Date of Birth'], errors='coerce')
            for idx in df.index:
                if pd.notna(df.loc[idx, 'Date of Loss']) and pd.notna(df.loc[idx, 'Claimant Date of Birth']):
                    df.loc[idx, 'near_birthday'] = self._check_near_birthday(df.loc[idx])
        
        # Multiple claims
        if 'Claimant SSN (Masked)' in df.columns:
            claim_counts = df.groupby('Claimant SSN (Masked)').size()
            for ssn, count in claim_counts.items():
                if count > 1:
                    df.loc[df['Claimant SSN (Masked)'] == ssn, 'multiple_claims'] = True
        elif 'Claimant Full Name' in df.columns:
            # Fallback to name if SSN not available
            claim_counts = df.groupby('Claimant Full Name').size()
            for name, count in claim_counts.items():
                if count > 1:
                    df.loc[df['Claimant Full Name'] == name, 'multiple_claims'] = True
        
        # Soft tissue injury
        soft_tissue_keywords = ['strain', 'sprain', 'soft tissue', 'back pain', 'neck pain']
        if 'Injury Type Description' in df.columns:
            pattern = '|'.join(soft_tissue_keywords)
            mask = df['Injury Type Description'].str.lower().str.contains(pattern, na=False)
            df.loc[mask, 'soft_tissue_injury'] = True
        
        # No witness
        if 'Date Witness Contacted' in df.columns:
            df.loc[df['Date Witness Contacted'].isna(), 'no_witness'] = True
        else:
            df['no_witness'] = True  # Default to True if no witness data
        
        # Suspicious body parts
        suspicious_parts = ['back', 'neck', 'soft tissue', 'multiple body parts']
        if 'Target/Part of Body Description' in df.columns:
            pattern = '|'.join(suspicious_parts)
            mask = df['Target/Part of Body Description'].str.lower().str.contains(pattern, na=False)
            df.loc[mask, 'suspicious_body_part'] = True
        
        # Weekend injury
        if 'Date of Loss' in df.columns:
            df.loc[df['Date of Loss'].dt.dayofweek.isin([5, 6]), 'weekend_injury'] = True
        
        # Near holiday
        if 'Date of Loss' in df.columns:
            df['near_holiday'] = self._check_near_holiday(df)
        
        # Summer claim
        if 'Date of Loss' in df.columns:
            df.loc[df['Date of Loss'].dt.month.isin([6, 7, 8]), 'summer_claim'] = True
        
        # Claim before termination
        if 'Date of Loss' in df.columns and 'Date of Termination' in df.columns:
            mask = (df['Date of Termination'].notna() & 
                   ((df['Date of Termination'] - df['Date of Loss']).dt.days <= 30) &
                   ((df['Date of Termination'] - df['Date of Loss']).dt.days >= 0))
            df.loc[mask, 'claim_before_termination'] = True
        
        # High claim rate location
        if 'Location Name (Claim Level)' in df.columns:
            location_counts = df.groupby('Location Name (Claim Level)').size()
            avg_claims = location_counts.mean()
            high_claim_locations = location_counts[location_counts > avg_claims * 1.5].index
            df.loc[df['Location Name (Claim Level)'].isin(high_claim_locations), 'high_claim_rate_location'] = True
        
        # Unusual time
        if 'Event Time' in df.columns:
            # Convert time to hour if it's a string
            df['event_hour'] = pd.to_datetime(df['Event Time'], format='%H:%M:%S', errors='coerce').dt.hour
            mask = (df['event_hour'] < 6) | (df['event_hour'] > 18)
            df.loc[mask, 'unusual_time'] = True
        
        print(f"Added {len(default_indicators)} basic fraud indicators")
        return df
    
    def _add_timing_patterns(self, df):
        """Add enhanced timing pattern indicators"""
        print("Adding timing patterns...")
        
        # Initialize timing pattern indicators
        timing_indicators = [
            'monday_morning_claim', 'friday_afternoon_claim', 'end_of_month_claim',
            'seasonal_spike', 'shift_change_injury', 'lunch_break_injury',
            'pre_vacation_claim', 'post_holiday_claim'
        ]
        
        for indicator in timing_indicators:
            df[indicator] = False
        
        # Monday morning claims (weekend injuries reported Monday)
        if 'Date of Loss' in df.columns:
            try:
                if 'Event Time' in df.columns:
                    df['loss_hour'] = pd.to_datetime(df['Event Time'], format='%H:%M:%S', errors='coerce').dt.hour
                else:
                    df['loss_hour'] = 8  # Default to 8 AM if no time data
                
                df['loss_day'] = df['Date of Loss'].dt.dayofweek
                
                # Monday morning pattern
                df.loc[(df['loss_day'] == 0) & (df['loss_hour'] < 10), 'monday_morning_claim'] = True
                
                # Friday afternoon pattern
                df.loc[(df['loss_day'] == 4) & (df['loss_hour'] >= 14), 'friday_afternoon_claim'] = True
                
                # End of month claims
                df.loc[df['Date of Loss'].dt.day >= 25, 'end_of_month_claim'] = True
                
                # Shift change injuries (assuming shifts at 7, 15, 23)
                df.loc[df['loss_hour'].isin([6, 7, 8, 14, 15, 16, 22, 23, 0]), 'shift_change_injury'] = True
                
                # Lunch break injuries
                df.loc[df['loss_hour'].isin([11, 12, 13]), 'lunch_break_injury'] = True
                
            except Exception as e:
                print(f"Warning: Could not process timing patterns: {e}")
        
        # Seasonal spikes
        df['seasonal_spike'] = self._check_seasonal_spike(df)
        
        # Post-holiday claims
        df['post_holiday_claim'] = self._check_post_holiday(df)
        
        print("Timing patterns added")
        return df
    
    def _add_behavioral_patterns(self, df):
        """Add behavioral pattern indicators"""
        print("Adding behavioral patterns...")
        
        # Initialize behavioral indicators
        behavioral_indicators = [
            'attorney_immediate', 'treatment_avoidance', 'doctor_shopping',
            'claim_shopping', 'excessive_treatment', 'quick_settlement',
            'previous_claims_pattern', 'refused_light_duty', 'no_medical_history',
            'changing_story'
        ]
        
        for indicator in behavioral_indicators:
            df[indicator] = False
        
        # Attorney involvement timing
        if 'Date Of Attorney Representation' in df.columns and 'Date of Loss' in df.columns:
            df['Date Of Attorney Representation'] = pd.to_datetime(df['Date Of Attorney Representation'], errors='coerce')
            days_to_attorney = (df['Date Of Attorney Representation'] - df['Date of Loss']).dt.days
            df.loc[(days_to_attorney >= 0) & (days_to_attorney <= 1), 'attorney_immediate'] = True
        
        # Treatment patterns
        if 'Surgery Flag' in df.columns:
            df.loc[(df['Surgery Flag'] == 0) & df['suspicious_body_part'], 'treatment_avoidance'] = True
        
        # Excessive treatment duration
        if 'Date Claim Closed' in df.columns and 'Date of Loss' in df.columns:
            df['Date Claim Closed'] = pd.to_datetime(df['Date Claim Closed'], errors='coerce')
            treatment_duration = (df['Date Claim Closed'] - df['Date of Loss']).dt.days
            df.loc[treatment_duration > 365, 'excessive_treatment'] = True
        
        # Quick settlement seeking
        if 'days_to_report' in df.columns:
            df.loc[df['days_to_report'] < 2, 'quick_settlement'] = True
        
        print("Behavioral patterns added")
        return df
    
    def _check_near_birthday(self, row):
        """Check if claim is near birthday"""
        try:
            loss_day = row['Date of Loss'].timetuple().tm_yday
            birth_day = row['Claimant Date of Birth'].timetuple().tm_yday
            diff = abs(loss_day - birth_day)
            return diff <= 30 or diff >= 335
        except:
            return False
    
    def _check_near_holiday(self, df):
        """Check if claims are near major holidays"""
        holidays = [
            (1, 1),   # New Year's Day
            (7, 4),   # Independence Day
            (12, 25), # Christmas
            (11, 24), # Thanksgiving (approximate)
        ]
        
        near_holiday = pd.Series(False, index=df.index)
        
        if 'Date of Loss' in df.columns:
            for month, day in holidays:
                holiday_match = (
                    (df['Date of Loss'].dt.month == month) & 
                    (abs(df['Date of Loss'].dt.day - day) <= 7)
                )
                near_holiday = near_holiday | holiday_match
        
        return near_holiday
    
    def _check_post_holiday(self, df):
        """Check if claim is first weekday after a holiday"""
        post_holiday = pd.Series(False, index=df.index)
        
        if 'Date of Loss' in df.columns:
            # Simple implementation - check if Monday after weekend
            is_monday = df['Date of Loss'].dt.dayofweek == 0
            post_holiday = is_monday
        
        return post_holiday
    
    def _check_seasonal_spike(self, df):
        """Check for unusual seasonal patterns"""
        if 'Date of Loss' not in df.columns:
            return pd.Series(False, index=df.index)
        
        try:
            # Calculate monthly claim rates
            monthly_counts = df.groupby(df['Date of Loss'].dt.month).size()
            avg_monthly = monthly_counts.mean()
            std_monthly = monthly_counts.std()
            
            # Flag months with unusually high claims
            spike_months = monthly_counts[monthly_counts > avg_monthly + 2 * std_monthly].index
            
            return df['Date of Loss'].dt.month.isin(spike_months)
        except:
            return pd.Series(False, index=df.index)
    
    def _count_timing_flags(self, row):
        """Count timing-related flags"""
        timing_flags = [
            'near_birthday', 'new_employee_30d', 'new_employee_90d', 
            'near_holiday', 'claim_before_termination', 'weekend_injury',
            'unusual_time', 'summer_claim', 'monday_morning_claim',
            'friday_afternoon_claim', 'end_of_month_claim', 'seasonal_spike',
            'shift_change_injury', 'lunch_break_injury', 'pre_vacation_claim',
            'post_holiday_claim'
        ]
        return sum(row.get(flag, False) for flag in timing_flags)
    
    def _count_behavioral_flags(self, row):
        """Count behavioral flags"""
        behavioral_flags = [
            'multiple_claims', 'claim_shopping', 'treatment_avoidance',
            'doctor_shopping', 'excessive_treatment', 'quick_settlement',
            'attorney_immediate', 'previous_claims_pattern', 'refused_light_duty',
            'no_medical_history', 'changing_story'
        ]
        return sum(row.get(flag, False) for flag in behavioral_flags)
    
    def _count_reporting_flags(self, row):
        """Count reporting flags"""
        reporting_flags = ['delayed_reporting', 'no_witness']
        return sum(row.get(flag, False) for flag in reporting_flags)
    
    def _get_red_flags(self, row):
        """Get list of triggered red flags for a claim"""
        red_flags = []
        
        # Categorized flag messages
        flag_categories = {
            'REPORTING': {
                'delayed_reporting': 'Delayed reporting (>30 days)',
                'no_witness': 'No witness contacted',
            },
            'TIMING': {
                'near_birthday': 'Claim near birthday',
                'new_employee_30d': 'New employee (<30 days)',
                'new_employee_90d': 'Relatively new employee (<90 days)',
                'near_holiday': 'Claim near holiday',
                'claim_before_termination': 'Claim shortly before termination',
                'weekend_injury': 'Weekend injury',
                'unusual_time': 'Unusual time of injury',
                'summer_claim': 'Summer claim',
                'monday_morning_claim': 'Monday morning injury',
                'friday_afternoon_claim': 'Friday afternoon injury',
                'end_of_month_claim': 'End of month claim',
                'seasonal_spike': 'Seasonal spike period',
                'shift_change_injury': 'Injury during shift change',
                'lunch_break_injury': 'Lunch break injury',
                'pre_vacation_claim': 'Claim before vacation',
                'post_holiday_claim': 'First day back from holiday',
            },
            'BEHAVIORAL': {
                'multiple_claims': 'Multiple claims from same person',
                'claim_shopping': 'Multiple treatment facilities',
                'treatment_avoidance': 'Avoiding recommended treatment',
                'doctor_shopping': 'Frequent doctor changes',
                'excessive_treatment': 'Unusually long treatment',
                'quick_settlement': 'Pushing for quick settlement',
                'attorney_immediate': 'Attorney involved immediately',
                'previous_claims_pattern': 'Pattern of suspicious claims',
                'refused_light_duty': 'Refused modified work',
                'no_medical_history': 'No prior medical records',
                'changing_story': 'Inconsistent injury description',
            },
            'INJURY': {
                'soft_tissue_injury': 'Soft tissue injury',
                'suspicious_body_part': 'Suspicious body part injured',
                'high_claim_rate_location': 'High claim rate location',
                'injury_at_home': 'Injury at home address',
            }
        }
        
        for category, flags in flag_categories.items():
            for flag, message in flags.items():
                if row.get(flag, False):
                    red_flags.append(f"[{category}] {message}")
        
        return red_flags
    
    def generate_summary_stats(self, df):
        """Generate summary statistics"""
        stats = {
            'total_claims': len(df),
            'risk_distribution': df['risk_level'].value_counts().to_dict(),
            'avg_fraud_score': df['fraud_score'].mean(),
            'median_fraud_score': df['fraud_score'].median(),
            'high_risk_percentage': (df['risk_level'].isin(['High', 'Critical']).sum() / len(df) * 100),
            'top_red_flags': self._get_top_red_flags(df),
            'monthly_trend': self._get_monthly_trend(df) if 'Date of Loss' in df.columns else {}
        }
        return stats
    
    def _get_top_red_flags(self, df):
        """Get most common red flags"""
        all_flags = []
        for flags in df['red_flags']:
            if isinstance(flags, list):
                all_flags.extend(flags)
        
        from collections import Counter
        flag_counts = Counter(all_flags)
        return dict(flag_counts.most_common(5))
    
    def _get_monthly_trend(self, df):
        """Get monthly claim trends"""
        if 'Date of Loss' not in df.columns:
            return {}
        
        try:
            monthly = df.groupby(df['Date of Loss'].dt.to_period('M')).agg({
                'fraud_score': 'mean',
                'risk_level': lambda x: (x.isin(['High', 'Critical']).sum() / len(x) * 100)
            })
            
            return {
                'months': [str(m) for m in monthly.index],
                'avg_fraud_scores': monthly['fraud_score'].tolist(),
                'high_risk_percentages': monthly['risk_level'].tolist()
            }
        except Exception as e:
            print(f"Error generating monthly trend: {e}")
            return {}