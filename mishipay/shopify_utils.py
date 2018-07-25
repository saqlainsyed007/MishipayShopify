import requests
import json
from django.conf import settings
from mishipay.models import Order
from mishipay.constants import (
    ORDER_TYPE_PLACED,
    ORDER_TYPE_CANCELLED
)
from requests.exceptions import RequestException


def get_products(ids=[]):
    """
        Returns a tuple where first item is the list of products and the
        second item is an error message. If ids are passed, then product
        list is the list of products with the given ids. If no ids are
        passed returns a list of all products.
        In case an error is encountered, an empty list along with an error
        message is returned.
    """

    ids = [str(_id) for _id in ids]

    # Get only these fields from the Shopify API.
    # Other fields do not have relevancy for this
    # application as of now.
    product_required_fields = [
        'id',
        'title',
        'body_html',
        'images',
        'variants'
    ]

    # Will end up as query param string
    product_ids_query_param = ''

    if ids:
        product_ids_query_param = '&ids={}'.format(','.join(ids))
    product_fields_query_param = 'fields={}'.format(','.join(product_required_fields))
    product_listing_url = '{}/admin/products.json?{}{}'.format(settings.SHOPIFY_STORE_URL, product_fields_query_param, product_ids_query_param)
    try:
        products_response = requests.get(product_listing_url, headers=settings.SHOPIFY_API_HEADERS)
    except RequestException:
        return [], 'Error retrieving products'

    products = products_response.json()

    if 'error' in products or 'errors' in products:
        return [], 'Error retrieving products: {}'.format(
            products.get('error', products.get('errors'))
        )
    return products['products'], ''


def filter_relevant_product_information(products):
    """
        Use this method to remove unnecessary nested
        information from products. This will help reduce
        data load on the Frontend.
    """

    for product in products:

        images = []
        for image in product['images']:
            images.append({
                'src': image['src'],
                'position': image['position']
            })
        product['images'] = images

        variants = []
        for variant in product['variants']:
            variants.append({
                'id': variant['id'],
                'title': variant['title'],
                'inventory_item_id': variant['inventory_item_id'],
                'inventory_quantity': variant['inventory_quantity'],
                'price': variant['price'],
            })
        product['variants'] = variants

    return products


def filter_out_of_stock_products(products):
    """
        Filter out products that are unavailable.
    """

    filtered_products = []
    for product in products:
        if int(product['variants'][0]['inventory_quantity']) > 0:
            filtered_products.append(product)
    return filtered_products


