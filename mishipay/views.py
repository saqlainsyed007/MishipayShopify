import urllib
import requests
import json
import shopify

from django.conf import settings

from django.urls import reverse

from django.contrib.auth import (
    login,
    logout,
    authenticate
)

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from custom_user.models import User
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import BasicAuthentication
from mishipay.custom_authentication import CsrfExemptSessionAuthentication

from django.views import View
from django.views.generic.base import TemplateView
from rest_framework.generics import (
    CreateAPIView,
    UpdateAPIView,
    DestroyAPIView
)

from django.http import (
    HttpResponse,
    HttpResponseRedirect,
)
from django.shortcuts import render

from mishipay.models import (
    CartItem,
    Order
)
from mishipay.serializers import CartItemSerializer
from mishipay.forms import (
    SignupForm,
    LoginForm
)

from mishipay.shopify_utils import (
    create_order,
    cancel_order as cancel_shopify_order,
    get_products,
    get_orders,
    filter_relevant_product_information,
    filter_relavant_order_information,
    filter_out_of_stock_products,
)


class SignUp(View):
    """
        Signup View. Renders a template with form to create user for 'GET'
        request. Validates form data and creates a user on 'POST' request.
    """
    form_class = SignupForm
    initial = {}
    template_name = 'signup.html'

    def get(self, request, *args, **kwargs):
        form = self.form_class(initial=self.initial)
        return render(request, self.template_name, {'form': form})

    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST)
        if form.is_valid():
            form.save()
            username = form.data['username']
            return HttpResponseRedirect("{}?username={}".format(reverse('login'), username))

        return render(request, self.template_name, {'form': form})


class Logout(View):
    """
        Logout current user.
    """
    def get(self, request, *args, **kwargs):
        logout(request)
        return HttpResponseRedirect(reverse('login'))


class Login(View):
    """
        Renders a template with form for user login for 'GET' request. Validates
        form data and logs in using the provided user credentials for 'POST' request.
    """
    form_class = LoginForm
    initial = {}
    template_name = 'login.html'

    def get(self, request, *args, **kwargs):
        next_page = request.GET.get('next', None)
        username = request.GET.get('username', None)
        if username:
            try:
                User.objects.get(username=username)
            except User.objects.DoesNotExist:
                username = ""
        if request.user.is_authenticated():
            if next_page:
                return HttpResponseRedirect(next_page)
            else:
                return HttpResponseRedirect(reverse('product_listing'))
        form = self.form_class(initial=self.initial)
        context = {
            'form': form,
            'next_page': next_page,
            'username': username
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST)
        if form.is_valid():
            username = request.POST['username']
            password = request.POST['password']
            next_page = request.GET.get('next', None)
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                if next_page:
                    return HttpResponseRedirect(next_page)
                else:
                    return HttpResponseRedirect(reverse('product_listing'))
            else:
                form.add_error(None, 'The entered credentials are invalid')
                return render(request, self.template_name, {'form': form})


class ProductListing(LoginRequiredMixin, View):
    """
        Renders a Product Listing page. Products are fetched from a
        shopify store using APIs
    """
    template_name = 'product_listing.html'

    def get(self, request, *args, **kwargs):
        products, err_msg = get_products()
        if err_msg:
            context = {
                'err_msg': err_msg,
                'products': [],
                'cart_products_ids': []
            }
            return render(request, self.template_name, context)

        context = {
            'products': filter_out_of_stock_products(
                filter_relevant_product_information(
                    products
                )
            ),
            # 'cart_products_ids' will be used to determine
            # if an item been added to cart.
            'cart_products_ids': CartItem.objects.filter(
                user=self.request.user,
                quantity__gt=0
            ).values_list('product_id', flat=True)
        }
        return render(request, self.template_name, context)


