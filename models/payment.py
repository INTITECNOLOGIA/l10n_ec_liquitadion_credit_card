import logging

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


class AccountCreditCardAuthorizer(models.Model):
    _name = "account.credit.card.authorizer"

    name = fields.Char("Short Name", required=True, readonly=False)
    partner_id = fields.Many2one("res.partner", "Partner Authorizer", required=True)


class CreditCardIssuer(models.Model):
    _name = "account.credit.card.issuer"

    name = fields.Char("Issuer Name", required=True, readonly=False)

    _sql_constraints = [("key_uniq", "unique(name)", "Issuer Name")]


class AccountPaymentRecap(models.Model):
    _name = "account.payment.recap"
    _description = "RECAP/LOTE"

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=False,
    )
    name = fields.Char("Number", required=False, readonly=True)
    date = fields.Date("Date", readonly=True)
    payment_line_ids = fields.One2many(
        "account.payment",
        "l10n_ec_recap_id",
        "Payment Records",
        required=False,
        readonly=True,
    )
    liquidation_line_ids = fields.One2many(
        "account.credit.card.liquidation.line",
        "recap_id",
        "Liquidation Records",
        required=False,
        readonly=True,
    )
    state = fields.Selection(
        [
            ("draft", "Created"),
            ("done", "Effected"),
            ("cancel", "Canceled"),
        ],
        "State",
        readonly=True,
        default="draft",
    )
    authorizer_id = fields.Many2one(
        "account.credit.card.authorizer", "Authorizer", required=False, readonly=True
    )
    create_uid = fields.Many2one("res.users", string="Create by", readonly=True)
    create_date = fields.Datetime(readonly=True)
    # printer_id = fields.Many2one(
    #     "l10n_ec.point.of.emission", "Point of Emission", readonly=True
    # )
    # shop_id = fields.Many2one(
    #     "l10n_ec.agency",
    #     "Agency",
    #     readonly=True,
    #     related="printer_id.agency_id",
    #     store=True,
    # )
    bank_id = fields.Many2one("res.bank", "Bank", readonly=True, ondelete="restrict")
    amount_total = fields.Float(
        string="Total Amount",
        compute="_compute_amounts",
        store=True,
    )
    amount_not_reconciled = fields.Float(
        type="float",
        string="Amount not reconciled",
        compute="_compute_amounts",
        store=True,
    )

    @api.depends(
        "payment_line_ids",
        "payment_line_ids.state",
        "payment_line_ids.amount",
        "liquidation_line_ids",
        "liquidation_line_ids.liquidation_id.state",
        "liquidation_line_ids.base",
    )
    def _compute_amounts(self):
        for rec in self:
            amount_total = 0.0
            amount_not_reconciled = 0.0
            for payment in rec.payment_line_ids.filtered(
                lambda x: x.state not in ("draft", "cancel")
            ):
                amount_total += payment.amount
                amount_not_reconciled += payment.amount
            for line in rec.liquidation_line_ids.filtered(
                lambda x: x.liquidation_id.state == "done"
            ):
                amount_not_reconciled -= line.base
            rec.amount_total = amount_total
            rec.amount_not_reconciled = amount_not_reconciled

    _sql_constraints = [
        (
            "name_uniq",
            "unique(name, bank_id, company_id)",
            _(
                "The number of Batch/RECAP must be unique by bank, "
                "there's another with the same number, please check!"
            ),
        ),
    ]

    @api.model
    def name_search(self, name, args=None, operator="ilike", limit=100):
        recs = self.browse()
        if name:
            recs = self.search([("name", "ilike", name)] + args, limit=limit)
        if not recs:
            recs = self.search([("bank_id", "ilike", name)] + args, limit=limit)
        if not recs:
            recs = self.search([("authorizer_id", "ilike", name)] + args, limit=limit)
        if not recs:
            return super(AccountPaymentRecap, self).name_search(
                name, args, operator, limit
            )
        return recs.name_get()

    def name_get(self):
        res = []
        for rec in self:
            name = "{} - {}".format(rec.name, rec.bank_id.name)
            res.append((rec.id, name))
        return res

    def copy_data(self, default=None):
        raise UserError(_("You cannot copy this record"))

    def unlink(self):
        for recap in self:
            if recap.state == "done":
                raise UserError(_("You cannot delete this record on done state"))
        return super(AccountPaymentRecap, self).unlink()

    def action_cancel(self):
        for recap in self:
            if recap.payment_line_ids:
                raise UserError(
                    _(
                        "You cannot cancel this document "
                        "because there's payments associates"
                    )
                )
        return self.write({"state": "cancel"})


