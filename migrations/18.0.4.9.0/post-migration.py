"""Estados del pedido (etapa 2): los pedidos que YA existían quedan como acordó Andrés (2026-10-14):
los publicados y pagados -> "Entregado y cobrado"; el resto de los publicados -> "Entregado".
Borradores y cancelados se quedan "En bodega" (valor por defecto). Solo corre al actualizar desde una
versión anterior; en una instalación nueva no hay nada que migrar."""


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        UPDATE account_move
           SET custom_delivery_state = 'entregado'
         WHERE move_type = 'out_invoice' AND state = 'posted'
    """)
    cr.execute("""
        UPDATE account_move
           SET custom_pedido_state = CASE
                 WHEN custom_delivery_state = 'entregado' AND payment_state IN ('paid', 'in_payment')
                 THEN 'cobrado' ELSE custom_delivery_state END
         WHERE move_type = 'out_invoice'
    """)
