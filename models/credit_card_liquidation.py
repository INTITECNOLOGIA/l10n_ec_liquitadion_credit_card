import logging
import re

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)

_STATES_DOC = {"draft": [("readonly", False)]}


class AccountCreditCardLiquidation(models.Model):

    _name = "account.credit.card.liquidation"
    _description = "account.credit.card.liquidation"

    number = fields.Char(
        string="Liquidation Number", readonly=True, default="/", required=True
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
        readonly=True,
        states=_STATES_DOC,
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Supplier",
        required=True,
        readonly=True,
        states=_STATES_DOC,
    )
    invoice_id = fields.Many2one(
        comodel_name="account.move", string="Invoice", readonly=True, states=_STATES_DOC
    )
    withhold_id = fields.Many2one(
        comodel_name="account.move", string="Withhold", readonly=True
    )
    account_id = fields.Many2one(
        comodel_name="account.account",
        string="Origin Account(CC)",
        required=True,
        readonly=True,
        states=_STATES_DOC,
    )
    journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Dest. Journal",
        required=True,
        readonly=True,
        states=_STATES_DOC,
    )
    move_id = fields.Many2one(
        comodel_name="account.move", string="Account Journal", readonly=True
    )
    move_ids = fields.One2many(
        related="move_id.line_ids",
        string="Journal Entries",
    )
    issue_date = fields.Date(
        string="Withhold Date",
        readonly=True,
        copy=False,
        states=_STATES_DOC,
    )

    journal_ret_id = fields.Many2one('account.journal', string="Diario", domain=[("l10n_ec_withhold_type", "=", "out_withhold")])

    date_account = fields.Date(
        string="Accounting Date",
        readonly=True,
        required=True,
        index=True,
        copy=False,
        states=_STATES_DOC,
    )
    document_number = fields.Char(
        string="Withhold Number", size=17, readonly=True, states=_STATES_DOC
    )
    document_type = fields.Selection(
        selection=[
            ("electronic", "Electronic"),
            ("pre_printed", "Pre Printed"),
            ("auto_printer", "Auto Printer"),
        ],
        string="Emission Type",
        readonly=True,
        required=False,
        states=_STATES_DOC,
        default="electronic",
    )

    electronic_authorization = fields.Char(
        string="Electronic Authorization",
        index=True,
        size=49,
        required=False,
        readonly=True,
        states=_STATES_DOC,
    )
    line_ids = fields.One2many(
        comodel_name="account.credit.card.liquidation.line",
        inverse_name="liquidation_id",
        string="Details",
        required=False,
        readonly=True,
        states=_STATES_DOC,
    )
    additional_lines_ids = fields.Many2many(
        comodel_name="account.credit.card.liquidation.line",
        relation="additional_line_liquidation_line_rel",
        string="Additional Details",
        readonly=True,
        states=_STATES_DOC,
    )
    line_invoice_ids = fields.One2many(
        comodel_name="account.credit.card.liquidation.invoice.detail",
        inverse_name="liquidation_id",
        string="Invoice to Reconcile",
        readonly=True,
        states=_STATES_DOC,
    )
    percentage_ret_iva = fields.Float(
        string="IVA Withhold Percent", readonly=True, states=_STATES_DOC, default=30
    )
    percentage_ret_rent = fields.Float(
        string="Rent Withhold Percent", readonly=True, states=_STATES_DOC, default=2
    )
    commission_wo_invoice = fields.Float(
        string="Commission without Invoice", readonly=True, states=_STATES_DOC
    )
    account_commission_id = fields.Many2one(
        "account.account",
        string="Account for commission without Invoice",
        readonly=True,
        states=_STATES_DOC,
    )
    account_withhold_rent_id = fields.Many2one(
        comodel_name="account.account",
        string="Rent Withhold Account",
        readonly=True,
        states=_STATES_DOC,
    )
    account_withhold_iva_id = fields.Many2one(
        comodel_name="account.account",
        string="IVA Withhold Account",
        readonly=True,
        states=_STATES_DOC,
    )
    account_commission_expense_id = fields.Many2one(
        comodel_name="account.account",
        string="Cuenta de Gasto de Comisión",
        readonly=True,
        states=_STATES_DOC,
    )
    no_invoice = fields.Boolean(
        string="No Reconcile Invoice?", readonly=True, states=_STATES_DOC
    )
    no_withhold = fields.Boolean(
        string="No Input Withhold?", readonly=True, states=_STATES_DOC
    )
    split_lines_by_recap = fields.Boolean(
        string="Split Journal by RECAP?", readonly=True, states=_STATES_DOC
    )
    account_analytic_id = fields.Many2one(
        comodel_name="account.analytic.account",
        string="Analytic Account",
        readonly=True,
        states=_STATES_DOC,
    )
    # analytic_tag_ids = fields.Many2many(
    #     comodel_name="account.analytic.tag",
    #     string="Analytic Tags",
    #     readonly=True,
    #     states=_STATES_DOC,
    # )

    @api.depends(
        "line_ids",
        "line_ids.base",
        "line_ids.commission",
        "line_ids.commission_iva",
        "line_ids.iva_withhold",
        "line_ids.rent_base",
        "line_ids.rent_withhold",
        "line_ids.net_value",
    )
    def _compute_liquidation_values(self):
        for liquidation in self:
            base = sum(
                liquidation.line_ids.filtered(lambda x: not x.skip_payment).mapped(
                    "base"
                )
            )
            base += sum(liquidation.additional_lines_ids.mapped("base"))
            commission = sum(
                liquidation.line_ids.filtered(lambda x: not x.skip_payment).mapped(
                    "commission"
                )
            )
            commission += sum(liquidation.additional_lines_ids.mapped("commission"))
            commission_iva = sum(
                liquidation.line_ids.filtered(lambda x: not x.skip_payment).mapped(
                    "commission_iva"
                )
            )
            commission_iva += sum(
                liquidation.additional_lines_ids.mapped("commission_iva")
            )
            iva_withhold = sum(
                liquidation.line_ids.filtered(lambda x: not x.skip_payment).mapped(
                    "iva_withhold"
                )
            )
            iva_withhold += sum(liquidation.additional_lines_ids.mapped("iva_withhold"))
            rent_base = sum(
                liquidation.line_ids.filtered(lambda x: not x.skip_payment).mapped(
                    "rent_base"
                )
            )
            rent_base += sum(liquidation.additional_lines_ids.mapped("rent_base"))
            rent_withhold = sum(
                liquidation.line_ids.filtered(lambda x: not x.skip_payment).mapped(
                    "rent_withhold"
                )
            )
            rent_withhold += sum(
                liquidation.additional_lines_ids.mapped("rent_withhold")
            )
            net_value = (
                sum(
                    liquidation.line_ids.filtered(lambda x: not x.skip_payment).mapped(
                        "net_value"
                    )
                )
                - liquidation.commission_wo_invoice
            )
            net_value += sum(liquidation.additional_lines_ids.mapped("net_value"))
            liquidation.base = base
            liquidation.commission = commission
            liquidation.commission_iva = commission_iva
            liquidation.iva_withhold = iva_withhold
            liquidation.rent_base = rent_base
            liquidation.rent_withhold = rent_withhold
            liquidation.net_value = net_value

    base = fields.Float(
        string="Base",
        digits="Account",
        store=True,
        compute="_compute_liquidation_values",
    )
    commission = fields.Float(
        string="Commission",
        digits="Account",
        store=True,
        compute="_compute_liquidation_values",
    )
    commission_iva = fields.Float(
        string="IVA Commission",
        digits="Account",
        store=True,
        compute="_compute_liquidation_values",
    )
    iva_withhold = fields.Float(
        string="IVA Withhold",
        digits="Account",
        store=True,
        compute="_compute_liquidation_values",
    )
    rent_base = fields.Float(
        string="Rent Base",
        digits="Account",
        store=True,
        compute="_compute_liquidation_values",
    )
    rent_withhold = fields.Float(
        string="Rent Withhold",
        digits="Account",
        store=True,
        compute="_compute_liquidation_values",
    )
    net_value = fields.Float(
        string="Net Value",
        digits="Account",
        store=True,
        compute="_compute_liquidation_values",
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("done", "Done"),
            ("cancel", "Cancel"),
        ],
        string="State",
        readonly=True,
        required=True,
        default="draft",
    )

    _rec_name = "number"

    @api.constrains(
        "document_number",
    )
    def check_retention_out(self):
        match_string = r"(\d{3})+\-(\d{3})+\-(\d{9})"
        for rec in self:
            if rec.document_number and not re.match(match_string, rec.document_number):
                raise ValidationError(
                    _(
                        "El número de retención es incorrecto, "
                        "este debe tener la forma 001-00X-000XXXXXX, X es un número"
                    )
                )

    @api.constrains(
        "electronic_authorization",
    )
    def check_electronic_authorization(self):
        match_string = r"(\d{37}$)|(\d{49}$)"
        for rec in self:
            if rec.document_type == "electronic" and rec.electronic_authorization:
                if len(rec.electronic_authorization) not in (37, 49):
                    raise ValidationError(
                        _(
                            "El número de autorización electrónica es incorrecto, "
                            "este debe tener exactamente 37 o 49 dígitos"
                        )
                    )
                if not re.match(match_string, rec.electronic_authorization):
                    raise ValidationError(
                        _(
                            "La autorización electronica debe tener solo números, "
                            "por favor verifique!"
                        )
                    )

    @api.onchange("no_invoice")
    def onchange_no_invoice(self):
        if self.no_invoice:
            self.commission_wo_invoice = 0.0
        else:
            self.split_lines_by_recap = False

    @api.onchange(
        "document_number",
        "issue_date",
        "document_type",
        "partner_id",
    )
    def onchange_retention_data(self):
        value = {}
        domain = {}
        warning = {}
        issue_date = (
            self.issue_date and self.issue_date or fields.Date.context_today(self)
        )
        document_number = self.document_number
        # Si es electronico no deberia validar fechas ni nada
        if (
            self.document_type
            and self.document_type == "electronic"
            or not self.partner_id
        ):
            return {"value": value, "domain": domain, "warning": warning}
        # Si se ha ingrasado los dos datos y estos han cambiado,
        # se debe verificar si siguen siendo validos
        if self.document_number:
            agency = None
            printer_point = None
            seq_number = None
            try:
                # Se verifica que no se haya ingresado un valor
                # del tipo 00X-00X-000000XXX
                split_number = self.document_number.split("-")
            except Exception as e:
                _logger.debug(
                    _("Error parsing number of document: %s : %s")
                    % (self.document_number, str(e))
                )
                # Se hace un entero para retirar los ceros
                try:
                    seq_number = int(self.document_number)
                except Exception as e:
                    _logger.debug(
                        _("Error parsing number of document: %s : %s")
                        % (self.document_number, str(e))
                    )

    def action_done(self):
        retention_model = self.env["account.move"]
        rline_model = self.env["account.move.line"]
        am_model = self.env["account.move"]
        invoice_model = self.env["account.move"]
        aml_model = self.env["account.move.line"]
        seq_model = self.env["ir.sequence"]
        for liquidation in self:
            if not liquidation.line_ids:
                raise UserError(_("Debe al menos ingresar una línea"))
            if (
                not liquidation.invoice_id
                and not liquidation.line_invoice_ids
                and not liquidation.no_invoice
            ):
                raise UserError(
                    _(
                        "Debe de seleccionar una unica forma "
                        "de conciliar facturas, de manera multiple "
                        "o una sola factura para asentar el documento"
                    )
                )
            if (
                liquidation.invoice_id
                and liquidation.line_invoice_ids
                and not liquidation.no_invoice
            ):
                raise UserError(
                    _(
                        "Debe de seleccionar una unica forma de conciliar facturas, "
                        "de manera multiple o una sola factura, "
                        "por favor revise no tener asignada las 2 formas a la ves"
                    )
                )
            if liquidation.split_lines_by_recap and not liquidation.no_invoice:
                raise UserError(_("You can't split journal items with comission value"))
            msg = []
            for iline in liquidation.line_invoice_ids:
                if iline.amount > iline.invoice_id.amount_residual:
                    msg.append(
                        "El monto %s supera al "
                        "monto residual de la factura %s que es %s"
                        % (
                            iline.amount,
                            iline.invoice_id.display_name,
                            iline.invoice_id.amount_residual,
                        )
                    )
            if msg:
                msg = "\n".join(msg)
                raise UserError(_("Restriccions: %s") % (msg))
            invoice_to_liquidate = {}
            multi_invoice = False
            if liquidation.invoice_id:
                invoice_to_liquidate[liquidation.invoice_id.id] = {
                    "amount_to_concile": liquidation.invoice_id.amount_residual,
                    "amls_to_concile": [],
                }
            for iline in liquidation.line_invoice_ids:
                multi_invoice = True
                invoice_to_liquidate[iline.invoice_id.id] = {
                    "amount_to_concile": iline.amount,
                    "amls_to_concile": [],
                }
            total_comission = (liquidation.commission_iva or 0.0) + (
                liquidation.commission + 0.0
            )
            if multi_invoice:
                total_to_concile = sum(
                    [v["amount_to_concile"] for v in invoice_to_liquidate.values()]
                )
                if (
                    float_compare(total_to_concile, total_comission, precision_digits=2)
                    != 0
                    and not liquidation.no_invoice
                ):
                    raise UserError(
                        _(
                            "El monto a conciliar de las facturas %s "
                            "no coincide con los valores de comisión e iva %s "
                        )
                        % (
                            total_to_concile,
                            (
                                (liquidation.commission_iva or 0.0)
                                + (liquidation.commission + 0.0)
                            ),
                        )
                    )
            # Se crea la retencion
            ret = retention_model.browse()
            if not liquidation.no_withhold:

                amount = float(liquidation.percentage_ret_rent) * -1
                group_tax = self.env['account.tax.group'].search([('l10n_ec_type', '=', 'withhold_income_sale')])
                tax_ret = self.env['account.tax'].search([('real_amount', '=', amount),
                                                      ('tax_group_id', 'in', group_tax.ids)], limit=1)

                retention = self.env['l10n_ec.wizard.account.withhold'].create({
                    'partner_id': liquidation.partner_id.id,
                    'date': liquidation.issue_date,
                   # 'related_invoice_ids': [(6, 0, [existing_moves.id])],
                    'journal_id': liquidation.journal_ret_id.id,
                    'document_number': liquidation.document_number,
                    "company_id": liquidation.company_id.id,
                })

                if liquidation.rent_base and liquidation.rent_withhold and liquidation.percentage_ret_rent:
                    line_vals = {
                       # 'invoice_id': existing_moves.id,
                        'tax_id': tax_ret.id,
                        'base': liquidation.rent_base,
                        'amount': liquidation.rent_withhold,
                        'wizard_id': retention.id,
                    }
                    retention.withhold_line_ids.create(line_vals)

                ret = retention.action_create_and_post_withhold()





            if not liquidation.no_invoice:
                # Se trata de conciliar la factura
                for invoice_id in invoice_to_liquidate.keys():
                    invoice = invoice_model.browse(invoice_id)
                    for line in invoice.line_ids:
                        if (
                            line.account_id.account_type
                            in ["asset_receivable", "liability_payable"]
                            and line.partner_id
                            and line.partner_id.id == invoice.partner_id.id
                        ):
                            invoice_to_liquidate[invoice_id]["amls_to_concile"].append(
                                line.id
                            )
            number_liquidation = liquidation.number
            if liquidation.number == "/":
                number_liquidation = seq_model.next_by_code("credit.card.liquidation")
            am = am_model.create(
                {
                    "name": "/",
                    "ref": "Liquidación TC %s" % (number_liquidation),
                    "journal_id": liquidation.journal_id.id,
                    "date": liquidation.date_account,
                }
            )
            if not liquidation.partner_id.property_account_payable_id:
                raise UserError(
                    _("Debe configurar la cuenta contable por pagar del proveedor %s")
                    % (liquidation.partner_id.name)
                )
            # Si se va a saldar una factura deberia solo tomar el parcial
            # Valor de base que se debe sacar de la cuenta contable
            base = 0.0
            name_recap = " Recaps " + " - ".join(
                str(e) for e in liquidation.line_ids.mapped("recap_id").mapped("name")
            )
            if liquidation.base:
                base = liquidation.base - (
                    liquidation.iva_withhold + liquidation.rent_withhold
                )
                if liquidation.no_withhold:
                    base = liquidation.base
                name = "Base de Liquidación TC %s" % (number_liquidation) + name_recap
                aml_model.with_context(check_move_validity=False).create(
                    liquidation._prepare_move_line_vals(
                        am,
                        liquidation.account_id,
                        name,
                        credit=base,
                        partner=liquidation.partner_id,
                    )
                )
            if liquidation.commission_wo_invoice > 0 and not liquidation.no_invoice:
                name = "Comisión sin Factura TC %s" % (number_liquidation) + name_recap
                aml_model.with_context(check_move_validity=False).create(
                    liquidation._prepare_move_line_vals(
                        am,
                        liquidation.account_commission_id,
                        name,
                        debit=liquidation.commission_wo_invoice,
                        partner=liquidation.partner_id,
                    )
                )
            if liquidation.commission or liquidation.commission_iva:
                for invoice_id in invoice_to_liquidate.keys():
                    amount_line = (liquidation.commission_iva or 0.0) + (
                        liquidation.commission + 0.0
                    )
                    if multi_invoice:
                        amount_line = invoice_to_liquidate[invoice_id].get(
                            "amount_to_concile", 0.0
                        )
                    name = (
                        "Comision Liquidación TC %s" % (number_liquidation) + name_recap
                    )
                    aml = aml_model.with_context(check_move_validity=False).create(
                        liquidation._prepare_move_line_vals(
                            am,
                            liquidation.partner_id.property_account_payable_id,
                            name,
                            debit=amount_line,
                            partner=liquidation.partner_id,
                        )
                    )
                    invoice_to_liquidate[invoice_id]["amls_to_concile"].append(aml.id)
            # crear apuntes agrupados o por cada recap
            # segun lo que el usuario haya seleccionado
            if liquidation.split_lines_by_recap:
                for line in liquidation.line_ids:
                    payment_account_id = liquidation.journal_id.default_debit_account_id
                    name = _("Valor Neto Liquidación TC: %s Recap: %s") % (
                        number_liquidation,
                        line.recap_id.name or "",
                    )
                    aml_model.with_context(check_move_validity=False).create(
                        liquidation._prepare_move_line_vals(
                            am,
                            payment_account_id,
                            name,
                            debit=line.net_value,
                            partner=liquidation.partner_id,
                        )
                    )

            elif liquidation.net_value:
                pmls = liquidation.journal_id.inbound_payment_method_line_ids
                default_payment_account = liquidation.company_id.account_journal_payment_debit_account_id

                payment_account_id = pmls.payment_account_id[:1] or default_payment_account

                name = (
                    _("Valor Neto Liquidación TC %s") % (number_liquidation)
                    + name_recap
                )
                aml_model.with_context(check_move_validity=False).create(
                    liquidation._prepare_move_line_vals(
                        am,
                        payment_account_id,
                        name,
                        debit=liquidation.net_value,
                        partner=liquidation.partner_id,
                    )
                )
            if liquidation.no_invoice and total_comission > 0:
                name = "Comisión TC %s" % (number_liquidation) + name_recap
                aml_model.with_context(check_move_validity=False).create(
                    liquidation._prepare_move_line_vals(
                        am,
                        liquidation.account_commission_expense_id,
                        name,
                        debit=total_comission,
                        partner=liquidation.partner_id,
                    )
                )
            if liquidation.no_withhold:
                if liquidation.rent_withhold > 0:
                    name = "Retencion I.R. TC %s" % (number_liquidation) + name_recap
                    aml_model.with_context(check_move_validity=False).create(
                        liquidation._prepare_move_line_vals(
                            am,
                            liquidation.account_withhold_rent_id,
                            name,
                            debit=liquidation.rent_withhold,
                            partner=liquidation.partner_id,
                        )
                    )
                if liquidation.iva_withhold > 0:
                    name = "Retención I.V.A. TC %s" % (number_liquidation) + name_recap
                    aml_model.with_context(check_move_validity=False).create(
                        liquidation._prepare_move_line_vals(
                            am,
                            liquidation.account_withhold_iva_id,
                            name,
                            debit=liquidation.iva_withhold,
                            partner=liquidation.partner_id,
                        )
                    )
            am.action_post()
            if not liquidation.no_invoice and invoice_to_liquidate:
                for invoice_id in invoice_to_liquidate.keys():
                    aml_model.browse(
                        invoice_to_liquidate[invoice_id]["amls_to_concile"]
                    ).reconcile()
            update_data = {
                "number": number_liquidation,
                "move_id": am.id,
                "state": "done",
            }
            if ret:
                update_data.update(
                    {
                        "withhold_id": ret.id,
                    }
                )
            liquidation.reconcile_invoice()
            liquidation.write(update_data)
        return True

    def _prepare_move_line_vals(
        self, move, account, name, debit=0, credit=0, partner=False
    ):
        return {
            "move_id": move.id,
            "account_id": account.id,
            "name": name,
            "analytic_distribution": self.account_analytic_id.id,
            #"analytic_tag_ids": [(6, 0, self.analytic_tag_ids.ids)],
            "debit": debit,
            "credit": credit,
            "partner_id": partner.id if partner else False,
        }

    def _prepare_witholding_vals(self):
        return {
            "company_id": self.company_id.id,
            "number": self.document_number,
            "issue_date": self.issue_date,
            "partner_id": self.partner_id.id,
            "type": "credit_card",
            "l10n_ec_credit_card_account_id": self.account_id.id,
            "l10n_ec_credit_card_liquidation_id": self.id,
            "state": "draft",
            "document_type": self.document_type,
            "electronic_authorization": self.electronic_authorization,
            # "partner_authorization_id": self.authorization_id.id,
        }

    def action_cancel(self):
        for liquidation in self:
            liquidation.move_ids.remove_move_reconcile()
            if liquidation.move_id:
                if liquidation.move_id.state == "posted":
                    liquidation.move_id.button_cancel()
                liquidation.move_id.unlink()
            if liquidation.withhold_id:
                liquidation.withhold_id.action_cancel()
                liquidation.withhold_id.action_back_to_draft()
                liquidation.withhold_id.unlink()
            liquidation.write({"state": "cancel"})
        return True

    def action_cancel_to_draft(self):
        self.write({"state": "draft"})

    def unlink(self):
        for credit_card in self:
            if credit_card.state != "draft":
                raise UserError(
                    _("You can not delete credit card liquidation, try cancel first")
                )
        return super(AccountCreditCardLiquidation, self).unlink()

    def reconcile_invoice(self):
        for rec in self:
            if rec.invoice_id.state == "open":
                for aml in rec.move_ids:
                    if (
                        aml.partner_id.commercial_partner_id.id
                        == rec.invoice_id.commercial_partner_id.id
                        and rec.invoice_id.account_id.id == aml.account_id.id
                        and aml.amount_residual != 0
                    ):
                        rec.invoice_id.register_payment(aml)


