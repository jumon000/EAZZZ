from autogen import register_function,ConversableAgent

from agents.functions import (
    search_amazon_products, filter_amazon_products,
    search_walmart_products, filter_walmart_products,
    amazon_product_details,amazon_product_reviews,walmart_product_description,walmart_product_reviews, WalmartService
)

from autogen import register_function

planner = ConversableAgent(name="planner")
executor = ConversableAgent(name="executor")


ALL_TOOLS = [
    register_function(
        search_amazon_products,
        caller=planner,
        executor=executor,
        description="Search top-k Amazon products by keyword."
    ),
    register_function(
        filter_amazon_products,
        caller=planner,
        executor=executor,
        description="Filter Amazon products by conditions like price, rating, etc."
    ),
    register_function(
        amazon_product_details,
        caller=planner,
        executor=executor,
        description="Retrieve Amazon product details using ASIN."
    ),
    register_function(
        amazon_product_reviews,
        caller=planner,
        executor=executor,
        description="Retrieve Amazon product reviews using ASIN."
    ),
    register_function(
        search_walmart_products,
        caller=planner,
        executor=executor,
        description="Search top-k Walmart products by keyword."
    ),
    register_function(
        filter_walmart_products,
        caller=planner,
        executor=executor,
        description="Filter Walmart products by conditions like price, brand, rating, etc."
    ),
    register_function(
        walmart_product_description,
        caller=planner,
        executor=executor,
        description="Retrieve Walmart product description using usItemId."
    ),
    register_function(
        walmart_product_reviews,
        caller=planner,
        executor=executor,
        description="Retrieve Walmart product reviews using usItemId."
    )
]