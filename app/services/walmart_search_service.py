import os
import requests
from dotenv import load_dotenv

load_dotenv()

class WalmartService:
    BASE_URL = "https://walmart2.p.rapidapi.com"
    HEADERS = {
        "X-RapidAPI-Key": os.getenv("RAPIDAPI_KEY"),
        "X-RapidAPI-Host": "walmart2.p.rapidapi.com"
    }

    @staticmethod
    def _search_products(keyword: str, count: int = 2) -> list:
        url = f"{WalmartService.BASE_URL}/searchV2"
        params = {"query": keyword}
        try:
            response = requests.get(url, headers=WalmartService.HEADERS, params=params)
            response.raise_for_status()
            return response.json().get("itemsV2", [])[:count]
        except Exception as e:
            print(f"[Search Error] Walmart: {e}")
            return []

    @staticmethod
    def _get_product_description(us_item_id: str) -> str:
        url = f"{WalmartService.BASE_URL}/productDescription"
        params = {"usItemId": us_item_id}
        try:
            response = requests.get(url, headers=WalmartService.HEADERS, params=params)
            response.raise_for_status()
            return response.json().get("shortDescription", "")
        except Exception as e:
            print(f"[Description Error] Walmart ID {us_item_id}: {e}")
            return ""

    @staticmethod
    def _get_product_reviews(us_item_id: str, page: int = 0) -> list:
        url = f"{WalmartService.BASE_URL}/productReviews"
        params = {
            "usItemId": us_item_id,
            "page": page,
            "sort": "RELEVANT"
        }
        try:
            response = requests.get(url, headers=WalmartService.HEADERS, params=params)
            response.raise_for_status()
            data = response.json()
            raw_reviews = data.get("reviews", [])[:3]

            formatted_reviews = []
            for r in raw_reviews:
                formatted_reviews.append({
                    "review": r.get("reviewText"),
                    "authorId": r.get("authorId"),
                    "rating": r.get("rating"),
                    "positiveFeedback": r.get("positiveFeedback"),
                    "negativeFeedback": r.get("negativeFeedback"),
                    "recommended": r.get("recommended"),
                    "submitted_on": r.get("reviewSubmissionTime"),
                    "externalSource": r.get("externalSource"),
                    "reviewId": r.get("reviewId")
                })

            return formatted_reviews

        except Exception as e:
            print(f"[Reviews Error] Walmart ID {us_item_id}: {e}")
            return []

    # NEW: Keyword-based reviews function
    @classmethod
    def get_product_reviews_by_keyword(cls, keyword: str, product_limit: int = 2) -> list:
        """
        Get reviews for products based on keyword search.
        Returns reviews for top products matching the keyword.
        """
        results = []
        products = cls._search_products(keyword, count=product_limit)
        
        for product in products:
            us_item_id = product.get("usItemId")
            if not us_item_id:
                continue
                
            reviews = cls._get_product_reviews(us_item_id)
            if reviews:
                results.append({
                    "product_name": product.get("name", "Unknown Product"),
                    "usItemId": us_item_id,
                    "reviews": reviews
                })
        
        return results

    # NEW: Keyword-based product descriptions function
    @classmethod
    def get_product_descriptions_by_keyword(cls, keyword: str, product_limit: int = 2) -> list:
        """
        Get detailed descriptions for products based on keyword search.
        """
        results = []
        products = cls._search_products(keyword, count=product_limit)
        
        for product in products:
            us_item_id = product.get("usItemId")
            if not us_item_id:
                continue
                
            description = cls._get_product_description(us_item_id)
            results.append({
                "product_name": product.get("name"),
                "usItemId": us_item_id,
                "description": description,
                "price": product.get("priceInfo", {}).get("currentPrice", {}).get("priceDisplay"),
                "rating": product.get("averageRating"),
                "image": product.get("imageInfo", {}).get("thumbnailUrl"),
                "product_url": f"https://www.walmart.com/ip/{us_item_id}"
            })
        
        return results

    @classmethod
    def get_top_products(cls, keyword: str, count: int = 2) -> list:
        results = []
        items = cls._search_products(keyword, count=count)

        for item in items:
            us_item_id = item.get("usItemId")
            if not us_item_id:
                continue

            description = cls._get_product_description(us_item_id)
            reviews = cls._get_product_reviews(us_item_id)

            results.append({
                "name": item.get("name"),
                "price": item.get("priceInfo", {}).get("currentPrice", {}).get("priceDisplay"),
                "image": item.get("imageInfo", {}).get("thumbnailUrl"),
                "product_url": f"https://www.walmart.com/ip/{us_item_id}",
                "description": description,
                "reviews": reviews,
                "usItemId": us_item_id
            })
        return results
    
    @staticmethod
    def _matches_filters(item: dict, filters: dict) -> bool:
        name = (item.get("name") or "").lower()
        desc = (item.get("shortDescription") or "").lower()
        for key, value in filters.items():
            key = key.lower()
            val = str(value).lower()

            if key in ["name", "title", "producttitle"] and val not in name:
                return False
            if key == "description" and val not in desc:
                return False
            if key == "price":
                try:
                    item_price = float(item.get("priceInfo", {}).get("currentPrice", {}).get("price", 0))
                    target = float(val)
                    if item_price > target:
                        return False
                except:
                    return False
            if key == "minprice":
                try:
                    item_price = float(item.get("priceInfo", {}).get("currentPrice", {}).get("price", 0))
                    target = float(val)
                    if item_price < target:
                        return False
                except:
                    return False
            if key == "rating":
                try:
                    item_rating = float(item.get("averageRating", 0))
                    if item_rating < float(val):
                        return False
                except:
                    return False
            if key not in ["name", "title", "price", "minprice", "rating", "description"]:
                if val not in name and val not in desc:
                    return False
        return True

    @classmethod
    def get_filtered_products(cls, keyword: str, filters: dict = {}) -> list:
        all_items = cls._search_products(keyword, count=20)
        matched = []
        for item in all_items:
            if len(matched) == 5:
                break
            if cls._matches_filters(item, filters):
                us_item_id = item.get("usItemId")
                desc = cls._get_product_description(us_item_id)
                reviews = cls._get_product_reviews(us_item_id)

                matched.append({
                    "usItemId": us_item_id,
                    "name": item.get("name"),
                    "price": item.get("priceInfo", {}).get("currentPrice", {}).get("priceDisplay"),
                    "rating": item.get("averageRating"),
                    "image": item.get("imageInfo", {}).get("thumbnailUrl"),
                    "description": desc,
                    "reviews": reviews,
                    "product_url": f"https://www.walmart.com/ip/{us_item_id}" if us_item_id else None
                })
        return matched
