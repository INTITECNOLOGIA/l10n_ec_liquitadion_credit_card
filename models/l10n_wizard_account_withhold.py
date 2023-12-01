from odoo import fields, models, api


class L10nEcWizardAccountWithhold(models.TransientModel):
    _inherit = 'l10n_ec.wizard.account.withhold'

    @api.model
    def default_get(self, fields_list):
        result = super().default_get(fields_list)
        # if 'related_invoice_ids' in fields_list:
        #     if self._context.get('active_model') != 'account.move' or not self._context.get('active_ids'):
        #         raise UserError(_('Withholds must be created from an invoice.'))
        #     invoices = self.env['account.move'].browse(self._context['active_ids'])
        #     self._validate_invoices_data_on_open(invoices)
        #     result['related_invoice_ids'] = [Command.set(invoices.ids)]
        return result
