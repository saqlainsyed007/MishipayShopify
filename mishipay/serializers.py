from rest_framework.serializers import ModelSerializer
from mishipay.models import CartItem


class CartItemSerializer(ModelSerializer):

    class Meta:
        model = CartItem
        fields = ('id', 'product_id', 'quantity', 'user')
