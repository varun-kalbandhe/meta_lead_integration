import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def after_install():
    setup_doctype()
    setup_custom_fields()
    frappe.db.commit()

def setup_custom_fields():
    custom_fields = {
        "Lead": [
            {
                "fieldname": "custom_meta_lead_id",
                "label": "Meta Lead ID",
                "fieldtype": "Data",
                "insert_after": "email_id",
                "unique": 1
            },
            {
                "fieldname": "custom_industry",
                "label": "Industry (Meta)",
                "fieldtype": "Data",
                "insert_after": "custom_meta_lead_id"
            },
            {
                "fieldname": "custom_current_software",
                "label": "Current Software",
                "fieldtype": "Data",
                "insert_after": "custom_industry"
            },
            {
                "fieldname": "custom_erp_implementation_timeline",
                "label": "ERP Implementation Timeline",
                "fieldtype": "Data",
                "insert_after": "custom_current_software"
            }
        ]
    }
    create_custom_fields(custom_fields)

def setup_doctype():
    if not frappe.db.exists("DocType", "Meta Integration Settings"):
        doc = frappe.get_doc({
            "doctype": "DocType",
            "name": "Meta Integration Settings",
            "module": "Meta Lead Integration",
            "custom": 1,
            "issingle": 1,
            "fields": [
                {
                    "fieldname": "access_token",
                    "label": "Meta Access Token",
                    "fieldtype": "Password",
                    "reqd": 1
                },
                {
                    "fieldname": "webhook_verify_token",
                    "label": "Webhook Verify Token",
                    "fieldtype": "Password",
                    "reqd": 1,
                    "insert_after": "access_token"
                },
                {
                    "fieldname": "lead_form_id",
                    "label": "Lead Form ID(s)",
                    "description": "Comma separated Meta Lead Form IDs for historical sync.",
                    "fieldtype": "Data",
                    "insert_after": "webhook_verify_token"
                }
            ],
            "permissions": [
                {
                    "role": "System Manager",
                    "read": 1,
                    "write": 1,
                    "create": 1
                }
            ]
        })
        doc.insert(ignore_permissions=True)
