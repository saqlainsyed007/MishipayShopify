from django import forms
from custom_user.models import User
from django.contrib.auth.forms import UserCreationForm
from django.core.validators import (
    EmailValidator,
    MinValueValidator,
    MaxValueValidator,
)


class SignupForm(UserCreationForm):

    email = forms.CharField(
        validators=[
            EmailValidator("Enter valid email")
        ]
    )

    phone_number = forms.IntegerField(
        # 10 digit number validation
        validators=[
            MinValueValidator(1000000000, "Enter Valid Phone Number"),
            MaxValueValidator(9999999999, "Enter Valid Phone Number")
        ]
    )

    class Meta:
        model = User
        fields = ['username', 'password1', 'password2', 'first_name', 'last_name', 'email', 'phone_number', 'address']


class LoginForm(forms.Form):

    username = forms.CharField()

    password = forms.CharField(
        widget=forms.PasswordInput,
    )
