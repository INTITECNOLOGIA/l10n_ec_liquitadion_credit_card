{
    "name": "Credit Card Liquidations",
    "version": "16.0.0.0.0",
    "category": "Localization",
    "author": "Intitecnologia",
    "website": "https://github.com/OCA/account-invoicing",
    "license": "LGPL-3",
    "depends": [
        "account", "account_edi", "account_check","base", "account_accountant"
    ],
    "data": [
        "security/ir.model.access.csv",
        #"security/security.xml",
        "data/payment_method_data.xml",
        "data/sequence_data.xml",
        "views/menu_root.xml",
        "views/account_credit_card_authorizer_view.xml",
        "views/payment_view.xml",
        "views/recap_view.xml",
        # "views/retention_credit_card.xml",
        "views/credit_card_liquidation_view.xml",
        "report/report.xml",
        "report/report_credit_card_liquidation.xml",
        "report/report_account_move_tc.xml",
    ],
    "demo": [],
    "installable": True,
    "auto_install": False,
    "external_dependencies": {
        "python": [],
    },
}