def update_inventory(products, order_type=ORDER_TYPE_PLACED):
    """
        Update availability of inventory items. If an order is placed the
        number of inventory items reduce with respect to the order items
        and their quantity. Likewise, if an order is cancelled, the number
        of inventory items increase with respect to the order items and
        their quantity.
    """

    if order_type == ORDER_TYPE_PLACED:
        # For placing an order, item is removed from inventory. i.e.,
        # New inventory quantity = Old inventory quantity - order quantity
        # = New inventory quantity = Old inventory quantity + (order quantity * -1)
        quantity_multiplication_factor = -1
    elif order_type == ORDER_TYPE_CANCELLED:
        # For cancelling an order, item is removed from inventory. i.e.,
        # New inventory quantity = Old inventory quantity + order quantity
        # = New inventory quantity = Old inventory quantity + (order quantity * 1)
        quantity_multiplication_factor = 1
    else:
        return False, 'Invalid Order Type'

    # Get Inventory IDs for each product varient added.
    inventory_ids = []
    inventory_item_id_quantity_map = {}
    for product in products:
        # Varients have not been considered in scope of this application.
        # Hence we simple use the first one. A product must have atleast 1.
        inventory_item_id = product['variants'][0]['inventory_item_id']
        inventory_quantity = product['variants'][0]['inventory_quantity']
        if (
            inventory_quantity < product['quantity'] and
            order_type == ORDER_TYPE_PLACED
        ):
            return False, '{} out of stock'.format(product['title'])
        inventory_ids.append(str(inventory_item_id))
        inventory_item_id_quantity_map[inventory_item_id] = product['quantity'] * quantity_multiplication_factor

    # Get inventory levels for each product that requires an update.
    # We need location id to update the inventory levels of products.
    # Hence, though this call may seem redudant but it is a must.
    inventory_item_ids_query_param = 'inventory_item_ids={}'.format(','.join(inventory_ids))
    inventory_levels_url = '{}/admin/inventory_levels.json?{}'.format(settings.SHOPIFY_STORE_URL, inventory_item_ids_query_param)
    try:
        inventory_levels_response = requests.get(inventory_levels_url, headers=settings.SHOPIFY_API_HEADERS)
    except RequestException:
        return False, 'Error retrieving inventory levels'
    inventory_levels = inventory_levels_response.json()
    if 'error' in inventory_levels or 'errors' in inventory_levels:
        return False, 'Error retrieving Inventory levels: {}'.format(
            inventory_levels.get('error', inventory_levels.get('errors'))
        )

    inventory_item_id_location_id_map = {}
    for inventory_level in inventory_levels['inventory_levels']:
        inventory_item_id = inventory_level['inventory_item_id']
        # No need to check for order type here because the quantity map will have
        # negative quantities for a cancelled order.
        if inventory_level['available'] < inventory_item_id_quantity_map[inventory_item_id]:
            return False, 'Some item out of stock'
        inventory_item_id_location_id_map[inventory_item_id] = inventory_level['location_id']

    # Adjust Inventory levels of each product. No bulk operation API.
    for inventory_item_id in inventory_item_id_quantity_map.keys():
        inventory_level_adjust_data = {
            'inventory_item_id': inventory_item_id,
            'location_id': inventory_item_id_location_id_map[inventory_item_id],
            'available_adjustment': inventory_item_id_quantity_map[inventory_item_id]
        }
        inventory_level_adjust_url = '{}/admin/inventory_levels/adjust.json'.format(settings.SHOPIFY_STORE_URL)
        try:
            inventory_level_adjust_response = requests.post(
                inventory_level_adjust_url,
                headers=settings.SHOPIFY_API_HEADERS,
                data=json.dumps(inventory_level_adjust_data)
            )
        except RequestException:
            return False, 'Error updating Inventory'
        inventory_level_adjust = inventory_level_adjust_response.json()
        if 'error' in inventory_level_adjust or 'errors' in inventory_level_adjust:
            return False, 'Inventory level adjustment failed: {}'.format(
                inventory_level_adjust.get('error', inventory_level_adjust.get('errors'))
            )
    return True, ''


def get_orders(shopify_order_ids=[], user=None):
    """
        Returns a tuple where first item is the list of orders and the
        second item is an error message. Order list is a list of all
        orders and is filtered by id if ids are passed. If a user is
        present, the orders are further filtered as those that belong
        to that user.
        In case an error is encountered, an empty list along with an
        error message is returned.
    """

    shopify_order_ids = [str(shopify_order_id) for shopify_order_id in shopify_order_ids]

    # Get only these fields from the Shopify API.
    # Other fields do not have relevancy for this
    # application as of now
    shopify_order_required_fields = [
        'id',
        'contact_email',
        'created_at',
        'cancelled_at',
        'email',
        'financial_status',
        'fulfillment_status',
        'line_items',
        'order_status',
        'phone',
        'subtotal_price',
        'total_line_items_price',
        'total_price'
    ]

    if user:
        # For a user context, retrieve all orders or orders with requested ids that belong to that user
        user_shopify_order_ids = Order.objects.filter(user=user).values_list('shopify_order_id', flat=True)
        user_shopify_order_ids = [str(user_shopify_order_id) for user_shopify_order_id in user_shopify_order_ids]
        shopify_order_ids = list(
            set(shopify_order_ids).intersection(set(user_shopify_order_ids))
        ) if shopify_order_ids else shopify_order_ids
        shopify_order_ids_query_param = 'ids={}'.format(','.join(shopify_order_ids))
    else:
        # If there is no user context retrieve all orders data. This could be a call for an admin order page.
        shopify_order_ids_query_param = ''
        if shopify_order_ids:
            shopify_order_ids_query_param = 'ids={}'.format(','.join(shopify_order_ids))

    # Retrieve orders
    shopify_order_fields_query_param = 'fields={}'.format(','.join(shopify_order_required_fields))
    shopify_orders_list_url = '{}/admin/orders.json?{}&status=any&{}'.format(settings.SHOPIFY_STORE_URL, shopify_order_fields_query_param, shopify_order_ids_query_param)
    try:
        shopify_orders_list_response = requests.get(shopify_orders_list_url, headers=settings.SHOPIFY_API_HEADERS)
    except RequestException:
        return [], 'Error retrieving Orders'
    shopify_orders_list = shopify_orders_list_response.json()

    if 'error' in shopify_orders_list or 'errors' in shopify_orders_list:
        return [], 'Error retrieving orders: {}'.format(
            shopify_orders_list.get('error', shopify_orders_list.get('errors'))
        )

    return shopify_orders_list['orders'], ''


