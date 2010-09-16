
from decimal import Decimal
from operator import mul

from django.core.urlresolvers import reverse
from django.test import TestCase

from cartridge.shop.models import Product, ProductOption, ProductVariation, Category, \
    Cart, CartItem
from cartridge.shop.settings import CHECKOUT_ACCOUNT_ENABLED, CHECKOUT_ACCOUNT_REQUIRED, \
    OPTION_TYPE_CHOICES


class ShopTests(TestCase):

    urls = "shop.urls"
    
    def setUp(self):
        self._category = Category.objects.create(active=True)
        self._product = Product.objects.create(active=True)
        for option_type in OPTION_TYPE_CHOICES:
            for i in range(10):
                name = "test%s" % i
                ProductOption.objects.create(type=option_type[0], name=name)

    def test_views(self):
        """
        test the main shop views for errors
        """
        # category
        response = self.client.get(self._category.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        # product
        response = self.client.get(self._product.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        # cart
        response = self.client.get(reverse("shop_cart"))
        self.assertEqual(response.status_code, 200)
        # checkout
        response = self.client.get(reverse("shop_checkout"))
        self.assertEqual(response.status_code, 200 if not 
            CHECKOUT_ACCOUNT_REQUIRED else 302)
        # Login
        if CHECKOUT_ACCOUNT_ENABLED:
            response = self.client.get(reverse("shop_account"))
            self.assertEqual(response.status_code, 200)

    def test_variations(self):
        """
        test creation of variations from options, and management of empty 
        variations
        """
        product_options = ProductOption.objects.as_fields()
        total_variations = reduce(mul, [len(values) 
            for values in product_options.values()])
        # clear variations
        self._product.variations.all().delete()
        self.assertEqual(self._product.variations.count(), 0)
        # create single empty variation
        self._product.variations.manage_empty()
        self.assertEqual(self._product.variations.count(), 1)
        # create variations from all options
        self._product.variations.create_from_options(product_options)
        # should do nothing
        self._product.variations.create_from_options(product_options)
        # all options plus empty
        self.assertEqual(self._product.variations.count(), total_variations + 1)
        # remove empty
        self._product.variations.manage_empty()
        self.assertEqual(self._product.variations.count(), total_variations)

    def test_stock(self):
        """
        test stock checking on product variations
        """
        self._product.variations.all().delete()
        self._product.variations.manage_empty()
        num_in_stock = 10
        variation = self._product.variations.all()[0]
        variation.num_in_stock = num_in_stock
        # check stock field not in use
        self.assertTrue(variation.has_stock())
        # check available and unavailable quantities
        self.assertTrue(variation.has_stock(num_in_stock))
        self.assertFalse(variation.has_stock(num_in_stock + 1))
        # check sold out
        variation = self._product.variations.all()[0]
        variation.num_in_stock = 0
        self.assertFalse(variation.has_stock())

    def test_cart(self):
        """
        test the cart object and cart add/remove forms
        """
        product_options = ProductOption.objects.as_fields()
        self._product.variations.all().delete()
        self._product.variations.create_from_options(product_options)
        price = Decimal("20")
        num_in_stock = 5
        variation = self._product.variations.all()[0]
        variation.unit_price = price
        variation.num_in_stock = num_in_stock * 2
        variation.save()

        # test initial cart
        cart = Cart.objects.from_request(self.client)
        self.assertFalse(cart.has_items())
        self.assertEqual(cart.total_quantity(), 0)
        self.assertEqual(cart.total_price(), Decimal("0"))

        # add quantity and check stock levels / cart totals
        data = dict(zip([field.name for field in 
            ProductVariation.option_fields()], variation.options()))
        data["quantity"] = num_in_stock
        self.client.post(self._product.get_absolute_url(), data)
        cart = Cart.objects.from_request(self.client)
        variation = self._product.variations.all()[0]
        self.assertTrue(variation.has_stock(num_in_stock))
        self.assertFalse(variation.has_stock(num_in_stock * 2))
        self.assertTrue(cart.has_items())
        self.assertEqual(cart.total_quantity(), num_in_stock)
        self.assertEqual(cart.total_price(), price * num_in_stock)

        # add remaining quantity and check again
        self.client.post(self._product.get_absolute_url(), data)
        cart = Cart.objects.from_request(self.client)
        variation = self._product.variations.all()[0]
        self.assertFalse(variation.has_stock())
        self.assertTrue(cart.has_items())
        self.assertEqual(cart.total_quantity(), num_in_stock * 2)
        self.assertEqual(cart.total_price(), price * num_in_stock * 2)

        # remove from cart
        for item in cart:
            self.client.post(reverse("shop_cart"), {"item_id": item.id})
        cart = Cart.objects.from_request(self.client)
        variation = self._product.variations.all()[0]
        self.assertTrue(variation.has_stock(num_in_stock * 2))
        self.assertFalse(cart.has_items())
        self.assertEqual(cart.total_quantity(), 0)
        self.assertEqual(cart.total_price(), Decimal("0"))

    def test_search(self):
        """
        test product search
        """
        Product.objects.all().delete()
        first = Product.objects.create(title="test product").id
        second = Product.objects.create(title="test another test product").id
        # either word
        results = Product.objects.search("another test")
        self.assertEqual(len(results), 2)
        # must include first word
        results = Product.objects.search("+another test")
        self.assertEqual(len(results), 1)
        # mustn't include first word
        results = Product.objects.search("-another test")
        self.assertEqual(len(results), 1)
        if results:
            self.assertEqual(results[0].id, first)
        # exact phrase
        results = Product.objects.search('"another test"')
        self.assertEqual(len(results), 1)
        if results:
            self.assertEqual(results[0].id, second)
        # test ordering
        results = Product.objects.search("test")
        self.assertEqual(len(results), 2)
        if results:
            self.assertEqual(results[0].id, second)

    def test_sales(self):
        """
        test sales
        """
        pass

    def test_checkout(self):
        """
        test the checkout process
        """
        pass
