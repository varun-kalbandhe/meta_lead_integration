import frappe
from meta_lead_integration.meta_lead_integration.api import webhook, sync_historical_leads

def test():
    print("=== Testing Webhook ===")
    test_webhook()
    print("\n=== Testing Historical Sync ===")
    test_sync()

def test_webhook():
    original_get_single = frappe.get_single
    def mock_get_single(doctype):
        if doctype == "Meta Integration Settings":
            return frappe._dict({
                "get_password": lambda f: "TEST_TOKEN" if f == "access_token" else "my_secret_token",
                "lead_form_id": "test_form_id"
            })
        return original_get_single(doctype)
    frappe.get_single = mock_get_single

    print("--- Testing GET (Valid Verification) ---")
    frappe.request = frappe._dict(method="GET")
    frappe.form_dict = frappe._dict({
        "hub.mode": "subscribe",
        "hub.verify_token": "my_secret_token",
        "hub.challenge": b"123456789"
    })
    resp1 = webhook()
    print(f"Status: {resp1.status}, Response: {resp1.get_data().decode('utf-8')}")

    print("\n--- Testing GET (Invalid Verification) ---")
    frappe.form_dict["hub.verify_token"] = "wrong_token"
    resp2 = webhook()
    print(f"Status: {resp2.status}, Response: {resp2.get_data().decode('utf-8')}")

    print("\n--- Testing POST (Leadgen Event & Duplicate Email Check) ---")
    frappe.request = type('Request', (object,), {
        'method': 'POST',
        'get_json': lambda self: {
            "object": "page",
            "entry": [{
                "changes": [{
                    "field": "leadgen",
                    "value": {"leadgen_id": "1322261564307693"}
                }]
            }]
        }
    })()
    
    import requests
    original_get = requests.get

    class MockResponse:
        def __init__(self, json_data, status_code):
            self.json_data = json_data
            self.status_code = status_code
            self.text = str(json_data)
        def json(self): return self.json_data

    existing_lead_email = frappe.db.get_value("Lead", "CRM-LEAD-2026-00040", "email_id")
    if not existing_lead_email:
        existing_lead_email = "duplicate@example.com"
        
    def mock_get(url, params=None, **kwargs):
        if "1322261564307693" in url:
            return MockResponse({
                "id": "1322261564307693",
                "created_time": "2024-01-01T00:00:00+0000",
                "field_data": [
                    {"name": "full_name", "values": ["Webhook User"]},
                    {"name": "email", "values": [existing_lead_email]},
                    {"name": "phone", "values": ["+1234567890"]}
                ]
            }, 200)
        return original_get(url, params=params, **kwargs)

    requests.get = mock_get

    try:
        resp3 = webhook()
        print(f"Status: {resp3.status}, Response: {resp3.get_data().decode('utf-8')}")
    finally:
        requests.get = original_get
        frappe.get_single = original_get_single


def test_sync():
    original_get_single = frappe.get_single
    def mock_get_single(doctype):
        if doctype == "Meta Integration Settings":
            return frappe._dict({
                "get_password": lambda f: "TEST_TOKEN" if f == "access_token" else "my_secret_token",
                "lead_form_id": "test_form_id"
            })
        return original_get_single(doctype)
    frappe.get_single = mock_get_single

    import requests
    original_get = requests.get

    class MockResponse:
        def __init__(self, json_data, status_code):
            self.json_data = json_data
            self.status_code = status_code
            self.text = str(json_data)
        def json(self): return self.json_data

    existing_lead_email = frappe.db.get_value("Lead", "CRM-LEAD-2026-00040", "email_id")
    if not existing_lead_email:
        existing_lead_email = "duplicate@example.com"

    # Pre-create a lead to test 'already_exists' logic
    if not frappe.db.exists("Lead", {"custom_meta_lead_id": "meta_lead_exist"}):
        frappe.get_doc({
            "doctype": "Lead",
            "lead_name": "Meta Lead Exist",
            "custom_meta_lead_id": "meta_lead_exist"
        }).insert(ignore_permissions=True)
        frappe.db.commit()

    def mock_get(url, params=None, **kwargs):
        if "test_form_id/leads" in url:
            if "after=page1" in url:
                # Page 2
                return MockResponse({
                    "data": [
                        {
                            "id": "meta_lead_3",
                            "field_data": [
                                {"name": "full_name", "values": ["User 3"]},
                                {"name": "email", "values": ["user3@example.com"]}
                            ]
                        }
                    ]
                }, 200)
            else:
                # Page 1
                return MockResponse({
                    "data": [
                        {
                            "id": "meta_lead_new",
                            "field_data": [
                                {"name": "full_name", "values": ["New User"]},
                                {"name": "email", "values": ["newuser@example.com"]}
                            ]
                        },
                        {
                            "id": "meta_lead_exist",
                            "field_data": [{"name": "full_name", "values": ["Exist User"]}]
                        },
                        {
                            "id": "meta_lead_email_dup",
                            "field_data": [
                                {"name": "full_name", "values": ["Email Dup User"]},
                                {"name": "email", "values": [existing_lead_email]}
                            ]
                        },
                        {
                            "id": "meta_lead_fail",
                            "ad_id": "ad_123",
                            "adset_id": "adset_456",
                            "campaign_id": "camp_789",
                            "field_data": [
                                {"name": "full_name", "values": ["Fail User"]},
                                {"name": "email", "values": ["fail@example.com"]}
                            ]
                        }
                    ],
                    "paging": {
                        "next": "https://graph.facebook.com/v19.0/test_form_id/leads?after=page1"
                    }
                }, 200)

    requests.get = mock_get
    
    import meta_lead_integration.meta_lead_integration.api as api_module
    original_create = api_module._create_lead_from_data
    def mock_create_lead(meta_lead_id, field_data, created_time=None):
        if meta_lead_id == "meta_lead_fail":
            raise Exception("Forced test error")
        return original_create(meta_lead_id, field_data, created_time)
    api_module._create_lead_from_data = mock_create_lead
    
    # Mock publish_realtime to capture the summary
    original_publish_realtime = frappe.publish_realtime
    captured_summary = {}
    def mock_publish_realtime(event, message=None, user=None, **kwargs):
        if event == "meta_lead_sync_complete":
            captured_summary.update(message)
        else:
            # Pass through for other realtime events like doc creation
            original_publish_realtime(event, message=message, user=user, **kwargs)
    frappe.publish_realtime = mock_publish_realtime

    try:
        from meta_lead_integration.meta_lead_integration.api import run_sync_historical_leads_job
        import logging
        logger = logging.getLogger("meta_integration")
        original_error = logger.error
        def mock_error(msg):
            print(f"LOGGER ERROR: {msg}")
            original_error(msg)
        logger.error = mock_error

        run_sync_historical_leads_job("Administrator")
        print(f"Sync Summary: {captured_summary}")
    finally:
        requests.get = original_get
        api_module._create_lead_from_data = original_create
        frappe.get_single = original_get_single
        frappe.publish_realtime = original_publish_realtime
        if 'logger' in locals():
            logger.error = original_error

