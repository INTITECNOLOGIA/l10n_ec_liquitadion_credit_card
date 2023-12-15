from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    tax_id_ret_liquidation = fields.Many2one('account.tax', string='Renta')
    tax_id_vat_liquidation = fields.Many2one('account.tax', string='IVA')
