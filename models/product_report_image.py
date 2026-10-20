import base64
import io
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _dk_report_img(self):
        """Foto del producto (256 px) lista para los PDF. El generador de PDF de Odoo (wkhtmltopdf) NO dibuja
        fotos WebP y deja un cuadrito vacío; aquí se pasan a JPEG. JPEG y PNG se entregan tal cual."""
        self.ensure_one()
        raw = self.image_256
        if not raw:
            return False
        data = base64.b64decode(raw)
        if data[:3] == b'\xff\xd8\xff':
            return 'data:image/jpeg;base64,%s' % raw.decode()
        if data[:8] == b'\x89PNG\r\n\x1a\n':
            return 'data:image/png;base64,%s' % raw.decode()
        try:
            from PIL import Image
            image = Image.open(io.BytesIO(data))
            if image.mode in ('RGBA', 'LA', 'P'):
                image = image.convert('RGBA')
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[-1])
                image = background
            else:
                image = image.convert('RGB')
            out = io.BytesIO()
            image.save(out, format='JPEG', quality=90)
            return 'data:image/jpeg;base64,%s' % base64.b64encode(out.getvalue()).decode()
        except Exception as error:
            # Sin poder convertir: se entrega la foto original (como antes de esta función), nunca una fila vacía.
            _logger.warning("PDF: no se pudo convertir la foto de %s (%s): %s", self.display_name, data[:12], error)
            mime = 'webp' if data[:4] == b'RIFF' else 'png'
            return 'data:image/%s;base64,%s' % (mime, raw.decode())
