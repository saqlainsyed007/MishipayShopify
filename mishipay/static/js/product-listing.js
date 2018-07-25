$(document).on('click', '.add-to-cart-button', function(event){

  let productInformation = event.target.dataset;
  productInformation = Object.assign({}, productInformation);

  $.ajax({
    type: 'POST',
    url: '/add-to-cart/',
    data: JSON.stringify(productInformation),
    contentType: "application/json",

    success: function(result){
      event.target.disabled = true;
      event.target.innerText = "Added to cart"
    },

    error: function() {
      console.log("Error!");
    },
  });
});
