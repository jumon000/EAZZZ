# app/tests/test_product.py

from app.services.amazon_search_service import AmazonService
from app.services.walmart_search_service import WalmartService
import json

def test_amazon():
    print("🔍 Testing AmazonService...\n")
    keyword = "iphone"
    products = AmazonService.get_top_products(keyword, limit=2)
    print(json.dumps(products, indent=2))

# def test_walmart():
#     print("🛒 Testing WalmartService...\n")
#     keyword = "xiaomi"
#     products = WalmartService.get_top_products(keyword, count=2)
#     print(json.dumps(products, indent=2))

if __name__ == "__main__":
    test_amazon()
    # print("\n" + "="*80 + "\n")
    # test_walmart()