class AddtoCartAPI(CreateAPIView):
    """
        Adds an item to cart. Shopify Product IDs and respective quantities
        are stored as CartItem objects against each user.
    """
    serializer_class = CartItemSerializer
    permission_classes = (IsAuthenticated,)
    authentication_classes = (CsrfExemptSessionAuthentication, BasicAuthentication)

    def get_queryset(self):
        user = self.request.user
        return CartItem.objects.filter(user=user)

    def create(self, request, *args, **kwargs):
        user = self.request.user
        request.data['user'] = user.id
        return super(AddtoCartAPI, self).create(request, *args, **kwargs)


class UpdateDestroyCartItemAPI(DestroyAPIView, UpdateAPIView):
    """
        Updates a CartItem. Basically changing quantity. OR
        Delete a CartItem.
    """
    serializer_class = CartItemSerializer
    permission_classes = (IsAuthenticated,)
    authentication_classes = (CsrfExemptSessionAuthentication, BasicAuthentication)

    def get_serializer(self, *args, **kwargs):
        # Overriding to perform partial update
        kwargs['partial'] = True
        return super(UpdateDestroyCartItemAPI, self).get_serializer(*args, **kwargs)

    def get_queryset(self):
        user = self.request.user
        return CartItem.objects.filter(user=user)


class Cart(LoginRequiredMixin, TemplateView):
    """
        Displays information about the products that the current user
        has added to cart. Items in cart are stored as CartItem objects.
        Products are fetched from Shopify store using Shopify APIs and
        product ids stored in CartItem objects.
    """
    template_name = 'cart.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # If placing order fails, cart page is rendered with
        # the relevant err_msg.
        if 'err_msg' in self.request.GET:
            context['err_msg'] = self.request.GET['err_msg']

        cart_product_id_quantities = CartItem.objects.filter(
            user=user
        ).values('product_id', 'id', 'quantity')

        cart_product_id_quantity_map = {}
        cart_product_ids = []
        for cart_product_id_quantity in cart_product_id_quantities:
            cart_product_ids.append(cart_product_id_quantity['product_id'])
            cart_product_id_quantity_map[cart_product_id_quantity['product_id']] = {
                'id': cart_product_id_quantity['id'],
                'quantity': cart_product_id_quantity['quantity']
            }

        # Try to retrieve products from shopify only if there are any
        # products in cart
        if cart_product_ids:
            cart_shopify_products, err_msg = get_products(
                ids=cart_product_ids
            )
            if err_msg:
                context['err_msg'] = err_msg
                cart_shopify_products = []
        else:
            cart_shopify_products = []

        cart_items = []
        cart_total = 0
        for product in cart_shopify_products:
            # Internal database cart item id
            cart_item_id = cart_product_id_quantity_map[product['id']]['id']
            product_quantity = cart_product_id_quantity_map[product['id']]['quantity']
            product_price = product['variants'][0]['price']
            cart_item = {
                'id': cart_item_id,
                'product_id': product['id'],
                'product_title': product['title'],
                'price': float(product_price),
                'quantity': product_quantity
            }
            cart_items.append(cart_item)
            cart_total = cart_total + product_quantity * float(product_price)

        context['cart_items'] = cart_items
        context['cart_total'] = cart_total
        return context


@login_required()
def place_order(request):
    """
        Place an order on the Shopify store for all the items in the Cart
        (all CartItem objects) and update the Shopify store inventory.
    """
    user = request.user

    cart_items = CartItem.objects.filter(user=user)
    cart_product_id_quantities = cart_items.values('product_id', 'id', 'quantity')

    cart_product_id_quantity_map = {}
    cart_product_ids = []
    for cart_product_id_quantity in cart_product_id_quantities:
        cart_product_ids.append(cart_product_id_quantity['product_id'])
        cart_product_id_quantity_map[cart_product_id_quantity['product_id']] = {
            'id': cart_product_id_quantity['id'],
            'quantity': cart_product_id_quantity['quantity']
        }

    if cart_product_ids:
        cart_shopify_products, err_msg = get_products(
            ids=cart_product_ids
        )
        if err_msg:
            return HttpResponseRedirect('{}?err_msg={}'.format(reverse('cart'), urllib.parse.quote(err_msg)))

        for product in cart_shopify_products:
            product['quantity'] = cart_product_id_quantity_map[product['id']]['quantity']

        order, err_msg = create_order(user, cart_shopify_products)
        if err_msg:
            return HttpResponseRedirect('{}?err_msg={}'.format(reverse('cart'), urllib.parse.quote(err_msg)))

        cart_items.delete()
        return render(request, 'order_success.html', {'order': order, 'order_status': 'placed'})
    else:
        return HttpResponseRedirect(reverse('product_listing'))


