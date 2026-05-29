from __future__ import annotations

from time import perf_counter

from cartflow.checkout import checkout_cart


def test_empty_cart_fails() -> None:
    result = checkout_cart([])

    assert result["success"] is False
    assert result["status"] == "结算失败"
    assert result["message"] == "购物车不能为空"
    assert result["final_amount"] == "0.00"
    assert result["items"] == []


def test_invalid_price_fails() -> None:
    result = checkout_cart([{"unit_price": 0, "quantity": 1, "stock": 1}])

    assert result["success"] is False
    assert result["message"] == "商品单价非法"
    assert result["items"][0]["subtotal"] is None


def test_negative_price_fails() -> None:
    result = checkout_cart([{"unit_price": -1, "quantity": 1, "stock": 1}])

    assert result["success"] is False
    assert result["message"] == "商品单价非法"


def test_invalid_quantity_fails() -> None:
    result = checkout_cart([{"unit_price": 10, "quantity": 0, "stock": 1}])

    assert result["success"] is False
    assert result["message"] == "购买数量非法"


def test_non_integer_quantity_fails() -> None:
    result = checkout_cart([{"unit_price": 10, "quantity": 1.5, "stock": 3}])

    assert result["success"] is False
    assert result["message"] == "购买数量非法"


def test_insufficient_stock_fails() -> None:
    result = checkout_cart([{"unit_price": 10, "quantity": 3, "stock": 2}])

    assert result["success"] is False
    assert result["message"] == "库存不足"


def test_single_item_below_threshold_charges_shipping() -> None:
    result = checkout_cart([{"unit_price": 99.99, "quantity": 1, "stock": 2}])

    assert result["success"] is True
    assert result["status"] == "结算成功"
    assert result["original_amount"] == "99.99"
    assert result["shipping_fee"] == "10.00"
    assert result["final_amount"] == "109.99"
    assert result["items"][0]["subtotal"] == "99.99"


def test_order_at_threshold_is_free_shipping() -> None:
    result = checkout_cart([{"unit_price": 100, "quantity": 2, "stock": 2}])

    assert result["success"] is True
    assert result["original_amount"] == "200.00"
    assert result["shipping_fee"] == "0.00"
    assert result["final_amount"] == "200.00"


def test_multiple_items_calculate_subtotals_and_total() -> None:
    result = checkout_cart(
        [
            {"unit_price": 50, "quantity": 2, "stock": 3},
            {"unit_price": 25.50, "quantity": 4, "stock": 4},
        ]
    )

    assert result["success"] is True
    assert [item["subtotal"] for item in result["items"]] == ["100.00", "102.00"]
    assert result["original_amount"] == "202.00"
    assert result["shipping_fee"] == "0.00"
    assert result["final_amount"] == "202.00"


def test_client_final_amount_is_ignored() -> None:
    result = checkout_cart(
        [{"unit_price": 100, "quantity": 1, "stock": 2, "final_amount": "0.01"}]
    )

    assert result["success"] is True
    assert result["original_amount"] == "100.00"
    assert result["shipping_fee"] == "10.00"
    assert result["final_amount"] == "110.00"


def test_same_input_returns_stable_result() -> None:
    items = [{"unit_price": "39.90", "quantity": "3", "stock": "9"}]

    assert checkout_cart(items) == checkout_cart(items)


def test_checkout_finishes_under_200ms() -> None:
    items = [{"unit_price": 1.23, "quantity": 1, "stock": 1} for _ in range(100)]

    started_at = perf_counter()
    result = checkout_cart(items)
    elapsed_ms = (perf_counter() - started_at) * 1000

    assert result["success"] is True
    assert elapsed_ms < 200

