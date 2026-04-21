<?php
/**
 * Snippet de WooCommerce para descuentos por cantidad.
 *
 * COMO USARLO
 * 1. Pega este archivo en functions.php del child theme
 *    o conviertelo en un mini plugin/snippet.
 * 2. Edita la funcion wc_bot_discount_tiers() si quieres cambiar
 *    los porcentajes o las cantidades.
 * 3. Guarda y prueba el carrito.
 *
 * REGLA ACTUAL
 * - 2 unidades de la misma referencia = 5% OFF
 * - 3 o mas unidades de la misma referencia = 10% OFF
 *
 * IMPORTANTE
 * - El descuento se calcula sobre el precio actual del producto,
 *   o sea el precio rebajado vigente si el producto ya tiene oferta.
 * - La regla aplica por referencia dentro del carrito.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

if ( ! function_exists( 'wc_bot_discount_tiers' ) ) {
	function wc_bot_discount_tiers() {
		return array(
			array(
				'min_qty'      => 2,
				'max_qty'      => 2,
				'discount_pct' => 5,
			),
			array(
				'min_qty'      => 3,
				'max_qty'      => null,
				'discount_pct' => 10,
			),
		);
	}
}

if ( ! function_exists( 'wc_bot_discount_percent_for_quantity' ) ) {
	function wc_bot_discount_percent_for_quantity( $quantity ) {
		$quantity = absint( $quantity );
		$percent  = 0;

		foreach ( wc_bot_discount_tiers() as $tier ) {
			$min_qty = isset( $tier['min_qty'] ) ? absint( $tier['min_qty'] ) : 0;
			$max_qty = array_key_exists( 'max_qty', $tier ) && null !== $tier['max_qty'] ? absint( $tier['max_qty'] ) : null;
			$value   = isset( $tier['discount_pct'] ) ? (float) $tier['discount_pct'] : 0;

			if ( $quantity >= $min_qty && ( null === $max_qty || $quantity <= $max_qty ) ) {
				$percent = $value;
			}
		}

		return $percent;
	}
}

if ( ! function_exists( 'wc_bot_qty_discount_rules' ) ) {
	function wc_bot_qty_discount_rules( $cart ) {
		if ( is_admin() && ! defined( 'DOING_AJAX' ) ) {
			return;
		}

		if ( ! $cart || ! is_a( $cart, 'WC_Cart' ) ) {
			return;
		}

		foreach ( $cart->get_cart() as $cart_item_key => $cart_item ) {
			if ( empty( $cart_item['data'] ) || ! is_a( $cart_item['data'], 'WC_Product' ) ) {
				continue;
			}

			$product  = $cart_item['data'];
			$quantity = isset( $cart_item['quantity'] ) ? absint( $cart_item['quantity'] ) : 0;

			/**
			 * Guardamos el precio base actual del producto solo la primera vez.
			 * Ese precio base normalmente ya incluye el precio rebajado si existe.
			 */
			if ( ! isset( $cart->cart_contents[ $cart_item_key ]['wc_bot_base_price'] ) ) {
				$cart->cart_contents[ $cart_item_key ]['wc_bot_base_price'] = (float) $product->get_price();
			}

			$base_price = (float) $cart->cart_contents[ $cart_item_key ]['wc_bot_base_price'];
			$discount   = wc_bot_discount_percent_for_quantity( $quantity );

			if ( $discount > 0 ) {
				$new_price = $base_price * ( 1 - ( $discount / 100 ) );
				$product->set_price( $new_price );
			} else {
				$product->set_price( $base_price );
			}
		}
	}
}

add_action( 'woocommerce_before_calculate_totals', 'wc_bot_qty_discount_rules', 20, 1 );