def filter_relavant_order_information(orders):
    """
        Use this method to remove unnecessary nested
        information from products. This will help reduce
        data load on the Frontend.
    """

    for order in orders:
        line_items = []
        for line_item in order['line_items']:
            line_items.append({
                'id': line_item['id'],
                'product_id': line_item['product_id'],
                'variant_id': line_item['variant_id'],
                'title': line_item['title'],
                'quantity': line_item['quantity'],
                'price': line_item['price']
            })
        order['line_items'] = line_items
    return orders


def create_order(user, products):
    """
        Create an order and update the inventory.
    """

    if not products or type(products) not in (list, tuple, set):
        return False, 'No products to order'

    # Update Inventory first so that there are no conflicts in
    # two simultaneous near Out of Stock orders.
    inventory_update_status, err_msg = update_inventory(products, order_type=ORDER_TYPE_PLACED)

    if err_msg:
        return False, err_msg

    order_data = {
        'order': {
            'send_receipt': True,
            'send_fulfillment_receipt': True,
            'line_items': []
        }
    }

    order_data['email'] = user.email
    order_data['phone'] = user.phone_number

    for product in products:
        order_data['order']['line_items'].append(
            {
                'variant_id': product['variants'][0]['id'],
                'quantity': product['quantity']
            }
        )

    # Create order
    create_order_url = '{}/admin/orders.json'.format(settings.SHOPIFY_STORE_URL)
    try:
        create_order_response = requests.post(create_order_url, headers=settings.SHOPIFY_API_HEADERS, data=json.dumps(order_data))
    except RequestException:
        return False, 'Error creating order'
    created_order = create_order_response.json()

    if 'error' in created_order or 'errors' in created_order:
        return False, 'Error creating order: {}'.format(
            created_order.get('error', created_order.get('errors'))
        )

    # If creating order on shopify was successful, create an entry
    # in our internal database.
    Order.objects.create(
        shopify_order_id=created_order['order']['id'],
        user=user,
    )

    return created_order['order'], ''


def cancel_order(shopify_order_id):
    """
        Cancel an order and update the inventory.
    """

    shopify_orders, err_msg = get_orders(shopify_order_ids=[str(shopify_order_id)])
    if err_msg:
        return False, err_msg

    if not shopify_orders:
        return False, 'Order #{} does not exist'.format(shopify_order_id)

    shopify_order = shopify_orders[0]

    if shopify_order['cancelled_at']:
        return False, 'Order #{} is already cancelled'.format(shopify_order_id)

    cancel_order_url = '{}/admin/orders/{}/cancel.json'.format(settings.SHOPIFY_STORE_URL, shopify_order['id'])
    try:
        cancel_order_response = requests.post(cancel_order_url, headers=settings.SHOPIFY_API_HEADERS, data={})
    except RequestException:
        return False, 'Error cancelling order'
    cancelled_order = cancel_order_response.json()

    if 'error' in cancelled_order or 'errors' in cancelled_order:
        return False, 'Error cancelling order: {}'.format(
            cancelled_order.get('error', cancelled_order.get('errors'))
        )

    # Get product information of products in order to update inventory.
    # We can't simply use line items in the order dict because they do
    # not have inventory item id.
    product_id_quantity_map = {}
    product_ids = []
    for line_item in shopify_order['line_items']:
        product_id = line_item['product_id']
        product_ids.append(product_id)
        product_id_quantity_map[product_id] = line_item['quantity']

    products, err_msg = get_products(product_ids)
    if err_msg:
        return False, err_msg

    # Update quantity of each product as per the order.
    for product in products:
        product['quantity'] = product_id_quantity_map[product['id']]

    # TBD: This can be async. Celery perhaps?
    inventory_update_status, err_msg = update_inventory(products, order_type=ORDER_TYPE_CANCELLED)

    if err_msg:
        print('Error Updating inventory: ', err_msg, '\nTBD: Handle this case')

    return cancelled_order['order'], ''
