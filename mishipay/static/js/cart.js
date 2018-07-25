$(document).on('change', '.product-quantity', function(event){

  $('input').prop('disabled', true)
  let productInformation = event.target.dataset;
  productInformation = Object.assign({}, productInformation);

  data = {
    "quantity": event.target.value
  }

  request_type = 'PUT'
  if (parseInt(event.target.value) == 0) {
    request_type = 'DELETE'
  }

  $.ajax({
    type: request_type,
    url: '/update-cart-item/' + productInformation['cartItemId'] + '/',
    data: JSON.stringify(data),
    contentType: "application/json",

    success: function(result){
      // We don't simply reload because error message would be retained.
      location.href = /cart/;
    },

    error: function() {
      event.target.value = $(event.target).attr('prev-value');
      $(event.target).siblings('.quantity-update-error').text("An error occured. Please try again.");
      $('input').prop('disabled', false);
    }
  });
});
