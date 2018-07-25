$(document).on('click', '.redirect-button', function(event){
  redirectURL = event.currentTarget.getAttribute('redirect-url')
  if (redirectURL != "" && redirectURL != null) {
    location.href = redirectURL
  }
});
