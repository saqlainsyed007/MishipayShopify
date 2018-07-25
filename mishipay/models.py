from django.db import models
from custom_user.models import User


class Order(models.Model):

    shopify_order_id = models.IntegerField(
        unique=True
    )

    user = models.ForeignKey(
        User,
        related_name='orders',
        on_delete=models.CASCADE
    )

    def __str__(self):
        return "{} | {}".format(self.user.username, self.shopify_order_id)


class CartItem(models.Model):

    product_id = models.IntegerField()

    quantity = models.IntegerField(
        default=1
    )

    user = models.ForeignKey(
        User,
        related_name='cart_items',
        on_delete=models.CASCADE
    )

    class Meta:
        # Ideally this should be ('product_id', 'varient_id', 'user')
        # but since we are concerned about varients at the moment, we
        # ignore that as of now.
        unique_together = ('product_id', 'user')

    def __str__(self):
        return "Cart Item: {} | {}".format(self.product_title, self.user.username)