_PAYMENT_STATES = {
    "draft": [
        ("readonly", False),
    ]
}


class AccountPayment(models.Model):
    _inherit = "account.payment"

    l10n_ec_recap_id = fields.Many2one(
        "account.payment.recap", "Batch / RECAP", readonly=True, ondelete="restrict"
    )
    l10n_ec_authorization_cc = fields.Char(
        "Credit Card Authorization Number", readonly=True, states=_PAYMENT_STATES
    )
    l10n_ec_authorizer_id = fields.Many2one(
        "account.credit.card.authorizer",
        "Authorizer",
        readonly=True,
        states=_PAYMENT_STATES,
    )
    l10n_ec_issuer_id = fields.Many2one(
        "account.credit.card.issuer",
        "Credit Card Issuer",
        readonly=True,
        states=_PAYMENT_STATES,
    )
    l10n_ec_credit_card_bank_id = fields.Many2one(
        "res.bank",
        "Credit Card Bank Issuer",
        readonly=True,
        states=_PAYMENT_STATES,
        ondelete="restrict",
    )
    l10n_ec_voucher_type = fields.Selection(
        [
            ("automatic", "Automatic"),
            ("manual", "Manual"),
        ],
        string="Voucher Type",
        default="automatic",
        readonly=True,
        states=_PAYMENT_STATES,
    )
    l10n_ec_voucher_number = fields.Char(
        "Voucher Number", required=False, readonly=True, states=_PAYMENT_STATES
    )
    l10n_ec_voucher_batch_number = fields.Char(
        "# Batch/RECAP", required=False, readonly=True, states=_PAYMENT_STATES
    )
    l10n_ec_credit_card_number = fields.Char(
        "Last Credit Card Numbers",
        size=4,
        required=False,
        readonly=True,
        states=_PAYMENT_STATES,
    )

    def action_post(self):
        self.action_create_recap()
        res = super(AccountPayment, self).action_post()
        for payment in self:
            if payment.payment_is_tc and payment.move_id:
                for line in payment.move_id.line_ids:
                    line.write(
                        {
                            "name": line.name
                            + " Recap "
                            + payment.l10n_ec_voucher_batch_number
                        }
                    )
        return res

    def action_create_recap(self):
        recap_model = self.env["account.payment.recap"].sudo()
        for payment in self:
            if payment.payment_is_tc:
                batch = payment.l10n_ec_voucher_batch_number
                recap = recap_model.search(
                    [
                        ("name", "=", batch),
                        ("bank_id", "=", payment.l10n_ec_credit_card_bank_id.id),
                        ("state", "!=", "cancel"),
                    ],
                    limit=1,
                )
                if recap:
                    if recap.state == "done":
                        recap.write({"state": "draft"})
                else:
                    recap = recap_model.create(
                        payment._prepare_l10n_ec_recap_values(batch)
                    )
                payment.write({"l10n_ec_recap_id": recap.id})
        return True

    def _prepare_l10n_ec_recap_values(self, batch):
        self.ensure_one()
        return {
            "company_id": self.company_id.id,
            "name": batch,
            "bank_id": self.l10n_ec_credit_card_bank_id.id,
            "date": self.payment_date,
            "authorizer_id": self.l10n_ec_authorizer_id.id,
            "state": "draft",
        }
