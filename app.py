from flask import Flask, request, jsonify
import hashlib
import hmac
import time
import requests
import json
import os

app = Flask(__name__)

APP_KEY = os.environ.get("ALIEXPRESS_APP_KEY")
APP_SECRET = os.environ.get("ALIEXPRESS_APP_SECRET")
TRACKING_ID = os.environ.get("ALIEXPRESS_TRACKING_ID", "default")

def generate_sign(params, secret):
    """Generate HMAC-MD5 signature for AliExpress API"""
    sorted_params = sorted(params.items())
    sign_string = secret
    for key, value in sorted_params:
        sign_string += key + str(value)
    sign_string += secret
    return hashlib.md5(sign_string.encode("utf-8")).hexdigest().upper()

@app.route("/product", methods=["GET"])
def get_product():
    product_id = request.args.get("product_id")
    if not product_id:
        return jsonify({"error": "product_id is required"}), 400

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    params = {
        "app_key": APP_KEY,
        "method": "aliexpress.affiliate.productdetail.get",
        "sign_method": "md5",
        "timestamp": timestamp,
        "format": "json",
        "v": "2.0",
        "product_ids": product_id,
        "target_currency": "EUR",
        "target_language": "ES",
        "tracking_id": TRACKING_ID,
        "fields": "product_id,product_title,target_sale_price,target_original_price,evaluate_rate,lastest_volume,product_main_image_url,product_detail_url,ship_to_days,relevant_market_commission_rate"
    }

    params["sign"] = generate_sign(params, APP_SECRET)

    try:
        response = requests.post(
            "https://api-sg.aliexpress.com/sync",
            data=params,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        data = response.json()

        result = data.get("aliexpress_affiliate_productdetail_get_response", {}).get("result", {})
        products = result.get("products", {}).get("product", [])

        if not products:
            return jsonify({"error": "Product not found"}), 404

        product = products[0]

        # Generate affiliate link
        affiliate_params = {
            "app_key": APP_KEY,
            "method": "aliexpress.affiliate.link.generate",
            "sign_method": "md5",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "format": "json",
            "v": "2.0",
            "promotion_link_type": "0",
            "source_values": product.get("product_detail_url", ""),
            "tracking_id": TRACKING_ID
        }
        affiliate_params["sign"] = generate_sign(affiliate_params, APP_SECRET)

        affiliate_response = requests.post(
            "https://api-sg.aliexpress.com/sync",
            data=affiliate_params,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        affiliate_data = affiliate_response.json()
        affiliate_links = affiliate_data.get("aliexpress_affiliate_link_generate_response", {}).get("result", {}).get("promotion_links", {}).get("promotion_link", [])
        affiliate_link = affiliate_links[0].get("promotion_link", "") if affiliate_links else ""

        price = float(product.get("target_sale_price", "0").replace("US $", "").replace("€", "").strip())
        free_shipping = "Yes" if product.get("ship_to_days") == "0" else "No"

        return jsonify({
            "product_id": product.get("product_id"),
            "product_name": product.get("product_title"),
            "price_eur": round(price, 2),
            "free_shipping": free_shipping,
            "rating": product.get("evaluate_rate", "").replace("%", ""),
            "orders": product.get("lastest_volume"),
            "image_url": product.get("product_main_image_url"),
            "aliexpress_link": product.get("product_detail_url"),
            "affiliate_link": affiliate_link
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