class AccountCreditCardLiquidationLine(models.Model):

    _name = "account.credit.card.liquidation.line"

    recap_id = fields.Many2one(
        comodel_name="account.payment.recap", string="Lote / RECAP"
    )

    liquidation_id = fields.Many2one(
        comodel_name="account.credit.card.liquidation",
        string="Credit Card Liquidation",
        required=True,
        ondelete="cascade",
    )
    description = fields.Char(string="Description", index=True)
    move_line_id = fields.Many2one(
        comodel_name="account.move.line", string="Journal Entry"
    )
    account_id = fields.Many2one(comodel_name="account.account", string="Account")
    base = fields.Float(string="Base", digits="Account")
    commission = fields.Float(string="Commission", digits="Account")
    commission_iva = fields.Float(string="Commission IVA", digits="Account")
    iva_withhold = fields.Float(string="IVA Withhold", digits="Account")
    rent_base = fields.Float(string="Rent Base", digits="Account")
    rent_withhold = fields.Float(string="Rent Withhold", digits="Account")
    skip_payment = fields.Boolean(string="Skip Payment?")

    @api.depends(
        "base", "commission", "commission_iva", "iva_withhold", "rent_withhold"
    )
    def _compute_net_value(self):
        for rec in self:
            rec.net_value = rec.base - (
                rec.commission
                + rec.commission_iva
                + rec.iva_withhold
                + rec.rent_withhold
            )

    net_value = fields.Float(
        string="Net Value", digits="Account", store=True, compute="_compute_net_value"
    )

    partner_id = fields.Many2one(related="liquidation_id.partner_id", store=True)
    state = fields.Selection(
        related="liquidation_id.state",
        store=True,
    )

    @api.onchange(
        "base",
        "commission",
        "commission_iva",
        "iva_withhold",
        "rent_withhold",
    )
    def onchange_amounts(self):
        for rec in self:
            rec.net_value = rec.base - (
                rec.commission
                + rec.commission_iva
                + rec.iva_withhold
                + rec.rent_withhold
            )
            if (
                rec.recap_id
                and float_compare(
                    rec.recap_id.amount_not_reconciled, self.base, precision_digits=2
                )
                == -1
            ):
                return {
                    "warning": {
                        "title": _("Advertencia"),
                        "message": _(
                            "El monto a conciliar %s "
                            "es superior al monto pendiente de conciliar %s "
                            "verifique y corrija le valor de ser necesario"
                        )
                        % (rec.base, rec.recap_id.amount_not_reconciled),
                    }
                }

    @api.onchange(
        "recap_id",
    )
    def onchange_recap_id(self):
        for rec in self:
            if rec.recap_id:
                rec.base = self.recap_id.amount_not_reconciled


class AccountCreditCardLiquidationInvoiceDetail(models.Model):

    _name = "account.credit.card.liquidation.invoice.detail"

    liquidation_id = fields.Many2one(
        comodel_name="account.credit.card.liquidation",
        string="Credit Card Liquidation",
        required=True,
    )
    invoice_id = fields.Many2one(
        comodel_name="account.move", string="Invoice", required=True
    )
    amount = fields.Float(string="Amount to Reconcile", digits="Account", required=True)