@login_required()
def cancel_order(request, shopify_order_id):
    """
        Cancels the order with the given order id
        and updates the store inventory using Shopify APIs.
    """
    user = request.user

    # Verify that order belongs to current user.
    try:
        Order.objects.get(user=user, shopify_order_id=shopify_order_id)
    except Order.DoesNotExist:
        err_msg = 'Order #{} does not exist'.format(shopify_order_id)
        return HttpResponseRedirect('{}?err_msg={}'.format(reverse('my_orders'), urllib.parse.quote(err_msg)))

    order, err_msg = cancel_shopify_order(shopify_order_id)
    if err_msg:
        return HttpResponseRedirect('{}?err_msg={}'.format(reverse('my_orders'), urllib.parse.quote(err_msg)))
    else:
        return render(request, 'order_success.html', {'order_number': order['id'], 'order_status': 'cancelled'})


class MyOrders(LoginRequiredMixin, TemplateView):
    """
        Renders an Order Listing page. Order information and also constituent product
        information for each order is fetched from the shopify store using APIs.
    """
    template_name = 'my_orders.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if 'err_msg' in self.request.GET:
            context['err_msg'] = self.request.GET['err_msg']

        user = self.request.user
        orders = Order.objects.filter(user=user)
        if not orders:
            context['orders'] = []
            return context

        shopify_order_ids = orders.values_list('shopify_order_id', flat=True)
        shopify_orders, err_msg = get_orders(shopify_order_ids=shopify_order_ids, user=user)
        if err_msg:
            context['orders'] = []
            context['err_msg'] = err_msg
        else:
            context['orders'] = filter_relavant_order_information(shopify_orders)
        return context


def get_access_token(request):

    shop_url = "https://{}:{}@{}/admin".format(
        settings.SHOPIFY_API_KEY, settings.SHOPIFY_API_PASSWORD,
        settings.SHOPIFY_STORE_DOMAIN
    )
    shopify.ShopifyResource.set_site(shop_url)

    shopify.Session.setup(api_key=settings.SHOPIFY_API_KEY, secret=settings.SHOPIFY_API_PASSWORD)

    session = shopify.Session(settings.SHOPIFY_STORE_URL)

    scope = [
        "read_products", "write_products",
        "read_orders", "write_orders",
        "read_draft_orders", "write_draft_orders",
        "read_inventory", "write_inventory",
        "read_fulfillments", "write_fulfillments",
        "read_shipping", "write_shipping",
        "read_checkouts", "write_checkouts",
    ]

    permission_url = session.create_permission_url(scope, settings.SHOPIFY_ACCESS_REDIRECT_URL)

    return HttpResponseRedirect(permission_url)


def access_token(request):

    if not shopify.Session.validate_hmac(request.GET):
        return HttpResponse("Invalid HMAC")

    access_token_api_data = {
        'client_id': settings.SHOPIFY_API_KEY,
        'client_secret': settings.SHOPIFY_API_PASSWORD,
        'code': request.GET.get('code', None)
    }

    access_token_api_url = '{}/admin/oauth/access_token'.format(settings.SHOPIFY_STORE_URL)
    access_token_api_response = requests.post(access_token_api_url.strip(), data=access_token_api_data)

    if access_token_api_response.status_code == 200:
        return HttpResponse("Access Token: {}".format(json.loads(access_token_api_response.text)['access_token']))
    else:
        return HttpResponse("Failed to get Access Token: {}".format(access_token_api_response.text))
