from django.db import models
from django.contrib.auth.models import User
import json

class UploadedFile(models.Model):
    """Track all uploaded files"""
    file = models.FileField(upload_to='uploads/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    file_name = models.CharField(max_length=255)
    file_size = models.IntegerField()
    
    def __str__(self):
        return f"{self.file_name} - {self.uploaded_at.strftime('%Y-%m-%d %H:%M')}"

class FraudAnalysis(models.Model):
    uploaded_file = models.FileField(upload_to='uploads/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    # Summary statistics
    total_claims = models.IntegerField(default=0)
    low_risk_count = models.IntegerField(default=0)
    medium_risk_count = models.IntegerField(default=0)
    high_risk_count = models.IntegerField(default=0)
    critical_risk_count = models.IntegerField(default=0)
    
    # File paths
    output_csv_path = models.CharField(max_length=500, blank=True)
    high_risk_csv_path = models.CharField(max_length=500, blank=True)
    
    # Visualization paths
    visualizations = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-uploaded_at']
        
    def __str__(self):
        return f"Analysis {self.id} - {self.uploaded_at.strftime('%Y-%m-%d %H:%M')}"

#Updated

class Claim(models.Model):
    RISK_LEVELS = [
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
        ('Critical', 'Critical'),
    ]
    
    # Your existing fields...
    analysis = models.ForeignKey(FraudAnalysis, on_delete=models.CASCADE, related_name='claims')
    claim_number = models.CharField(max_length=100)
    claimant_name = models.CharField(max_length=200)
    date_of_loss = models.DateField(null=True, blank=True)
    injury_type = models.CharField(max_length=200, blank=True)
    body_part = models.CharField(max_length=200, blank=True)
    fraud_score = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    risk_level = models.CharField(max_length=20, choices=RISK_LEVELS, default='Low')
    red_flags = models.JSONField(default=list, blank=True)
    days_to_report = models.IntegerField(null=True, blank=True)
    claim_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    # NEW FIELDS for enhanced functionality
    # Geographic information
    state = models.CharField(max_length=2, blank=True, help_text="2-letter state code")
    city = models.CharField(max_length=100, blank=True)
    zip_code = models.CharField(max_length=10, blank=True)
    location_description = models.CharField(max_length=500, blank=True)
    
    # Enhanced claim details
    date_reported = models.DateField(null=True, blank=True)
    date_of_hire = models.DateField(null=True, blank=True)
    claimant_dob = models.DateField(null=True, blank=True)
    
    # Employment information
    job_title = models.CharField(max_length=200, blank=True)
    department = models.CharField(max_length=200, blank=True)
    supervisor = models.CharField(max_length=200, blank=True)
    
    # Claim specifics
    cause_of_injury = models.CharField(max_length=500, blank=True)
    attorney_involved = models.BooleanField(default=False)
    witness_available = models.BooleanField(default=False)
    medical_treatment = models.CharField(max_length=200, blank=True)
    
    # Financial details
    medical_costs = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    indemnity_costs = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    legal_costs = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-fraud_score', '-date_of_loss']
        indexes = [
            models.Index(fields=['risk_level']),
            models.Index(fields=['fraud_score']),
            models.Index(fields=['date_of_loss']),
            models.Index(fields=['state']),
            models.Index(fields=['claimant_name']),
        ]
    
    def __str__(self):
        return f"{self.claim_number} - {self.claimant_name} ({self.risk_level})"
    
    @property
    def is_high_risk(self):
        return self.risk_level in ['High', 'Critical']
    
    @property
    def red_flags_count(self):
        return len(self.red_flags) if self.red_flags else 0
    
    @property
    def days_employed_before_incident(self):
        if self.date_of_hire and self.date_of_loss:
            return (self.date_of_loss - self.date_of_hire).days
        return None
    
    @property
    def age_at_incident(self):
        if self.claimant_dob and self.date_of_loss:
            return (self.date_of_loss - self.claimant_dob).days // 365
        return None