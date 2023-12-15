from odoo import models, api, fields, tools
import odoo.addons.decimal_precision as dp
from odoo.tools.translate import _


class StockConfig(models.TransientModel):
    _inherit = 'res.config.settings'

    tax_id_ret_liquidation = fields.Many2one('account.tax', string='Renta',
                                             related="company_id.tax_id_ret_liquidation",
                                             readonly=False)
    tax_id_vat_liquidation = fields.Many2one('account.tax', string='IVA',
                                             related="company_id.tax_id_vat_liquidation",
                                             readonly=False)
