from app.services.amazon_search_service import AmazonService
from app.services.walmart_search_service import WalmartService
from typing import Union


def search_amazon_products(keyword: str, limit: int = 2):
    """Search for top Amazon products by keyword"""
    return AmazonService.get_top_products(keyword, limit)

def filter_amazon_products(keyword: str, filters: dict, limit: int = 2):
    """Filter Amazon products by keyword and specific criteria"""
    return AmazonService.get_filtered_products(keyword=keyword, filters=filters, limit=limit)
    

def amazon_product_reviews_by_keyword(keyword: str, product_limit: int = 2):
    """Get reviews for Amazon products based on keyword search"""
    return AmazonService.get_product_reviews_by_keyword(keyword, product_limit)

def amazon_product_descriptions_by_keyword(keyword: str, product_limit: int = 2):
    """Get detailed descriptions for Amazon products based on keyword search"""
    return AmazonService.get_product_descriptions_by_keyword(keyword, product_limit)


def search_walmart_products(keyword: str, limit: int = 2):
    """Search for top Walmart products by keyword"""
    return WalmartService.get_top_products(keyword, limit)

def filter_walmart_products(keyword: str, filters: dict):
    """Filter Walmart products by keyword and specific criteria"""
    return WalmartService.get_filtered_products(keyword, filters)


def walmart_product_reviews_by_keyword(keyword: str, product_limit: int = 2):
    """Get reviews for Walmart products based on keyword search"""
    return WalmartService.get_product_reviews_by_keyword(keyword, product_limit)

def walmart_product_descriptions_by_keyword(keyword: str, product_limit: int = 2):
    """Get detailed descriptions for Walmart products based on keyword search"""
    return WalmartService.get_product_descriptions_by_keyword(keyword, product_limit)


def get_product_reviews_from_both_platforms(keyword: str, product_limit: int = 2):
    """Get reviews from both Amazon and Walmart for a given keyword"""
    amazon_reviews = amazon_product_reviews_by_keyword(keyword, product_limit)
    walmart_reviews = walmart_product_reviews_by_keyword(keyword, product_limit)
    
    return {
        "amazon_reviews": amazon_reviews,
        "walmart_reviews": walmart_reviews
    }

def get_product_descriptions_from_both_platforms(keyword: str, product_limit: int = 2):
    """Get detailed descriptions from both Amazon and Walmart for a given keyword"""
    amazon_descriptions = amazon_product_descriptions_by_keyword(keyword, product_limit)
    walmart_descriptions = walmart_product_descriptions_by_keyword(keyword, product_limit)
    
    return {
        "amazon_descriptions": amazon_descriptions,
        "walmart_descriptions": walmart_descriptions
    }

def search_products_from_both_platforms(keyword: str, limit: int = 2):
    """Search for products from both Amazon and Walmart"""
    amazon_products = search_amazon_products(keyword, limit)
    walmart_products = search_walmart_products(keyword, limit)
    
    return {
        "amazon_products": amazon_products,
        "walmart_products": walmart_products
    }