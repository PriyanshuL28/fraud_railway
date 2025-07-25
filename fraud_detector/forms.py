from django import forms
from .models import FraudAnalysis

class UploadFileForm(forms.ModelForm):
    """Form for uploading CSV files for fraud analysis"""
    
    class Meta:
        model = FraudAnalysis
        fields = ['uploaded_file']
        widgets = {
            'uploaded_file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.csv',
                'required': True
            })
        }
    
    def clean_uploaded_file(self):
        uploaded_file = self.cleaned_data.get('uploaded_file')
        
        if uploaded_file:
            # Check file extension
            if not uploaded_file.name.lower().endswith('.csv'):
                raise forms.ValidationError("Please upload a CSV file only.")
            
            # Check file size (max 50MB)
            if uploaded_file.size > 500 * 1024 * 1024:
                raise forms.ValidationError("File size must be under 500MB.")
        
        return uploaded_file