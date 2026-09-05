{
    'name': 'Stock Picking - Botones Orden de Venta y Facturas',
    'version': '18.0.2.0.0',
    'summary': 'Smart buttons, imágenes redimensionadas y mejoras visuales en traslados, facturas, ventas y productos',
    'author': 'AutomatePTY',
    'depends': ['stock', 'sale_stock', 'account', 'sale', 'product', 'purchase', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/stock_picking_views.xml',
        'views/account_move_views.xml',
        'views/sale_order_views.xml',
        'views/sale_order_dianke_export.xml',
        'views/product_views.xml',
        'views/purchase_order_views.xml',
        'views/report_invoice_inherit.xml',
        'views/report_deliveryslip_inherit.xml',
        'views/report_saleorder_inherit.xml',
        'views/product_kanban_search_inherit.xml',
        'views/purchase_bulk_email_wizard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'stock_picking_sale_buttons/static/src/css/wrap_columns.css',
            'stock_picking_sale_buttons/static/src/js/picking_description.js',
        ],
        'web.assets_web': [
            'stock_picking_sale_buttons/static/src/css/wrap_columns.css',
        ],
    },
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
