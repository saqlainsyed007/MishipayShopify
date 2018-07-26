# MishipayShopify

This Application requires `Python3 and Pip3`


Python 3 can be downloaded from https://www.python.org/downloads/. if you are using python 3.4 or higher, pip3 is already installed. Otherwise download and install manually from https://pip.pypa.io/en/stable/installing/.


Use of virtual environment is recommended. https://virtualenvwrapper.readthedocs.io/en/latest/install.html.


### Download
```
git clone https://github.com/saqlainsyed007/MishipayShopify.git

cd MishipayShopify/
```

### Install
```
pip install -r requirements.txt

python manage.py migrate
```

### Environment variables

create a `.env` file under `MishipayShopify/` and add the following environment variables
```
SHOPIFY_API_KEY=<Your Shopify API key> Eg: 5009229ddaddya1e72e1qcdd6bre1ac3
SHOPIFY_API_PASSWORD=<Your Shopify API secret key> Eg: 724e80526d5te12053b24w68976a1a3k
SHOPIFY_ACCESS_TOKEN=<Your Shopify Access Token> Eg: 8109229wraddta1e72e1adfh6lre3ac4
SHOPIFY_STORE_URL=<Your Shopify Store URL> Eg: https://examplestore.myshopify.com
SHOPIFY_STORE_DOMAIN=<Your Shopify Store Domain> Eg: examplestore.myshopify.com
```

### Run Application
```
python manage.py runserver 0:8000
```

### View Application
Go to `http://localhost:8000/`

### Access Token
If you want to retrieve/verify your access token after setting the other envs mentioned above, You can go to `http://localhost:8000/get-access-token/`

**Note:**

CDNs are used in this application and they do not load sometimes. Please hard refresh untill all CDNs are loaded and there are no 403, 404 errors in the browser console
