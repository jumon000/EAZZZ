from app.services.amazon_search_service import AmazonService
from app.services.walmart_search_service import WalmartService
from typing import Union

# Amazon functions

def search_amazon_products(keyword: str, limit: int = 2):
    return AmazonService.get_top_products(keyword, limit)

def filter_amazon_products(keyword: str, filters: dict, limit: int = 2):
    return AmazonService.get_filtered_products(keyword=keyword, filters=filters, limit=limit)
    
def amazon_product_details(asin: str):
    return AmazonService._get_product_details(asin)

def amazon_product_reviews(asin: str):
    return AmazonService._get_product_reviews(asin)

def search_walmart_products(keyword: str, limit: int = 2):
    return WalmartService.get_top_products(keyword, limit)

def filter_walmart_products(keyword: str, filters: dict):
    return WalmartService.get_filtered_products(keyword,filters)

def walmart_product_description(us_item_id: str):
    return WalmartService._get_product_description(us_item_id)

def walmart_product_reviews(us_item_id: str):
    return WalmartService._get_product_reviews(us_item_id)