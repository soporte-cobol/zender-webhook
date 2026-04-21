<?php
/**
 * Snippet de WooCommerce para enviar notas al cliente al bot de WhatsApp.
 *
 * COMO USARLO
 * 1. Pega este archivo en functions.php del child theme
 *    o conviertelo en un mini plugin/snippet.
 * 2. Reemplaza WC_BOT_WEBHOOK_URL por la URL real de tu bot.
 * 3. Reemplaza WC_BOT_WEBHOOK_SECRET por el mismo secret que pusiste
 *    en el .env del bot como WC_WEBHOOK_SECRET.
 * 4. Guarda y prueba agregando una nota para el cliente en un pedido.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

if ( ! defined( 'WC_BOT_WEBHOOK_URL' ) ) {
	define( 'WC_BOT_WEBHOOK_URL', 'https://wa.onlinecomprafacil.com/zender-webhook/woocommerce-webhook' );
}

if ( ! defined( 'WC_BOT_WEBHOOK_SECRET' ) ) {
	define( 'WC_BOT_WEBHOOK_SECRET', 'pon_aqui_tu_wc_webhook_secret' );
}

if ( ! function_exists( 'wc_bot_normalize_phone' ) ) {
	function wc_bot_normalize_phone( $phone ) {
		$phone = trim( (string) $phone );
		$phone = preg_replace( '/(?!^\+)[^\d]/', '', $phone );
		return $phone;
	}
}

add_action(
	'woocommerce_new_customer_note',
	function ( $data ) {
		if ( empty( $data ) || ! is_array( $data ) ) {
			return;
		}

		$order_id = isset( $data['order_id'] ) ? absint( $data['order_id'] ) : 0;
		$note     = isset( $data['customer_note'] ) ? wp_strip_all_tags( (string) $data['customer_note'] ) : '';

		if ( ! $order_id || '' === $note ) {
			return;
		}

		$order = wc_get_order( $order_id );
		if ( ! $order ) {
			return;
		}

		$phone = wc_bot_normalize_phone( $order->get_billing_phone() );
		if ( '' === $phone ) {
			return;
		}

		$payload = array(
			'secret'       => WC_BOT_WEBHOOK_SECRET,
			'type'         => 'customer_note',
			'topic'        => 'customer_note',
			'order_id'     => (string) $order_id,
			'order_number' => (string) $order->get_order_number(),
			'phone'        => $phone,
			'note'         => $note,
			'note_id'      => isset( $data['comment_id'] ) ? (string) $data['comment_id'] : sha1( $order_id . '|' . $note ),
		);

		$response = wp_remote_post(
			WC_BOT_WEBHOOK_URL,
			array(
				'timeout' => 15,
				'headers' => array(
					'Content-Type' => 'application/json',
				),
				'body'    => wp_json_encode( $payload ),
			)
		);

		if ( is_wp_error( $response ) && function_exists( 'wc_get_logger' ) ) {
			wc_get_logger()->warning(
				'No se pudo enviar la nota del cliente al bot: ' . $response->get_error_message(),
				array( 'source' => 'wc-bot-customer-note' )
			);
		}
	},
	10,
	1
);
