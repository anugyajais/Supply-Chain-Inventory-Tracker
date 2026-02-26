from django import forms
from .models import Product

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        # We only ask for the essentials to keep the form quick!
        fields = ['sku', 'name', 'category', 'unit_cost']
        widgets = {
            'sku': forms.TextInput(attrs={'placeholder': 'e.g. LAP-MAC-16'}),
            'name': forms.TextInput(attrs={'placeholder': 'e.g. MacBook Pro 16"'}),
            'category': forms.TextInput(attrs={'placeholder': 'e.g. Electronics'}),
            'unit_cost': forms.NumberInput(attrs={'placeholder': '0.00', 'step': '0.01'}),
        }