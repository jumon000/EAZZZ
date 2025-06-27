import requests
import os
from dotenv import load_dotenv

load_dotenv()

class AmazonService:
    BASE_URL = "https://realtime-amazon-data.p.rapidapi.com"
    HEADERS = {
        "X-RapidAPI-Key": os.getenv("RAPIDAPI_KEY"),
        "X-RapidAPI-Host": "realtime-amazon-data.p.rapidapi.com"
    }

    @staticmethod
    def _search_products(keyword: str, count: int = 2) -> list:
        url = f"{AmazonService.BASE_URL}/product-search"
        params = {
            "keyword": keyword,
            "country": "us",
            "page": "1",
            "sort": "Featured"
        }
        try:
            response = requests.get(url, headers=AmazonService.HEADERS, params=params)
            response.raise_for_status()
            data = response.json()
            if data.get("status") != "success":
                raise ValueError("Amazon search failed.")
            return data.get("details", [])[:count]
        except Exception as e:
            print(f"Search error: {e}")
            return []

    @staticmethod
    def _get_product_details(asin: str) -> dict:
        url = f"{AmazonService.BASE_URL}/product-details"
        params = {"asin": asin, "country": "us"}
        try:
            response = requests.get(url, headers=AmazonService.HEADERS, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Detail fetch error for ASIN {asin}: {e}")
            return {}

    @staticmethod
    def _get_product_reviews(asin: str) -> list:
        url = f"{AmazonService.BASE_URL}/product-reviews"
        params = {"asin": asin, "country": "us"}

        try:
            response = requests.get(url, headers=AmazonService.HEADERS, params=params)
            response.raise_for_status()
            data = response.json()

            reviews = data.get("reviews", [])
            simplified_reviews = []

            for r in reviews[:3]:
                simplified_reviews.append({
                    "title": r.get("title"),
                    "rating": r.get("rating"),
                    "review": r.get("review"),
                    "author": r.get("author"),
                    "date": r.get("date")
                })

            return simplified_reviews

        except Exception as e:
            print(f"Review fetch error for ASIN {asin}: {e}")
            return []



    @classmethod
    
    def get_top_products(cls, keyword: str, limit: int = 2) -> list:
        results = []
        top_items = cls._search_products(keyword, count=limit)

        for item in top_items:
            asin = item.get("asin")
            if not asin:
                continue

            product_details = cls._get_product_details(asin)
            if product_details.get("status") != "success":
                continue

            result = {
                "title": product_details.get("title"),
                "price": product_details.get("price"),
                "original_price": product_details.get("originalPrice"),
                "discount_percentage": product_details.get("discountPercentage"),
                "rating": product_details.get("rating"),
                "total_reviews": product_details.get("ratingNumber"),
                "description": " ".join(product_details.get("aboutThisItem", [])),
                "product_url": f"https://www.amazon.com/dp/{asin}",
                "image": product_details.get("images", [None])[0],  
                "asin": asin
            }

            results.append(result)

        return results
            
    
    @classmethod
    def get_filtered_products(cls, keyword: str, filters: dict, limit: int = 5) -> list:
        results = []
        raw_items = cls._search_products(keyword, count=30)

        def passes_filters(product: dict) -> bool:
            for field, condition in filters.items():
                value = product.get(field)

                if value is None:
                    return False

                if isinstance(condition, str):
                    if condition.startswith(">="):
                        try: return float(value) >= float(condition[2:])
                        except: return False
                    elif condition.startswith("<="):
                        try: return float(value) <= float(condition[2:])
                        except: return False
                    elif condition.startswith(">"):
                        try: return float(value) > float(condition[1:])
                        except: return False
                    elif condition.startswith("<"):
                        try: return float(value) < float(condition[1:])
                        except: return False
                    elif condition.startswith("=="):
                        return str(value).lower() == condition[2:].strip().lower()
                    elif condition.startswith("contains "):
                        return condition[9:].strip().lower() in str(value).lower()
                    else:
                        return str(value).lower() == condition.lower()

                if isinstance(condition, (int, float)):
                    try:
                        return float(value) == float(condition)
                    except:
                        return False

            return True

        for item in raw_items:
            try:
                asin = item.get("asin")
                if not asin:
                    continue

                item_lower = {k.lower(): v for k, v in item.items()}

                if passes_filters(item_lower):
                    details = cls._get_product_details(asin)
                    reviews = cls._get_product_reviews(asin)

                    if details.get("status") == "success":
                        results.append({
                            "asin": asin,
                            "title": item.get("ProductTitle"),
                            "price": item.get("price"),
                            "image": item.get("productImage"),
                            "url": item.get("productUrl"),
                            "details": details,
                            "reviews": reviews
                        })

                if len(results) == limit:
                    break
            except Exception as e:
                print(f"[Flexible Filter Error] {e}")
                continue

        return results
