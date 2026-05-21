from flask import Flask, request, jsonify
import hashlib
import time
import requests
import os
import urllib.request

app = Flask(__name__)

APP_KEY = os.environ.get("ALIEXPRESS_APP_KEY")
APP_SECRET = os.environ.get("ALIEXPRESS_APP_SECRET")
TRACKING_ID = os.environ.get("ALIEXPRESS_TRACKING_ID", "default")


def generate_sign(params, secret):
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
        "fields": "product_id,product_title,target_sale_price,evaluate_rate,lastest_volume,product_main_image_url,product_detail_url,ship_to_days,promotion_link"
    }

    params["sign"] = generate_sign(params, APP_SECRET)

    try:
        response = requests.post(
            "https://api-sg.aliexpress.com/sync",
            data=params,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        data = response.json()

        resp_result = data.get("aliexpress_affiliate_productdetail_get_response", {}).get("resp_result", {})
        result = resp_result.get("result", {})
        products = result.get("products", {}).get("product", [])

        if not products:
            return jsonify({"error": "Product not found", "raw_response": data}), 404

        product = products[0]

        price_raw = product.get("target_sale_price", "0")
        try:
            price = float(str(price_raw).replace("US $", "").replace("EUR", "").replace("€", "").strip())
        except Exception:
            price = 0.0

        free_shipping = "Yes" if str(product.get("ship_to_days", "1")) == "0" else "No"

        return jsonify({
            "product_id": product.get("product_id"),
            "product_name": product.get("product_title"),
            "price_eur": round(price, 2),
            "free_shipping": free_shipping,
            "rating": str(product.get("evaluate_rate", "")).replace("%", ""),
            "orders": product.get("lastest_volume"),
            "image_url": product.get("product_main_image_url"),
            "aliexpress_link": product.get("product_detail_url"),
            "affiliate_link": product.get("promotion_link", "")
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    try:
        external_ip = urllib.request.urlopen("https://api.ipify.org").read().decode("utf8")
    except Exception:
        external_ip = "unknown"
    return jsonify({"status": "ok", "server_ip": external_ip})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
