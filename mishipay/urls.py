from django.conf.urls import url
from mishipay.views import (
    get_access_token,
    access_token,
    ProductListing,
    AddtoCartAPI,
    UpdateDestroyCartItemAPI,
    Cart,
    place_order,
    cancel_order,
    MyOrders
)

urlpatterns = [
    url(r'^$', ProductListing.as_view(), name='product_listing'),
    url(r'^get-access-token/', get_access_token, name="get_access_token"),
    url(r'^access-token/', access_token, name="access_token"),
    url(r'^products/$', ProductListing.as_view(), name='product_listing'),
    url(r'^add-to-cart/$', AddtoCartAPI.as_view(), name='add_to_cart'),
    url(r'^update-cart-item/(?P<pk>[0-9]+)/$', UpdateDestroyCartItemAPI.as_view(), name='add_to_cart'),
    url(r'^cart/$', Cart.as_view(), name='cart'),
    url(r'^my-orders/$', MyOrders.as_view(), name='my_orders'),
    url(r'^place-order/$', place_order, name='place_order'),
    url(r'^cancel-order/(?P<shopify_order_id>[0-9]+)$', cancel_order, name='cancel_order'),
]
