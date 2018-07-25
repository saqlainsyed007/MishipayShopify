from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import (
    MinValueValidator,
    MaxValueValidator
)


class User(AbstractUser):

    address = models.CharField(
        max_length=512
    )

    phone_number = models.IntegerField(
        # 10 digit phone number validation
        validators=[
            MinValueValidator(1000000000),
            MaxValueValidator(9999999999)
        ]
    )
